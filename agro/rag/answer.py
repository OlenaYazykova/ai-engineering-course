"""Answers with sources: search -> threshold -> context -> model -> checks -> answer or "not in the documents".

    python main.py rag ask "питання"            # make rag-ask Q="..."

The chain follows the lecture example (autoparts-rag-evals, pipeline.py):

1. Search: hybrid + reranker + filters read from the question (the configuration chosen in step 2),
   the best `retrieve_k` chunks.
2. Threshold: the reranker score is turned into 0..1 (sigmoid). If the best chunk is below
   `threshold`, the answer is "not in the documents" at once, without a model call (cost 0).
   The threshold is calibrated on the dev questions: `make rag-threshold` (results/rag/threshold_dev.md).
3. Context: chunks with a score of at least half the threshold, at most `max_per_doc` from one document
   (so a two-document question keeps room for the second one), the best `k`, and only while they fit
   in `context_tokens` (a chunk that does not fit is skipped; the first one is always kept). Every
   chunk is numbered [1]..[k] and starts with its document, period and section. Places left after the
   limit per document are filled with the chunks it skipped (a question about one table).
4. The model answers by the prompt prompts/rag/answer_<version>.txt: a [n] after every sentence with a
   fact, or the marker НЕМАЄ_ВІДПОВІДІ when the chunks have no answer. From v2 the prompt names the
   language of the answer ({language}: the language of the question, found by the code).
5. Checks without a model (agro/rag/verify.py): every number is in the cited chunks, every [n] is a
   chunk that was given, every sentence with a fact has a [n]. If a check fails, the model gets one
   more try with the problems listed (prompts/rag/retry_<version>.txt). If the numbers or citations are
   still wrong, the answer is withdrawn ("retracted"): a wrong number is worse than no answer.

Outcome of a question: answer | refused_threshold (step 2) | refused_model (marker) | retracted | error.
The sources under an answer: "[n] document, period, section, page" of every chunk it cites.
"""

import math
import time
from dataclasses import asdict, dataclass, field
from html import escape

from ..common.providers import CachedProvider, Provider, ProviderError, make_provider
from ..common.settings import CACHE, ROOT
from .search import Hit, Retriever
from .tokens import count_tokens
from .verify import cited_numbers, uncited_sentences, verify_numbers

PROMPTS = ROOT / "prompts" / "rag"
ANSWER_CACHE = CACHE / "answers"
NO_ANSWER_MARKER = "НЕМАЄ_ВІДПОВІДІ"
REFUSAL = {"uk": "У документах цього немає.", "en": "The documents do not contain this."}
LANGUAGE = {"uk": "українською", "en": "англійською (in English)"}   # {language} of the prompts (v2)
RETRACTED = {"uk": "У документах цього немає: відповідь не пройшла перевірку чисел і посилань.",
             "en": "The documents do not contain this: the answer failed the check of numbers and citations."}
DEFAULTS = {"model": "gpt4o_mini", "prompt": "v1", "sampling": "t0", "max_tokens": 700, "cache": True,
            "retrieve_k": 10, "k": 5, "context_tokens": 3000, "max_per_doc": 3, "threshold": 0.3}


def settings() -> dict:
    """config.toml [answer] over the defaults, and the model and sampling sections it names."""
    import tomllib

    with (ROOT / "config.toml").open("rb") as f:
        cfg = tomllib.load(f)
    s = DEFAULTS | cfg.get("answer", {})
    s["model_cfg"] = cfg["models"][s["model"]]
    s["sampling_cfg"] = cfg["sampling"][s["sampling"]]
    return s


def language(text: str) -> str:
    return "uk" if any("а" <= ch.lower() <= "я" or ch.lower() in "іїєґ" for ch in text) else "en"


def probability(score: float) -> float:
    """Reranker score (a logit of the cross-encoder) -> 0..1."""
    return 1.0 / (1.0 + math.exp(-score))


@dataclass
class AnswerResult:
    question: str
    outcome: str = "error"
    text: str = ""
    citations: list[dict] = field(default_factory=list)   # [n] used -> document, period, section, page
    retrieved: list[dict] = field(default_factory=list)   # chunk ids found, with the reranker probability
    context: list[str] = field(default_factory=list)      # chunk ids given to the model, in order [1]..[k]
    context_tokens: int = 0
    max_probability: float = 0.0
    checks: dict = field(default_factory=dict)
    first_answer: str = ""                                 # before the retry, when there was one
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    seconds: dict = field(default_factory=dict)            # retrieval / generation (cached calls: original time)
    prompt: str = ""
    model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def citation(n: int, hit: Hit) -> dict:
    c = hit.chunk
    return {"n": n, "chunk_id": c.chunk_id, "doc_id": c.doc_id, "title": c.title, "period": c.period,
            "section": c.section, "page": c.page, "source": c.source}


def format_sources(citations: list[dict]) -> str:
    lines = []
    for c in citations:
        where = ", ".join(x for x in (c["period"], c["section"], f"p. {c['page']}" if c["page"] else "") if x)
        lines.append(f"[{c['n']}] {c['title']} ({where}) — {c['doc_id']}")
    return "\n".join(lines)


class Answerer:
    def __init__(self, retriever: Retriever | None = None, provider: Provider | None = None,
                 cfg: dict | None = None) -> None:
        self.cfg = cfg or settings()
        self.retriever = retriever
        provider = provider or make_provider(self.cfg["model_cfg"])
        if self.cfg["cache"] and self.cfg["sampling_cfg"]["temperature"] == 0 and not isinstance(provider, CachedProvider):
            provider = CachedProvider(provider, ANSWER_CACHE)
        self.provider = provider
        self.system = (PROMPTS / f"answer_{self.cfg['prompt']}.txt").read_text(encoding="utf-8") \
            .replace("{marker}", NO_ANSWER_MARKER)
        self.retry_note = (PROMPTS / f"retry_{self.cfg['prompt']}.txt").read_text(encoding="utf-8")

    # ------------------------------------------------------------ retrieval and context

    def retrieve(self, question: str) -> tuple[list[Hit], float]:
        """The best retrieve_k chunks (hybrid + reranker + filters) and the search time, s."""
        if self.retriever is None:
            self.retriever = Retriever()
        self.retriever.cached_seconds = 0.0
        t = time.perf_counter()
        hits = self.retriever.search(question, k=self.cfg["retrieve_k"], method="hybrid_rerank", auto_filters=True)
        return hits, time.perf_counter() - t + self.retriever.cached_seconds

    def select_context(self, hits: list[Hit], k: int | None = None) -> tuple[list[Hit], int]:
        """Two passes over the hits in rank order: first with at most max_per_doc chunks of one document
        (room for the second document of a question), then, if places are left, the chunks the limit
        skipped (a question about one table needs no room for another document). In rank order."""
        k = k or self.cfg["k"]
        floor = self.cfg["threshold"] * 0.5
        per_doc: dict[str, int] = {}
        chosen: list[int] = []
        tokens = 0
        for capped in (True, False):
            for i, h in enumerate(hits):
                if len(chosen) == k:
                    break
                if i in chosen or probability(h.score) < floor:
                    continue
                if capped and per_doc.get(h.chunk.doc_id, 0) >= self.cfg["max_per_doc"]:
                    continue
                n = count_tokens(h.chunk.for_embedding())
                if chosen and tokens + n > self.cfg["context_tokens"]:
                    continue                   # does not fit the budget: a smaller chunk further down may
                chosen.append(i)
                tokens += n
                per_doc[h.chunk.doc_id] = per_doc.get(h.chunk.doc_id, 0) + 1
        return [hits[i] for i in sorted(chosen)], tokens

    @staticmethod
    def user_message(question: str, context: list[Hit]) -> str:
        docs = [f'<document index="{n}">\n{escape(h.chunk.header)}\n{h.chunk.text}\n</document>'
                for n, h in enumerate(context, 1)]
        return "<documents>\n" + "\n".join(docs) + f"\n</documents>\n\n<question>{escape(question)}</question>"

    # ------------------------------------------------------------ checks

    @staticmethod
    def check(text: str, context: list[Hit], question: str) -> dict:
        cited = cited_numbers(text)
        invalid = [n for n in cited if not 1 <= n <= len(context)]
        sources = [context[n - 1].chunk.for_embedding() for n in cited if 1 <= n <= len(context)]
        numbers = verify_numbers(text, sources, question)
        uncited = uncited_sentences(text)
        problems = []
        if not sources:
            problems.append("немає жодного посилання [n] на наданий фрагмент")
        if invalid:
            problems.append("посилання на фрагменти, яких немає: " + ", ".join(f"[{n}]" for n in invalid))
        if numbers.unsupported:
            problems.append("числа, яких немає в процитованих фрагментах: " + ", ".join(numbers.unsupported))
        if uncited:
            problems.append("речення без посилання [n]: " + " / ".join(f"«{s[:80]}»" for s in uncited))
        return {"cited": cited, "invalid_citations": invalid, "unsupported_numbers": numbers.unsupported,
                "numbers_checked": numbers.checked, "uncited_sentences": uncited, "problems": problems,
                "hard_fail": bool(not sources or invalid or numbers.unsupported)}

    # ------------------------------------------------------------ the chain

    def _call(self, messages: list[dict], res: AnswerResult) -> str:
        t = time.perf_counter()
        c = self.provider.complete(messages, None, self.cfg["sampling_cfg"], self.cfg["max_tokens"])
        res.seconds["generation"] = res.seconds.get("generation", 0.0) + (
            c.cached_seconds if c.cached_seconds is not None else time.perf_counter() - t)
        res.input_tokens += c.input_tokens
        res.output_tokens += c.output_tokens
        res.cost_usd += self.provider.cost_usd(c)
        return c.content.strip()

    def answer(self, question: str, hits: list[Hit] | None = None, k: int | None = None) -> AnswerResult:
        res = AnswerResult(question, prompt=self.cfg["prompt"], model=self.cfg["model_cfg"]["model"])
        lang = language(question)
        if hits is None:
            hits, res.seconds["retrieval"] = self.retrieve(question)
        res.retrieved = [{"chunk_id": h.chunk.chunk_id, "p": round(probability(h.score), 4)} for h in hits]
        res.max_probability = max((probability(h.score) for h in hits), default=0.0)
        if res.max_probability < self.cfg["threshold"]:
            res.outcome, res.text = "refused_threshold", REFUSAL[lang]
            return res
        context, res.context_tokens = self.select_context(hits, k)
        res.context = [h.chunk.chunk_id for h in context]
        messages = [{"role": "system", "content": self.system.replace("{language}", LANGUAGE[lang])},
                    {"role": "user", "content": self.user_message(question, context)}]
        try:
            text = self._call(messages, res)
            if NO_ANSWER_MARKER in text:
                res.outcome, res.text = "refused_model", REFUSAL[lang]
                return res
            checks = self.check(text, context, question)
            res.checks = {"first": checks, "retried": False}
            if checks["problems"]:
                res.first_answer = text
                note = self.retry_note.replace("{problems}", "; ".join(checks["problems"])) \
                    .replace("{marker}", NO_ANSWER_MARKER).replace("{language}", LANGUAGE[lang])
                retry = self._call(messages + [{"role": "assistant", "content": text},
                                               {"role": "user", "content": note}], res)
                res.checks["retried"] = True
                if NO_ANSWER_MARKER in retry:
                    res.outcome, res.text = "refused_model", REFUSAL[lang]
                    return res
                second = self.check(retry, context, question)
                res.checks["second"] = second
                if not second["hard_fail"]:
                    text, checks = retry, second
                elif checks["hard_fail"]:
                    res.outcome, res.text = "retracted", RETRACTED[lang]
                    return res
                # else: the retry broke the numbers or citations, the first answer had only uncited sentences
            res.checks["final"] = checks
        except ProviderError as e:
            res.outcome, res.text = "error", str(e)
            return res
        res.outcome, res.text = "answer", text
        res.citations = [citation(n, context[n - 1]) for n in checks["cited"] if 1 <= n <= len(context)]
        return res


def ask(question: str, k: int | None = None) -> AnswerResult:
    res = Answerer().answer(question, k=k)
    print(res.text)
    if res.citations:
        print("\nSources:\n" + format_sources(res.citations))
    final = res.checks.get("final", {})
    print(f"\n[{res.outcome}; best chunk p={res.max_probability:.3f}; context {len(res.context)} chunks, "
          f"{res.context_tokens} tokens; {res.input_tokens}+{res.output_tokens} tokens, ${res.cost_usd:.5f}"
          + ("; retried" if res.checks.get("retried") else "")
          + (f"; uncited: {len(final['uncited_sentences'])}" if final.get("uncited_sentences") else "") + "]")
    return res

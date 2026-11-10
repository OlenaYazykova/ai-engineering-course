"""LLM-as-a-judge: is an answer correct (against the expected answer) and grounded (faithfulness: every
statement supported by the chunks given to the model)?

The judge is a model of another family than the generator (Gemini 2.5 Flash-Lite vs GPT-4o-mini), so it
does not favour answers written the way it would write them. Prompt: prompts/judge/<version>.txt
(CHANGELOG there). Temperature 0, structured output (JSON schema), answers cached in .cache/judge/.
Whether the judge can be trusted is measured against the manual labels: `make evals-calibrate`
(evals/calibration.py).
"""

import json
from dataclasses import asdict, dataclass, field
from html import escape

from agro.common.providers import CachedProvider, Provider, make_provider
from agro.common.settings import CACHE, ROOT

PROMPTS = ROOT / "prompts" / "judge"
JUDGE_CACHE = CACHE / "judge"
DEFAULTS = {"judge_model": "gemini_flash_lite", "judge_prompt": "v1", "judge_sampling": "t0",
            "judge_max_tokens": 1200, "judge_cache": True}

SCHEMA = {
    "type": "object",
    "properties": {
        "correct_reason": {"type": "string"},
        "correct": {"type": "boolean"},
        "unsupported_statements": {"type": "array", "items": {"type": "string"}},
        "grounded_reason": {"type": "string"},
        "grounded": {"type": "boolean"},
    },
    "required": ["correct_reason", "correct", "unsupported_statements", "grounded_reason", "grounded"],
    "additionalProperties": False,
}


def settings() -> dict:
    import tomllib

    with (ROOT / "config.toml").open("rb") as f:
        cfg = tomllib.load(f)
    s = DEFAULTS | cfg.get("evals", {})
    s["model_cfg"] = cfg["models"][s["judge_model"]]
    s["sampling_cfg"] = cfg["sampling"][s["judge_sampling"]]
    return s


@dataclass
class Verdict:
    correct: bool
    grounded: bool
    correct_reason: str = ""
    grounded_reason: str = ""
    unsupported_statements: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    prompt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Judge:
    def __init__(self, provider: Provider | None = None, cfg: dict | None = None, cache: bool | None = None) -> None:
        self.cfg = cfg or settings()
        provider = provider or make_provider(self.cfg["model_cfg"])
        use_cache = self.cfg["judge_cache"] if cache is None else cache
        if use_cache and self.cfg["sampling_cfg"]["temperature"] == 0 and not isinstance(provider, CachedProvider):
            provider = CachedProvider(provider, JUDGE_CACHE)
        self.provider = provider
        self.system = (PROMPTS / f"{self.cfg['judge_prompt']}.txt").read_text(encoding="utf-8")

    @staticmethod
    def user_message(question: str, expected: str, answer: str, chunks: list[dict]) -> str:
        """chunks: [{"n": 1, "text": "header + text", "cited": True}, ...] as the model saw them."""
        docs = "\n".join(f'<chunk n="{c["n"]}"{" cited" if c["cited"] else ""}>\n{c["text"]}\n</chunk>' for c in chunks)
        return (f"<question>{escape(question)}</question>\n\n<expected_answer>{escape(expected)}</expected_answer>\n\n"
                f"<answer>{answer}</answer>\n\n<chunks>\n{docs}\n</chunks>")

    def judge(self, question: str, expected: str, answer: str, chunks: list[dict]) -> Verdict:
        messages = [{"role": "system", "content": self.system},
                    {"role": "user", "content": self.user_message(question, expected, answer, chunks)}]
        c = self.provider.complete(messages, SCHEMA, self.cfg["sampling_cfg"], self.cfg["judge_max_tokens"])
        data = parse(c.content)
        return Verdict(bool(data["correct"]), bool(data["grounded"]), data.get("correct_reason", ""),
                       data.get("grounded_reason", ""), list(data.get("unsupported_statements", [])),
                       c.input_tokens, c.output_tokens, self.provider.cost_usd(c),
                       self.cfg["model_cfg"]["model"], self.cfg["judge_prompt"])


def parse(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):                       # a model that wraps JSON in a code fence anyway
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def chunks_for(context: list[str], cited: list[str], by_id: dict) -> list[dict]:
    """The chunks of an answer in the order the model saw them ([1]..[k]), with the cited ones marked."""
    out = []
    for n, cid in enumerate(context, 1):
        c = by_id.get(cid)
        text = f"{c.header}\n{c.text}" if c else f"(chunk {cid} is not in data/rag/chunks.jsonl)"
        out.append({"n": n, "text": text, "cited": cid in cited})
    return out

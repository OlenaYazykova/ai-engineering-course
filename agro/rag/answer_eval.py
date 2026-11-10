"""Answers on the test set questions: the threshold, the size of the context (k), metrics without a judge.

    make rag-threshold       # threshold of "not in the documents" from the reranker scores (no model calls)
    make rag-answer-eval     # answers of the dev questions for k = 3 / 5 / 10 -> results/rag/answers_dev_<prompt>.*

Threshold (results/rag/threshold_dev.md). For every dev question: the probability of the best chunk
(answer.probability of the reranker score). For each candidate threshold: answerable questions refused,
split into those whose source was found (a refusal is an error) and those whose source was not found
(a refusal is right: there is nothing to answer from), and no-answer questions refused. Suggested: the
highest candidate not above half of the lowest best-chunk probability among the answerable questions
whose source was found. Half, not the lowest itself: the dev questions are few, a new question with the
source found may score lower, and a refusal of an answerable question costs more than one model call
(the model can still say НЕМАЄ_ВІДПОВІДІ).

Answers (results/rag/answers_dev_<prompt>.md: one file per prompt version, so the versions can be compared).
Per question, deterministic (evals/scoring.py, agro/rag/verify.py):
  retrieved     share of the expected sources among the chunks found (retrieve_k)
  in context    share of the expected sources among the chunks given to the model
  answered      the outcome is an answer (not a refusal)
  correct       answered and every key fact of the test set is in the answer
  cited source  the answer cites a chunk of every expected document (match: all) or of one (any)
  cited evidence a cited chunk contains the evidence phrase of the test set
  uncited       the final answer has a sentence with a statement but without [n]
  retried / retracted   the checks failed: one more try / the answer was withdrawn
No-answer questions: abstained (the right outcome) or answered (an invented answer).
Cost: tokens of every call (retries too) x the prices of config.toml, per 1000 questions; time: median
of search and of generation (calls replayed from the cache report their original time).
"""

import json

from evals.scoring import score, summary   # the deterministic scoring functions live in evals/ (step 4)

from ..common.settings import RESULTS_RAG
from .answer import Answerer, probability
from .retrieval_eval import found_share
from .testset import load

KS = (3, 5, 10)
THRESHOLDS = (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9)
REFUSED = ("refused_threshold", "refused_model", "retracted")


def retrieve_all(answerer: Answerer, questions: list[dict]) -> dict:
    out = {}
    for q in questions:
        hits, seconds = answerer.retrieve(q["question"])
        out[q["id"]] = (hits, seconds)
        print(f"  {q['id']}: best chunk p={max((probability(h.score) for h in hits), default=0):.3f}")
    return out


# ---------------------------------------------------------------- threshold

def threshold_rows(questions: list[dict], retrieved: dict, k: int) -> tuple[list[dict], list[dict], float]:
    per_q = []
    for q in questions:
        hits = retrieved[q["id"]][0]
        best = max((probability(h.score) for h in hits), default=0.0)
        found = bool(q["sources"]) and found_share(hits[:k], q) > 0
        per_q.append({"id": q["id"], "kind": q["kind"], "best_p": best, "answerable": bool(q["sources"]),
                      "source_found": found})
    rows = []
    for t in THRESHOLDS:
        refused = [r for r in per_q if r["best_p"] < t]
        rows.append({"threshold": t,
                     "refused_found": [r["id"] for r in refused if r["answerable"] and r["source_found"]],
                     "refused_not_found": [r["id"] for r in refused if r["answerable"] and not r["source_found"]],
                     "refused_no_answer": [r["id"] for r in refused if not r["answerable"]],
                     "no_answer": sum(1 for r in per_q if not r["answerable"])})
    lowest = min((r["best_p"] for r in per_q if r["source_found"]), default=1.0)
    suggested = max(t for t in THRESHOLDS if t <= lowest / 2)
    return per_q, rows, suggested


def threshold_report(split: str, per_q, rows, suggested, k: int, current: float) -> list[str]:
    lines = [f"# Threshold of \"not in the documents\" ({split} set)", "",
             f"Probability of the best chunk = sigmoid of the reranker score (hybrid + reranker + filters). "
             f"\"Source found\": an expected source is among the {k} chunks the model would get. "
             f"Below the threshold the answer is \"not in the documents\" without a model call.", "",
             "| threshold | answerable refused, source found (errors) | answerable refused, source not found "
             "| no-answer refused |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['threshold']} | {len(r['refused_found'])} {', '.join(r['refused_found'])} | "
                     f"{len(r['refused_not_found'])} {', '.join(r['refused_not_found'])} | "
                     f"{len(r['refused_no_answer'])} of {r['no_answer']} {', '.join(r['refused_no_answer'])} |")
    lines += ["", f"Suggested (the highest candidate not above half of the lowest best-chunk probability of the "
                  f"answerable questions with the source found): **{suggested}**; "
                  f"config.toml [answer] threshold = {current}.", "",
              "| id | kind | best chunk p | source found |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['kind']} | {r['best_p']:.3f} | "
              f"{'yes' if r['source_found'] else ('-' if not r['answerable'] else 'no')} |" for r in per_q]
    return lines


def run_threshold(split: str = "dev") -> float:
    questions = load(split)
    a = Answerer()
    retrieved = retrieve_all(a, questions)
    per_q, rows, suggested = threshold_rows(questions, retrieved, a.cfg["k"])
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    lines = threshold_report(split, per_q, rows, suggested, a.cfg["k"], a.cfg["threshold"])
    (RESULTS_RAG / f"threshold_{split}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Suggested threshold {suggested} (config: {a.cfg['threshold']}); saved results/rag/threshold_{split}.md")
    return suggested


# ---------------------------------------------------------------- answers

def run(split: str = "dev", ks=KS) -> dict:
    if split == "test":
        print("The test split is measured once, for the final report (evals/README.md).")
    questions = load(split)
    a = Answerer()
    print(f"{len(questions)} {split} questions; model {a.cfg['model']}, prompt {a.cfg['prompt']}, "
          f"threshold {a.cfg['threshold']}, budget {a.cfg['context_tokens']} tokens, "
          f"at most {a.cfg['max_per_doc']} chunks of one document")
    retrieved = retrieve_all(a, questions)
    per_q, thr_rows, suggested = threshold_rows(questions, retrieved, a.cfg["k"])
    results, records = {}, []
    for k in ks:
        rows = []
        for q in questions:
            hits, seconds = retrieved[q["id"]]
            res = a.answer(q["question"], hits=hits, k=k)
            res.seconds["retrieval"] = seconds
            rows.append(score(q, res, hits, hits[:k]))
            records.append({"k": k, "id": q["id"], "split": split} | res.to_dict())
        results[k] = {"summary": summary(rows), "rows": rows}
        s = results[k]["summary"]
        print(f"  k={k:<2} correct {s['correct']:.2f}  cited source {s['cited_source']:.2f}  "
              f"false abstain {s['false_abstain']:.2f}  no-answer abstained {s['abstained_no_answer']:.2f}  "
              f"${s['cost_per_1000']:.3f} / 1000")
    write_report(split, a, results, per_q, thr_rows, suggested)
    with (RESULTS_RAG / f"answers_{split}_{a.cfg['prompt']}.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return results


def _f(x) -> str:
    return f"{x:.2f}"


def write_report(split, a: Answerer, results, per_q, thr_rows, suggested) -> None:
    cfg = a.cfg
    chosen = cfg["k"] if cfg["k"] in results else next(iter(results))
    lines = [f"# Answers with sources ({split} set)", "",
             f"Model {cfg['model_cfg']['model']} ({cfg['sampling']}), prompt rag/{cfg['prompt']}, search: hybrid + "
             f"reranker + filters, {cfg['retrieve_k']} chunks found; threshold {cfg['threshold']}, context budget "
             f"{cfg['context_tokens']} tokens, at most {cfg['max_per_doc']} chunks of one document. "
             "Metrics without a judge (agro/rag/answer_eval.py); `correct` = every key fact of the test set is "
             "in the answer.", "",
             "## Size of the context (k chunks)", "",
             "| k | retrieved | in context | answered | correct | cited source | cited evidence | uncited "
             "| false abstain | no-answer abstained | retried | retracted | context tokens | tokens / question "
             "| $ / 1000 questions | s search | s generation |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in results.items():
        s = r["summary"]
        lines.append(f"| {k}{' (used)' if k == chosen else ''} | " + " | ".join(_f(s[x]) for x in (
            "retrieved", "in_context", "answered", "correct", "cited_source", "cited_evidence", "uncited",
            "false_abstain", "abstained_no_answer", "retried", "retracted"))
            + f" | {s['context_tokens']:.0f} | {s['tokens_per_question']:.0f} | {s['cost_per_1000']:.3f} "
              f"| {s['s_retrieval']:.1f} | {s['s_generation']:.1f} |")
    s = results[chosen]["summary"]
    lines += ["", f"{s['answerable']} questions with an answer, {s['no_answer']} without; "
                  f"{s['errors']} calls failed.", "",
              "## Threshold", ""]
    lines += threshold_report(split, per_q, thr_rows, suggested, cfg["k"], cfg["threshold"])[2:]
    lines += ["", f"## Per question (k = {chosen})", "",
              "| id | kind | outcome | correct | key facts | cited source | uncited | retried |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results[chosen]["rows"]:
        if r["answerable"]:
            facts = "".join("+" if f else "-" for f in r["facts"])
            lines.append(f"| {r['id']} | {r['kind']} | {r['outcome']} | {'yes' if r['correct'] else 'no'} | "
                         f"{facts} | {'yes' if r['cited_source'] else 'no'} | {'yes' if r['uncited'] else ''} | "
                         f"{'yes' if r['retried'] else ''} |")
        else:
            lines.append(f"| {r['id']} | {r['kind']} | {r['outcome']} | "
                         f"{'yes (abstained)' if r['abstained'] else 'no (answered)'} | | | | "
                         f"{'yes' if r['retried'] else ''} |")
    name = f"answers_{split}_{cfg['prompt']}"
    lines += ["", f"Every answer with its sources, context and checks: results/rag/{name}.jsonl"]
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    (RESULTS_RAG / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved results/rag/{name}.md and {name}.jsonl")

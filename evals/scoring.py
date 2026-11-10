"""Scoring functions of the evals (homework 2, step 4). What each metric means and who computes it:
evals/METRICS.md.

Deterministic, by the code (no model):
  score()           one answer: source found / in the context / cited, key facts, "not in the documents"
                    where it is needed, sentences without [n], retries and withdrawn answers, cost
  retrieval()       one question: rank of the first relevant chunk, recall@5 / hit@5 (search of the system)
  passed()          one answer passes: an answer to a question with an answer is correct and grounded by the
                    judge and cites an expected source; a question without an answer is refused
By the LLM judge (evals/judge.py, calibrated on manual labels): correct, grounded (faithfulness).
"""

import statistics

from agro.rag.answer import AnswerResult
from agro.rag.retrieval_eval import found_share, relevant, score_question
from agro.rag.verify import key_facts_found


def score(q: dict, res: AnswerResult, hits, k_hits) -> dict:
    """Deterministic metrics of one answer (see the module docstring)."""
    by_id = {h.chunk.chunk_id: h for h in hits}
    context = [by_id[c] for c in res.context if c in by_id]
    cited = [by_id[c["chunk_id"]].chunk for c in res.citations if c["chunk_id"] in by_id]
    answered = res.outcome == "answer"
    row = {"id": q["id"], "kind": q["kind"], "language": q["language"], "outcome": res.outcome,
           "answerable": bool(q["sources"]), "answered": answered,
           "retried": bool(res.checks.get("retried")), "retracted": res.outcome == "retracted",
           "context_tokens": res.context_tokens, "input_tokens": res.input_tokens,
           "output_tokens": res.output_tokens, "cost_usd": res.cost_usd,
           "seconds_retrieval": res.seconds.get("retrieval", 0.0),
           "seconds_generation": res.seconds.get("generation", 0.0)}
    if not q["sources"]:
        return row | {"abstained": not answered}
    facts = key_facts_found(res.text, q["key_facts"]) if answered else [False] * len(q["key_facts"])
    docs = {c.doc_id for c in cited}
    expected = [s["doc_id"] for s in q["sources"]]
    final = res.checks.get("final", {})
    return row | {
        "retrieved": found_share(k_hits, q),
        "in_context": found_share(context, q) if context else 0.0,
        "facts": facts,
        "correct": answered and all(facts),
        "cited_source": answered and (any(d in docs for d in expected) if q.get("match") == "any"
                                      else all(d in docs for d in expected)),
        "cited_evidence": answered and any(relevant(c, s) for c in cited for s in q["sources"]),
        "uncited": answered and bool(final.get("uncited_sentences")),
        "false_abstain": not answered,
    }


def summary(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    no = [r for r in rows if not r["answerable"]]

    def share(items, key):
        return sum(bool(r[key]) for r in items) / len(items) if items else 0.0

    n = len(rows)
    return {
        "questions": n, "answerable": len(ans), "no_answer": len(no),
        "retrieved": sum(r["retrieved"] for r in ans) / len(ans),
        "in_context": sum(r["in_context"] for r in ans) / len(ans),
        "answered": share(ans, "answered"), "correct": share(ans, "correct"),
        "cited_source": share(ans, "cited_source"), "cited_evidence": share(ans, "cited_evidence"),
        "uncited": share(ans, "uncited"), "false_abstain": share(ans, "false_abstain"),
        "abstained_no_answer": share(no, "abstained"),
        "retried": share(rows, "retried"), "retracted": share(rows, "retracted"),
        "refused_threshold": sum(r["outcome"] == "refused_threshold" for r in rows) / n,
        "context_tokens": statistics.mean(r["context_tokens"] for r in rows),
        "tokens_per_question": statistics.mean(r["input_tokens"] + r["output_tokens"] for r in rows),
        "cost_per_1000": 1000 * statistics.mean(r["cost_usd"] for r in rows),
        "s_retrieval": statistics.median(r["seconds_retrieval"] for r in rows),
        "s_generation": statistics.median(r["seconds_generation"] for r in rows),
        "errors": sum(r["outcome"] == "error" for r in rows),
    }


def retrieval(hits, q: dict) -> dict:
    """Search of the system for one question with an answer: rank of the first relevant chunk, recall@5."""
    r = score_question(hits, q)
    return {"first_rank": r["first_rank"], "recall@5": r["recall"][5]}


def passed(row: dict) -> bool:
    if not row["answerable"]:
        return row["abstained"]
    return bool(row["answered"] and row.get("judge_correct") and row.get("judge_grounded") and row["cited_source"])


def judged_summary(rows: list[dict]) -> dict:
    """The metrics of the judge and the retrieval over the rows of one run (one repeat)."""
    ans = [r for r in rows if r["answerable"]]
    answered = [r for r in ans if r["answered"]]
    n_ans = len(ans) or 1
    return {
        "recall@5": sum(r["recall@5"] for r in ans) / n_ans,
        "hit@5": sum(1 for r in ans if r["first_rank"] and r["first_rank"] <= 5) / n_ans,
        "MRR": sum(1 / r["first_rank"] for r in ans if r["first_rank"]) / n_ans,
        "judge_correct": sum(bool(r.get("judge_correct")) for r in ans) / n_ans,
        "judge_grounded": (sum(bool(r.get("judge_grounded")) for r in answered) / len(answered)) if answered else 0.0,
        "unsupported_numbers": sum(bool(r.get("unsupported_numbers")) for r in answered),
        "pass": sum(r["pass"] for r in rows) / len(rows),
        "judge_cost_per_1000": 1000 * statistics.mean(r.get("judge_cost_usd", 0.0) for r in rows),
    }

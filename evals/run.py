"""The eval run (homework 2, step 4): every question of the test set through the system, scored by the code
and by the judge, several times.

    make evals-run                         # dev, 1 run (answers replayed from the cache when nothing changed)
    python main.py evals run --split dev --repeats 3
    python main.py evals run --split all --repeats 3     # dev + test (CI, after the one measurement of test)

For every question: the search of the system once (it is deterministic), then `repeats` runs of the
answer (k, prompt, threshold of config.toml [answer]) and of the judge. With more than one repeat the
answers are not replayed from the cache: the point of a repeat is to see whether the model answers the
same way again (`--fresh` does the same for one run: CI). The judge is cached: the same answer gets the
same verdict.

Results, per split (dev and test apart, so a difference between them is seen):
  evals/results/<split>.md     the report: metrics, per kind, per question, unstable questions
  evals/results/<split>.json   the summary the gate compares with evals/baseline.json (evals/gate.py)
  evals/results/<split>.jsonl  every answer of every repeat with its scores and the judge's reasons
Metrics: evals/METRICS.md.
"""

import json
import os
import statistics
import time
from collections import defaultdict

from agro.common.settings import ROOT
from agro.rag.answer import Answerer, settings
from agro.rag.chunking import load_chunks
from agro.rag.testset import load

from .judge import Judge, chunks_for
from .scoring import judged_summary, passed, retrieval, score, summary

RESULTS = ROOT / "evals" / "results"
# the metrics of a run, in the order of the report; "share" metrics are 0..1
METRICS = ["pass", "judge_correct", "judge_grounded", "correct", "cited_source", "abstained_no_answer",
           "false_abstain", "unsupported_numbers", "uncited", "retried", "retracted",
           "recall@5", "hit@5", "MRR", "cost_per_1000", "judge_cost_per_1000"]


def splits_of(split: str) -> list[str]:
    return ["dev", "test"] if split == "all" else [split]


def run_split(split: str, repeats: int, answerer: Answerer, judge: Judge, chunks: dict) -> dict:
    questions = load(split)
    print(f"{split}: {len(questions)} questions, {repeats} run(s); prompt {answerer.cfg['prompt']}, "
          f"k {answerer.cfg['k']}, threshold {answerer.cfg['threshold']}")
    found = {}
    for q in questions:
        hits, seconds = answerer.retrieve(q["question"])
        found[q["id"]] = (hits, seconds)
    rows_by_repeat = []
    for rep in range(repeats):
        rows = []
        for q in questions:
            hits, seconds = found[q["id"]]
            res = answerer.answer(q["question"], hits=hits)
            res.seconds["retrieval"] = seconds
            row = score(q, res, hits, hits[:answerer.cfg["k"]]) | {"repeat": rep + 1, "text": res.text,
                                                                     "citations": [c["chunk_id"] for c in res.citations],
                                                                     "context": res.context}
            if q["sources"]:
                row |= retrieval(hits, q)
            row["unsupported_numbers"] = res.checks.get("final", {}).get("unsupported_numbers", [])
            if row["answered"]:
                v = judge.judge(q["question"], q["expected_answer"], res.text,
                                chunks_for(res.context, row["citations"], chunks))
                row |= {"judge_correct": v.correct, "judge_grounded": v.grounded,
                        "judge_correct_reason": v.correct_reason, "judge_grounded_reason": v.grounded_reason,
                        "judge_unsupported": v.unsupported_statements, "judge_cost_usd": v.cost_usd}
            row["pass"] = passed(row)
            rows.append(row)
        rows_by_repeat.append(rows)
        s = summary(rows) | judged_summary(rows)
        print(f"  run {rep + 1}: pass {s['pass']:.2f}  judge correct {s['judge_correct']:.2f}  "
              f"grounded {s['judge_grounded']:.2f}  no-answer refused {s['abstained_no_answer']:.2f}")
    return aggregate(split, questions, rows_by_repeat, answerer, judge)


def aggregate(split: str, questions: list[dict], rows_by_repeat: list[list[dict]], answerer: Answerer,
              judge: Judge) -> dict:
    per_run = [summary(rows) | judged_summary(rows) for rows in rows_by_repeat]
    metrics = {m: {"mean": statistics.mean(r[m] for r in per_run), "min": min(r[m] for r in per_run),
                   "max": max(r[m] for r in per_run)} for m in METRICS}
    by_q = defaultdict(list)
    for rows in rows_by_repeat:
        for r in rows:
            by_q[r["id"]].append(r)
    per_question = []
    for q in questions:
        rs = by_q[q["id"]]
        per_question.append({"id": q["id"], "kind": q["kind"], "passes": sum(r["pass"] for r in rs), "runs": len(rs),
                             "outcomes": sorted({r["outcome"] for r in rs})})
    unstable = [p["id"] for p in per_question if 0 < p["passes"] < p["runs"]]
    kinds = defaultdict(list)
    for p in per_question:
        kinds[p["kind"]].append(p["passes"] / p["runs"])
    return {
        "split": split, "questions": len(questions), "answerable": per_run[0]["answerable"],
        "no_answer": per_run[0]["no_answer"], "repeats": len(rows_by_repeat),
        "config": {"model": answerer.cfg["model_cfg"]["model"], "prompt": answerer.cfg["prompt"],
                   "k": answerer.cfg["k"], "threshold": answerer.cfg["threshold"],
                   "context_tokens": answerer.cfg["context_tokens"], "judge": judge.cfg["model_cfg"]["model"],
                   "judge_prompt": judge.cfg["judge_prompt"]},
        "metrics": metrics,
        "pass@1": metrics["pass"]["mean"],
        "per_kind": {k: statistics.mean(v) for k, v in sorted(kinds.items())},
        "per_question": per_question,
        "unstable": unstable,
        "rows": [r for rows in rows_by_repeat for r in rows],
    }


def report(res: dict) -> str:
    m, c = res["metrics"], res["config"]
    lines = [f"# Evals: {res['split']} ({res['questions']} questions, {res['answerable']} with an answer, "
             f"{res['no_answer']} without; {res['repeats']} run(s))", "",
             f"System: {c['model']}, prompt rag/{c['prompt']}, k {c['k']}, threshold {c['threshold']}, context "
             f"{c['context_tokens']} tokens. Judge: {c['judge']}, prompt judge/{c['judge_prompt']}. "
             f"Metrics: evals/METRICS.md. With several runs: the mean, and min ... max over the runs.", "",
             "| metric | value | min ... max |", "|---|---|---|"]
    for name in METRICS:
        v = m[name]
        fmt = (lambda x: f"{x:.3f}") if "cost" in name or name == "MRR" else (
            (lambda x: f"{x:g}") if name == "unsupported_numbers" else (lambda x: f"{x:.2f}"))
        lines.append(f"| {name} | **{fmt(v['mean'])}** | {fmt(v['min'])} ... {fmt(v['max'])} |")
    lines += ["", f"pass@1 (the share of questions that pass in one run, mean over the runs): **{res['pass@1']:.2f}**. "
              f"Unstable questions (pass in some runs only): {', '.join(res['unstable']) or 'none'}.", "",
              "## Per kind (pass@1)", "", "| kind | pass@1 |", "|---|---|"]
    lines += [f"| {k} | {v:.2f} |" for k, v in res["per_kind"].items()]
    lines += ["", "## Per question", "", "| id | kind | passed runs | outcomes |", "|---|---|---|---|"]
    lines += [f"| {p['id']} | {p['kind']} | {p['passes']} / {p['runs']} | {', '.join(p['outcomes'])} |"
              for p in res["per_question"]]
    failed = [r for r in res["rows"] if not r["pass"] and r["repeat"] == 1]
    if failed:
        lines += ["", "## Failed in run 1, with the reasons of the judge", ""]
        for r in failed:
            why = []
            if not r["answerable"]:
                why.append(f"answered a question without an answer: «{r['text'][:160]}»")
            elif not r["answered"]:
                why.append(f"{r['outcome']} (the source {'was' if r.get('in_context') else 'was not'} in the context)")
            else:
                if not r.get("judge_correct"):
                    why.append(f"not correct: {r.get('judge_correct_reason', '')}")
                if not r.get("judge_grounded"):
                    why.append(f"not grounded: {'; '.join(r.get('judge_unsupported') or [])} {r.get('judge_grounded_reason', '')}")
                if not r["cited_source"]:
                    why.append("the expected source is not cited")
            lines.append(f"* **{r['id']}** ({r['kind']}): " + " / ".join(why))
    lines += ["", f"Every answer of every run: evals/results/{res['split']}.jsonl"]
    return "\n".join(lines) + "\n"


def save(res: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = res["split"]
    (RESULTS / f"{name}.md").write_text(report(res), encoding="utf-8")
    summary_only = {k: v for k, v in res.items() if k != "rows"}
    (RESULTS / f"{name}.json").write_text(json.dumps(summary_only, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with (RESULTS / f"{name}.jsonl").open("w", encoding="utf-8") as f:
        for r in res["rows"]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")        # the report on the page of the CI run
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(report(res) + "\n")
    print(f"Saved evals/results/{name}.md, .json, .jsonl")


def run(split: str = "dev", repeats: int = 1, fresh: bool = False) -> list[dict]:
    t = time.perf_counter()
    cfg = settings()
    if repeats > 1 or fresh:
        cfg = cfg | {"cache": False}
    answerer, judge = Answerer(cfg=cfg), Judge()
    chunks = {c.chunk_id: c for c in load_chunks()}
    out = []
    for s in splits_of(split):
        res = run_split(s, repeats, answerer, judge, chunks)
        save(res)
        out.append(res)
    print(f"Done in {time.perf_counter() - t:.0f} s")
    return out

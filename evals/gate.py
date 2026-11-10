"""The gate of CI: the summary of an eval run against evals/baseline.json; a metric below its threshold fails.

    make evals-baseline   # evals/results/{dev,test}.json of the final local run -> evals/baseline.json
    make evals-gate       # evals/results/{dev,test}.json against evals/baseline.json; exit code 1 below a threshold

The baseline is the mean of the final local run (3 runs of dev and test). The thresholds (RULES) leave room
for what changes without any change in the code: the generator answers some questions differently from
session to session (on dev one question, d19, changed between two sessions at temperature 0), and the
reranker may order chunks a little differently on another CPU. One question is 4-5% of a split, so a
drop of 0.10 is about two questions:

  pass, judge_correct, correct, judge_grounded   baseline - 0.10
  abstained_no_answer                            at least 0.75 (one of the 4 questions without an answer may slip)
  unsupported_numbers                            0: an unsupported number never reaches a final answer
  recall@5, hit@5, MRR                           baseline - 0.05 (the search is deterministic; more is a broken index)
"""

import json
import os
import sys
from datetime import date

from agro.common.settings import ROOT

RESULTS = ROOT / "evals" / "results"
BASELINE = ROOT / "evals" / "baseline.json"
SPLITS = ("dev", "test")
RULES = {
    "pass": {"drop": 0.10},
    "judge_correct": {"drop": 0.10},
    "correct": {"drop": 0.10},
    "judge_grounded": {"drop": 0.10},
    "abstained_no_answer": {"min": 0.75},
    "unsupported_numbers": {"max": 0},
    "recall@5": {"drop": 0.05},
    "hit@5": {"drop": 0.05},
    "MRR": {"drop": 0.05},
}


def _load(split: str) -> dict:
    path = RESULTS / f"{split}.json"
    if not path.exists():
        raise SystemExit(f"{path.relative_to(ROOT)} is missing: run `make evals-run SPLIT=all` first")
    return json.loads(path.read_text(encoding="utf-8"))


def make_baseline() -> dict:
    splits = {}
    for s in SPLITS:
        res = _load(s)
        splits[s] = {"questions": res["questions"], "repeats": res["repeats"], "config": res["config"],
                     "metrics": {m: round(res["metrics"][m]["mean"], 4) for m in RULES}}
    baseline = {"created": date.today().isoformat(), "rules": RULES, "splits": splits}
    BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Saved {BASELINE.relative_to(ROOT)} from evals/results/{{dev,test}}.json")
    return baseline


def threshold(rule: dict, base: float) -> tuple[str, float]:
    if "drop" in rule:
        return ">=", round(base - rule["drop"], 4)
    if "min" in rule:
        return ">=", rule["min"]
    return "<=", rule["max"]


def check(baseline: dict, results: dict[str, dict]) -> tuple[bool, list[str]]:
    ok_all = True
    lines = ["## Gate: the run against evals/baseline.json", "",
             "| split | metric | baseline | now | threshold | |", "|---|---|---|---|---|---|"]
    for s in SPLITS:
        base, res = baseline["splits"][s], results[s]
        for m, rule in baseline["rules"].items():
            b, now = base["metrics"][m], res["metrics"][m]["mean"]
            op, t = threshold(rule, b)
            ok = now >= t - 1e-9 if op == ">=" else now <= t + 1e-9
            ok_all &= ok
            lines.append(f"| {s} | {m} | {b:g} | {now:.4g} | {op} {t:g} | {'ok' if ok else '**FAIL**'} |")
        if res["config"] != base["config"]:
            lines.append(f"| {s} | config | {base['config']} | {res['config']} | (information) | |")
    lines += ["", "**Gate passed.**" if ok_all else "**Gate failed: a metric is below its threshold.**"]
    return ok_all, lines


def run_gate() -> bool:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    ok, lines = check(baseline, {s: _load(s) for s in SPLITS})
    text = "\n".join(lines) + "\n"
    print(text)
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if not ok:
        sys.exit(1)
    return ok

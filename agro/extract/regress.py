"""Regression check of a new prompt version on the golden set, before it goes into the full matrix.

    python main.py regress --model gpt4o_mini --prompt v3 --baseline v2

1. runs the new prompt on the golden-set texts only (cheap: 10 texts, cached at T=0);
2. takes the baseline answers for the same texts from results/ (or runs the baseline too);
3. compares overall and per-field accuracy, valid answers and hallucinations;
4. writes results/extract/regression/<model>__<new>_vs_<baseline>.md and exits with code 1 if the new
   prompt is worse than the baseline by more than the tolerance (overall accuracy, valid answers,
   or any single field), so it can be used as a gate in a script or CI.
"""

import json
import sys

from . import metrics
from .run import RESULTS, load_config, run_experiment, run_name


def _golden_rows(path, ids: set[str]) -> list[dict]:
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r["text_id"] in ids]


def regress(model_key: str, prompt: str, baseline: str, sampling_key: str = "t0",
            tolerance: float = 2.0, field_tolerance: float = 10.0) -> bool:
    gold = metrics.load_golden()
    if not gold:
        sys.exit("data/extract/golden/ is empty: the regression check needs the golden set")
    ids = sorted(gold)
    cfg = load_config()

    new_path = run_experiment(model_key, prompt, sampling_key, ids=ids, config=cfg, subdir="regression")
    new_rows = _golden_rows(new_path, set(ids))
    if new_rows and all((r.get("error") or "").startswith("provider:") for r in new_rows):
        sys.exit(f"No answer from the model ({new_rows[0]['error']}). "
                 "Check the network / API key and run the check again; nothing was compared.")

    base_rows = _golden_rows(RESULTS / f"{run_name(model_key, baseline, sampling_key)}.jsonl", set(ids))
    if len(base_rows) < len(ids):   # no full baseline run yet: run the baseline on the golden set too
        base_path = run_experiment(model_key, baseline, sampling_key, ids=ids, config=cfg, subdir="regression")
        base_rows = _golden_rows(base_path, set(ids))

    m_new, _, f_new = metrics.run_metrics(new_rows, gold)
    m_base, _, f_base = metrics.run_metrics(base_rows, gold)

    problems = []
    d_acc = m_new["acc_all"] - m_base["acc_all"]
    if d_acc < -tolerance:
        problems.append(f"field accuracy dropped by {-d_acc:.1f} pp")
    d_valid = m_new["valid_pct"] - m_base["valid_pct"]
    if d_valid < -tolerance:
        problems.append(f"valid answers dropped by {-d_valid:.1f} pp")
    worse_fields = [f for f in metrics.FIELDS if f_new[f] - f_base[f] < -field_tolerance]
    if worse_fields:
        problems.append("fields worse by more than "
                        f"{field_tolerance:g} pp: {', '.join(worse_fields)}")

    title = f"{run_name(model_key, prompt, sampling_key)} vs {baseline}"
    lines = [f"# Regression check: {title}", "",
             f"Golden set: {len(ids)} texts. Tolerance: {tolerance:g} pp overall, "
             f"{field_tolerance:g} pp per field.", "",
             "| Metric | " + baseline + " | " + prompt + " | Δ |", "|---|---|---|---|"]
    for key, label in (("acc_all", "Field accuracy %"), ("acc_hydromet", "Accuracy Hydromet %"),
                       ("acc_jrc", "Accuracy JRC %"), ("valid_pct", "Valid %"),
                       ("hallucinations", "Hallucinations"), ("set_f1", "Set F1 %")):
        a, b = m_base[key], m_new[key]
        lines.append(f"| {label} | {metrics.num(a)} | {metrics.num(b)} | {metrics.num(b - a)} |")
    lines += ["", "| Field | " + baseline + " | " + prompt + " | Δ |", "|---|---|---|---|"]
    for f in metrics.FIELDS:
        a, b = f_base[f], f_new[f]
        mark = " ⚠" if f in worse_fields else ""
        lines.append(f"| {f} | {metrics.num(a, 0)} | {metrics.num(b, 0)} | {metrics.num(b - a, 0)}{mark} |")
    verdict = "PASS" if not problems else "FAIL: " + "; ".join(problems)
    lines += ["", f"**Result: {verdict}**", ""]

    out = RESULTS / "regression" / f"{model_key}__{prompt}_vs_{baseline}__{sampling_key}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"Saved {out.relative_to(RESULTS.parent)}")
    return not problems

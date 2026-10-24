"""Metrics for every run in results/ against the golden set in data/golden/.

A record is flattened into scored fields. Lists are compared as sets (order does not matter):
  year, month, decade, moisture_status, moisture_layer, min_mm, max_mm,
  deficit_oblasts, crops, crop_condition, crop_bbch, hazards, yield_vs_avg, yield_mt
A field is correct when it equals the gold value exactly (a set field: the same set).
Hallucination: the gold field is empty (null / [] / not_stated) but the model filled it
(an invented crop counts in crops, crop_condition and crop_bbch: up to three fields).

Per run: valid answers (ok + fixed), field accuracy on the golden set (all / Hydromet / JRC),
set F1 (partial credit for list fields), hallucinations, latency p50/p95, cost per 1000 documents.

Outputs: results/metrics.md, results/metrics.csv, results/errors/<run>.md (every wrong field).
"""

import csv
import json
import math
from pathlib import Path

from .run import RESULTS, ROOT, source_of

GOLDEN = ROOT / "data" / "golden"

SCALAR = ["year", "month", "decade", "moisture_status", "moisture_layer", "min_mm", "max_mm"]
SETS = ["deficit_oblasts", "crops", "crop_condition", "crop_bbch", "hazards", "yield_vs_avg", "yield_mt"]
FIELDS = SCALAR + SETS


def flatten(rec: dict | None) -> dict | None:
    if rec is None:
        return None
    sm = rec.get("soil_moisture") or {}
    crops = rec.get("crops") or []
    yields = rec.get("yield_outlook") or []
    return {
        "year": rec.get("year"),
        "month": rec.get("month"),
        "decade": rec.get("decade"),
        "moisture_status": sm.get("status"),
        "moisture_layer": sm.get("layer"),
        "min_mm": sm.get("min_mm"),
        "max_mm": sm.get("max_mm"),
        "deficit_oblasts": frozenset(sm.get("deficit_oblasts") or []),
        "crops": frozenset(c["crop"] for c in crops),
        "crop_condition": frozenset((c["crop"], c["condition"]) for c in crops if c["condition"] != "not_stated"),
        "crop_bbch": frozenset((c["crop"], c["bbch_stage"]) for c in crops if c["bbch_stage"] is not None),
        "hazards": frozenset(rec.get("hazards") or []),
        "yield_vs_avg": frozenset((y["crop"], y["vs_5yr_average"]) for y in yields if y["vs_5yr_average"] != "not_stated"),
        "yield_mt": frozenset((y["crop"], round(float(y["production_mt"]), 2)) for y in yields
                              if y.get("production_mt") is not None),
    }


def is_empty(v) -> bool:
    return v is None or v == "not_stated" or (isinstance(v, frozenset) and not v)


def score(pred: dict | None, gold: dict) -> dict:
    """Compare one prediction with its gold record (both as returned by flatten)."""
    out = {"correct": 0, "hallucinated": 0, "wrong": [], "set_tp": 0, "set_fp": 0, "set_fn": 0}
    for f in FIELDS:
        g = gold[f]
        p = pred[f] if pred is not None else None
        if pred is not None and p == g:
            out["correct"] += 1
        else:
            out["wrong"].append((f, g, p))
            if pred is not None and is_empty(g) and not is_empty(p):
                out["hallucinated"] += 1
        if f in SETS:
            ps = p if isinstance(p, frozenset) else frozenset()
            out["set_tp"] += len(ps & g)
            out["set_fp"] += len(ps - g)
            out["set_fn"] += len(g - ps)
    return out


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    v = sorted(values)
    k = max(0, math.ceil(q / 100 * len(v)) - 1)   # nearest-rank
    return v[k]


def load_golden() -> dict[str, dict]:
    gold = {}
    for p in sorted(GOLDEN.glob("*.json")):
        gold[p.stem] = flatten(json.loads(p.read_text(encoding="utf-8")))
    return gold


def load_run(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt(v) -> str:
    if isinstance(v, frozenset):
        return "[" + ", ".join(sorted(map(str, v))) + "]" if v else "[]"
    return "null" if v is None else str(v)


def run_metrics(rows: list[dict], gold: dict[str, dict]) -> tuple[dict, list[str], dict]:
    n = len(rows)
    valid = [r for r in rows if r["status"] in ("ok", "fixed")]
    latency = [r["seconds"] for r in rows if r["attempts"]]   # every text that reached the model
    cost = [r["cost_usd"] for r in rows]

    totals = {"all": [0, 0], "hydromet": [0, 0], "jrc": [0, 0]}
    per_field = {f: [0, 0] for f in FIELDS}
    halluc = tp = fp = fn = 0
    errors = []
    scored = 0
    for r in rows:
        g = gold.get(r["text_id"])
        if g is None:
            continue
        scored += 1
        s = score(flatten(r["parsed"]), g)
        group = "hydromet" if r["source"] == "hydromet" else "jrc"
        for key in ("all", group):
            totals[key][0] += s["correct"]
            totals[key][1] += len(FIELDS)
        for f in FIELDS:
            per_field[f][1] += 1
        for f in FIELDS:
            if f not in {w[0] for w in s["wrong"]}:
                per_field[f][0] += 1
        halluc += s["hallucinated"]
        tp, fp, fn = tp + s["set_tp"], fp + s["set_fp"], fn + s["set_fn"]
        if r["status"] == "failed":
            errors.append(f"### {r['text_id']}: FAILED\n\n```\n{r['error']}\n```\n")
        elif s["wrong"]:
            lines = [f"### {r['text_id']} ({s['correct']}/{len(FIELDS)})", "",
                     "| field | expected | got |", "|---|---|---|"]
            lines += [f"| {f} | {fmt(g_)} | {fmt(p_)} |" for f, g_, p_ in s["wrong"]]
            errors.append("\n".join(lines) + "\n")

    def acc(key):
        c, t = totals[key]
        return c / t if t else float("nan")

    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if tp and (precision + recall) else 0.0
    first = rows[0] if rows else {}
    m = {
        "run": f"{first.get('model_key')}__{first.get('prompt_version')}__{first.get('sampling')}",
        "model": first.get("model"), "prompt": first.get("prompt_version"),
        "T": first.get("temperature"), "top_p": first.get("top_p"),
        "texts": n,
        "valid_pct": 100 * len(valid) / n if n else float("nan"),
        "fixed": sum(r["status"] == "fixed" for r in rows),
        "failed": sum(r["status"] == "failed" for r in rows),
        "golden": scored,
        "acc_all": 100 * acc("all"), "acc_hydromet": 100 * acc("hydromet"), "acc_jrc": 100 * acc("jrc"),
        "set_f1": 100 * f1 if scored else float("nan"),
        "hallucinations": halluc,
        "p50_s": percentile(latency, 50), "p95_s": percentile(latency, 95),
        "usd_per_1000": 1000 * sum(cost) / n if n else float("nan"),
        "usd_total": sum(cost),
    }
    field_acc = {f: (100 * c / t if t else float("nan")) for f, (c, t) in per_field.items()}
    return m, errors, field_acc


def num(v, digits=1) -> str:
    if isinstance(v, float):
        return "–" if math.isnan(v) else f"{v:.{digits}f}"
    return str(v)


def main() -> None:
    gold = load_golden()
    runs = sorted(p for p in RESULTS.glob("*.jsonl"))
    if not runs:
        raise SystemExit("No results yet: run `make run` first")
    if not gold:
        print("WARNING: data/golden/ is empty, accuracy cannot be measured yet\n")

    all_m, all_fields = [], {}
    (RESULTS / "errors").mkdir(exist_ok=True)
    for path in runs:
        rows = load_run(path)
        if not rows:
            continue
        m, errors, field_acc = run_metrics(rows, gold)
        all_m.append(m)
        all_fields[m["run"]] = field_acc
        header = (f"# Errors: {m['run']}\n\nEvery golden-set field where the model differs from the gold "
                  f"value (expected = gold). Use these for the error analysis in REPORT.md.\n\n")
        (RESULTS / "errors" / f"{path.stem}.md").write_text(
            header + ("\n".join(errors) if errors else "No errors.\n"), encoding="utf-8")

    cols = [("model", "Model"), ("prompt", "Prompt"), ("T", "T"), ("top_p", "top_p"),
            ("valid_pct", "Valid %"), ("fixed", "Fixed"), ("failed", "Failed"),
            ("acc_all", "Field acc %"), ("acc_hydromet", "Acc Hydromet %"), ("acc_jrc", "Acc JRC %"),
            ("set_f1", "Set F1 %"), ("hallucinations", "Halluc."),
            ("p50_s", "p50 s"), ("p95_s", "p95 s"), ("usd_per_1000", "$ / 1000 docs")]
    golden_n = max((m["golden"] for m in all_m), default=0)
    lines = ["# Metrics", "",
             f"Texts per run: {all_m[0]['texts'] if all_m else 0}. Golden set: {golden_n} texts × "
             f"{len(FIELDS)} fields. Accuracy, F1 and hallucinations are measured on the golden set; "
             "valid %, latency and cost on all texts.", "",
             "| " + " | ".join(c[1] for c in cols) + " |",
             "|" + "---|" * len(cols)]
    for m in all_m:
        lines.append("| " + " | ".join(num(m[k], 4 if k == "usd_per_1000" else 1) for k, _ in cols) + " |")

    lines += ["", "## Accuracy per field, %", "",
              "| Field | " + " | ".join(all_fields) + " |", "|---|" + "---|" * len(all_fields)]
    for f in FIELDS:
        lines.append(f"| {f} | " + " | ".join(num(all_fields[r][f], 0) for r in all_fields) + " |")
    lines.append("")
    (RESULTS / "metrics.md").write_text("\n".join(lines), encoding="utf-8")

    with (RESULTS / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_m[0]))
        w.writeheader()
        w.writerows(all_m)

    print("\n".join(lines[:5 + len(all_m) + 1]))
    print(f"\nSaved results/metrics.md, results/metrics.csv, results/errors/*.md")


def check_golden() -> None:
    """Validate every golden file against the schema and its text."""
    from pydantic import ValidationError

    from .schema import AgroReport

    files = sorted(GOLDEN.glob("*.json"))
    if not files:
        raise SystemExit("data/golden/ is empty")
    bad = 0
    for p in files:
        text_path = ROOT / "data" / "texts" / f"{p.stem}.txt"
        if not text_path.exists():
            print(f"  {p.name}: no text data/texts/{p.stem}.txt")
            bad += 1
            continue
        try:
            AgroReport.model_validate_json(p.read_text(encoding="utf-8"),
                                           context={"text": text_path.read_text(encoding="utf-8")})
            print(f"  {p.name}: ok ({source_of(p.stem)[0]})")
        except ValidationError as e:
            bad += 1
            print(f"  {p.name}: INVALID\n" + "\n".join(f"      {x['loc']}: {x['msg']}" for x in e.errors()))
    print(f"\n{len(files) - bad}/{len(files)} golden files are valid")
    if bad:
        raise SystemExit(1)

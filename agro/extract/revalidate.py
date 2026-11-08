"""Re-apply the current validation and list cleaning to answers already saved in results/.

    python main.py revalidate

Used after the checks in agro/extract/checks.py were made stricter: no model is called, the
saved answers are checked again.

For every row of results/extract/*.jsonl and results/extract/regression/*.jsonl:
  * the first answer (raw) is validated with the current checks -> status "ok";
  * if it fails and a corrected answer (raw_fixed) was saved -> that one is validated -> "fixed";
  * otherwise -> "failed" (a new correction request is not sent, so this is a pessimistic count:
    in a live run the model would get one more attempt);
  * values the text does not support are removed or reset and stored in "removed".
The previous result is kept in status_before / parsed_before / error_before, so the change is
visible, and running the command again gives the same result.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from .run import RESULTS, load_texts, short_error, validate_and_clean


def _check(content: str | None, text: str):
    if not content:
        return None, [], "no answer"
    try:
        parsed, removed = validate_and_clean(content, text)
        return parsed, removed, None
    except ValidationError as e:
        return None, [], short_error(e)


def revalidate_file(path: Path, texts: dict[str, str]) -> dict:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    stats = {"rows": len(rows), "now_failed": 0, "removed_items": 0, "changed": 0}
    out = []
    for r in rows:
        if "status_before" not in r:   # first revalidation: keep the original result
            r["status_before"], r["parsed_before"], r["error_before"] = r["status"], r["parsed"], r["error"]
        text = texts.get(r["text_id"])
        provider_problem = (r["error_before"] or "").startswith(("provider:", "answer cut"))
        if text is None or provider_problem:
            out.append(r)
            continue
        parsed, removed, err = _check(r.get("raw"), text)
        status = "ok"
        if parsed is None and r.get("raw_fixed"):
            parsed, removed, err2 = _check(r["raw_fixed"], text)
            status = "fixed" if parsed is not None else "failed"
            err = err2 if parsed is None else None
        elif parsed is None:
            status = "failed"
        r["status"], r["parsed"], r["removed"] = status, parsed, removed
        r["error"] = None if parsed is not None else f"invalid after revalidation:\n{err}"
        r["revalidated"] = True
        stats["now_failed"] += status == "failed" and r["status_before"] != "failed"
        stats["removed_items"] += len(removed)
        stats["changed"] += (status != r["status_before"]) or (parsed != r["parsed_before"])
        out.append(r)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    return stats


def main() -> None:
    texts = load_texts()
    files = sorted(RESULTS.glob("*.jsonl")) + sorted((RESULTS / "regression").glob("*.jsonl"))
    if not files:
        raise SystemExit("No results to revalidate")
    print(f"{'run':<45} {'rows':>4} {'changed':>7} {'now failed':>10} {'items removed':>13}")
    for f in files:
        s = revalidate_file(f, texts)
        name = str(f.relative_to(RESULTS))
        print(f"{name:<45} {s['rows']:>4} {s['changed']:>7} {s['now_failed']:>10} {s['removed_items']:>13}")
    print("\nNow run `python main.py metrics` for the updated tables.")

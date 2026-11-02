"""Accuracy and hallucinations of the answers BEFORE the fact checks, on the dev and test golden sets.

The answers of the first version (before agro_extract/checks.py existed) are kept in git under the
tag `hw1-initial`; results/ now holds the answers after the checks. This script reads the old
answers from git (nothing is called, nothing is changed) and scores them against the current dev
and test golden sets, so the "before" columns of REPORT.md (section 3) can be reproduced:

    python scripts/before_checks.py                  # from the git tag hw1-initial
    python scripts/before_checks.py --ref <commit>   # any other commit or tag

The "after" numbers are in results/metrics.md (`python main.py metrics`).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agro_extract.metrics import FIELDS, GOLDEN, GOLDEN_TEST, flatten, load_golden, score  # noqa: E402


def git_files(ref: str) -> list[str]:
    out = subprocess.run(["git", "ls-tree", "--name-only", ref, "results/"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split() if p.endswith(".jsonl")]


def git_rows(ref: str, path: str) -> list[dict]:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def scores(rows: list[dict], gold: dict) -> tuple[float, int, int]:
    correct = halluc = n = 0
    for r in rows:
        g = gold.get(r["text_id"])
        if g is None:
            continue
        s = score(flatten(r["parsed"]), g)
        correct, halluc, n = correct + s["correct"], halluc + s["hallucinated"], n + 1
    return (100 * correct / (n * len(FIELDS)) if n else float("nan")), halluc, n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="hw1-initial", help="git commit or tag with the answers before the checks")
    ref = ap.parse_args().ref
    try:
        files = git_files(ref)
    except subprocess.CalledProcessError:
        sys.exit(f"git ref '{ref}' not found: run `git fetch --tags` first")
    dev, test = load_golden(GOLDEN), load_golden(GOLDEN_TEST)
    print(f"Answers before the fact checks (git {ref}), scored on the current golden sets\n")
    print("| Run | Dev acc % | Dev halluc. | Test acc % | Test halluc. |")
    print("|---|---|---|---|---|")
    for path in files:
        rows = git_rows(ref, path)
        d_acc, d_h, _ = scores(rows, dev)
        t_acc, t_h, _ = scores(rows, test)
        print(f"| {Path(path).stem} | {d_acc:.1f} | {d_h} | {t_acc:.1f} | {t_h} |")


if __name__ == "__main__":
    main()

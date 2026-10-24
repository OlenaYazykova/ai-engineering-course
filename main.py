"""Agro-analyst, stage 1: structured extraction from agrometeorological bulletins.

    python main.py                       # every experiment from config.toml (skips done ones) + metrics
    python main.py run --model gpt4o_mini --prompt v1 --sampling t0 [--force]
    python main.py smoke --model qwen3b --id uk_hydromet_2023-07-d1__moisture
    python main.py metrics               # tables from results/ against data/golden/
    python main.py regress --model gpt4o_mini --prompt v3 --baseline v2   # new prompt vs old on golden set
    python main.py check-golden
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from agro_extract import metrics
from agro_extract.regress import regress
from agro_extract.providers import ProviderError
from agro_extract.run import load_config, run_all, run_experiment


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("all", help="every experiment from config.toml, then metrics (default)")
    a.add_argument("--force", action="store_true", help="redo runs that already have results")

    r = sub.add_parser("run", help="one model x prompt x sampling over all texts")
    r.add_argument("--model", required=True)
    r.add_argument("--prompt", required=True)
    r.add_argument("--sampling", default="t0")
    r.add_argument("--force", action="store_true")

    s = sub.add_parser("smoke", help="one or a few texts, prints the answer (results/smoke/)")
    s.add_argument("--model", required=True)
    s.add_argument("--prompt", default="v1")
    s.add_argument("--sampling", default="t0")
    s.add_argument("--id", nargs="+", required=True, help="text ids (file names without .txt)")

    sub.add_parser("metrics", help="metrics tables and error lists")
    g = sub.add_parser("regress", help="compare a new prompt with a baseline on the golden set")
    g.add_argument("--model", required=True)
    g.add_argument("--prompt", required=True, help="new prompt version")
    g.add_argument("--baseline", required=True, help="prompt version to compare with")
    g.add_argument("--sampling", default="t0")
    g.add_argument("--tolerance", type=float, default=2.0, help="allowed drop, pp (overall)")
    sub.add_parser("check-golden", help="validate data/golden/*.json")

    args = p.parse_args()
    cmd = args.cmd or "all"
    if cmd == "all":
        run_all(force=getattr(args, "force", False))
        metrics.main()
    elif cmd == "run":
        cfg = load_config()
        for key, name in ((args.model, "models"), (args.sampling, "sampling")):
            if key not in cfg[name]:
                sys.exit(f"Unknown {name[:-1] if name == 'models' else name} {key!r}; see config.toml")
        run_experiment(args.model, args.prompt, args.sampling, force=args.force, config=cfg)
    elif cmd == "smoke":
        out = run_experiment(args.model, args.prompt, args.sampling, ids=args.id)
        for line in out.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            print(f"\n=== {row['text_id']}: {row['status']}, {row['seconds']}s, "
                  f"{row['input_tokens']}+{row['output_tokens']} tokens")
            print(json.dumps(row["parsed"], ensure_ascii=False, indent=2) if row["parsed"] else row["error"])
    elif cmd == "metrics":
        metrics.main()
    elif cmd == "regress":
        ok = regress(args.model, args.prompt, args.baseline, args.sampling, args.tolerance)
        sys.exit(0 if ok else 1)
    elif cmd == "check-golden":
        metrics.check_golden()


if __name__ == "__main__":
    try:
        main()
    except ProviderError as e:
        sys.exit(f"Error: {e}")

"""Agro-analyst: an assistant for agro analysts over Ukrhydrometcenter and JRC MARS bulletins.

Every stage of the course project has its own group of commands.

Stage 1 (homework 1), structured extraction:
    python main.py extract all            # every experiment from config.toml (skips done ones) + metrics
    python main.py extract run --model gpt4o_mini --prompt v1 --sampling t0 [--force]
    python main.py extract smoke --model qwen3b --id uk_hydromet_2023-07-d1__moisture
    python main.py extract metrics        # tables from results/extract/ against data/extract/golden/
    python main.py extract regress --model gpt4o_mini --prompt v3 --baseline v2   # new prompt vs old
    python main.py extract revalidate     # re-check saved answers with the current checks (no model calls)
    python main.py extract check-golden

Stage 2 (homework 2), RAG over the corpus:
    python main.py rag ingest [--force] [--only DOC_ID ...]   # data/raw/ -> data/corpus/ (+ manifest)
    python main.py rag chunk                                   # data/corpus/ -> data/rag/chunks.jsonl
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from agro.common.providers import ProviderError
from agro.extract import metrics
from agro.extract import revalidate
from agro.extract.regress import regress
from agro.extract.run import load_config, run_all, run_experiment


def add_extract(stages) -> None:
    """Stage 1 (homework 1): structured extraction."""
    e = stages.add_parser("extract", help="stage 1: structured extraction (homework 1)",
                          description=add_extract.__doc__)
    sub = e.add_subparsers(dest="cmd")

    a = sub.add_parser("all", help="every experiment from config.toml, then metrics (default)")
    a.add_argument("--force", action="store_true", help="redo runs that already have results")

    r = sub.add_parser("run", help="one model x prompt x sampling over all texts")
    r.add_argument("--model", required=True)
    r.add_argument("--prompt", required=True)
    r.add_argument("--sampling", default="t0")
    r.add_argument("--force", action="store_true")

    s = sub.add_parser("smoke", help="one or a few texts, prints the answer (results/extract/smoke/)")
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
    sub.add_parser("check-golden", help="validate data/extract/golden*/*.json")
    sub.add_parser("revalidate", help="re-check saved answers with the current checks (no model calls)")


def run_extract(args) -> None:
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
    elif cmd == "revalidate":
        revalidate.main()


def add_rag(stages) -> None:
    """Stage 2 (homework 2): RAG over the corpus."""
    r = stages.add_parser("rag", help="stage 2: RAG over the corpus (homework 2)", description=add_rag.__doc__)
    sub = r.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="read, clean and de-duplicate the documents -> data/corpus/")
    ing.add_argument("--force", action="store_true", help="read every document again (ignore the cache)")
    ing.add_argument("--only", nargs="+", help="read these documents again")
    sub.add_parser("chunk", help="cut the documents into chunks -> data/rag/chunks.jsonl (+ fixed-size baseline)")


def run_rag(args) -> None:
    if args.cmd == "ingest":
        from agro.corpus.ingest import run
        run(force=args.force, only=args.only)
    elif args.cmd == "chunk":
        from agro.rag.chunking import run
        run()


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    stages = p.add_subparsers(dest="stage", required=True)
    add_extract(stages)
    add_rag(stages)
    args = p.parse_args()
    if args.stage == "extract":
        run_extract(args)
    elif args.stage == "rag":
        run_rag(args)


if __name__ == "__main__":
    try:
        main()
    except ProviderError as e:
        sys.exit(f"Error: {e}")

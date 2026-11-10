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
    python main.py rag index [--models e5 ...]                 # embeddings + Qdrant (cached)
    python main.py rag search "питання" [--year 2023 --month 7 --source JRC] [--auto-filters]
    python main.py rag retrieval-eval [--split dev]            # recall@k / MRR -> results/rag/
    python main.py rag lint-testset                            # checks of the test set itself
    python main.py rag ocr-compare                             # vision OCR vs EasyOCR -> results/rag/
    python main.py rag ask "питання" [-k 5]                     # answer with sources [n] or "not in the documents"
    python main.py rag threshold [--split dev]                 # threshold of "not in the documents" (no model calls)
    python main.py rag answer-eval [--split dev] [--k 3 5 10]  # answers of the test set questions -> results/rag/

Stage 2, evals (homework 2, step 4):
    python main.py evals label-dump                            # answers to label by hand -> evals/calibration/
    python main.py evals label-load                            # the filled table -> evals/calibration/labels.jsonl
    python main.py evals calibrate                             # the judge against the labels -> agreement.md
    python main.py evals run [--split dev|test|all] [--repeats 3] [--fresh]   # the evals -> evals/results/
    python main.py evals baseline                              # evals/results/ -> evals/baseline.json
    python main.py evals gate                                  # evals/results/ vs evals/baseline.json (CI)
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
    idx = sub.add_parser("index", help="embeddings + Qdrant index of the structural chunks")
    idx.add_argument("--models", nargs="+", default=["minilm", "mpnet", "e5"])
    s = sub.add_parser("search", help="search the corpus and print the chunks found")
    s.add_argument("query")
    s.add_argument("--method", default="hybrid_rerank", choices=["vector", "bm25", "hybrid", "hybrid_rerank", "vector_rerank"])
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--chunker", default="structural", choices=["structural", "fixed"])
    s.add_argument("--model", help="embedding model (default: config.toml [rag])")
    s.add_argument("--reranker", help="reranker (default: config.toml [rag])")
    s.add_argument("--auto-filters", action="store_true", help="read year / month / decade / source from the question")
    for name, typ in (("year", int), ("month", int), ("decade", int), ("source", str), ("language", str),
                      ("topic", str), ("kind", str), ("date-from", str), ("date-to", str)):
        s.add_argument(f"--{name}", type=typ)
    sub.add_parser("lint-testset", help="check the test set: fields, kinds, evidence phrases in the documents")
    sub.add_parser("ocr-compare", help="vision OCR transcripts vs EasyOCR on the same pages -> results/rag/")
    ev = sub.add_parser("retrieval-eval", help="recall@k / MRR of the search configurations")
    ev.add_argument("--split", default="dev", choices=["dev", "test"])
    a = sub.add_parser("ask", help="answer a question from the documents, with sources")
    a.add_argument("query")
    a.add_argument("-k", type=int, help="chunks given to the model (default: config.toml [answer] k)")
    t = sub.add_parser("threshold", help="threshold of \"not in the documents\" from the reranker scores")
    t.add_argument("--split", default="dev", choices=["dev", "test"])
    ae = sub.add_parser("answer-eval", help="answers of the test set questions for several k -> results/rag/")
    ae.add_argument("--split", default="dev", choices=["dev", "test"])
    ae.add_argument("--k", type=int, nargs="+", default=[3, 5, 10])


def run_rag(args) -> None:
    if args.cmd == "ingest":
        from agro.corpus.ingest import run
        run(force=args.force, only=args.only)
    elif args.cmd == "chunk":
        from agro.rag.chunking import run
        run()
    elif args.cmd == "index":
        from agro.rag.search import run_index
        run_index(models=tuple(args.models))
    elif args.cmd == "search":
        from agro.rag.filters import Filters, from_question
        from agro.rag.search import Retriever, print_hits
        flt = Filters(year=args.year, month=args.month, decade=args.decade, source=args.source,
                      language=args.language, topic=args.topic, kind=args.kind,
                      date_from=args.date_from, date_to=args.date_to)
        if args.auto_filters:
            auto = from_question(args.query)
            flt = Filters(**{k: getattr(flt, k) if getattr(flt, k) is not None else getattr(auto, k)
                             for k in flt.__dataclass_fields__})
        print(f"filters: {flt.active() or 'none'}")
        r = Retriever(args.chunker, args.model, args.reranker)
        print_hits(r.search(args.query, k=args.k, method=args.method, flt=flt if flt.active() else None))
    elif args.cmd == "lint-testset":
        from agro.rag.testset import run
        run()
    elif args.cmd == "ocr-compare":
        from agro.corpus.ocr_compare import run
        run()
    elif args.cmd == "retrieval-eval":
        from agro.rag.retrieval_eval import run
        run(args.split)
    elif args.cmd == "ask":
        from agro.rag.answer import ask
        ask(args.query, k=args.k)
    elif args.cmd == "threshold":
        from agro.rag.answer_eval import run_threshold
        run_threshold(args.split)
    elif args.cmd == "answer-eval":
        from agro.rag.answer_eval import run
        run(args.split, tuple(args.k))


def add_evals(stages) -> None:
    """Stage 2 (homework 2, step 4): evals of the answers."""
    e = stages.add_parser("evals", help="stage 2: evals of the RAG answers (homework 2, step 4)",
                          description=add_evals.__doc__)
    sub = e.add_subparsers(dest="cmd", required=True)
    sub.add_parser("label-dump", help="answers to label by hand -> evals/calibration/to_label.xlsx")
    sub.add_parser("label-load", help="the filled table -> evals/calibration/labels.jsonl")
    sub.add_parser("calibrate", help="the judge on the labelled answers -> evals/calibration/agreement.md")
    r = sub.add_parser("run", help="the test set through the system, scored by the code and the judge -> evals/results/")
    r.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    r.add_argument("--repeats", type=int, default=1, help="runs of the answers (more than 1: no replay from the cache)")
    r.add_argument("--fresh", action="store_true", help="call the model even for one run (no replay from the cache; CI)")
    sub.add_parser("baseline", help="evals/results/{dev,test}.json -> evals/baseline.json")
    sub.add_parser("gate", help="evals/results/{dev,test}.json against evals/baseline.json (exit code 1 below a threshold)")


def run_evals(args) -> None:
    from evals import calibration

    if args.cmd == "label-dump":
        calibration.dump()
    elif args.cmd == "label-load":
        calibration.load_labels()
    elif args.cmd == "calibrate":
        calibration.calibrate()
    elif args.cmd == "run":
        from evals.run import run
        run(args.split, args.repeats, fresh=args.fresh)
    elif args.cmd == "baseline":
        from evals.gate import make_baseline
        make_baseline()
    elif args.cmd == "gate":
        from evals.gate import run_gate
        run_gate()


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    stages = p.add_subparsers(dest="stage", required=True)
    add_extract(stages)
    add_rag(stages)
    add_evals(stages)
    args = p.parse_args()
    if args.stage == "extract":
        run_extract(args)
    elif args.stage == "rag":
        run_rag(args)
    elif args.stage == "evals":
        run_evals(args)


if __name__ == "__main__":
    try:
        main()
    except ProviderError as e:
        sys.exit(f"Error: {e}")

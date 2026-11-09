"""Retrieval quality: recall@k and MRR on the questions of the test set that have an answer.

    make rag-retrieval-eval            # dev questions (tuning); `--split test` only for the final report

A chunk is relevant to a question when it is from the expected document and contains the evidence
phrase of the test set (spaces normalised). For fixed-size chunks the phrase may be cut by a chunk
border, so half of the phrase (its first or second half) is enough. The labels are documents +
phrases, not chunk ids, so the same labels serve both chunkings.

  recall@k  share of the expected sources (documents + phrases) found in the top k
  hit@k     share of questions with at least one relevant chunk in the top k
  MRR       mean of 1 / rank of the first relevant chunk (0 if none in the top 10)

Configurations (results/rag/retrieval.md):
  A. embedding models, vector search, structural chunks
  B. methods: vector / bm25 / bm25 without stemming / hybrid / hybrid + reranker (both rerankers),
     structural vs fixed-size chunks, with the best embedding model
  C. the best method with metadata filters read from the question
  D. structural chunk sizes (chunking.SIZES) with the best model: vector and hybrid + reranker,
     and the share of chunks longer than the input window of the model (they are cut before embedding)
  E. reranker speed vs quality: 20 or 10 candidates, both rerankers; vector + reranker without BM25
     (what BM25 adds to the candidates)
"""

import json
import re
import statistics
import time

from ..common.settings import RESULTS_RAG, ROOT
from .chunking import SIZES, chunk_file, chunk_size, load_chunks
from .embed import window_stats
from .search import RERANKERS, Retriever, ensure_index

EVALS = ROOT / "evals"
KS = (1, 3, 5, 10)


def load_questions(split: str) -> list[dict]:
    from .testset import load

    return load(split)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def relevant(chunk, source: dict) -> bool:
    if chunk.doc_id != source["doc_id"]:
        return False
    text, ev = _norm(chunk.text), _norm(source["evidence"])
    if ev in text:
        return True
    half = len(ev) // 2
    return len(ev) >= 40 and (ev[:half] in text or ev[half:] in text)


def score_question(hits, q: dict) -> dict:
    """Per question: rank of the first relevant chunk, and for each k the sources found."""
    sources = q["sources"]
    first = next((r for r, h in enumerate(hits, 1) if any(relevant(h.chunk, s) for s in sources)), None)
    if q.get("match") == "any":      # the same fact in several documents: one of them is enough
        found = {k: float(any(relevant(h.chunk, s) for h in hits[:k] for s in sources)) for k in KS}
    else:
        found = {k: sum(any(relevant(h.chunk, s) for h in hits[:k]) for s in sources) / len(sources) for k in KS}
    return {"id": q["id"], "kind": q["kind"], "first_rank": first, "recall": found,
            "top": [h.chunk.chunk_id for h in hits[:5]]}


def evaluate(retriever: Retriever, questions: list[dict], method: str, auto_filters: bool = False) -> dict:
    rows, times = [], []
    for q in questions:
        t = time.perf_counter()
        hits = retriever.search(q["question"], k=max(KS), method=method, auto_filters=auto_filters)
        times.append(1000 * (time.perf_counter() - t))
        rows.append(score_question(hits, q))
    n = len(rows)
    return {
        **{f"recall@{k}": sum(r["recall"][k] for r in rows) / n for k in KS},
        **{f"hit@{k}": sum(1 for r in rows if r["first_rank"] and r["first_rank"] <= k) / n for k in KS},
        "MRR": sum(1 / r["first_rank"] for r in rows if r["first_rank"]) / n,
        "ms/query": statistics.median(times),
        "rows": rows,
    }


def _row(name: str, m: dict) -> str:
    name = name.replace(" | ", ", ")
    return (f"| {name} | {m['recall@1']:.2f} | {m['recall@3']:.2f} | {m['recall@5']:.2f} | {m['recall@10']:.2f} "
            f"| {m['MRR']:.3f} | {m['ms/query']:.0f} |")


HEAD = "| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |\n|---|---|---|---|---|---|---|"


def run(split: str = "dev", models=("minilm", "mpnet", "e5")) -> dict:
    questions = [q for q in load_questions(split) if q["sources"]]   # no-answer questions have no chunk
    print(f"{len(questions)} {split} questions with an expected source")
    results: dict[str, dict] = {}
    windows: dict[str, dict | None] = {}      # "<model> | <chunker>" -> window statistics

    def window(model, chunker):
        texts = [c.for_embedding() for c in load_chunks(chunk_file(chunker))]
        windows[f"{model} | {chunker}"] = window_stats(model, texts)

    def do(name, retriever, method, auto=False):
        m = evaluate(retriever, questions, method, auto)
        results[name] = m
        print(f"  {name:<52} recall@5 {m['recall@5']:.2f}  MRR {m['MRR']:.3f}  {m['ms/query']:.0f} ms")
        return m

    # A. embedding models
    for model in models:
        ensure_index("structural", model)
        do(f"A vector | structural | {model}", Retriever("structural", model), "vector")
        window(model, "structural")
    best_model = max(models, key=lambda mo: (results[f"A vector | structural | {mo}"]["MRR"],
                                             results[f"A vector | structural | {mo}"]["recall@5"]))
    # B. methods x chunking (the fixed-size index is built for the best model only)
    ensure_index("fixed", best_model)
    for chunker in ("structural", "fixed"):
        r = Retriever(chunker, best_model)
        r.rerank_top = 20                     # part B: 20 candidates (part E compares with 10)
        do(f"B vector | {chunker} | {best_model}", r, "vector")
        do(f"B bm25 | {chunker}", r, "bm25")
        if chunker == "structural":
            do("B bm25 without stemming | structural", Retriever(chunker, best_model, stem=None), "bm25")
        do(f"B hybrid | {chunker} | {best_model}", r, "hybrid")
        for rk in RERANKERS:
            r.reranker_key = rk
            do(f"B hybrid + rerank {rk} | {chunker} | {best_model}", r, "hybrid_rerank")
    best_rk = max(RERANKERS, key=lambda rk: results[f"B hybrid + rerank {rk} | structural | {best_model}"]["MRR"])
    # C. filters
    r = Retriever("structural", best_model, best_rk)
    do(f"C hybrid + filters | structural | {best_model}", r, "hybrid", auto=True)
    do(f"C hybrid + rerank {best_rk} + filters | structural | {best_model}", r, "hybrid_rerank", auto=True)

    # D. chunk sizes (the size used is config.toml [rag] chunk_tokens; the others are in .cache/chunks)
    used = chunk_size()
    for size in sorted(set(SIZES) | {used}):
        chunker = "structural" if size == used else f"structural_{size}"
        if not chunk_file(chunker).exists():
            print(f"  no {chunk_file(chunker)}: run `make rag-chunk`")
            continue
        ensure_index(chunker, best_model)
        r = Retriever(chunker, best_model, best_rk)
        label = f"max {size}" + (" (used)" if size == used else "")
        do(f"D vector | {label} | {best_model}", r, "vector")
        do(f"D hybrid + rerank {best_rk} | {label} | {best_model}", r, "hybrid_rerank")
        if chunker != "structural":
            window(best_model, chunker)

    # E. reranker: number of candidates, and candidates without BM25
    r = Retriever("structural", best_model)
    for rk in RERANKERS:
        r.reranker_key = rk
        for top in (20, 10):
            r.rerank_top = top
            if top == 20:     # = part B (same settings): not measured twice
                results[f"E hybrid + rerank {rk}, top {top} | structural | {best_model}"] = \
                    results[f"B hybrid + rerank {rk} | structural | {best_model}"]
            else:
                do(f"E hybrid + rerank {rk}, top {top} | structural | {best_model}", r, "hybrid_rerank")
    r.reranker_key = best_rk
    for top in (20, 10):
        r.rerank_top = top
        do(f"E vector + rerank {best_rk}, top {top} (no BM25) | structural | {best_model}", r, "vector_rerank")

    write_report(split, questions, results, best_model, best_rk, windows, used)
    return results


def write_report(split, questions, results, best_model, best_rk, windows, used) -> None:
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    lines = [f"# Retrieval quality ({split} set)", "",
             f"{len(questions)} questions with an expected source (no-answer questions excluded). "
             "A chunk is relevant if it is from the expected document and contains the evidence phrase "
             "(agro/rag/retrieval_eval.py). recall@k: share of expected sources found in the top k; "
             "MRR: 1 / rank of the first relevant chunk.", ""]
    for part, title in (("A", "A. Embedding models (vector search, structural chunks)"),
                        ("B", f"B. Methods and chunking (embeddings: {best_model})"),
                        ("C", "C. Metadata filters read from the question"),
                        ("D", f"D. Structural chunk size (embeddings: {best_model}, reranker: {best_rk})"),
                        ("E", f"E. Reranker: candidates reordered (top 20 / 10), with and without BM25 "
                              f"(embeddings: {best_model}, no filters)")):
        lines += [f"## {title}", "", HEAD]
        lines += [_row(name[2:], m) for name, m in results.items() if name.startswith(part)]
        lines.append("")
    lines += ["## Chunks longer than the input window of the embedding model", "",
              "Tokens of the model's own tokenizer (with the e5 prefix). The part of a chunk after the window",
              "is cut off before embedding: vector search cannot find it (BM25 and the reranker still see it).", "",
              "| model | chunks | window, tokens | median chunk, tokens | chunks over the window, % |",
              "|---|---|---|---|---|"]
    for name, w in windows.items():
        lines.append(f"| {name} | " + (f"{w['window']} | {w['median_tokens']} | {w['over_window_%']} |"
                                        if w else "- | - | - |"))
    lines.append("")
    lines += [f"Structural chunk size used: {used} tokens (config.toml [rag] chunk_tokens).", ""]
    lines += [f"Chosen: embeddings **{best_model}**, reranker **{best_rk}** (best MRR on {split}).", "",
              "## Per question (best configuration with filters)", "",
              "| id | kind | first relevant rank | recall@5 | top 3 chunks |", "|---|---|---|---|---|"]
    best = results[f"C hybrid + rerank {best_rk} + filters | structural | {best_model}"]
    for r in best["rows"]:
        lines.append(f"| {r['id']} | {r['kind']} | {r['first_rank'] or '-'} | {r['recall'][5]:.2f} | "
                     + ", ".join(r["top"][:3]) + " |")
    (RESULTS_RAG / f"retrieval_{split}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    slim = {k: {kk: vv for kk, vv in v.items() if kk != "rows"} | {"rows": v["rows"]} for k, v in results.items()}
    (RESULTS_RAG / f"retrieval_{split}.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
    print(f"Saved results/rag/retrieval_{split}.md")

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
  F. fusion of the two lists: RRF with the weight of BM25 1.0 ... 0.1, or relative score fusion with the
     vector weight alpha 0.9 / 0.8 / 0.7; BM25 on 6-letter stems or dictionary forms. Hybrid without the
     reranker for every variant; then the whole chain (hybrid + reranker + filters) for the setting of
     the checkpoint, the chosen one and the best relative fusion. The setting is chosen by the whole chain:
     the reranker can only reorder the candidates it gets, so the order of the hybrid alone decides little.

For every configuration with a reranker, "recall before rerank" is the share of the expected sources
among the candidates the reranker gets (20): what search lost cannot be found by the reranker.
"""

import json
import re
import statistics
import time

from ..common.settings import RESULTS_RAG, ROOT
from .chunking import SIZES, chunk_file, chunk_size, load_chunks
from .embed import window_stats
from .search import RERANKERS, TOKENS, Retriever, ensure_index

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


def found_share(hits, q: dict) -> float:
    """Share of the expected sources among these hits (one is enough for `match: any`)."""
    found = [any(relevant(h.chunk, s) for h in hits) for s in q["sources"]]
    return float(any(found)) if q.get("match") == "any" else sum(found) / len(found)


def evaluate(retriever: Retriever, questions: list[dict], method: str, auto_filters: bool = False) -> dict:
    rows, times = [], []
    for q in questions:
        retriever.cached_seconds = 0.0          # reranker time of the pairs taken from the cache
        t = time.perf_counter()
        hits = retriever.search(q["question"], k=max(KS), method=method, auto_filters=auto_filters)
        times.append(1000 * (time.perf_counter() - t + retriever.cached_seconds))
        rows.append(score_question(hits, q))
        if method.endswith("_rerank"):
            rows[-1]["candidates_recall"] = found_share(retriever.last_candidates, q)
    n = len(rows)
    out = {
        **{f"recall@{k}": sum(r["recall"][k] for r in rows) / n for k in KS},
        **{f"hit@{k}": sum(1 for r in rows if r["first_rank"] and r["first_rank"] <= k) / n for k in KS},
        "MRR": sum(1 / r["first_rank"] for r in rows if r["first_rank"]) / n,
        "ms/query": statistics.median(times),
        "rows": rows,
    }
    if method.endswith("_rerank"):
        out["recall_before_rerank"] = sum(r["candidates_recall"] for r in rows) / n
    return out


def _row(name: str, m: dict) -> str:
    name = name.replace(" | ", ", ")
    before = f"{m['recall_before_rerank']:.2f}" if "recall_before_rerank" in m else "-"
    return (f"| {name} | {m['recall@1']:.2f} | {m['recall@3']:.2f} | {m['recall@5']:.2f} | {m['recall@10']:.2f} "
            f"| {m['hit@5']:.2f} | {m['MRR']:.3f} | {before} | {m['ms/query']:.0f} |")


HEAD = ("| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |\n"
        "|---|---|---|---|---|---|---|---|---|")


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
        do(f"B bm25 ({r.bm25.tokens}) | {chunker}", r, "bm25")
        if chunker == "structural":
            for tokens in TOKENS:
                if tokens != r.bm25.tokens:
                    do(f"B bm25 ({tokens}) | structural", Retriever(chunker, best_model, bm25_tokens=tokens), "bm25")
        do(f"B hybrid | {chunker} | {best_model}", r, "hybrid")
        for rk in RERANKERS:
            r.reranker_key = rk
            do(f"B hybrid + rerank {rk} | {chunker} | {best_model}", r, "hybrid_rerank")
    best_rk = max(RERANKERS, key=lambda rk: results[f"B hybrid + rerank {rk} | structural | {best_model}"]["MRR"])
    # C. filters, the configured system (the setting of the checkpoint hw2-v1 is in part F)
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

    # F. fusion x words of BM25; the best variant (MRR of hybrid) with the reranker and with filters
    variants = [(tokens, "rrf", w) for tokens in ("stem6", "lemma") for w in (1.0, 0.5, 0.3, 0.2, 0.15, 0.1)]
    variants += [(tokens, "relative", a) for tokens in ("stem6", "lemma") for a in (0.9, 0.8, 0.7)]
    retrievers = {tokens: Retriever("structural", best_model, best_rk, bm25_tokens=tokens) for tokens in ("stem6", "lemma")}

    def setup(tokens, fusion, value):
        r = retrievers[tokens]
        r.fusion = fusion
        if fusion == "rrf":
            r.bm25_weight = value
        else:
            r.fusion_alpha = value
        return r

    def label(tokens, fusion, value):
        return f"bm25 {tokens}, " + (f"rrf, bm25 weight {value}" if fusion == "rrf" else f"relative, alpha {value}")

    for v in variants:
        do(f"F hybrid | {label(*v)} | {best_model}", setup(*v), "hybrid")
    cfg = Retriever("structural", best_model, best_rk)
    chosen = (cfg.bm25.tokens, cfg.fusion, cfg.bm25_weight if cfg.fusion == "rrf" else cfg.fusion_alpha)
    best_relative = max((v for v in variants if v[1] == "relative"),
                        key=lambda v: results[f"F hybrid | {label(*v)} | {best_model}"]["MRR"])
    for v in dict.fromkeys([("stem6", "rrf", 1.0), chosen, best_relative]):
        r = setup(*v)
        r.rerank_top = 20
        do(f"F hybrid + rerank {best_rk} + filters | {label(*v)}" + (" (chosen)" if v == chosen else "")
           + (" (checkpoint hw2-v1)" if v == ("stem6", "rrf", 1.0) else "")
           + f" | {best_model}", r, "hybrid_rerank", auto=True)

    write_report(split, questions, results, best_model, best_rk, windows, used)
    return results


def write_report(split, questions, results, best_model, best_rk, windows, used) -> None:
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    lines = [f"# Retrieval quality ({split} set)", "",
             f"{len(questions)} questions with an expected source (no-answer questions excluded). "
             "A chunk is relevant if it is from the expected document and contains the evidence phrase "
             "(agro/rag/retrieval_eval.py). recall@k: share of expected sources found in the top k; "
             "hit@5: share of questions with a relevant chunk in the top 5 (recall@5 of lesson 7); "
             "MRR: 1 / rank of the first relevant chunk; recall before rerank: share of expected sources "
             "among the 20 candidates the reranker gets.", ""]
    for part, title in (("A", "A. Embedding models (vector search, structural chunks)"),
                        ("B", f"B. Methods and chunking (embeddings: {best_model})"),
                        ("C", "C. Metadata filters read from the question"),
                        ("D", f"D. Structural chunk size (embeddings: {best_model}, reranker: {best_rk})"),
                        ("E", f"E. Reranker: candidates reordered (top 20 / 10), with and without BM25 "
                              f"(embeddings: {best_model}, no filters)"),
                        ("F", f"F. Fusion of the lists (RRF with a BM25 weight / relative score fusion) and words "
                              f"of BM25 (embeddings: {best_model}, structural chunks)")):
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
    cfg = Retriever("structural", best_model, best_rk)
    fusion = f"rrf, bm25 weight {cfg.bm25_weight}" if cfg.fusion == "rrf" else f"relative, alpha {cfg.fusion_alpha}"
    lines += [f"Chosen: embeddings **{best_model}**, reranker **{best_rk}** (best MRR on {split}); "
              f"BM25 **{cfg.bm25.tokens}**, fusion **{fusion}** (config.toml [rag], part F).", "",
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

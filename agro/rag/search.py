"""Index and search: Qdrant (vectors) + BM25 (words), hybrid by RRF, a cross-encoder reranker, filters.

    make rag-index                                   # build the indexes (embeddings cached)
    python main.py rag search "питання" [--year 2023 --source JRC ...] [--method hybrid_rerank]

Methods: vector | bm25 | hybrid (RRF of both) | hybrid_rerank (hybrid top-N reranked) |
vector_rerank (vector top-N reranked: the same without BM25, to measure what BM25 adds).
BM25 words (config.toml [rag] bm25_tokens): "lemma" (Ukrainian words to their dictionary form with
pymorphy3, other words cut to 6 letters), "stem6" (every word cut to 6 letters), "none".
Fusion of the two lists ([rag] fusion):
  rrf       score = sum of weight / (60 + rank); the vector list has weight 1, BM25 has [rag] bm25_weight.
            A chunk ranked 10th in both lists (2/70) beats the 1st of one list (1/61): with a BM25 that cannot
            read the other language or the right year, the best vector hit is pushed down.
  relative  scores of each list scaled to 0..1 (min-max per question), then
            fusion_alpha * vector + (1 - fusion_alpha) * BM25 ("relative score fusion"): a confident
            vector hit is not outvoted by chunks that are mediocre in both lists.
search() returns Hit objects (chunk + score + rank in every list), the input of the answer step and,
in stage 3, a tool of the agent.
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache

from ..common.settings import CACHE, MODELS_DIR, RAG_DATA, use_local_model_dirs
from .chunking import Chunk, chunk_file, load_chunks
from .embed import Embedder
from .filters import Filters, from_question, year_span

QDRANT_PATH = CACHE / "qdrant"
RERANKERS = {
    "jina": "jinaai/jina-reranker-v2-base-multilingual",     # 1.1 GB, multilingual
    "bge": "BAAI/bge-reranker-v2-m3",                       # 2.3 GB, multilingual
}
RRF_K = 60            # as in the lecture: rank fusion constant
CANDIDATES = 30       # taken from each list before fusion
RERANK_TOP = 20       # candidates the reranker reorders (config.toml [rag] rerank_top; 20 vs 10: part E)


# ---------------------------------------------------------------- BM25

_WORD = re.compile(r"[0-9]+(?:[.,][0-9]+)?|[A-Za-zА-Яа-яІіЇїЄєҐґ’']+")
_CYRILLIC = re.compile(r"[а-яіїєґ]")
STEM = 6              # "stem6": keep the first 6 letters: "вологи", "вологою", "вологість" -> "волог…"
TOKENS = ("lemma", "stem6", "none")


@lru_cache(maxsize=1)
def _morph():
    import pymorphy3            # installed with the Ukrainian spaCy model (Presidio, agro/corpus/pii.py)

    return pymorphy3.MorphAnalyzer(lang="uk")


@lru_cache(maxsize=200_000)
def lemma(word: str) -> str:
    """Dictionary form of a Ukrainian word ("вологою" -> "волога", "областях" -> "область").
    The first reading of the dictionary is taken: "року" -> "рок", the same in the question and the text."""
    return _morph().parse(word.replace("’", "'"))[0].normal_form


def tokenize(text: str, mode: str = "lemma") -> list[str]:
    """Lower case words and numbers for BM25 ("4.22" and "4,22" are the same number).
    lemma: Ukrainian words to their dictionary form, other words cut to 6 letters; stem6: every word cut
    to 6 letters; none: words as they are."""
    out = []
    for w in _WORD.findall(text.lower().replace("ʼ", "’")):
        if w[0].isdigit():
            out.append(w.replace(",", "."))
        elif mode == "lemma" and _CYRILLIC.search(w):
            out.append(lemma(w))
        elif mode in ("lemma", "stem6") and len(w) > STEM:
            out.append(w[:STEM])
        else:
            out.append(w)
    return out


class BM25:
    def __init__(self, chunks: list[Chunk], tokens: str = "lemma") -> None:
        from rank_bm25 import BM25Okapi

        if tokens not in TOKENS:
            raise ValueError(f"bm25 tokens: {tokens!r}, one of {TOKENS}")
        self.tokens = tokens
        self.chunks = chunks
        self.index = BM25Okapi([tokenize(c.for_embedding(), tokens) for c in chunks])

    def search(self, query: str, k: int, flt: Filters | None, payloads: list[dict]) -> list[tuple[int, float]]:
        scores = self.index.get_scores(tokenize(query, self.tokens))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            if flt is None or flt.matches(payloads[i]):
                out.append((i, float(scores[i])))
                if len(out) == k:
                    break
        return out


# ---------------------------------------------------------------- Qdrant

def payload(c: Chunk) -> dict:
    y0, y1 = year_span(c.period)
    return {"i": None, "chunk_id": c.chunk_id, "doc_id": c.doc_id, "source": c.source,
            "source_group": c.source.split()[0] if c.source else "", "language": c.language,
            "topic": c.topic, "kind": c.kind, "year_from": y0, "year_to": y1, "month": c.month,
            "decade": c.decade, "effective": c.effective, "format": c.format}


def qdrant_filter(flt: Filters | None):
    if flt is None or not flt.active():
        return None
    from qdrant_client import models as m

    must, should_month, should_decade = [], None, None
    if flt.year is not None:
        must += [m.FieldCondition(key="year_from", range=m.Range(lte=flt.year)),
                 m.FieldCondition(key="year_to", range=m.Range(gte=flt.year))]
    for key in ("language", "topic", "kind"):
        if getattr(flt, key):
            must.append(m.FieldCondition(key=key, match=m.MatchValue(value=getattr(flt, key))))
    if flt.source:
        must.append(m.FieldCondition(key="source_group", match=m.MatchValue(value=flt.source)))
    if flt.date_from or flt.date_to:
        must.append(m.FieldCondition(key="effective", range=m.DatetimeRange(gte=flt.date_from, lte=flt.date_to)))
    for key in ("month", "decade"):            # documents without a month / decade stay in
        value = getattr(flt, key)
        if value is not None:
            must.append(m.Filter(should=[m.FieldCondition(key=key, match=m.MatchValue(value=value)),
                                         m.IsNullCondition(is_null=m.PayloadField(key=key)),
                                         m.IsEmptyCondition(is_empty=m.PayloadField(key=key))]))
    return m.Filter(must=must)


@lru_cache(maxsize=1)
def _client():
    import atexit

    from qdrant_client import QdrantClient

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(QDRANT_PATH))
    atexit.register(client.close)          # close the local database before Python shuts down
    return client


def collection_name(chunker: str, model: str) -> str:
    return f"{chunker}__{model}"


def fingerprint(chunks: list[Chunk]) -> str:
    """One id of a list of chunks: changes when any chunk is added, removed or changed."""
    h = hashlib.sha256()
    for c in chunks:
        h.update(f"{c.chunk_id}\n{c.for_embedding()}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def _fingerprint_file(chunker: str, model: str):
    return QDRANT_PATH.parent / "index_fingerprints" / f"{collection_name(chunker, model)}.txt"


def index_is_current(chunker: str, model: str, chunks: list[Chunk] | None = None) -> bool:
    """The collection exists and was built from exactly these chunks (point i = chunk i)."""
    f = _fingerprint_file(chunker, model)
    if not _client().collection_exists(collection_name(chunker, model)) or not f.exists():
        return False
    chunks = chunks if chunks is not None else load_chunks(chunk_file(chunker))
    return f.read_text().strip() == fingerprint(chunks)


def ensure_index(chunker: str, model: str) -> None:
    """Build the index if it is missing or older than the chunks (unchanged chunks come from the cache)."""
    if not index_is_current(chunker, model):
        print(f"  index {collection_name(chunker, model)} is missing or out of date: building...")
        build_index(chunker, model)


def build_index(chunker: str = "structural", model: str = "e5") -> int:
    """(Re)create the Qdrant collection of one chunker x embedding model."""
    from qdrant_client import models as m

    chunks = load_chunks(chunk_file(chunker))
    vectors = Embedder(model).passages([c.for_embedding() for c in chunks])
    client = _client()
    name = collection_name(chunker, model)
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(name, vectors_config=m.VectorParams(size=vectors.shape[1], distance=m.Distance.COSINE))
    points = []
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        p = payload(c)
        p["i"] = i
        points.append(m.PointStruct(id=i, vector=v.tolist(), payload=p))
    for start in range(0, len(points), 256):
        client.upsert(name, points=points[start:start + 256])
    f = _fingerprint_file(chunker, model)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(fingerprint(chunks))           # written last: a broken build stays "out of date"
    return len(points)


# ---------------------------------------------------------------- reranker

RERANK_CACHE = CACHE / "rerank"


class RerankCache:
    """Scores of (question, chunk text) pairs of one reranker, on disk (.cache/rerank/<model>.jsonl).

    The reranker is the slow part on a CPU (~40 s per question with bge); a repeated evaluation reranks
    only the pairs it has not seen. The time each pair took is stored with its score and added back when
    the score comes from the cache, so the reported ms per question stays the time of a real search
    (as the response cache of the models does, agro/common/providers.py)."""

    def __init__(self, key: str) -> None:
        self.path = RERANK_CACHE / f"{key}.jsonl"
        self.scores: dict[str, tuple[float, float]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self.scores[d["k"]] = (d["s"], d["t"])

    @staticmethod
    def key(query: str, text: str) -> str:
        return hashlib.sha256(f"{query}\x00{text}".encode("utf-8")).hexdigest()[:32]

    def add(self, items: list[tuple[str, float, float]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for k, s, t in items:
                self.scores[k] = (s, t)
                f.write(json.dumps({"k": k, "s": s, "t": t}) + "\n")


@lru_cache(maxsize=2)
def _rerank_cache(key: str) -> RerankCache:
    return RerankCache(key)


@lru_cache(maxsize=2)
def _reranker(key: str):
    use_local_model_dirs()
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(RERANKERS[key], cache_dir=str(MODELS_DIR / "fastembed"))


# ---------------------------------------------------------------- search

@dataclass
class Hit:
    chunk: Chunk
    score: float
    ranks: dict = field(default_factory=dict)      # rank (1-based) in each list it came from


def configured() -> dict:
    """The embedding model and reranker chosen by the retrieval evaluation (config.toml, [rag])."""
    import tomllib

    from ..common.settings import ROOT

    with (ROOT / "config.toml").open("rb") as f:
        return tomllib.load(f).get("rag", {})


class Retriever:
    def __init__(self, chunker: str = "structural", model: str | None = None, reranker: str | None = None,
                 bm25_tokens: str | None = None) -> None:
        cfg = configured()
        model = model or cfg.get("embedding", "e5")
        reranker = reranker or cfg.get("reranker", "bge")
        self.chunker, self.model, self.reranker_key = chunker, model, reranker
        self.rerank_top = int(cfg.get("rerank_top", RERANK_TOP))
        self.bm25_weight = float(cfg.get("bm25_weight", 1.0))
        self.fusion = cfg.get("fusion", "rrf")
        self.fusion_alpha = float(cfg.get("fusion_alpha", 0.8))
        self.chunks = load_chunks(chunk_file(chunker))
        self.payloads = [payload(c) for c in self.chunks]
        self.bm25 = BM25(self.chunks, bm25_tokens or cfg.get("bm25_tokens", "lemma"))
        self.embedder = Embedder(model)
        self.collection = collection_name(chunker, model)
        if not index_is_current(chunker, model, self.chunks):
            raise SystemExit(f"index {self.collection} is missing or older than the chunks: run `make rag-index`")

    def vector(self, query: str, k: int, flt: Filters | None) -> list[tuple[int, float]]:
        res = _client().query_points(self.collection, query=self.embedder.query(query).tolist(), limit=k,
                                     query_filter=qdrant_filter(flt), with_payload=["i"]).points
        return [(p.payload["i"], float(p.score)) for p in res]

    def search(self, query: str, k: int = 10, method: str = "hybrid_rerank", flt: Filters | None = None,
               auto_filters: bool = False) -> list[Hit]:
        if auto_filters:
            flt = from_question(query) if flt is None else flt
        if method == "vector":
            return [Hit(self.chunks[i], s, {"vector": r}) for r, (i, s) in enumerate(self.vector(query, k, flt), 1)]
        if method == "vector_rerank":
            hits = [Hit(self.chunks[i], s, {"vector": r})
                    for r, (i, s) in enumerate(self.vector(query, self.rerank_top, flt), 1)]
            self.last_candidates = list(hits)
            return self.rerank(query, hits, k)
        if method == "bm25":
            return [Hit(self.chunks[i], s, {"bm25": r})
                    for r, (i, s) in enumerate(self.bm25.search(query, k, flt, self.payloads), 1)]
        hits = self.fuse(self.vector(query, CANDIDATES, flt), self.bm25.search(query, CANDIDATES, flt, self.payloads))
        if method == "hybrid":
            return hits[:k]
        if method != "hybrid_rerank":
            raise ValueError(method)
        for r, h in enumerate(hits, 1):
            h.ranks["rrf"] = r
        self.last_candidates = hits[:self.rerank_top]     # what the reranker gets (recall before reranking)
        return self.rerank(query, hits[:self.rerank_top], k)

    def fuse(self, vector: list[tuple[int, float]], bm25: list[tuple[int, float]]) -> list[Hit]:
        """One list from the two (see the module docstring: rrf or relative)."""
        if self.fusion not in ("rrf", "relative"):
            raise ValueError(f"fusion: {self.fusion!r}, rrf or relative")
        fused: dict[int, Hit] = {}
        relative = self.fusion == "relative"
        weights = (self.fusion_alpha, 1.0 - self.fusion_alpha) if relative else (1.0, self.bm25_weight)
        for name, weight, results in (("vector", weights[0], vector), ("bm25", weights[1], bm25)):
            if not results:
                continue
            lo, hi = min(s for _, s in results), max(s for _, s in results)
            for r, (i, s) in enumerate(results, 1):
                hit = fused.setdefault(i, Hit(self.chunks[i], 0.0))
                if relative:
                    hit.score += weight * ((s - lo) / (hi - lo) if hi > lo else 1.0)
                else:
                    hit.score += weight / (RRF_K + r)
                hit.ranks[name] = r
        return sorted(fused.values(), key=lambda h: -h.score)

    def rerank(self, query: str, top: list[Hit], k: int) -> list[Hit]:
        """The cross-encoder reads the question with each whole candidate and reorders them
        (scores of pairs seen before come from the cache)."""
        if not top:
            return []
        cache = _rerank_cache(self.reranker_key)
        texts = [h.chunk.for_embedding() for h in top]
        keys = [cache.key(query, t) for t in texts]
        missing = [i for i, key in enumerate(keys) if key not in cache.scores]
        if missing:
            start = time.perf_counter()
            new = list(_reranker(self.reranker_key).rerank(query, [texts[i] for i in missing]))
            per_pair = (time.perf_counter() - start) / len(missing)
            cache.add([(keys[i], float(s), per_pair) for i, s in zip(missing, new)])
        self.cached_seconds = getattr(self, "cached_seconds", 0.0) + sum(
            cache.scores[key][1] for i, key in enumerate(keys) if i not in missing)
        for h, key in zip(top, keys):
            h.score = cache.scores[key][0]
        return sorted(top, key=lambda h: -h.score)[:k]


def run_index(chunkers=("structural",), models=("minilm", "mpnet", "e5")) -> None:
    """Indexes of the structural chunks with every model (the fixed-size baseline is built by the
    retrieval evaluation for the best model only)."""
    for chunker in chunkers:
        for model in models:
            t = time.time()
            n = build_index(chunker, model)
            print(f"  index {collection_name(chunker, model):<22} {n} chunks, {time.time() - t:.0f} s")
    print(f"Indexes in {QDRANT_PATH}")


def print_hits(hits: list[Hit], width: int = 220) -> None:
    for r, h in enumerate(hits, 1):
        c = h.chunk
        where = f"{c.doc_id} | {c.section[:60]}" + (f" | p.{c.page}" if c.page else "")
        print(f"{r:>2}. [{h.score:.3f}] {c.chunk_id}  ({where})  ranks={h.ranks}")
        print("    " + " ".join(c.text.split())[:width])

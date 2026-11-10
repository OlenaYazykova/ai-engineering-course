"""Stage 2, step 2: tokenizer, filters, relevance labels, Qdrant filters (no model downloads)."""

from types import SimpleNamespace

import pytest

from agro.rag.filters import Filters, from_question, year_span
from agro.rag.retrieval_eval import relevant, score_question
from agro.rag.search import qdrant_filter, tokenize


@pytest.fixture(autouse=True)
def rerank_cache_in_tmp(tmp_path, monkeypatch):
    """No test writes into the real cache of reranker scores (.cache/rerank/)."""
    from agro.rag import search

    monkeypatch.setattr(search, "RERANK_CACHE", tmp_path / "rerank")
    search._rerank_cache.cache_clear()
    yield
    search._rerank_cache.cache_clear()


def test_tokenize_lemmas_stems_and_numbers():
    assert tokenize("Запаси вологи 4,22 мм", "stem6") == ["запаси", "вологи", "4.22", "мм"]
    assert tokenize("вологість вологою", "stem6") == ["вологі", "волого"]
    assert tokenize("продуктивної", "none") == ["продуктивної"]
    # lemmas: forms of one word meet, also with the other apostrophe; Latin words are cut to 6 letters
    assert tokenize("вологою вологи", "lemma") == ["волога", "волога"]
    assert tokenize("Одеській областях", "lemma") == ["одеський", "область"]
    assert tokenize("Міжгір'ї Міжгір’я", "lemma") == ["міжгір'я", "міжгір'я"]
    assert tokenize("forecasts 4,22", "lemma") == ["foreca", "4.22"]


def test_weighted_rrf(monkeypatch):
    """A list with a smaller weight moves its chunks down; equal weights give plain RRF."""
    from agro.rag import search

    r = object.__new__(search.Retriever)
    r.chunks = [SimpleNamespace(chunk_id=str(i)) for i in range(4)]
    r.payloads = [{}] * 4
    r.vector = lambda q, k, flt: [(0, .9), (1, .8)]
    r.bm25 = SimpleNamespace(search=lambda q, k, flt, p: [(2, 9.0), (1, 5.0)])
    r.bm25_weight, r.fusion, r.fusion_alpha = 1.0, "rrf", 0.8
    assert [h.chunk.chunk_id for h in r.search("q", k=3, method="hybrid")] == ["1", "0", "2"]
    r.bm25_weight = 0.3
    order = [h.chunk.chunk_id for h in r.search("q", k=3, method="hybrid")]
    assert order[0] == "1" and order.index("0") < order.index("2")


def test_filters_from_the_question():
    f = from_question("Яка урожайність кукурудзи в Одеській області у 2024 році?")
    assert (f.year, f.month, f.decade) == (2024, None, None)
    f = from_question("Запаси вологи у третій декаді липня 2023 року за даними Гідрометцентру")
    assert (f.year, f.month, f.decade, f.source) == (2023, 7, 3, "Ukrhydrometcenter")
    assert from_question("Порівняйте 20 жовтня 2022 і 2023 років").year is None      # two years: no filter
    assert from_question("What may JRC expect for maize in 2025?").month is None      # "may" the verb
    assert from_question("What is the JRC forecast?").source == "JRC"


def test_filter_matches_documents_covering_the_year_and_without_a_month():
    stats = {"year_from": 2019, "year_to": 2025, "month": None, "decade": None, "source_group": "State"}
    bulletin = {"year_from": 2023, "year_to": 2023, "month": 7, "decade": 2, "source_group": "Ukrhydrometcenter"}
    assert year_span("2019-2025") == (2019, 2025) and year_span("2023-07-d1") == (2023, 2023)
    assert Filters(year=2020).matches(stats)
    assert Filters(year=2023, month=7, decade=3).matches(stats)            # no month: kept
    assert not Filters(year=2023, month=7, decade=3).matches(bulletin)     # the neighbouring decade: out
    assert not Filters(source="JRC").matches(bulletin)


def test_qdrant_filter_on_an_in_memory_collection():
    from qdrant_client import QdrantClient, models as m

    client = QdrantClient(":memory:")
    client.create_collection("t", vectors_config=m.VectorParams(size=2, distance=m.Distance.COSINE))
    docs = [
        {"i": 0, "year_from": 2023, "year_to": 2023, "month": 7, "decade": 3, "source_group": "Ukrhydrometcenter"},
        {"i": 1, "year_from": 2023, "year_to": 2023, "month": 7, "decade": 2, "source_group": "Ukrhydrometcenter"},
        {"i": 2, "year_from": 2019, "year_to": 2025, "month": None, "decade": None, "source_group": "State"},
        {"i": 3, "year_from": 2022, "year_to": 2022, "month": 7, "decade": 3, "source_group": "Ukrhydrometcenter"},
    ]
    client.upsert("t", points=[m.PointStruct(id=d["i"], vector=[1.0, 0.1 * d["i"]], payload=d) for d in docs])
    hits = client.query_points("t", query=[1.0, 0.0], limit=10,
                               query_filter=qdrant_filter(Filters(year=2023, month=7, decade=3))).points
    assert sorted(p.payload["i"] for p in hits) == [0, 2]
    hits = client.query_points("t", query=[1.0, 0.0], limit=10, query_filter=qdrant_filter(Filters(source="State"))).points
    assert [p.payload["i"] for p in hits] == [2]
    assert qdrant_filter(Filters()) is None


def test_relevance_by_document_and_evidence_phrase():
    chunk = SimpleNamespace(doc_id="d", text="Станом на 31 липня запаси   продуктивної вологи у метровому шарі", chunk_id="d#1")
    src = {"doc_id": "d", "evidence": "запаси продуктивної вологи"}
    assert relevant(chunk, src)
    assert not relevant(chunk, {"doc_id": "other", "evidence": "запаси продуктивної вологи"})
    long = {"doc_id": "d", "evidence": "Станом на 31 липня запаси продуктивної вологи у метровому шарі ґрунту під кукурудзою"}
    assert relevant(chunk, long)                       # half of a long phrase: cut by a chunk border
    hits = [SimpleNamespace(chunk=SimpleNamespace(doc_id="x", text="", chunk_id="x#0")), SimpleNamespace(chunk=chunk)]
    s = score_question(hits, {"id": "q", "kind": "exact", "sources": [src]})
    assert s["first_rank"] == 2 and s["recall"][1] == 0 and s["recall"][3] == 1


def test_reranker_gets_top_n_whole_candidates(monkeypatch):
    """vector_rerank: the top `rerank_top` vector results, given to the reranker whole, reordered."""
    from agro.rag import search

    seen = []

    class FakeReranker:
        def rerank(self, query, texts):
            seen.extend(texts)
            return [len(t) for t in texts]          # the longest candidate wins

    monkeypatch.setattr(search, "_reranker", lambda key: FakeReranker())
    chunks = [SimpleNamespace(for_embedding=lambda i=i: "x" * (i + 1)) for i in range(30)]
    r = object.__new__(search.Retriever)
    r.chunks, r.reranker_key, r.rerank_top = chunks, "bge", 10
    r.vector = lambda q, k, flt: [(i, 1.0 - i / 100) for i in range(k)]
    hits = r.search("q", k=3, method="vector_rerank")
    assert seen == ["x" * (i + 1) for i in range(10)]            # 10 candidates, not cut
    assert [h.chunk for h in hits] == [chunks[9], chunks[8], chunks[7]]


def test_index_fingerprint_changes_with_the_chunks():
    """An index built from other chunks is out of date (point i must be chunk i)."""
    from agro.rag.search import fingerprint

    a = [SimpleNamespace(chunk_id=f"d#{i}", for_embedding=lambda i=i: f"text {i}") for i in range(3)]
    changed = a[:2] + [SimpleNamespace(chunk_id="d#2", for_embedding=lambda: "text 2, masked")]
    assert fingerprint(a) == fingerprint(list(a))
    assert fingerprint(a) != fingerprint(a[:2]) and fingerprint(a) != fingerprint(changed)


def test_recall_before_the_reranker():
    """The candidates the reranker got are scored too: a source lost before reranking is visible."""
    from agro.rag.retrieval_eval import evaluate

    good = SimpleNamespace(doc_id="d", text="запаси вологи 80 мм", chunk_id="d#1")
    bad = SimpleNamespace(doc_id="x", text="інше", chunk_id="x#1")

    class R:
        def search(self, question, k, method, auto_filters):
            self.last_candidates = [SimpleNamespace(chunk=bad), SimpleNamespace(chunk=good)]
            return [SimpleNamespace(chunk=bad)]          # the reranker dropped the good one

    q = {"id": "q", "kind": "exact", "question": "?", "sources": [{"doc_id": "d", "evidence": "вологи 80 мм"}]}
    m = evaluate(R(), [q], "hybrid_rerank")
    assert m["recall@5"] == 0.0 and m["recall_before_rerank"] == 1.0
    assert "recall_before_rerank" not in evaluate(R(), [q], "vector")


def test_reranker_scores_are_cached_with_their_time(tmp_path, monkeypatch):
    from agro.rag import search

    calls = []

    class Model:
        def rerank(self, query, texts):
            calls.append(len(texts))
            return [float(len(t)) for t in texts]

    monkeypatch.setattr(search, "_reranker", lambda key: Model())
    r = object.__new__(search.Retriever)
    r.reranker_key = "bge"
    hits = lambda n: [search.Hit(SimpleNamespace(for_embedding=lambda i=i: "x" * (i + 1)), 0.0) for i in range(n)]
    first = [len(h.chunk.for_embedding()) for h in r.rerank("q", hits(3), 3)]
    r.cached_seconds = 0.0
    again = [len(h.chunk.for_embedding()) for h in r.rerank("q", hits(4), 4)]   # 3 pairs known, 1 new
    assert first == [3, 2, 1] and again == [4, 3, 2, 1]
    assert calls == [3, 1] and r.cached_seconds >= 0.0
    search._rerank_cache.cache_clear()
    assert len(search.RerankCache("bge").scores) == 4                             # kept on disk


def test_relative_fusion_keeps_a_confident_vector_hit_first():
    """RRF: a chunk 10th in both lists outvotes the 1st of the vector list; relative score fusion does not."""
    from agro.rag import search

    r = object.__new__(search.Retriever)
    r.chunks = [SimpleNamespace(chunk_id=str(i)) for i in range(40)]
    vector = [(0, 0.90)] + [(i, 0.80 - 0.005 * i) for i in range(1, 30)]        # chunk 0: clearly the best
    bm25 = [(i, 12.0 - 0.3 * i) for i in range(10, 40)]                          # BM25 does not know chunk 0
    r.bm25_weight, r.fusion, r.fusion_alpha = 1.0, "rrf", 0.8
    assert r.fuse(vector, bm25)[0].chunk.chunk_id != "0"
    r.fusion = "relative"
    fused = r.fuse(vector, bm25)
    assert fused[0].chunk.chunk_id == "0" and fused[0].ranks == {"vector": 1}
    r.fusion = "other"
    with pytest.raises(ValueError):
        r.fuse(vector, bm25)

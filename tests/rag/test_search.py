"""Stage 2, step 2: tokenizer, filters, relevance labels, Qdrant filters (no model downloads)."""

from types import SimpleNamespace

from agro.rag.filters import Filters, from_question, year_span
from agro.rag.retrieval_eval import relevant, score_question
from agro.rag.search import qdrant_filter, tokenize


def test_tokenize_stems_words_and_keeps_numbers():
    assert tokenize("Запаси вологи 4,22 мм") == ["запаси", "вологи", "4.22", "мм"]
    assert tokenize("вологість вологою") == ["вологі", "волого"]
    assert tokenize("продуктивної", stem=None) == ["продуктивної"]


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

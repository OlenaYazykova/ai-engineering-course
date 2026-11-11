"""Stage 2, step 1: ingestion never deletes the corpus in git when the originals are not downloaded."""

from types import SimpleNamespace

import pytest

from agro.corpus import ingest


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    text = tmp_path / "text"
    text.mkdir()
    (text / "a.md").write_text("cleaned document a")
    monkeypatch.setattr(ingest, "TEXT_DIR", text)
    return tmp_path


def docs(tmp_path, present):
    out = []
    for doc_id in ("a", "b"):
        raw = tmp_path / "raw" / f"{doc_id}.pdf"
        if doc_id in present:
            raw.parent.mkdir(exist_ok=True)
            raw.write_bytes(b"%PDF")
        out.append(SimpleNamespace(doc_id=doc_id, raw_path=raw))
    return out


def test_no_originals_keep_the_corpus(corpus, monkeypatch, capsys):
    monkeypatch.setattr(ingest, "load_registry", lambda: docs(corpus, present=()))
    ingest.run()
    assert (corpus / "text" / "a.md").read_text() == "cleaned document a"
    assert "kept as it is (1 documents" in capsys.readouterr().out


def test_some_originals_missing_stop_and_change_nothing(corpus, monkeypatch):
    monkeypatch.setattr(ingest, "load_registry", lambda: docs(corpus, present=("a",)))
    with pytest.raises(SystemExit, match="1 of 2 originals are missing \\(b\\)"):
        ingest.run()
    assert (corpus / "text" / "a.md").exists()

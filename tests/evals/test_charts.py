"""Stage 2: the charts of REPORT.md are drawn from result files (synthetic ones here)."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("seaborn")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reports"))

import charts_hw2 as ch  # noqa: E402


def test_charts(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "OUT", tmp_path / "out")
    ch.style()
    retrieval = {k: {"MRR": 0.1 * i} for i, (k, _) in enumerate(ch.RETRIEVAL, 1)}
    retrieval |= {f"F hybrid | bm25 lemma, rrf, bm25 weight {w} | e5": {"MRR": 0.5 - w / 10} for w in ch.WEIGHTS}
    (tmp_path / "r.json").write_text(json.dumps(retrieval))
    data = ch.retrieval_data(tmp_path / "r.json")
    assert data[-1][2] and len(data) == len(ch.RETRIEVAL)                 # the final configuration is marked
    ch.chart_retrieval(data)
    ch.chart_fusion(ch.fusion_data(tmp_path / "r.json"))
    (tmp_path / "testset.jsonl").write_text("\n".join(json.dumps(q) for q in [
        {"id": "d01", "key_facts": ["40"], "sources": [{"doc_id": "a"}], "match": "all"},
        {"id": "d17", "key_facts": [], "sources": []}]))
    (tmp_path / "answers_dev_v1.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"k": 5, "id": "d01", "outcome": "answer", "text": "Було 40 [1].", "citations": [{"doc_id": "a"}]},
        {"k": 5, "id": "d17", "outcome": "refused_model", "text": "-", "citations": []}]))
    prompts = ch.prompt_data(tmp_path, tmp_path / "testset.jsonl")
    assert list(prompts["v1"].values()) == [1.0, 1.0, 1.0]
    ch.chart_prompts(prompts)
    m = {k: {"mean": 0.8} for k, _ in ch.DEV_TEST}
    for split in ("dev", "test"):
        (tmp_path / f"{split}.json").write_text(json.dumps({"metrics": m}))
    ch.chart_dev_test(ch.dev_test_data(tmp_path))
    (tmp_path / "judge.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"human_correct": True, "correct": True, "human_grounded": False, "grounded": True}]))
    cal = ch.calibration_data(tmp_path / "judge.jsonl")
    assert cal == {"correct": [[1, 0], [0, 0]], "grounded": [[0, 0], [1, 0]]}
    ch.chart_calibration(cal)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "calibration.png", "dev_test.png", "fusion.png", "prompts.png", "retrieval.png"]

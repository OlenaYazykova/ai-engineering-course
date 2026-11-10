"""Stage 2, step 4: the gate of CI fails a run below its thresholds (no network, no models)."""

import json

import pytest

from evals import gate

CONFIG = {"model": "m", "prompt": "v3", "k": 5, "threshold": 0.3, "context_tokens": 3000, "judge": "j",
          "judge_prompt": "v1"}
BASE = {"pass": 0.87, "judge_correct": 0.84, "correct": 0.84, "judge_grounded": 1.0, "abstained_no_answer": 1.0,
        "unsupported_numbers": 0, "recall@5": 0.87, "hit@5": 0.89, "MRR": 0.808}


def result(**changes) -> dict:
    metrics = {m: {"mean": v, "min": v, "max": v} for m, v in (BASE | changes).items()}
    return {"questions": 23, "repeats": 1, "config": CONFIG, "metrics": metrics}


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "RESULTS", tmp_path)
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "baseline.json")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    for s in gate.SPLITS:
        (tmp_path / f"{s}.json").write_text(json.dumps(result()))
    gate.make_baseline()
    return tmp_path


def write(files, split, **changes):
    (files / f"{split}.json").write_text(json.dumps(result(**changes)))


def test_same_numbers_pass(files):
    assert gate.run_gate()


def test_a_drop_within_the_tolerance_passes(files):
    write(files, "test", **{"pass": 0.78, "MRR": 0.77, "abstained_no_answer": 0.75})   # 0.87-0.10, 0.808-0.05
    assert gate.run_gate()


@pytest.mark.parametrize("changes", [
    {"pass": 0.76},                       # more than 0.10 below the baseline
    {"judge_grounded": 0.85},
    {"abstained_no_answer": 0.5},         # two of the four questions without an answer got an answer
    {"unsupported_numbers": 1},           # an unsupported number reached a final answer
    {"recall@5": 0.80},                   # the search broke
])
def test_below_a_threshold_fails(files, changes):
    write(files, "dev", **changes)
    with pytest.raises(SystemExit) as e:
        gate.run_gate()
    assert e.value.code == 1


def test_missing_results_fail(files):
    (files / "test.json").unlink()
    with pytest.raises(SystemExit, match="missing"):
        gate.run_gate()

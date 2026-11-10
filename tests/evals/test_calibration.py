"""Stage 2, step 4: the table of manual labels for the calibration of the judge (no network, no models)."""

import json
from types import SimpleNamespace

import pytest

from evals import calibration as cal

Q = [{"id": "d01", "question": "Q1?", "expected_answer": "40", "key_facts": ["40"]},
     {"id": "d02", "question": "Q2?", "expected_answer": "22", "key_facts": ["22"]}]


def run(version, k, qid, text, outcome="answer"):
    return {"k": k, "id": qid, "question": qid, "outcome": outcome, "text": text, "context": [f"{qid}#1"],
            "citations": [{"chunk_id": f"{qid}#1", "n": 1}]}


@pytest.fixture
def files(tmp_path, monkeypatch):
    v1, v2 = tmp_path / "v1.jsonl", tmp_path / "v2.jsonl"
    v2.write_text("\n".join(json.dumps(r) for r in [
        run("v2", 5, "d01", "Було 40 [1]."), run("v2", 5, "d02", "-", "refused_model"),
        run("v2", 3, "d01", "Було 41 [1]."), run("v2", 10, "d01", "Було 40 [1].")]), encoding="utf-8")
    v1.write_text("\n".join(json.dumps(r) for r in [
        run("v1", 5, "d01", "Було 39 [1]."), run("v1", 5, "d02", "Було 22 [1].")]), encoding="utf-8")
    monkeypatch.setattr(cal, "RUNS", (("v2", v2), ("v1", v1)))
    monkeypatch.setattr(cal, "load", lambda split: Q)
    monkeypatch.setattr(cal, "load_chunks", lambda: [SimpleNamespace(chunk_id=f"d0{i}#1", header="H", text="T")
                                                     for i in (1, 2)])
    monkeypatch.setattr(cal, "CALIBRATION", tmp_path)
    monkeypatch.setattr(cal, "TO_LABEL", tmp_path / "to_label.xlsx")
    monkeypatch.setattr(cal, "SELECTION", tmp_path / "selection.jsonl")
    monkeypatch.setattr(cal, "LABELS", tmp_path / "labels.jsonl")
    monkeypatch.setattr(cal, "ROOT", tmp_path)
    return tmp_path


def test_select_system_answers_and_one_wrong_per_question(files):
    chosen = {(r["id"], r["text"]) for r in cal.select()}
    # the system (v2, k=5) answer of d01; one wrong answer of d01 (41 or 39); d02 of the system is a refusal,
    # d02 of v1 is right by the key facts, so it is not taken; "Було 40" of k=10 repeats the system answer
    assert ("d01", "Було 40 [1].") in chosen and len(chosen) == 2
    assert not any(qid == "d02" for qid, _ in chosen)


def test_dump_and_load(files):
    from openpyxl import load_workbook

    cal.dump()
    wb = load_workbook(files / "to_label.xlsx")
    ws = wb["label"]
    assert [c.value for c in ws[1]][:4] == ["label_id", "question", "expected answer", "answer"]
    assert "prompt" not in [c.value for c in ws[1]]                 # blind: no version, no verdict
    ws["G2"], ws["H2"], ws["G3"], ws["H3"] = 1, 1, 0, 1
    wb.save(files / "to_label.xlsx")
    cal.load_labels()
    labels = [json.loads(line) for line in (files / "labels.jsonl").open()]
    assert [(r["correct"], r["grounded"]) for r in labels] == [(True, True), (False, True)]
    with pytest.raises(SystemExit):
        cal.dump()                                                    # never overwrites a table with labels


def test_load_refuses_empty_labels(files):
    cal.dump()
    with pytest.raises(SystemExit, match="must be 1 or 0"):
        cal.load_labels()


# ---------------------------------------------------------------- the judge

class FakeJudgeModel:
    def __init__(self, verdicts):
        from agro.common.providers import Provider
        self.p = Provider({"model": "fake-judge", "price_in": 0.1, "price_out": 0.4})
        self.verdicts, self.calls = list(verdicts), []
        self.cfg, self.model = self.p.cfg, "fake-judge"

    def complete(self, messages, schema, sampling, max_tokens):
        from agro.common.providers import Completion
        assert schema["required"][-1] == "grounded"
        self.calls.append(messages)
        c, g = self.verdicts.pop(0)
        body = {"correct_reason": "r", "correct": c, "unsupported_statements": [] if g else ["x"],
                "grounded_reason": "g", "grounded": g}
        return Completion("```json\n" + json.dumps(body) + "\n```", 1000, 100, "stop")

    def cost_usd(self, c):
        return self.p.cost_usd(c)


JCFG = {"judge_model": "fake", "judge_prompt": "v1", "judge_sampling": "t0", "judge_max_tokens": 1200,
        "judge_cache": False, "model_cfg": {"model": "fake-judge"}, "sampling_cfg": {"temperature": 0.0, "top_p": 1.0}}


def test_judge_message_and_verdict():
    from evals.judge import Judge, chunks_for

    model = FakeJudgeModel([(True, False)])
    j = Judge(provider=model, cfg=JCFG)
    chunks = chunks_for(["a#1", "b#2"], ["b#2"], {"a#1": SimpleNamespace(header="H1", text="T1"),
                                                   "b#2": SimpleNamespace(header="H2", text="T2")})
    v = j.judge("Q?", "40", "Було 40 [2].", chunks)
    assert v.correct and not v.grounded and v.unsupported_statements == ["x"]
    user = model.calls[0][1]["content"]
    assert '<chunk n="1">\nH1\nT1' in user and '<chunk n="2" cited>\nH2\nT2' in user and "<expected_answer>40" in user


def test_agreement():
    a = cal.agreement([(True, True), (True, False), (False, True), (False, False)])
    assert a["agree"] == 2 and a["false_pass"] == 1 and a["false_fail"] == 1 and a["kappa"] == 0.0
    assert cal.agreement([(True, True), (False, False)])["kappa"] == 1.0


def test_calibrate(files, monkeypatch):
    import evals.judge as judge_mod
    from openpyxl import load_workbook

    cal.dump()
    wb = load_workbook(files / "to_label.xlsx")
    ws = wb["label"]
    ws["G2"], ws["H2"], ws["G3"], ws["H3"] = 1, 1, 0, 1
    wb.save(files / "to_label.xlsx")
    cal.load_labels()
    monkeypatch.setattr(cal, "AGREEMENT", files / "agreement.md")
    model = FakeJudgeModel([(True, True), (True, True)])
    monkeypatch.setattr(judge_mod, "settings", lambda: JCFG)
    monkeypatch.setattr(judge_mod, "make_provider", lambda cfg: model)
    result = cal.calibrate()
    assert result["correct"]["false_pass"] == 1 and result["grounded"]["agreement"] == 1.0
    assert "false pass" in (files / "agreement.md").read_text() and (files / "judge_v1.jsonl").exists()

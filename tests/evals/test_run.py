"""Stage 2, step 4: the eval run with a fake search, a fake model and a fake judge (no network, no models)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))

from test_answer import CFG, FakeModel, chunk  # noqa: E402

from agro.common.providers import Completion  # noqa: E402
from agro.rag.search import Hit  # noqa: E402
from evals import run as run_mod  # noqa: E402
from test_calibration import JCFG, FakeJudgeModel  # noqa: E402

QUESTIONS = [
    {"id": "d01", "kind": "exact", "language": "uk", "question": "Температура?", "expected_answer": "+40 °С",
     "key_facts": ["40"], "match": "all", "sources": [{"doc_id": "b", "evidence": "У Миколаєві +40 °С."}]},
    {"id": "d17", "kind": "no_answer", "language": "uk", "question": "Ціни?", "expected_answer": "Немає",
     "key_facts": [], "match": "all", "sources": []},
]


class Model(FakeModel):
    def __init__(self):
        super().__init__([])

    def complete(self, messages, schema, sampling, max_tokens):
        user = messages[1]["content"]
        text = "У Миколаєві +40 °С [1]." if "Температура" in user else "НЕМАЄ_ВІДПОВІДІ"
        return Completion(text, 1000, 50, "stop")


def test_run(tmp_path, monkeypatch):
    import agro.rag.answer as answer_mod
    import evals.judge as judge_mod

    monkeypatch.setattr(answer_mod, "count_tokens", lambda text: len(text.split()))   # no tokenizer download

    hits = {"Температура?": [Hit(chunk(1, "b", "У Миколаєві +40 °С."), 3.0)],
            "Ціни?": [Hit(chunk(1, "z", "Інше."), 1.0)]}

    class A(run_mod.Answerer):
        def __init__(self, cfg=None):
            super().__init__(provider=Model(), cfg=CFG | {"cache": (cfg or {}).get("cache", True)})

        def retrieve(self, question):
            return hits[question], 0.1

    monkeypatch.setattr(run_mod, "Answerer", A)
    monkeypatch.setattr(run_mod, "settings", lambda: CFG)
    monkeypatch.setattr(run_mod, "load", lambda split: QUESTIONS)
    monkeypatch.setattr(run_mod, "load_chunks", lambda: [])
    monkeypatch.setattr(run_mod, "RESULTS", tmp_path)
    monkeypatch.setattr(judge_mod, "settings", lambda: JCFG)
    monkeypatch.setattr(judge_mod, "make_provider", lambda cfg: FakeJudgeModel([(True, True)] * 2))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    [res] = run_mod.run("dev", repeats=2)
    m = res["metrics"]
    assert res["pass@1"] == 1.0 and m["abstained_no_answer"]["mean"] == 1.0 and m["judge_grounded"]["mean"] == 1.0
    assert m["recall@5"]["mean"] == 1.0 and res["unstable"] == []
    summary = json.loads((tmp_path / "dev.json").read_text())
    assert "rows" not in summary and summary["repeats"] == 2
    assert len((tmp_path / "dev.jsonl").read_text().splitlines()) == 4          # 2 questions x 2 runs
    assert "pass@1" in (tmp_path / "dev.md").read_text()

"""Offline tests: schema rules, scoring and the run loop with a fake provider (no network)."""

import json

import pytest
from pydantic import ValidationError

from agro_extract import metrics, run
from agro_extract.providers import CachedProvider, Completion, Provider, ProviderError
from agro_extract.schema import AgroReport, json_schema

TEXT = ("Агрометеорологічний бюлетень по території України за першу декаду липня 2021 р. "
        "Запаси продуктивної вологи в орному шарі становили 11-20 мм, в Одеській області менше 10 мм. "
        "Озима пшениця у фазі воскової стиглості, стан задовільний. Wheat 26.88 Mt.")

GOOD = {
    "year": 2021, "month": 7, "decade": 1,
    "soil_moisture": {"status": "deficit", "layer": "0-20cm", "min_mm": 10, "max_mm": 20,
                      "deficit_oblasts": ["odesa"]},
    "crops": [{"crop": "winter_wheat", "bbch_stage": 8, "condition": "satisfactory"}],
    "hazards": ["drought"],
    "yield_outlook": [{"crop": "winter_wheat", "vs_5yr_average": "not_stated", "production_mt": 26.88}],
}


def parse(d, text=TEXT):
    return AgroReport.model_validate_json(json.dumps(d), context={"text": text})


# ---------- schema ----------

def test_valid_record():
    assert parse(GOOD).soil_moisture.deficit_oblasts == ["odesa"]


@pytest.mark.parametrize("path,value,message", [
    (("soil_moisture", "min_mm"), 30, "larger than max_mm"),
    (("soil_moisture", "max_mm"), 99, "not written in the text"),
    (("month",), 13, "must be 1-12"),
    (("decade",), 4, "must be 1-3"),
])
def test_validators(path, value, message):
    d = json.loads(json.dumps(GOOD))
    target = d
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError, match=message):
        parse(d)


def test_bbch_range_and_duplicates():
    d = json.loads(json.dumps(GOOD))
    d["crops"] = [{"crop": "maize", "bbch_stage": 12, "condition": "good"},
                  {"crop": "maize", "bbch_stage": 1, "condition": "good"}]
    with pytest.raises(ValidationError) as e:
        parse(d)
    assert "0-9" in str(e.value) and "once" in str(e.value)


def test_unknown_enum_and_extra_keys_rejected():
    d = json.loads(json.dumps(GOOD))
    d["hazards"] = ["tornado"]
    with pytest.raises(ValidationError):
        parse(d)
    d = json.loads(json.dumps(GOOD))
    d["comment"] = "extra"
    with pytest.raises(ValidationError):
        parse(d)


def test_schema_is_strict_compatible():
    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "object":
                assert o.get("additionalProperties") is False
                assert set(o["properties"]) == set(o["required"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json_schema())


# ---------- scoring ----------

def test_score_identical_and_order_free():
    gold = metrics.flatten(GOOD)
    pred = json.loads(json.dumps(GOOD))
    pred["soil_moisture"]["deficit_oblasts"] = ["odesa"]
    pred["hazards"] = ["drought"]
    s = metrics.score(metrics.flatten(pred), gold)
    assert s["correct"] == len(metrics.FIELDS) and s["hallucinated"] == 0


def test_score_hallucination_and_failed():
    gold_rec = json.loads(json.dumps(GOOD))
    gold_rec["hazards"] = []
    gold = metrics.flatten(gold_rec)
    s = metrics.score(metrics.flatten(GOOD), gold)          # model added "drought"
    assert s["hallucinated"] == 1 and ("hazards", frozenset(), frozenset({"drought"})) in s["wrong"]
    failed = metrics.score(None, gold)                      # no valid answer: every field wrong
    assert failed["correct"] == 0 and failed["hallucinated"] == 0


def test_percentile():
    assert metrics.percentile([1, 2, 3, 4, 100], 50) == 3
    assert metrics.percentile([1, 2, 3, 4, 100], 95) == 100


# ---------- run loop ----------

class FakeProvider(Provider):
    def __init__(self, answers):
        super().__init__({"model": "fake", "price_in": 1.0, "price_out": 2.0})
        self.answers = list(answers)

    def complete(self, messages, schema, sampling, max_tokens):
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        if isinstance(a, Completion):
            return a
        return Completion(content=a, input_tokens=100, output_tokens=50, finish_reason="stop")


SAMPLING = {"temperature": 0.0, "top_p": 1.0}
MSGS = run.build_messages("system", TEXT)


def test_ok():
    r = run.extract_one(FakeProvider([json.dumps(GOOD)]), MSGS, TEXT, SAMPLING, 100)
    assert r["status"] == "ok" and r["attempts"] == 1 and r["cost_usd"] == pytest.approx(200 / 1e6)


def test_fixed_after_one_correction():
    bad = json.dumps({**GOOD, "month": 13})
    r = run.extract_one(FakeProvider([bad, json.dumps(GOOD)]), MSGS, TEXT, SAMPLING, 100)
    assert r["status"] == "fixed" and r["attempts"] == 2 and r["raw"] == bad


def test_failed_after_correction():
    r = run.extract_one(FakeProvider(["not json", "still not json"]), MSGS, TEXT, SAMPLING, 100)
    assert r["status"] == "failed" and r["attempts"] == 2 and "invalid after correction" in r["error"]


def test_provider_error_and_cut_answer():
    r = run.extract_one(FakeProvider([ProviderError("timeout")]), MSGS, TEXT, SAMPLING, 100)
    assert r["status"] == "failed" and "provider" in r["error"]
    cut = Completion(content='{"year": 20', input_tokens=10, output_tokens=100, finish_reason="length")
    r = run.extract_one(FakeProvider([cut]), MSGS, TEXT, SAMPLING, 100)
    assert r["status"] == "failed" and "max_tokens" in r["error"]


def test_run_experiment_logs_everything(tmp_path, monkeypatch):
    texts = tmp_path / "texts"
    texts.mkdir()
    (texts / "uk_hydromet_2021-07-d1__moisture.txt").write_text(TEXT, encoding="utf-8")
    monkeypatch.setattr(run, "TEXTS", texts)
    monkeypatch.setattr(run, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(run, "CACHE", tmp_path / "cache")
    cfg = {"models": {"fake": {"model": "fake", "provider": "x"}},
           "sampling": {"t0": SAMPLING}, "run": {"max_tokens": 100}}
    out = run.run_experiment("fake", "v1", "t0", config=cfg, provider=FakeProvider([json.dumps(GOOD)]))
    row = json.loads(out.read_text(encoding="utf-8"))
    for key in ("model", "prompt_version", "prompt_hash", "temperature", "top_p", "status", "seconds", "cost_usd"):
        assert key in row
    assert row["source"] == "hydromet" and row["status"] == "ok" and out.name == "fake__v1__t0.jsonl"


# ---------- cache ----------

class CountingProvider(FakeProvider):
    def __init__(self, answers):
        super().__init__(answers)
        self.calls = 0

    def complete(self, messages, schema, sampling, max_tokens):
        self.calls += 1
        return super().complete(messages, schema, sampling, max_tokens)


def test_cache_replays_same_request_and_keeps_latency(tmp_path):
    inner = CountingProvider([json.dumps(GOOD)])
    cached = CachedProvider(inner, tmp_path)
    first = run.extract_one(cached, MSGS, TEXT, SAMPLING, 100)
    second = run.extract_one(cached, MSGS, TEXT, SAMPLING, 100)   # same request: no second call
    assert inner.calls == 1 and cached.hits == 1
    assert first["parsed"] == second["parsed"] and second["cached"] and not first["cached"]
    assert second["seconds"] == pytest.approx(first["seconds"], abs=0.05)
    assert second["cost_usd"] == first["cost_usd"]


def test_cache_key_changes_with_prompt(tmp_path):
    inner = CountingProvider([json.dumps(GOOD), json.dumps(GOOD)])
    cached = CachedProvider(inner, tmp_path)
    run.extract_one(cached, MSGS, TEXT, SAMPLING, 100)
    run.extract_one(cached, run.build_messages("other prompt", TEXT), TEXT, SAMPLING, 100)
    assert inner.calls == 2 and cached.hits == 0


def test_json_object_fallback():
    from agro_extract.providers import OpenAICompatibleProvider
    p = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    p.cfg = {"response_format": "json_object"}
    assert p._response_format({}) == {"type": "json_object"}
    p.cfg = {}
    assert p._response_format({"x": 1})["json_schema"]["strict"] is True

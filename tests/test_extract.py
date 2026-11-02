"""Offline tests: schema rules, scoring and the run loop with a fake provider (no network)."""

import json

import pytest
from pydantic import ValidationError

from agro_extract import metrics, run
from agro_extract.providers import CachedProvider, Completion, Provider, ProviderError
from agro_extract.schema import AgroReport, json_schema

TEXT = ("Агрометеорологічний бюлетень по території України за першу декаду липня 2021 р. "
        "Запаси продуктивної вологи в орному шарі були недостатніми: 11-20 мм, в Одеській області менше 10 мм. "
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


# ---------- deterministic checks (agro_extract/checks.py) ----------

from agro_extract.checks import clean_lists, number_with_unit  # noqa: E402

HYDRO = ("Агрометеорологічний бюлетень по території України за третю декаду липня 2023 р.\n"
         "Станом на 20 липня запаси продуктивної вологи під кукурудзою 101-120 мм, на окремих площах "
         "Волинської, Кіровогр адської та Одеської областей недостатні (менше 8 0 мм). "
         "Відмічалося перезволоження ґрунту.")


def test_number_must_stand_next_to_its_unit():
    assert number_with_unit(HYDRO, 101, r"мм", 30)
    assert number_with_unit(HYDRO, 80, r"мм", 30)          # "8 0 мм": number split by PDF
    assert not number_with_unit(HYDRO, 20, r"мм", 30)      # "20 липня" is a date, not mm
    assert number_with_unit("26.88 Mt of wheat", 26.88, r"^\s*mt\b", 12)


def _rec(**kw):
    d = json.loads(json.dumps(GOOD))
    d.update(kw)
    return d


def test_mm_value_from_a_date_is_rejected():
    d = _rec(year=2023, month=7, decade=3, yield_outlook=[], hazards=[], crops=[])
    d["soil_moisture"].update(min_mm=20, max_mm=120, deficit_oblasts=[])
    with pytest.raises(ValidationError, match="min_mm=20 is not written in the text as a value in mm"):
        parse(d, HYDRO)


def test_year_month_decade_are_reset_without_support():
    base = {"year": 2022, "month": 8, "decade": 1, "soil_moisture": {"deficit_oblasts": [], "layer": "0-100cm",
            "status": "deficit", "min_mm": 80, "max_mm": 120}, "crops": [], "yield_outlook": [], "hazards": []}
    clean, removed = clean_lists(base, HYDRO)       # HYDRO: третю декаду липня 2023
    assert (clean["year"], clean["month"], clean["decade"]) == (None, None, None)
    assert {"year:2022", "month:8", "decade:1"} <= set(removed)


def test_unsupported_list_items_are_removed():
    rec = {
        "year": 2023, "month": 7, "decade": 3,
        "soil_moisture": {"status": "deficit", "layer": "0-100cm", "min_mm": 80, "max_mm": 120,
                          "deficit_oblasts": ["volyn", "kirovohrad", "odesa", "kherson", "lviv"]},
        "crops": [{"crop": "maize", "bbch_stage": None, "condition": "not_stated"},
                  {"crop": "soybean", "bbch_stage": None, "condition": "good"}],
        "hazards": ["waterlogging", "drought", "hail"],
        "yield_outlook": [{"crop": "winter_wheat", "vs_5yr_average": "near", "production_mt": None}],
    }
    clean, removed = clean_lists(rec, HYDRO)
    assert clean["soil_moisture"]["deficit_oblasts"] == ["volyn", "kirovohrad", "odesa"]   # split name found
    assert clean["crops"] == []      # maize has neither a stage nor a condition, soybean is not in the text
    assert clean["hazards"] == ["waterlogging"]
    assert clean["yield_outlook"] == []
    assert set(removed) == {"deficit_oblasts:kherson", "deficit_oblasts:lviv", "crops:soybean",
                            "crops:maize (no stage, no condition)",
                            "hazards:drought", "hazards:hail", "yield_outlook:winter_wheat"}


def test_hazard_keywords_do_not_match_inside_other_words():
    text = "Kirovohrad oblast, Кіровоградської області, warmer weather, wheat"
    clean, removed = clean_lists({"soil_moisture": {"deficit_oblasts": []}, "crops": [],
                                  "yield_outlook": [], "hazards": ["hail", "hostilities", "heat"]}, text)
    assert clean["hazards"] == [] and len(removed) == 3


def test_run_logs_removed_items():
    d = json.loads(json.dumps(GOOD))
    d["soil_moisture"]["deficit_oblasts"] = ["odesa", "lviv"]   # lviv is not in TEXT
    r = run.extract_one(FakeProvider([json.dumps(d)]), MSGS, TEXT, SAMPLING, 100)
    # TEXT names neither Lviv nor any drought word: both items are removed, the answer stays valid
    assert r["status"] == "ok" and r["removed"] == ["deficit_oblasts:lviv", "hazards:drought"]
    assert r["parsed"]["soil_moisture"]["deficit_oblasts"] == ["odesa"]


def test_layer_and_status_are_checked_against_the_text():
    sm = {"deficit_oblasts": [], "layer": "0-20cm", "status": "excess", "min_mm": None, "max_mm": None}
    rec = {"soil_moisture": sm, "crops": [], "yield_outlook": [], "hazards": []}
    clean, removed = clean_lists(rec, "Запаси в метровому шарі недостатні.")
    assert clean["soil_moisture"]["layer"] == "0-100cm" and clean["soil_moisture"]["status"] == "not_stated"
    rec["soil_moisture"] = {**sm, "status": "mixed"}
    clean, _ = clean_lists(rec, "Оптимальні запаси в орному шарі.")
    assert clean["soil_moisture"]["status"] == "not_stated"
    # mm values without a layer stay strict
    d = _rec(year=2023, month=7, decade=3, yield_outlook=[], hazards=[], crops=[])
    d["soil_moisture"].update(min_mm=80, max_mm=120, deficit_oblasts=[], layer="not_stated")
    with pytest.raises(ValidationError, match="layer cannot be not_stated"):
        parse(d, HYDRO)


def test_condition_stage_and_average_are_reset_without_support():
    rec = {
        "soil_moisture": {"deficit_oblasts": ["odesa", "odesa"]},
        "crops": [{"crop": "maize", "bbch_stage": 6, "condition": "poor"},
                  {"crop": "sunflower", "bbch_stage": 0, "condition": "good"}],
        "yield_outlook": [{"crop": "maize", "vs_5yr_average": "above", "production_mt": None}],
        "hazards": ["frost", "frost"],
    }
    text = "Одеська область. Кукурудза і соняшник: сходи, стан добрий. Заморозки."
    clean, removed = clean_lists(rec, text)
    # maize: stage and condition reset -> an empty entry -> removed; the same for its yield entry
    assert clean["crops"] == [{"crop": "sunflower", "bbch_stage": 0, "condition": "good"}]
    assert clean["yield_outlook"] == []
    assert "crops:maize (no stage, no condition)" in removed
    assert "yield_outlook:maize (no comparison, no production)" in removed
    assert clean["soil_moisture"]["deficit_oblasts"] == ["odesa"] and clean["hazards"] == ["frost"]
    assert "crops[maize].bbch_stage:6" in removed and "crops[maize].condition:poor" in removed
    assert "hazards:frost (duplicate)" in removed


def test_condition_must_stand_near_its_crop():
    far = " ".join(["Опади випадали нерівномірно."] * 12)          # > 250 characters
    text = f"Озима пшениця у фазі кущіння, стан добрий. {far} Кукурудза: сходи."
    rec = {"soil_moisture": {"deficit_oblasts": []}, "yield_outlook": [], "hazards": [],
           "crops": [{"crop": "winter_wheat", "bbch_stage": 2, "condition": "good"},
                     {"crop": "maize", "bbch_stage": 0, "condition": "good"}]}
    clean, removed = clean_lists(rec, text)
    assert clean["crops"][0] == {"crop": "winter_wheat", "bbch_stage": 2, "condition": "good"}
    assert clean["crops"][1] == {"crop": "maize", "bbch_stage": 0, "condition": "not_stated"}
    assert removed == ["crops[maize].condition:good"]

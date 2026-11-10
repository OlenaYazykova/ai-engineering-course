"""Stage 2, step 3: answers with sources. Checks of numbers, citations and key facts; the answer chain
with a fake search and a fake model (no network, no model downloads)."""

from types import SimpleNamespace

import pytest

from agro.common.providers import Completion, OpenAICompatibleProvider, Provider
from agro.rag import answer as answer_mod
from agro.rag.answer import NO_ANSWER_MARKER, Answerer, language
from agro.rag.answer_eval import score, summary, threshold_rows
from agro.rag.search import Hit
from agro.rag.verify import extract_numbers, has_fact, sentences, uncited_sentences, verify_numbers


# ---------------------------------------------------------------- numbers

def test_numbers_ranges_units_and_formats():
    got = [(sorted(n.values), n.unit) for n in extract_numbers("22-50 мм, 217 538,5 т, 7.40 t/ha, +40 °С, 4 % [3]")]
    assert got == [(["22"], "мм"), (["50"], "мм"), (["217538.5"], None), (["7.4"], "т/га"), (["40"], "°c"), (["4"], "%")]
    assert sorted(extract_numbers("24,769")[0].values) == ["24.769", "24769"]     # English thousands: both readings


def test_verify_numbers_against_cited_chunks():
    src = ["Запаси 22-50 мм. У Миколаєві (+40 °С). Production: 24 769 thousand t. 4,22"]
    assert verify_numbers("Запаси 22–50 мм [1]. Температура +40 °C [1].", src).ok
    assert verify_numbers("Wheat 24,769 thousand t [1]; 4.22 [1].", src).ok        # en thousands, decimal point
    bad = verify_numbers("Запаси 41 мм [1].", src)
    assert not bad.ok and bad.unsupported == ["41 мм"]
    assert verify_numbers("Запаси 22 см [1].", src).unsupported == ["22 см"]      # the number with another unit
    # numbers of the question (year, date) are not facts of the answer
    assert verify_numbers("У 2023 році 20 липня: 22 мм [1].", src, "Станом на 20 липня 2023 року?").ok
    assert verify_numbers("[2] [3, 4] запаси 50 мм", src).ok                       # citation marks are not numbers


def test_key_facts_forms_and_numbers():
    a = "Озимі у фазах 3-го листка та кущіння, стан переважно доброму [1]. Production 24,769 kt; 0,6–0,7 норми."
    assert has_fact(a, "кущіння") and has_fact(a, "добрий") and has_fact(a, "3-го листка")
    assert has_fact(a, "24 769") and has_fact(a, "0,6-0,7")
    assert not has_fact(a, "задовільний") and not has_fact(a, "27 863")
    assert has_fact("Ні, 36,9 ц/га проти 46 [1]", "Ні") and has_fact("No, there was no snow [1].", "No")
    assert not has_fact("Yes, it was above [1].", "No")


def test_sentences_do_not_end_after_abbreviations():
    a = "У червні 24 769 тис. т [4]. У вересні 27 863 тис. т [2]. Випало 46 мм. Далі [1]."
    assert sentences(a) == ["У червні 24 769 тис. т [4].", "У вересні 27 863 тис. т [2].", "Випало 46 мм.", "Далі [1]."]
    assert sentences("No. There was no snow [1].") == ["No.", "There was no snow [1]."]


def test_uncited_sentences():
    a = ("Так. Запаси 22-50 мм [1]. Даних по Одеській області в документах немає. Це був найтепліший рік.\n"
         "- рядок без посилання")
    assert uncited_sentences(a) == ["Це був найтепліший рік.", "- рядок без посилання"]


def test_language():
    assert language("Яка урожайність?") == "uk" and language("What was the yield?") == "en"


def test_free_text_without_schema():
    p = object.__new__(OpenAICompatibleProvider)
    p.cfg = {}
    assert p._response_format(None) is None
    assert p._response_format({"type": "object"})["type"] == "json_schema"


# ---------------------------------------------------------------- the chain

def chunk(i, doc, text, section="Вологість ґрунту", page=1):
    return SimpleNamespace(chunk_id=f"{doc}#{i}", doc_id=doc, title=f"Бюлетень {doc}", period="2023-07-d1",
                           section=section, page=page, source="Ukrhydrometcenter", text=text,
                           header=f"Бюлетень {doc} | period: 2023-07-d1 | section: {section}",
                           for_embedding=lambda t=text, d=doc: f"Бюлетень {d}\n{t}")


class FakeModel(Provider):
    def __init__(self, answers):
        super().__init__({"model": "fake", "price_in": 1.0, "price_out": 2.0})
        self.answers, self.calls = list(answers), []

    def complete(self, messages, schema, sampling, max_tokens):
        assert schema is None
        self.calls.append(messages)
        return Completion(self.answers.pop(0), 1000, 100, "stop")


CFG = {"model": "fake", "prompt": "v1", "sampling": "t0", "max_tokens": 700, "cache": False, "retrieve_k": 10,
       "k": 5, "context_tokens": 3000, "max_per_doc": 3, "threshold": 0.05,
       "model_cfg": {"model": "fake"}, "sampling_cfg": {"temperature": 0.0, "top_p": 1.0}}


@pytest.fixture(autouse=True)
def word_tokens(monkeypatch):
    monkeypatch.setattr(answer_mod, "count_tokens", lambda text: len(text.split()))


def hits():
    # reranker logits: 3.0 -> p 0.95, 0.0 -> p 0.5, -4.0 -> p 0.018 (below half of the threshold 0.05)
    return [Hit(chunk(1, "a", "Запаси вологи 22-50 мм."), 3.0), Hit(chunk(2, "b", "У Миколаєві +40 °С."), 0.0),
            Hit(chunk(3, "c", "Інше."), -4.0)]


def test_select_context_floor_cap_and_budget():
    a = Answerer(provider=FakeModel([]), cfg=CFG)
    ctx, _ = a.select_context(hits())
    assert [h.chunk.chunk_id for h in ctx] == ["a#1", "b#2"]           # c#3 below half of the threshold
    many = [Hit(chunk(i, "a", "x " * 10), 3.0) for i in range(5)] + [Hit(chunk(9, "b", "y"), 2.0)]
    ctx, _ = a.select_context(many)
    assert [h.chunk.doc_id for h in ctx] == ["a", "a", "a", "a", "b"]   # 3 of "a", then "b", then a 4th "a" ...
    assert [h.chunk.chunk_id for h in ctx] == ["a#0", "a#1", "a#2", "a#3", "b#9"]   # ... in rank order
    few = [Hit(chunk(i, "a", "x"), 3.0) for i in range(5)]
    assert len(a.select_context(few)[0]) == 5                           # one document only: no room is kept
    a.cfg = CFG | {"context_tokens": 25}
    big = [Hit(chunk(1, "a", "x " * 10), 3.0), Hit(chunk(2, "b", "x " * 20), 2.0), Hit(chunk(3, "c", "y"), 1.0)]
    ctx, tokens = a.select_context(big)
    assert [h.chunk.chunk_id for h in ctx] == ["a#1", "c#3"] and tokens <= 25   # b#2 does not fit, c#3 does


def test_threshold_refuses_without_a_model_call():
    model = FakeModel([])
    res = Answerer(provider=model, cfg=CFG | {"threshold": 0.99}).answer("Які запаси вологи?", hits=hits())
    assert res.outcome == "refused_threshold" and res.text == "У документах цього немає." and not model.calls
    assert res.cost_usd == 0


def test_answer_with_citations():
    model = FakeModel(["Запаси вологи становили 22-50 мм [1]. У Миколаєві було +40 °С [2]."])
    res = Answerer(provider=model, cfg=CFG).answer("Які запаси вологи і температура?", hits=hits())
    assert res.outcome == "answer" and [c["doc_id"] for c in res.citations] == ["a", "b"]
    assert res.citations[0]["section"] == "Вологість ґрунту" and res.citations[0]["page"] == 1
    user = model.calls[0][1]["content"]
    assert '<document index="1">' in user and "section: Вологість ґрунту" in user and "Інше" not in user
    assert res.cost_usd == pytest.approx((1000 * 1.0 + 100 * 2.0) / 1e6)


def test_language_of_the_answer_in_the_prompt():
    model = FakeModel(["Soil 22-50 mm [1].", "Запаси 22-50 мм [1]."])
    a = Answerer(provider=model, cfg=CFG)
    a.system = "Мова відповіді: {language}. Rules."
    a.answer("What were the moisture reserves?", hits=hits())
    a.answer("Які запаси вологи?", hits=hits())
    assert model.calls[0][0]["content"] == "Мова відповіді: англійською (in English). Rules."
    assert model.calls[1][0]["content"] == "Мова відповіді: українською. Rules."
    v1 = Answerer(provider=FakeModel([]), cfg=CFG | {"prompt": "v1"}).system
    v2 = Answerer(provider=FakeModel([]), cfg=CFG | {"prompt": "v2"}).system
    assert "{language}" not in v1 and v2.count("{language}") == 2      # v1 stays as it was measured


def test_marker_is_a_refusal():
    res = Answerer(provider=FakeModel([NO_ANSWER_MARKER]), cfg=CFG).answer("What about Romania?", hits=hits())
    assert res.outcome == "refused_model" and res.text == "The documents do not contain this."


def test_wrong_number_retried_then_fixed():
    model = FakeModel(["Запаси 41 мм [1].", "Запаси 22-50 мм [1]."])
    res = Answerer(provider=model, cfg=CFG).answer("Які запаси?", hits=hits())
    assert res.outcome == "answer" and res.text == "Запаси 22-50 мм [1]." and res.checks["retried"]
    note = model.calls[1][-1]["content"]
    assert "41 мм" in note and model.calls[1][-2] == {"role": "assistant", "content": "Запаси 41 мм [1]."}
    assert res.input_tokens == 2000                      # both calls are counted in the cost


def test_wrong_twice_is_retracted():
    model = FakeModel(["Запаси 41 мм [1].", "Запаси 42 мм [7]."])
    res = Answerer(provider=model, cfg=CFG).answer("Які запаси?", hits=hits())
    assert res.outcome == "retracted" and res.checks["second"]["invalid_citations"] == [7]


def test_uncited_only_keeps_the_first_answer_if_the_retry_is_worse():
    model = FakeModel(["Запаси 22-50 мм [1]. Це достатньо для озимих.", "Запаси 99 мм [1]."])
    res = Answerer(provider=model, cfg=CFG).answer("Які запаси?", hits=hits())
    assert res.outcome == "answer" and res.text.startswith("Запаси 22-50 мм [1].")
    assert res.checks["final"]["uncited_sentences"] == ["Це достатньо для озимих."]


# ---------------------------------------------------------------- metrics

def test_score_and_threshold_rows():
    q = {"id": "d01", "kind": "exact", "language": "uk", "question": "?", "key_facts": ["40"], "match": "all",
         "sources": [{"doc_id": "b", "evidence": "У Миколаєві +40 °С."}]}
    no = {"id": "d17", "kind": "no_answer", "language": "uk", "question": "?", "key_facts": [], "sources": []}
    h = hits()
    res = Answerer(provider=FakeModel(["У Миколаєві було +40 °С [2]."]), cfg=CFG).answer("?", hits=h)
    r = score(q, res, h, h[:5])
    assert r["correct"] and r["cited_source"] and r["cited_evidence"] and r["retrieved"] == 1.0 and not r["uncited"]
    res_no = Answerer(provider=FakeModel([NO_ANSWER_MARKER]), cfg=CFG).answer("?", hits=h)
    s = summary([r, score(no, res_no, h, h[:5])])
    assert s["correct"] == 1.0 and s["abstained_no_answer"] == 1.0 and s["false_abstain"] == 0.0
    per_q, rows, suggested = threshold_rows([q, no], {"d01": (h, 0.1), "d17": ([Hit(chunk(1, "z", "z"), -1.0)], 0.1)}, 5)
    assert suggested == 0.3          # half of p 0.95 of d01 (source found) is 0.475; d17 (p 0.27) is refused from 0.3 up
    assert next(x for x in rows if x["threshold"] == 0.3)["refused_no_answer"] == ["d17"]

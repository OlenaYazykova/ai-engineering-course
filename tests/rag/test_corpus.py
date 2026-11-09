"""Stage 2, step 1: reading, cleaning, de-duplication and chunking (no network, no models)."""

from collections import Counter

import pandas as pd
import pytest

from agro.corpus import extract
from agro.corpus.clean import build_vocabulary, join_broken_words, normalize
from agro.corpus.dedup import find_duplicates
from agro.corpus.ingest import read_markdown, table_to_markdown
from agro.corpus.registry import DocMeta
from agro.rag import chunking, tokens


@pytest.fixture(autouse=True)
def simple_tokens(monkeypatch):
    """Tests do not download the tokenizer: one token = one word or punctuation mark."""
    import re

    class Words:
        def encode(self, t):
            return re.findall(r"\S+|\s+", t)

        def decode(self, ids):
            return "".join(ids)

    monkeypatch.setattr(tokens, "_encoder", lambda: Words())


def meta(**kw):
    base = dict(doc_id="uk_x", format="pdf", language="uk", source="s", title="T", period="2023-07-d1",
                effective="2023-07-10", topic="agromet", ocr="", url="u")
    base.update(kw)
    return DocMeta(**base)


# ---------------------------------------------------------------- registry, reading

def test_registry_period_and_ocr_pages():
    m = meta(ocr="pages:12, 13")
    assert (m.year, m.month, m.decade) == (2023, 7, 1)
    assert m.ocr_pages(20) == {12, 13}
    assert meta(ocr="all").ocr_pages(3) == {1, 2, 3}
    assert meta().ocr_pages(3) == set()
    assert (meta(period="2019-2025").year, meta(period="2019-2025").month) == (2019, None)    # a span of years


def test_good_table_rejects_text_set_in_columns():
    numbers = [["Crop", "2024", "2025"], ["Wheat", "4.43", "4.28"], ["Barley", "3.68", "3.49"]]
    prose = [["Під озимими культурами вологозабезпечення було", "оптимальним у західних областях країни"],
             ["на більшості площ центральних областей", "недостатнім на півдні та сході"]]
    assert extract._good_table(numbers)
    assert not extract._good_table(prose)


def test_two_columns_are_read_left_then_right():
    def line(text, x0, x1, top):
        return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 10, "size": 10}

    lines = [line("Title over both columns", 50, 540, 10)]
    for i in range(3):
        lines += [line(f"left {i}", 50, 290, 30 + 15 * i), line(f"right {i}", 305, 540, 30 + 15 * i)]
    order = [l["text"] for l in extract._reading_order(lines, 595)]
    assert order == ["Title over both columns", "left 0", "left 1", "left 2", "right 0", "right 1", "right 2"]


def test_known_hydromet_heading_needs_a_capital_and_a_short_line():
    assert extract._line_is_heading("Зволоження ґрунту", 14, 14, 0.3)
    assert not extract._line_is_heading("агрометеорологічні умови для вегетації культур", 14, 14, 0.9)
    assert not extract._line_is_heading("Агрометеорологічні умови упродовж декади для вегетації пізніх", 14, 14, 0.95)


def test_derzhstat_subset_keeps_only_crop_rows():
    row = {"Farm type": "All agricultural holdings", "Land type": "On all lands", "Size area": "Total",
           "Breakdown": "Wheat", "Indicator": "Yield of one-year and two-year agricultural crops"}
    df = pd.DataFrame([row, {**row, "Breakdown": "Grapes"}, {**row, "Farm type": "Households"},
                       {**row, "Indicator": "Number of enterprises"}])
    assert len(extract.derzhstat_subset(df)) == 1


# ---------------------------------------------------------------- cleaning, duplicates

def test_normalize_spaces_letter_spacing_and_punctuation():
    assert normalize("С т е п  1105-1230 , ( мм )") == "Степ 1105-1230, (мм)"
    assert normalize("пере­нос​") == "перенос"


def test_join_broken_words_only_into_words_of_the_corpus():
    vocab = build_vocabulary(["періоду періоду Тернопільській Тернопільській в сіх"])
    log = Counter()
    assert join_broken_words("за п еріоду у Тернопіль ській", vocab, log) == "за періоду у Тернопільській"
    assert join_broken_words("в організації", vocab, log) == "в організації"   # "в" is a word on its own
    assert log["п еріоду -> періоду"] == 1


def test_duplicates_exact_and_related():
    a = " ".join(f"word{i}" for i in range(200))
    b = a                                   # the same file published twice
    c = " ".join(f"word{i}" for i in range(60)) + " " + " ".join(f"other{i}" for i in range(100))
    out = find_duplicates([("a", a), ("b", b), ("c", c)])
    assert out["b"]["status"] == "exact_duplicate" and out["b"]["duplicate_of"] == "a"
    assert out["c"]["status"] == "ok" and "a" in out["c"]["related"] and "c" in out["a"]["related"]


# ---------------------------------------------------------------- Markdown, chunking

def test_markdown_table_and_front_matter(tmp_path):
    md = table_to_markdown([["Crop", "Yield"], ["Wheat", "4.2"]])
    assert md.splitlines()[1] == "|---|---|"
    p = tmp_path / "d.md"
    p.write_text("---\ndoc_id: d\ntitle: T\n---\n\n# T\n\ntext\n", encoding="utf-8")
    m, body = read_markdown(p)
    assert m["doc_id"] == "d" and body.startswith("# T")


def test_structural_chunks_keep_sections_and_table_headers(monkeypatch):
    monkeypatch.setattr(chunking, "MAX_TOKENS", 40)
    monkeypatch.setattr(chunking, "MIN_TOKENS", 5)
    monkeypatch.setattr(chunking, "TABLE_MAX_TOKENS", 40)
    rows = [["Region", "2024"]] + [[f"Region{i}", str(i)] for i in range(30)]
    body = "\n\n".join([
        "# Title", "<!-- page 3 -->", "## Зволоження ґрунту",
        "Перше речення про вологу. " * 6, "Друге речення про вологу. " * 6,
        "## Ріст і розвиток", "Речення про фази розвитку культур.",
        table_to_markdown(rows),
    ])
    items = chunking.structural_chunks({"doc_id": "d"}, body)
    sections = [s for s, _, _, _ in items]
    assert sections[0] == "Зволоження ґрунту" and sections[-1] == "Ріст і розвиток"
    for s, page, kind, text in items:
        assert page == 3
        if kind == "text":
            assert tokens.count_tokens(text) <= 40 + 5
            assert not ("волог" in text and "фази" in text)         # never two sections in one chunk
    table_parts = [t for _, _, k, t in items if k == "table"]
    assert len(table_parts) > 1
    assert all(t.splitlines()[0] == "| Region | 2024 |" and t.splitlines()[1] == "|---|---|" for t in table_parts)
    stats = chunking.chunk_stats(chunking._to_chunks({"doc_id": "d", "period": "2023-07-d1"}, items, "s", "v", "now"))
    assert stats["table_parts_without_header"] == 0


def test_fixed_chunks_overlap():
    body = " ".join(f"w{i}" for i in range(1000))
    items = chunking.fixed_chunks({}, body)
    assert len(items) >= 2
    assert all(tokens.count_tokens(t) <= chunking.FIXED_SIZE for _, _, _, t in items)


def test_contents_table_and_title_lines():
    toc = [["І.", "Огляд погоди……………………", "5"], ["ІІ.", "Стихійні явища……………………", "22"]]
    assert extract._is_toc(toc) and not extract._good_table(toc)
    blocks = [extract.Block("heading", "ОГЛЯД"), extract.Block("heading", "ПОГОДИ ТА СТИХІЙНИХ ЯВИЩ"),
              extract.Block("heading", "І. Огляд погоди")]
    merged = extract._merge_title_headings(blocks)
    assert [b.text for b in merged] == ["ОГЛЯД ПОГОДИ ТА СТИХІЙНИХ ЯВИЩ", "І. Огляд погоди"]


def test_latin_look_alike_letters_in_cyrillic_words():
    from agro.corpus.clean import fix_homoglyphs

    log = Counter()
    assert fix_homoglyphs("Iвано-Франкiвська, Avg 5yrs, MARS", log) == "Івано-Франківська, Avg 5yrs, MARS"
    assert log["Франкiвська -> Франківська"] == 1
    # OCR text: italic Cyrillic read as Latin, and the degree sign read as "%"
    assert fix_homoglyphs("Memеоролоаічні умовu декадu: 26%С", Counter(), ocr=True) == \
        "Метеоролоаічні умови декади: 26 °С"
    assert fix_homoglyphs("умовu", Counter(), ocr=False) == "умовu"      # outside OCR text: only look-alikes


def test_map_labels_are_not_text():
    from agro.corpus.clean import clean_blocks
    from agro.corpus.ocr import is_map_labels, is_map_place_names

    assert is_map_place_names("Чернав Пуцьк Сун") and not is_map_place_names("Зволоження ґрунту під посівами")
    blocks = [extract.Block("text", "Чернав Пуцьк Сун", ocr=True), extract.Block("text", "Чернав Пуцьк Сун"),
              extract.Block("heading", "Метеорологічні Умови Декади", ocr=True)]
    assert [b.text for b in clean_blocks(blocks, Counter(), Counter())] == \
        ["Чернав Пуцьк Сун", "Метеорологічні Умови Декади"]           # only an OCR text block is dropped

    assert is_map_labels("27 26 26 Черніаів 27 8 27 Пуцью 16 Рівне 18")
    assert not is_map_labels("У першій декаді в Україні переважала дуже тепла для початку вересня погода, на 2-3 °С.")


def test_table_cells_are_read_from_page_words():
    """The decimal point set a little lower than the digits stays inside the number ("4.22", not "422.")."""
    class Row:
        def __init__(self, cells):
            self.cells = cells

    class Table:
        rows = [Row([(0, 0, 50, 10), (50, 0, 100, 10)]), Row([(0, 10, 50, 20), None])]

    words = [(5, 2, 20, 9, "Wheat"), (55, 2, 70, 9, "4.22"), (5, 12, 15, 19, "6"), (17, 12, 30, 19, "308")]
    assert extract._table_rows(Table(), words) == [["Wheat", "4.22"], ["6 308", ""]]


def test_running_headers_and_footers_are_found():
    pages = [[f"JRC MARS Bulletin – Global outlook Ukraine, June 2025", f"Text of page {i} about crops.", str(i)]
             for i in range(1, 9)]
    pages[3].append("A line that occurs once.")
    repeated = extract._repeated_lines(pages)
    assert "JRC MARS Bulletin – Global outlook Ukraine, June #" in repeated     # digits do not matter
    assert "Text of page # about crops." in repeated                          # the same line with a number
    assert "A line that occurs once." not in repeated
    assert extract._repeated_lines(pages[:3]) == set()                        # too few pages to tell


def test_personal_data_masked_and_nothing_left():
    from agro.corpus.pii import PiiMasker

    lower = {"this", "data", "reporting"}
    m = PiiMasker(lower, ner=False)
    text = ("Analysis and reports W. Ben Aoun, I. Cerrani, M. van den Berg. Contact JRCMARSBULLETIN@ec.europa.eu. "
            "Тел.: 279 10 80, 239 93 87, Факс: 279 10 80. Тел/Факс: (044) 525 94 58, 525 69 69. "
            "Укладач О. П. Петренко. Figure A. This shows M. Data for 2025.")
    out = m.mask(text, "d", "en")
    assert "Cerrani" not in out and "Ben Aoun" not in out and "Berg" not in out and "Петренко" not in out
    assert "@" not in out and "279" not in out and "525" not in out
    assert "A. This" in out and "M. Data" in out and "2025" in out                # not names, not phones
    assert "Тел.: [PHONE]" in out and "Contact [EMAIL]" in out
    assert m.find(out, "en") == []
    assert m.counts[("d", "name")] == 2 and m.counts[("d", "email")] == 1         # a list of names is one [NAME]


def test_surname_first_names_and_link_handles():
    """JRC bulletins since 2023 list people surname first; references too."""
    from agro.corpus.pii import PiiMasker

    lower = {"reporting", "support", "data", "production"}
    text = ("Analysis and reports Ben Aoun, W., Bussay, A., Claverie. M., Henin, R., De Palma, P., Mollà-Bononad, B., "
            "Sobrino, J. A., van den Berg, M., Tarnavsky, E. Reporting support Prepress projects, Biavetti, I. "
            "Lemoine, G., 2022. https://medium.com/@gglemoine62/12day-coherence. In Ukraine, wheat and maize, A. B. "
            "Ben Aoun, Claverie, M. et al. Claverie, M., Ben Aoun W. et al. Morel et al. (2024). N., Batič, M.")
    m = PiiMasker(lower, ner=False)
    out = m.mask(text, "d", "en")
    for name in ("Aoun", "Bussay", "Claverie", "Henin", "Palma", "Bononad", "Sobrino", "Berg", "Tarnavsky",
                 "Biavetti", "Lemoine", "gglemoine62", "Morel", "Batič"):
        assert name not in out, name
    assert "Reporting support" in out and "In Ukraine, wheat and maize" in out and "2022" in out
    assert "medium.com/@[NAME]/" in out
    assert m.find(out, "en") == []


def test_ukrainian_staff_names_and_what_is_not_a_name():
    from agro.corpus.pii import PiiMasker

    lower = {"кількість", "огляд"}
    text = ("Огляд склали фахівці: начальник відділу В. Білик, завідувач сектору З. Олійник, к.геог.н. М. Кульбіда.\n"
            "Директор центру, к.геог.н. Микола КУЛЬБІДА. Харківського РЦГМ.\n"
            "О. Носовська і А. Білозерова, синоптики.\n"
            "## І. Огляд погоди\nМаксимум +36 °С. Кількість опадів. Станції Б.Церква, Н.Ворота. По вул. У. Самчука.")
    m = PiiMasker(lower, ner=False)
    out = m.mask(text, "d", "uk")
    for name in ("Білик", "Олійник", "Кульбіда", "КУЛЬБІДА", "Носовська", "Білозерова"):
        assert name not in out, name
    for kept in ("## І. Огляд погоди", "°С. Кількість", "Б.Церква", "Н.Ворота", "вул. У. Самчука", "Харківського РЦГМ"):
        assert kept in out, kept
    assert m.find(out, "uk") == []


def test_spacy_finds_full_names_and_keeps_places():
    """The model (through Presidio) finds names the rules do not; places it takes for persons stay."""
    from agro.corpus.pii import PiiMasker, person_like

    lower = {"thank", "teams", "support", "річках", "області", "випало"}
    m = PiiMasker(lower)
    en = m.mask("We thank the teams of Prof. Nataliia Kussul and Dr. Klaus Deininger for their support.", "d", "en")
    assert "Kussul" not in en and "Deininger" not in en and "We thank" in en
    uk = "На річках Сула, Рось, Ворскла; на Сл Пожежевська (Івано-Франківської) випало 20 мм."
    assert m.mask(uk, "d", "uk") == uk
    text = "ЦГО імені Бориса Срезневського, Ivano- Frankivs’ka, Andrii Shelestov"
    assert not person_like(text, 9, 30, lower)[0]                      # an institution named after a person
    assert not person_like(text, 32, 50, lower)[0]                     # an oblast cut by a line break
    assert person_like(text, 52, 68, lower)[0]
    assert not person_like("Бориса Срезневського", 0, 20, lower, before="ОБСЕРВАТОРІЯ імені")[0]   # "імені" ends the line before
    tables = "Станції:\n| Синюха | Синюхин Брід | 2,19 |"
    assert m.find(tables, "uk") == []                                  # tables: rules only, also in the check


def test_name_cut_by_a_line_break():
    from agro.corpus.pii import PiiMasker

    blocks = [extract.Block("text", "Analysis and reports I. Cerrani, L."), extract.Block("text", "Panarello, F. Sedano")]
    PiiMasker(set(), ner=False).mask_blocks(blocks, "d", "en")
    assert "Panarello" not in blocks[1].text and "Sedano" not in blocks[1].text


def test_committed_corpus_has_no_personal_data():
    """The check of the real corpus: Presidio (spaCy + rules) finds no e-mail, phone or name in data/corpus/text/."""
    from agro.common.settings import CORPUS
    from agro.corpus.pii import PiiMasker, lowercase_words

    docs = [read_markdown(p) for p in sorted((CORPUS / "text").glob("*.md"))]
    if not docs:
        pytest.skip("no corpus built")
    m = PiiMasker(lowercase_words(body for _, body in docs))
    left = {meta["doc_id"]: m.find(body, meta.get("language", "en")) for meta, body in docs}
    assert not {d: kinds for d, kinds in left.items() if kinds}

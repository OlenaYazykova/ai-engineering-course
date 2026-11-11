"""Checks of an answer without a model: numbers against the cited chunks, citations, key facts.

Numbers (as in the lecture example autoparts-rag-evals, verify.py): every number of the answer, with its
unit when it has one, must be in the chunks the answer cites. Not checked: citation marks [n], page
references and numbers of the question itself (the year, the date asked about).

  "22-50 мм"      -> 22, 50 мм          a range is two numbers
  "217 538,5"     -> 217538.5           a space between groups of thousands, a decimal comma
  "24,769" (en)   -> 24769 or 24.769    English thousands: either reading may be the one in the chunk
  "7.40"          -> 7.4                trailing zeros do not matter
  "+40 °С"        -> 40 °c              the sign is not compared, °С (Cyrillic) = °C

A number with a unit must have the same unit in the chunk, or stand there without a unit (a table with
the unit in its header). Units of the corpus: мм, см, °C, %, т/га, ц/га (and the English forms).

Key facts (the deterministic "correct" of the test set, evals/README.md): every key fact must be in the
answer. A fact with digits: all its numbers must be among the numbers of the answer. A fact in words:
its words must follow one another in the answer, a word matching when they share a dictionary form
(pymorphy3; every reading of the word, so "добрий" matches "в доброму стані", which is read first as
the noun "добре"). A fact with digits and words ("3-го листка") is checked by its numbers.
"""

import re
from dataclasses import dataclass, field

_NUM = r"\d+(?:[  ]\d{3})*(?:[.,]\d+)*"
_UNITS = {
    "мм": "мм", "mm": "мм", "см": "см", "cm": "см",
    "°с": "°c", "°c": "°c", "° с": "°c", "° c": "°c", "ос": "°c",
    "%": "%", "т/га": "т/га", "t/ha": "т/га", "ц/га": "ц/га",
}
_UNIT_RE = "|".join(sorted((re.escape(u) for u in _UNITS), key=len, reverse=True))
_NUM_UNIT = re.compile(rf"(?<![\w.,])({_NUM})(?:\s?({_UNIT_RE})(?![а-яіїєґa-z]))?", re.IGNORECASE)

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_PAGE_REF = re.compile(r"(?:с\.|стор\.|сторінк\w*|p\.|page)\s*\d+", re.IGNORECASE)


def _plain(raw: str) -> str:
    s = raw.replace(",", ".")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def readings(raw: str) -> set[str]:
    """Every way to read one written number: '217 538,5' -> {'217538.5'}; '24,769' -> {'24769', '24.769'}."""
    s = re.sub(r"[  ]", "", raw)
    out = set()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):     # English groups of thousands: 24,769 / 1,234.5
        out.add(_plain(s.replace(",", "")))
    if s.count(",") + s.count(".") <= 1:
        out.add(_plain(s))
    return out or {_plain(s)}


@dataclass
class Number:
    raw: str
    values: set[str]          # readings of the whole number
    parts: list[set[str]]     # readings of each group when the spaces were not thousands ("2023 40")
    unit: str | None


def extract_numbers(text: str) -> list[Number]:
    text = _PAGE_REF.sub(" ", CITATION.sub(" ", text))
    out, ends = [], []
    for m in _NUM_UNIT.finditer(text):
        raw, unit = m.group(1), m.group(2)
        groups = re.split(r"[  ]", raw)
        n = Number(raw, readings(raw), [readings(g) for g in groups] if len(groups) > 1 else [],
                   _UNITS.get(unit.lower()) if unit else None)
        if n.unit and out and out[-1].unit is None and re.fullmatch(r"\s?[-–—]\s?", text[ends[-1]:m.start()]):
            out[-1].unit = n.unit              # a range "22-50 мм": both ends in мм
        out.append(n)
        ends.append(m.end(1))
    return out


def number_values(text: str) -> set[str]:
    """All readings of all numbers of a text (with the readings of space-separated groups)."""
    vals = set()
    for n in extract_numbers(text):
        vals |= n.values
        for p in n.parts:
            vals |= p
    return vals


@dataclass
class NumberCheck:
    ok: bool
    unsupported: list[str] = field(default_factory=list)
    checked: int = 0


def verify_numbers(answer: str, sources: list[str], question: str = "") -> NumberCheck:
    with_unit: set[tuple[str, str]] = set()
    bare: set[str] = set()
    for s in sources:
        for n in extract_numbers(s):
            vals = n.values | {v for p in n.parts for v in p}
            if n.unit:
                with_unit |= {(v, n.unit) for v in vals}
            else:
                bare |= vals
    known = bare | {v for v, _ in with_unit}
    asked = number_values(question)
    unsupported = []
    numbers = extract_numbers(answer)
    for n in numbers:
        if n.values & asked:
            continue
        found = n.values & known or (n.parts and all(p & known for p in n.parts))
        if not found:
            unsupported.append(n.raw + (f" {n.unit}" if n.unit else ""))
        elif n.unit and not (n.values & bare) and not any((v, n.unit) in with_unit for v in n.values):
            unsupported.append(f"{n.raw} {n.unit}")      # the number is there, with another unit
    return NumberCheck(not unsupported, unsupported, len(numbers))


def verify_numbers_by_sentence(answer: str, cited_sources: dict[int, str], question: str = "") -> NumberCheck:
    """Every number of a sentence must be in the chunks THAT sentence cites, not in any chunk the answer
    cites: "In June 2025 the forecast was 23,546 [3]" fails when 23 546 is only in chunk [2] (there: the
    production of 2024). A sentence without a valid [n] is checked against every chunk the answer cites
    (it is reported as uncited anyway). cited_sources: n -> text of chunk [n]."""
    unsupported, checked = [], 0
    every = list(cited_sources.values())
    for s in sentences(answer):
        own = [cited_sources[n] for n in cited_numbers(s) if n in cited_sources]
        c = verify_numbers(s, own or every, question)
        checked += c.checked
        marks = ", ".join(f"[{n}]" for n in cited_numbers(s) if n in cited_sources)
        unsupported += [f"{u} (не у фрагменті {marks})" if own else u for u in c.unsupported]
        if own:
            bad = {u.split(" ")[0] for u in c.unsupported}
            unsupported += [f"{u} (у фрагменті {marks})" for u in table_mismatches(s, own, question)
                            if u.split(" ")[0] not in bad]
    return NumberCheck(not unsupported, unsupported, checked)


# ---------------------------------------------------------------- numbers in table cells

# A number of a table is a value of one cell: of its row (an oblast, a crop), its column (a year) and its
# table (the section of the chunk: "Maize: yield, centners per ha"). The check above only asks whether the
# number is in the chunk, so "the yield of wheat was 37.6" passes when 37.6 is the yield of maize in the
# next row. Here: a number of a sentence that stands in the cited chunks only in table cells must have at
# least one cell that does not contradict the sentence. A contradiction: the sentence names crops (oblasts,
# zones) and the cell is of another one, or it names one year and the cell is in the column of another year.
# What the sentence does not name is not checked, so a sentence without a crop passes. Numbers also found in
# the text of the chunk outside the cells are not checked (they cannot be placed).

CROPS = {
    "wheat": r"пшениц|(?<!buck)wheat", "maize": r"кукурудз|maize|\bcorn\b", "barley": r"ячмін|ячмен|barley",
    "sunflower": r"соняшник|sunflower", "soy": r"\bсо(?:я|ї|ю|єю)\b|\bsoy", "rapeseed": r"ріпак|rapeseed|\brape\b",
    "rye": r"\bжит(?:о|а|у|ом|і)\b|\brye\b", "oats": r"\bовес|\bвівс|\boats?\b", "buckwheat": r"гречк|гречан|buckwheat",
    "peas": r"\bгорох|\bpeas?\b", "sugar beet": r"буряк|beet", "potato": r"картопл|potato", "millet": r"\bпрос(?:о|а|у)\b|millet",
}
# "the country", "on average" name Ukraine: "нижче середнього по країні (46)" is the row Ukraine
REGIONS = {
    "Україна": r"україн|ukrain|країн|country|national|середн|average",
    "Вінницька": r"вінниц|vinnyts", "Волинська": r"волин|volyn", "Дніпропетровська": r"дніпропетр|dnipropetr",
    "Донецька": r"донец|донеч|donets", "Житомирська": r"житомир|zhytomyr", "Закарпатська": r"закарпат|zakarpat",
    "Запорізька": r"запоріз|zaporiz", "Івано-Франківська": r"івано-франк|прикарпат|ivano-frank",
    "Київська": r"київ|києв|kyiv|kiev", "Кіровоградська": r"кіровоград|кропивниц|kirovohrad",
    "Луганська": r"луган|luhans", "Львівська": r"львів|lviv", "Миколаївська": r"миколаїв|mykolai",
    "Одеська": r"одес|одещ|odes", "Полтавська": r"полтав|poltav", "Рівненська": r"рівненськ|рівненщ|rivne",
    "Сумська": r"сумськ|сумщ|sumsk|sumy", "Тернопільська": r"тернопіл|ternopil", "Харківська": r"харків|kharkiv",
    "Херсонська": r"херсон|kherson", "Хмельницька": r"хмельниц|khmelnyt", "Черкаська": r"черкас|cherkas",
    "Чернівецька": r"чернівец|чернівц|chernivet|chernivts", "Чернігівська": r"чернігів|chernihiv",
    "Крим": r"крим|crimea", "Степ": r"\bстеп|(?<!forest-)steppe", "Лісостеп": r"лісостеп|forest-steppe",
    "Полісся": r"полісс|polissia|polesie",
}
_CROP_RE = {k: re.compile(v, re.IGNORECASE) for k, v in CROPS.items()}
_REGION_RE = {k: re.compile(v, re.IGNORECASE) for k, v in REGIONS.items()}
_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
_YEAR_COLUMN = re.compile(r"^\s*(19[5-9]\d|20\d\d)\s*(?:р\.?|рік|year)?\s*$", re.IGNORECASE)
# a sentence that compares years ("37.6 проти 41.5 у попередньому році") is not checked by the year
_COMPARES = re.compile(r"попередн|минул|торік|торішн|проти|порівнян|ніж|вищ|нижч|більш|менш|зріс|зрост|знизи|"
                       r"зменш|збільш|previous|last year|year before|compared|than|\bvs\b|higher|lower|more|less|"
                       r"increase|decrease|growth|change", re.IGNORECASE)
_LETTERS = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]{3,}")


def _names(text: str, table: dict) -> set[str]:
    return {k for k, r in table.items() if r.search(text)}


@dataclass
class Cell:
    values: set[str]
    crops: set[str]
    regions: set[str]
    year: str | None
    where: str              # for the retry note: row, column, table


def _header_row(row: list[str]) -> bool:
    """A row of column names: "| | 2021 | 2022 |", "| Oblast | Avg 5yrs | 2024 | %25/24 |" (words and years)."""
    rest = [c for c in row[1:] if c]
    return bool(rest) and (not row[0] or _LETTERS.search(row[0]) is not None) and \
        all(_LETTERS.search(c) or _YEAR_COLUMN.match(c) or re.fullmatch(r"%\s?\d{2}\s?/\s?\d{2}", c) for c in rest)


def _cells(chunk: str) -> tuple[list[Cell], str]:
    """The value cells of the Markdown tables of a chunk (its first line is the header of the chunk), and the
    text outside the value cells (the header, the lines of text, the header rows of the tables)."""
    lines = chunk.split("\n")
    header, rest = (lines[0], lines[1:]) if lines else ("", [])
    general_crops, general_regions = _names(header, _CROP_RE), _names(header, _REGION_RE)
    table_name = header.split("section:")[-1].strip()
    cells, outside, i = [], [header], 0
    while i < len(rest):
        if not rest[i].lstrip().startswith("|"):
            outside.append(rest[i])
            i += 1
            continue
        block = []
        while i < len(rest) and rest[i].lstrip().startswith("|"):
            block.append([c.strip() for c in rest[i].strip().strip("|").split("|")])
            i += 1
        sep = next((j for j, r in enumerate(block) if r and all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)), None)
        if sep is None:
            outside += [" | ".join(r) for r in block]
            continue
        head = [r for r in block[:sep]]
        body = block[sep + 1:]
        while body and _header_row(body[0]):                # header rows under the line: "| | 2021 | 2022 |"
            head.append(body.pop(0))
        outside += [" | ".join(r) for r in head]
        width = max(len(r) for r in block)
        filled = []                                           # a header over several columns: "Area | | |"
        for r in head:
            row, last = [], ""
            for j in range(width):
                c = r[j] if j < len(r) else ""
                last = c or last
                row.append(last)
            filled.append(row)
        for r in body:
            labels = " ".join(c for c in r if _LETTERS.search(c))
            for j, c in enumerate(r):
                if not c or _LETTERS.search(c) or not re.search(r"\d", c):
                    continue
                column = " ".join(dict.fromkeys(f[j] for f in filled if f[j]))
                exact = next((h[j] for h in reversed(head) if j < len(h) and h[j]), "")
                year = m.group(1) if (m := _YEAR_COLUMN.match(exact)) else None
                specific = f"{labels} {column}"
                cells.append(Cell({v for n in extract_numbers(c) for v in n.values}, _names(specific, _CROP_RE) or general_crops,
                                  _names(specific, _REGION_RE) or general_regions, year,
                                  f"рядок «{labels}», стовпець «{column}», таблиця «{table_name}»"))
    return cells, "\n".join(outside)


def table_mismatches(sentence: str, chunks: list[str], question: str = "") -> list[str]:
    """Numbers of the sentence whose every cell in the chunks contradicts the sentence, with where they are."""
    crops, regions = _names(sentence, _CROP_RE), _names(sentence, _REGION_RE)
    years = set(_YEAR.findall(sentence))
    year = next(iter(years)) if len(years) == 1 and not _COMPARES.search(sentence) else None
    if not (crops or regions or year):
        return []
    parsed = [_cells(c) for c in chunks]
    outside = set()
    for _, text in parsed:
        outside |= number_values(text)
    asked, out = number_values(question), []
    for n in extract_numbers(sentence):
        vals = n.values | {v for p in n.parts for v in p}
        if vals & asked or vals & outside or (not n.unit and _YEAR.fullmatch(n.raw)):
            continue
        hits = [c for cells, _ in parsed for c in cells if n.values & c.values]   # whole numbers only
        if not hits:
            continue
        if not any((not crops or not c.crops or crops & c.crops) and (not regions or not c.regions or regions & c.regions)
                   and (not year or not c.year or c.year == year) for c in hits):
            msg = (f"{n.raw}{f' {n.unit}' if n.unit else ''}: це значення клітинки ({hits[0].where}), "
                   f"а не того, про що речення")
            if msg not in out:
                out.append(msg)
    return out


# ---------------------------------------------------------------- citations

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[^\s\[])|\n+")
# sentences that say what is missing need no citation
_ABSENCE = re.compile(r"немає|не містять|не містить|не наведен|не вказан|не зазначен|не надають|не наводять|"
                      r"не подають|відсутн|not (?:contain|include|given|stated|mention)|"
                      r"no (?:information|data)|there is no|do(?:es)? not (?:say|give|provide)", re.IGNORECASE)


def cited_numbers(answer: str) -> list[int]:
    """Numbers n of the [n] marks, in order of first use."""
    out = []
    for m in CITATION.finditer(answer):
        for n in m.group(1).split(","):
            if int(n) not in out:
                out.append(int(n))
    return out


# a full stop after these is not the end of a sentence: "24 769 тис. т", "у 2019 р. опадів", "Kyiv obl. 7-10".
# Units that end sentences ("випало 46 мм.") are not in the list.
_ABBREVIATIONS = {"тис", "млн", "млрд", "т", "ц", "р", "рр", "обл", "с", "стор", "табл", "див", "п", "ст",
                  "th", "obl", "approx", "e.g", "i.e", "vs", "p"}


def sentences(answer: str) -> list[str]:
    out, start = [], 0
    for m in _SENTENCE_END.finditer(answer):
        if "\n" not in m.group(0):
            word = re.search(r"([\w.]+)\.$", answer[start:m.start()])
            if word and word.group(1).lower() in _ABBREVIATIONS:
                continue
        out.append(answer[start:m.start()])
        start = m.end()
    out.append(answer[start:])
    return [s.strip() for s in out if s and s.strip() and re.search(r"\w", s)]


def uncited_sentences(answer: str) -> list[str]:
    """Sentences with a statement but without a [n] mark (a sentence about what is missing is not one)."""
    out = []
    for s in sentences(answer):
        if CITATION.search(s) or _ABSENCE.search(s):
            continue
        if len(re.findall(r"\w+", s)) < 3 and not re.search(r"\d", s):
            continue                                  # "Так." / "Yes." before the cited sentence
        out.append(s)
    return out


# ---------------------------------------------------------------- key facts

_WORD = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ’'ʼ]+")


def _forms(word: str) -> frozenset[str]:
    """Every dictionary form a word may have ("доброму" -> {"добре", "добрий"}); Latin words cut to 6 letters."""
    from .search import STEM, _CYRILLIC, _morph

    w = word.lower().replace("ʼ", "'").replace("’", "'")
    if _CYRILLIC.search(w):
        return frozenset(p.normal_form for p in _morph().parse(w))
    return frozenset({w[:STEM]})


def has_fact(answer: str, fact: str) -> bool:
    if re.search(r"\d", fact):
        have = number_values(answer)
        return all(n.values & have or (n.parts and all(p & have for p in n.parts)) for n in extract_numbers(fact))
    want = [_forms(w) for w in _WORD.findall(fact)]
    have = [_forms(w) for w in _WORD.findall(answer)]
    return bool(want) and any(all(want[j] & have[i + j] for j in range(len(want)))
                              for i in range(len(have) - len(want) + 1))


def key_facts_found(answer: str, facts: list[str]) -> list[bool]:
    return [has_fact(answer, f) for f in facts]

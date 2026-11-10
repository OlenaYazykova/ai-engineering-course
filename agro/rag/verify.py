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


# ---------------------------------------------------------------- citations

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[^\s\[])|\n+")
# sentences that say what is missing need no citation
_ABSENCE = re.compile(r"немає|не містять|не наведен|не вказан|відсутн|not (?:contain|include|given|stated|mention)|"
                      r"no (?:information|data)|do(?:es)? not (?:say|give|provide)", re.IGNORECASE)


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

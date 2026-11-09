"""Metadata filters: given explicitly or read from the question.

A filter limits the search to chunks whose metadata match; it is applied inside the vector search
(Qdrant payload filter) and to BM25 the same way, never by asking the model.

Fields: year (a document covers it: a bulletin of 2023, the 2019-2025 statistics), month and decade
(documents without a month, e.g. annual reviews, are kept: they may cover that month too), source,
language, topic, kind (text / table), effective date range.

From the question: a year ("2023", "2023 року"), a month (Ukrainian in any case: "липня", "липні",
"липень"; English), a decade ("третя / третій / третьої декади", "first dekad"), the source
("JRC", "Держстат", "облстат", "Гідрометцентр").
"""

import re
from dataclasses import asdict, dataclass

MONTHS = {
    1: ("січ", "january"), 2: ("лют", "february"), 3: ("берез", "march"), 4: ("квіт", "april"),
    5: ("трав", "may"), 6: ("черв", "june"), 7: ("лип", "july"), 8: ("серп", "august"),
    9: ("верес", "september"), 10: ("жовт", "october"), 11: ("листопад", "november"),
    12: ("груд", "december"),
}
DECADES = {1: ("перш", "first"), 2: ("друг", "second"), 3: ("трет", "third", "останн", "last")}
SOURCES = {                     # source group (first word of `source`) -> how a question names it
    "JRC": r"\bJRC\b|MARS",
    "State": r"Держстат|State Statistics",
    "Odesa": r"облстат|oblast statistics",
    "Ukrhydrometcenter": r"Гідрометцентр|Укргідрометцентр|Hydromet",
}


@dataclass
class Filters:
    year: int | None = None
    month: int | None = None
    decade: int | None = None
    source: str | None = None        # source group: JRC | Ukrhydrometcenter | State | Odesa
    language: str | None = None
    topic: str | None = None
    kind: str | None = None
    date_from: str | None = None     # ISO dates, on `effective`
    date_to: str | None = None

    def active(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def matches(self, c) -> bool:
        """The same filter on a chunk in memory (BM25 side and the tests)."""
        if self.year is not None and not (c["year_from"] <= self.year <= c["year_to"]):
            return False
        if self.month is not None and c.get("month") not in (None, self.month):
            return False
        if self.decade is not None and c.get("decade") not in (None, self.decade):
            return False
        if self.source and c.get("source_group") != self.source:
            return False
        for key in ("language", "topic", "kind"):
            if getattr(self, key) and c.get(key) != getattr(self, key):
                return False
        if self.date_from and c.get("effective", "") < self.date_from:
            return False
        if self.date_to and c.get("effective", "9999") > self.date_to:
            return False
        return True


def year_span(period: str) -> tuple[int, int]:
    """'2023-07-d1' -> (2023, 2023); '2019-2025' -> (2019, 2025)."""
    years = [int(y) for y in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", period)]
    return (min(years), max(years)) if years else (0, 9999)


def from_question(question: str) -> Filters:
    q = question.lower()
    f = Filters()
    years = re.findall(r"(?<!\d)(20[12]\d)(?!\d)", q)
    if len(set(years)) == 1:                  # two different years: a comparison, no year filter
        f.year = int(years[0])
    months = [m for m, stems in MONTHS.items() if any(re.search(r"\b" + s, q) for s in stems)]
    if 5 in months and not re.search(r"\bтрав|\d\s+may\b|\bmay\s+\d|\bin may\b", q):
        months.remove(5)                      # English "may" is mostly the verb
    if len(months) == 1:
        f.month = months[0]
    m = re.search(r"\b(\w+)\s+(?:декад|dekad|decade)", q)
    if m and f.month:
        for d, stems in DECADES.items():
            if m.group(1).startswith(stems):
                f.decade = d
    for source, pattern in SOURCES.items():
        if re.search(pattern, question):
            f.source = source
            break
    return f

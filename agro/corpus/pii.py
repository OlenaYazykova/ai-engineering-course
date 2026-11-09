"""Personal data and contacts are masked before anything is written to the corpus or the index.

The documents are public reports, but they name people: the analysts and editors of every JRC bulletin
("W. Ben Aoun, I. Cerrani" until 2023, "Ben Aoun, W., Cerrani, I." since), the people thanked in them
("Prof. Nataliia Kussul"), authors of cited papers, the staff who wrote the annual reviews of
Ukrhydrometcenter ("начальник відділу В. Білик", "Директор ... Микола КУЛЬБІДА"); and they give e-mails and
phone numbers of the issuing offices. Masked:

  person          -> [NAME]
  e-mail          -> [EMAIL]
  phone / fax     -> [PHONE]
  user in a link  -> @[NAME]   ("medium.com/@user/...")

Microsoft Presidio does the masking (AnalyzerEngine finds, AnonymizerEngine replaces), with two kinds of
recognizers for Ukrainian and English text:

  PersonNer   spaCy NER (uk_core_news_md, en_core_web_md) through Presidio. The model also calls rivers,
              stations and oblasts persons ("Сула", "Сл Пожежевська", "Sums'ka"), so a hit is kept only
              if it looks like a person: two or more capitalised words, none of which occurs in the
              corpus in lower case, no abbreviation ("Сл", "М"), no oblast adjective ("-s'ka", "-ська"),
              not after "імені" (an institution named after a person). Rejected hits are counted.
  AgroRules   our patterns as a Presidio recognizer, for what the model misses: name lists with initials
              in either order ("Cerrani, I., Claverie, M."), one initial + surname ("В. Білик"), e-mails,
              phone numbers after "Тел." / "Факс" / "Phone" or in the +380 / (044) form. An "initial +
              word" is a name only if the word never occurs in lower case ("A. This", "36 °С. Кількість"
              stay); section numbers in headings ("## І. Огляд"), stations in tables ("Б.Церква") and
              streets ("вул. У. Самчука") are not names.

Table cells are masked by AgroRules only (the model is slow on thousands of cells and finds no names
there). After masking every document is analysed again (`find`): anything found is an audit warning.
Only counts are logged (data/corpus/pii_log.csv): the log must not repeat the data it removed.
"""

import re
from collections import Counter
from functools import lru_cache

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_NUM = r"(?:\+?\(?\d[\d\s()\-]{5,}\d)"
PHONE_AFTER_WORD = re.compile(
    r"(\b(?:Тел(?:\.|ефон)?|тел\.?|Факс|факс|Tel\.?|Phone|Fax)(?:\s*/\s*(?:Факс|факс|Fax))?\.?\s*:?\s*)"
    rf"({_NUM}(?:\s*,\s*{_NUM})*)")
PHONE_FORM = re.compile(r"(?:\+38\s?)?\(0\d{2}\)\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\+380[\s\d-]{9,13}\d")
NAME_LATIN = re.compile(
    r"\b[A-Z]\.\s?(?:[A-Z]\.\s?)?(?:(?:van den|van der|van|de|Ben)\s)?([A-Z][a-z]{2,}(?:-[A-Z][a-z]+)?)\b")
_LOW = r"(?:(?![A-Z])[^\W\d_])"     # a lower-case letter, also "č", "à", "ł"
_SURNAME = rf"(?:(?:van den|van der|van|de|De|Ben)\s)?[A-Z]{_LOW}{{2,}}(?:-[A-Z]{_LOW}+)?"
NAME_LATIN_AFTER = re.compile(     # "Claverie, M." (JRC credits and references); typos of a list: "Claverie. M.,",
    rf"\b({_SURNAME})(?:,\s?|\.\s(?=[A-Z]\.,)|\s(?=[A-Z]\.(?:,|\s?et al)))[A-Z]\.(?:\s?[A-Z]\.)?")   # "Ben Aoun W. et al."
NAME_ET_AL = re.compile(rf"\b({_SURNAME})\s(?=et al\b)")                       # "Ben Aoun et al."
NAME_BEFORE_LIST = re.compile(rf"\b({_SURNAME}),\s?$")                          # "Ben Aoun, " + a name
HANDLE = re.compile(r"(?<=/)@[A-Za-z0-9_.-]+")
NAME_CYRILLIC = re.compile(r"\b[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ][а-яіїєґ’']{2,}\b")      # О. П. Петренко
_CL = "а-яіїєґ’'"
NAME_CYRILLIC_ONE = re.compile(    # "начальник відділу В. Білик": one initial, a space, a surname
    rf"(?<![\w.])[А-ЯІЇЄҐ]\.\s([А-ЯІЇЄҐ][{_CL}]{{2,}}(?:-[А-ЯІЇЄҐ][{_CL}]+)?)")
NAME_CYRILLIC_CAPS = re.compile(rf"\b[А-ЯІЇЄҐ][{_CL}]{{2,}}\s([А-ЯІЇЄҐ][А-ЯІЇЄҐ’']{{4,}})\b")   # "Микола КУЛЬБІДА"
NAME_CYRILLIC_AFTER = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ’']{2,}\s[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.")    # Петренко О. П.


SPACY_MODELS = {"uk": "uk_core_news_md", "en": "en_core_web_md"}
REPLACE = {"PERSON": "[NAME]", "EMAIL_ADDRESS": "[EMAIL]", "PHONE_NUMBER": "[PHONE]"}
KIND = {"PERSON": "name", "EMAIL_ADDRESS": "email", "PHONE_NUMBER": "phone"}
_PLACE = re.compile(r"(?:s[’']ka|ська|цька|зька)$")


def rule_spans(text: str, lowercase: set[str]) -> list[tuple[str, int, int]]:
    """(entity, start, end) of everything the rules find."""
    out = [("EMAIL_ADDRESS", m.start(), m.end()) for m in EMAIL.finditer(text)]
    out += [("PHONE_NUMBER", m.start(2), m.end(2)) for m in PHONE_AFTER_WORD.finditer(text)]
    out += [("PHONE_NUMBER", m.start(), m.end()) for m in PHONE_FORM.finditer(text)]
    out += [("PERSON", m.start() + 1, m.end()) for m in HANDLE.finditer(text) if m.group(0) != "@[NAME]"]
    out += [("PERSON", s, e) for s, e, _ in latin_name_spans(text, lowercase)]
    out += [("PERSON", m.start(), m.end()) for m in NAME_CYRILLIC.finditer(text)]
    out += [("PERSON", m.start(), m.end()) for m in NAME_CYRILLIC_AFTER.finditer(text)]
    out += [("PERSON", m.start(), m.end()) for m in NAME_CYRILLIC_ONE.finditer(text) if _is_cyr_name(m, lowercase)]
    out += [("PERSON", m.start(), m.end()) for m in NAME_CYRILLIC_CAPS.finditer(text)
            if m.group(0).split()[0].lower() not in lowercase]
    return out


def person_like(text: str, start: int, end: int, lowercase: set[str], before: str = "") -> tuple[bool, str]:
    """Is a spaCy PERSON hit a person? (False, reason) for places, abbreviations, institutions.
    before: the text of the previous block ("імені" may end the line before the name)."""
    span = text[start:end]
    toks = re.findall(r"[^\s,;()]+", span)
    if len(toks) < 2 or re.search(r"\d", span):
        return False, "one word or digits"
    if re.search(r"(?:імені|ім\.)\s*$", (before + "\n" + text[:start])[-12:]):
        return False, "named after a person"
    for tok in toks:
        w = tok.strip(".’'")
        if not tok[0].isupper():
            return False, "lower-case word"
        if tok.endswith("-") or _PLACE.search(w):
            return False, "place name"
        if len(w) <= 2 and not tok.endswith("."):
            return False, "abbreviation"
        if len(w) > 2 and w.lower() in lowercase:
            return False, "word occurs in lower case"
    return True, ""


def _merge(results: list) -> list:
    """Overlapping finds become one (a list of names is one [NAME]); the longer one gives the entity."""
    out = []
    for r in sorted(results, key=lambda r: (r.start, -r.end)):
        if out and r.start < out[-1].end:
            if r.end - r.start > out[-1].end - out[-1].start:
                out[-1].entity_type = r.entity_type
            out[-1].end = max(out[-1].end, r.end)
        else:
            out.append(r)
    return out


def _language(language: str) -> str:
    return language if language in SPACY_MODELS else "en"


class PiiMasker:
    def __init__(self, lowercase_words: set[str], ner: bool = True) -> None:
        """lowercase_words: words that occur in the corpus in lower case (not surnames).
        ner=False: rules only (unit tests of the rules; table cells)."""
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_anonymizer import AnonymizerEngine

        self.lower = lowercase_words
        self.counts: Counter = Counter()      # (doc_id, kind) -> number of masked items
        self.found_by: Counter = Counter()    # "rules" / "spacy" -> finds before merging
        self.anonymizer = AnonymizerEngine()
        self.rules = {lang: _rules_recognizer(self.lower, lang) for lang in SPACY_MODELS}
        self.ner = {}
        self.analyzer = None
        if ner:
            engine = _nlp_engine()
            registry = RecognizerRegistry(supported_languages=list(SPACY_MODELS))
            for lang in SPACY_MODELS:
                self.ner[lang] = _person_ner(self.lower, lang)
                registry.add_recognizer(self.ner[lang])
                registry.add_recognizer(self.rules[lang])
            self.analyzer = AnalyzerEngine(nlp_engine=engine, registry=registry,
                                           supported_languages=list(SPACY_MODELS))

    def analyze(self, text: str, language: str = "uk", ner: bool = True, before: str = "") -> list:
        lang = _language(language)
        if ner and self.analyzer is not None:
            self.ner[lang].before = before
            results = self.analyzer.analyze(text, language=lang, entities=list(REPLACE))
        else:
            results = self.rules[lang].analyze(text, list(REPLACE))
        return [r for r in results if "[" not in text[r.start:r.end]]     # not a mask already put

    def mask(self, text: str, doc_id: str = "", language: str = "uk", ner: bool = True, before: str = "") -> str:
        from presidio_anonymizer.entities import OperatorConfig

        results = self.analyze(text, language, ner, before)
        if not results:
            return text
        for r in results:
            self.found_by["spacy" if r.recognition_metadata.get("recognizer_name") == "PersonNer" else "rules"] += 1
        results = _merge(results)
        for r in results:
            self.counts[(doc_id, KIND[r.entity_type])] += 1
        ops = {e: OperatorConfig("replace", {"new_value": v}) for e, v in REPLACE.items()}
        return self.anonymizer.anonymize(text=text, analyzer_results=results, operators=ops).text

    def find(self, text: str, language: str = "uk") -> list[str]:
        """What is still there (the check after masking): kinds of items found. The model reads the
        text without the Markdown tables (tables are masked by the rules, which also check them here)."""
        no_tables = "\n".join(" " * len(l) if l.startswith("|") else l for l in text.split("\n"))
        found = [r for r in self.analyze(no_tables, language) if r.recognition_metadata.get("recognizer_name") == "PersonNer"]
        found += self.analyze(text, language, ner=False)
        return [KIND[r.entity_type] for r in found]

    def rejected(self) -> Counter:
        """spaCy PERSON hits that did not look like a person, by reason."""
        out = Counter()
        for rec in self.ner.values():
            out.update(rec.rejected)
        return out

    def mask_blocks(self, blocks, doc_id: str, language: str = "uk"):
        prev = ""
        for i, b in enumerate(blocks):
            original = b.text if b.kind != "table" else ""
            if b.kind == "table":
                b.rows = [[self.mask(c, doc_id, language, ner=False) for c in row] for row in b.rows]
                continue
            # A name cut by a line break: "..., L." + "Panarello, ..." in the next block.
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            m = re.search(r"\b[A-Z]\.$", b.text)
            if m and nxt is not None and nxt.kind == "text":
                first = re.match(r"([A-Z][a-z]{2,})\b", nxt.text)
                if first and first.group(1).lower() not in self.lower:
                    b.text = b.text[:m.start()] + "[NAME]"
                    nxt.text = nxt.text[first.end():]
                    self.counts[(doc_id, "name")] += 1
            b.text = self.mask(b.text, doc_id, language, before=prev)
            prev = original
        return blocks


@lru_cache(maxsize=1)
def _nlp_engine():
    """spaCy models loaded once per process (the tests build several maskers)."""
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    other = ["ORG", "LOC", "GPE", "NORP", "FAC", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE", "DATE",
             "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL", "MISC"]
    return NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": lang, "model_name": m} for lang, m in SPACY_MODELS.items()],
        "ner_model_configuration": {"model_to_presidio_entity_mapping": {"PER": "PERSON", "PERSON": "PERSON"},
                                    "labels_to_ignore": other,
                                    "low_confidence_score_multiplier": 1.0, "low_score_entity_names": []},
    }).create_engine()


def _rules_recognizer(lowercase: set[str], language: str):
    from presidio_analyzer import EntityRecognizer, RecognizerResult

    class AgroRules(EntityRecognizer):
        def load(self):
            pass

        def analyze(self, text, entities, nlp_artifacts=None):
            return [RecognizerResult(e, s, end, 1.0, recognition_metadata={"recognizer_name": "AgroRules"})
                    for e, s, end in rule_spans(text, lowercase) if e in entities]

    return AgroRules(supported_entities=list(REPLACE), supported_language=language, name="AgroRules")


def _person_ner(lowercase: set[str], language: str):
    from presidio_analyzer.predefined_recognizers import SpacyRecognizer

    class PersonNer(SpacyRecognizer):
        def __init__(self):
            super().__init__(supported_language=language, supported_entities=["PERSON"], name="PersonNer")
            self.rejected = Counter()
            self.before = ""

        def analyze(self, text, entities, nlp_artifacts=None):
            kept = []
            for r in super().analyze(text, entities, nlp_artifacts):
                ok, why = person_like(text, r.start, r.end, lowercase, self.before)
                if ok:
                    r.recognition_metadata = {**(r.recognition_metadata or {}), "recognizer_name": "PersonNer"}
                    kept.append(r)
                else:
                    self.rejected[why] += 1
            return kept

    return PersonNer()


def _is_cyr_name(m: re.Match, lowercase: set[str]) -> bool:
    """One initial + a word is a person unless: the word occurs in lower case ("°С. Кількість"),
    the "initial" is a section number in a heading or after "ЗМІСТ" ("## І. Огляд"),
    or it is a street ("вул. У. Самчука")."""
    if m.group(1).lower() in lowercase:
        return False
    before = m.string[:m.start()].rsplit("\n", 1)[-1]
    if re.fullmatch(r"#+\s*", before) or re.search(r"(?:ЗМІСТ|вул\.|просп\.|пр\.)\s*$", before):
        return False
    return True


def _is_surname(word: str, lowercase: set[str]) -> bool:
    return word.split()[-1].split("-")[-1].lower() not in lowercase


def latin_name_spans(text: str, lowercase: set[str]) -> list[tuple[int, int, int]]:
    """(start, end, number of surnames) of every Latin name or list of names, overlaps merged."""
    found = [(m.start(), m.end(), m.end(1)) for m in NAME_LATIN.finditer(text) if _is_surname(m.group(1), lowercase)]
    found += [(m.start(), m.end(), m.end(1)) for m in NAME_LATIN_AFTER.finditer(text)
              if _is_surname(m.group(1), lowercase)]
    found += [(m.start(), m.end(1), m.end(1)) for m in NAME_ET_AL.finditer(text) if _is_surname(m.group(1), lowercase)]
    merged: list[list] = []
    for start, end, surname in sorted(found):
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].add(surname)
        else:
            merged.append([start, end, {surname}])
    for span in merged:             # a surname without its initial at the head of a list: "Ben Aoun, Claverie, M."
        while (m := NAME_BEFORE_LIST.search(text[max(0, span[0] - 40):span[0]])) and _is_surname(m.group(1), lowercase):
            span[0] -= len(m.group(0))
            span[2].add(-span[0] - 1)
    return [(s, e, len(names)) for s, e, names in merged]


def lowercase_words(texts) -> set[str]:
    words = set()
    for t in texts:
        words.update(re.findall(r"[a-z]{3,}", t))
        words.update(re.findall(r"[а-яіїєґ’']{3,}", t))
    return words

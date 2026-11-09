"""Normalise the text of the blocks.

  * Unicode NFC, no soft hyphens / zero-width characters, one kind of space
  * a word broken by a hyphen at a line end is already glued by the readers ("пере-" + "нос")
  * letter-spaced words of the PDFs ("С т е п" -> "Степ")
  * words broken by a space inside ("п еріоду", "Тернопіль ській", "Ukrain e"): the two pieces are
    glued if the glued word occurs elsewhere in the corpus and one of the pieces is not a word on its
    own. The vocabulary comes from the corpus itself; every glued pair is logged (clean_log.csv)
  * no space before punctuation, single spaces
  * Latin look-alike letters inside Cyrillic words ("Франкiвська" with a Latin i) -> Cyrillic; in OCR
    text also the usual OCR confusions (u/и, m/т, n/п, w/ш) inside such words and "26%С" -> "26 °С".
    Every changed word is logged (letters_log.csv)

Tables are normalised cell by cell (NFC and spaces only): their numbers are never changed.
"""

import re
import unicodedata
from collections import Counter

WORD = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ’']+")
_INVISIBLE = re.compile(r"[­​‌‍﻿-]")
_SPACES = re.compile(r"[ \t   ]+")
_LETTER_SPACED = re.compile(r"(?<!\S)[А-ЯІЇЄҐа-яіїєґA-Za-z](?: [А-ЯІЇЄҐа-яіїєґA-Za-z]){3,}(?!\S)")
_SPACE_BEFORE_PUNCT = re.compile(r" +([,.;:!?)\]%])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[]) +")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE.sub("", text)
    text = text.replace("ʼ", "’").replace("`", "’")
    text = _SPACES.sub(" ", text)
    text = _LETTER_SPACED.sub(lambda m: m.group(0).replace(" ", ""), text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text)
    return text.strip()


def build_vocabulary(texts) -> Counter:
    vocab: Counter = Counter()
    for t in texts:
        vocab.update(w.lower() for w in WORD.findall(t))
    return vocab


# Latin letters that look like Cyrillic ones. Some files type the Ukrainian "і" as the Latin "i"
# ("Франкiвська"): for search that is another word. Only words that mix both alphabets are changed.
HOMOGLYPHS = str.maketrans("aceiopxyACEHIKMOPTXB", "асеіорхуАСЕНІКМОРТХВ")
# OCR also confuses these letters of the italic Cyrillic script; used in OCR text only.
OCR_CONFUSIONS = str.maketrans("umnw", "итпш")
_CYR = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
_LAT = re.compile(r"[A-Za-z]")
_OCR_DEGREE = re.compile(r"(\d)\s*%\s*([СC])\b")


def fix_homoglyphs(text: str, log: Counter, ocr: bool = False) -> str:
    """Latin look-alike letters inside a Cyrillic word -> Cyrillic ("Франкiвська" -> "Франківська")."""
    def fix(m):
        w = m.group(0)
        if not (_CYR.search(w) and _LAT.search(w)):
            return w
        new = w.translate(HOMOGLYPHS)
        if ocr:
            new = new.translate(OCR_CONFUSIONS)
        if new != w:
            log[f"{w} -> {new}"] += 1
        return new

    text = WORD.sub(fix, text)
    if ocr:
        text = _OCR_DEGREE.sub(r"\1 °С", text)       # "26%С" read by OCR -> "26 °С"
    return text


# Short words that are words on their own (never glued to the next word).
_STANDALONE = {"в", "у", "з", "і", "й", "а", "о", "та", "не", "на", "до", "за", "по", "від", "із", "зі",
               "a", "i", "in", "on", "of", "to", "at", "by", "an", "as", "is", "or", "the", "and"}


def join_broken_words(text: str, vocab: Counter, log: Counter, min_count: int = 2) -> str:
    """Glue "п еріоду" -> "періоду" when the glued word is a known word of the corpus."""
    tokens = text.split(" ")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        a = tokens[i]
        if i + 1 < len(tokens):
            b = tokens[i + 1]
            ma = re.fullmatch(r"(.*?)([A-Za-zА-Яа-яІіЇїЄєҐґ’']+)", a)
            mb = re.fullmatch(r"([A-Za-zА-Яа-яІіЇїЄєҐґ’']+)(.*)", b)
            if ma and mb and not ma.group(1).endswith(("-", "–")):
                left, right = ma.group(2), mb.group(1)
                glued = (left + right).lower()
                left_is_word = vocab[left.lower()] >= min_count or left.lower() in _STANDALONE
                right_is_word = vocab[right.lower()] >= min_count
                same_case = not (right[:1].isupper() and left[-1:].islower())
                if vocab[glued] >= min_count and same_case and not (left_is_word and right_is_word) \
                        and left.lower() not in _STANDALONE:
                    log[f"{left} {right} -> {left}{right}"] += 1
                    out.append(a + b)
                    i += 2
                    continue
        out.append(a)
        i += 1
    return " ".join(out)


def clean_blocks(blocks, vocab: Counter, log: Counter, letters_log: Counter | None = None):
    letters_log = letters_log if letters_log is not None else Counter()
    for b in blocks:
        if b.kind == "table":
            b.rows = [[fix_homoglyphs(normalize(c), letters_log, b.ocr) for c in row] for row in b.rows]
        else:
            b.text = join_broken_words(fix_homoglyphs(normalize(b.text), letters_log, b.ocr), vocab, log)
    from .ocr import is_map_place_names       # no heavy import: ocr.py imports easyocr only inside OcrReader

    return [b for b in blocks if b.kind == "table" or (b.text and not (b.ocr and b.kind == "text"
                                                                       and is_map_place_names(b.text)))]

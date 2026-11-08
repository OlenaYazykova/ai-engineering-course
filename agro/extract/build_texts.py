"""Cut the downloaded documents into short texts for homework 1 (data/extract/texts/).

Input:  data/raw/text/<doc_id>.txt           (made by `make fetch`, agro/corpus/fetch.py)
        data/extract/doc_ids.txt             the documents of homework 1: only these are cut, so documents
                                             added to the corpus later (homework 2) do not change it
Output: data/extract/texts/<doc_id>.txt      one text per document, ready for the model
        data/extract/texts_report.csv        what was found in every document and the text length

Rules:
  * uk_hydromet_*  one text per section, each with the bulletin period line:
                   <doc_id>__moisture.txt ("Зволоження ґрунту"), <doc_id>__growth.txt
                   ("Ріст і розвиток"), or a joint section used in late summer and autumn:
                   __growth_moisture ("Ріст, розвиток та вологозабезпечення") or
                   __conditions ("Агрометеорологічні умови, зволоження ґрунту, ріст ...");
                   winter bulletins have none of them: "Вплив погодних умов" is taken
  * en_jrcnews_*   the article without the site footer (survey, subscription, links)
  * en_jrc_*       the first pages of the bulletin (summary and crop conditions)
  * scans (no text layer) are skipped
Only runs of spaces are cleaned; typos and broken words are kept on purpose ("dirty" texts).

Usage:
    make extract-texts            (python -m agro.extract.build_texts)
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_TEXT = ROOT / "data" / "raw" / "text"
DOC_IDS = ROOT / "data" / "extract" / "doc_ids.txt"
OUT_DIR = ROOT / "data" / "extract" / "texts"
REPORT = ROOT / "data" / "extract" / "texts_report.csv"

MAX_CHARS = 6000          # about 1.5-2k tokens: safe for a small local model
MIN_TEXT_CHARS = 1000     # shorter raw text = scanned PDF without a text layer
JRC_PDF_PAGES = 2         # how many first pages of a JRC bulletin to keep


def ws(pattern: str) -> str:
    """Make a heading pattern tolerant to spaces inside words, line breaks and г/ґ spelling.

    Use the result with re.IGNORECASE: some bulletins write headings in CAPITALS.
    """
    def char(ch: str) -> str:
        if ch.isspace():
            return r"\s+"
        if ch.lower() in "гґ":
            return "[гґГҐ]"
        return re.escape(ch)

    return r"\s*".join(char(ch) for ch in pattern).replace(r"\s*\s+\s*", r"\s+")


# Bulletin headings (order matters: each section ends where the next known heading starts).
UK_HEADINGS = {
    "weather": ws("Метеорологічні умови"),
    "impact": ws("Вплив погодних умов"),
    "heat": ws("Теплозабезпечення"),
    "moisture": ws("Зволоження ґрунту"),
    "growth": ws("Ріст і розвиток"),
    # late summer / September: one joint section
    "growth_moisture": ws("Ріст, розвиток та вологозабезпечення"),
    # October: "Агрометеорологічні умови, зволоження ґрунту, ріст та розвиток ..." (one section)
    "conditions": ws("Агрометеорологічні умови, зволоження"),
}
UK_WANTED = ["moisture", "growth", "growth_moisture", "conditions"]
UK_FALLBACK = ["impact"]

# Back cover / imprint of a bulletin: everything from here on is not content.
UK_BACK_COVER = re.compile(
    r"Агрометеорологічний\s+бюлетень\s+по\s+території\s+України\s+№"
    r"|Державна\s+служба\s+України\s+з\s+надзвичайних\s+ситуацій"
    r"|Копіювання\s+матеріалів|Відповідальний\s+за\s+випуск",
    re.I,
)

PERIOD_RE = re.compile(r"за\s+(першу|другу|третю)\s+декаду\s+\w+\s+\d{4}\s*р\.?", re.I)

JRC_NEWS_FOOTER = re.compile(
    r"We need your help|Subscribe to the JRC MARS|JRC MARS \(Monitoring Agricultural Resources\)"
    r"|For comprehensive agricultural insights|The latest information about global agricultural",
    re.I,
)


def clean(text: str) -> str:
    text = re.sub(r"^--- page \d+ ---$", "", text, flags=re.M)
    text = re.sub(r"^\s*\d{1,2}\s*$", "", text, flags=re.M)      # lone page numbers
    text = re.sub(r"[ \t ]+", " ", text)                     # runs of spaces
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cut_hydromet(raw: str) -> list[tuple[str, str, str]]:
    """Return (file suffix, text, parts) for every text cut from one bulletin."""
    period = PERIOD_RE.search(raw)
    header = f"Агрометеорологічний бюлетень по території України {period.group(0)}" if period else ""

    starts = []
    for name, pattern in UK_HEADINGS.items():
        for m in re.finditer(r"(?mi)^\s*(" + pattern + ")", raw):
            # a heading starts with a capital letter; "зволоження ґрунту за прогнозом..." is text
            if m.group(1)[0].isupper():
                starts.append((m.start(), name))
    starts.sort()

    def section(name: str) -> str:
        parts = []
        for i, (pos, n) in enumerate(starts):
            if n == name:
                end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
                chunk = raw[pos:end]
                cover = UK_BACK_COVER.search(chunk)
                parts.append(chunk[: cover.start()] if cover else chunk)
        return "\n".join(parts)

    # Soil moisture and crop growth become two separate texts: both matter for the project
    # (moisture vs. ERA5 soil water, growth stage vs. NDVI/LAI and BBCH), and each stays short.
    found = [n for n in UK_WANTED if section(n).strip()]
    if found:
        return [(f"__{n}", clean(header + "\n\n" + section(n)), n) for n in found]
    found = [n for n in UK_FALLBACK if section(n).strip()]
    if found:
        return [("", clean(header + "\n\n" + section(found[0])), found[0])]
    first = starts[0][0] if starts else 0   # unknown layout: everything after the title pages
    return [("", clean(header + "\n\n" + raw[first:]), "whole")]


def cut_jrc_news(raw: str) -> list[tuple[str, str, str]]:
    m = JRC_NEWS_FOOTER.search(raw)
    return [("", clean(raw[: m.start()] if m else raw), "article" + ("-footer" if m else ""))]


def cut_jrc_pdf(raw: str) -> list[tuple[str, str, str]]:
    pages = re.split(r"^--- page \d+ ---$", raw, flags=re.M)
    pages = [p for p in pages if p.strip()]
    return [("", clean("\n".join(pages[:JRC_PDF_PAGES])), f"pages1-{JRC_PDF_PAGES}")]


def main() -> None:
    doc_ids = {line.strip() for line in DOC_IDS.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")}
    paths = [p for p in sorted(RAW_TEXT.glob("*.txt")) if p.stem in doc_ids]   # homework 1 documents only
    missing = sorted(doc_ids - {p.stem for p in paths})
    if missing:   # never delete the committed texts because the downloads are missing
        raise SystemExit(f"{len(missing)} of {len(doc_ids)} documents are not in {RAW_TEXT.relative_to(ROOT)}/ "
                         f"(e.g. {missing[0]}): run `make fetch` first")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.txt"):   # rebuild from scratch, no stale texts
        old.unlink()
    rows = []
    for path in paths:
        doc_id = path.stem
        raw = path.read_text(encoding="utf-8")
        if len(clean(raw)) < MIN_TEXT_CHARS:
            rows.append({"doc_id": doc_id, "parts": "SKIPPED: scan", "chars": 0, "truncated": ""})
            continue
        if doc_id.startswith("uk_hydromet"):
            pieces = cut_hydromet(raw)
        elif doc_id.startswith("en_jrcnews"):
            pieces = cut_jrc_news(raw)
        elif doc_id.startswith("en_jrc"):
            pieces = cut_jrc_pdf(raw)
        else:
            continue
        for suffix, text, parts in pieces:
            truncated = len(text) > MAX_CHARS
            if truncated:
                cut = text.rfind("\n", 0, MAX_CHARS)
                text = text[: cut if cut > MAX_CHARS // 2 else MAX_CHARS]
            text_id = doc_id + suffix
            (OUT_DIR / f"{text_id}.txt").write_text(text + "\n", encoding="utf-8")
            rows.append({"doc_id": text_id, "parts": parts, "chars": len(text),
                         "truncated": "yes" if truncated else ""})

    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doc_id", "parts", "chars", "truncated"])
        w.writeheader()
        w.writerows(rows)

    for r in rows:
        print(f"{r['doc_id']:<36} {r['parts']:<22} {r['chars']:>6} {r['truncated']}")
    made = sum(1 for r in rows if r["chars"])
    print(f"\n{made} texts in data/extract/texts/, report: data/extract/texts_report.csv")


if __name__ == "__main__":
    main()

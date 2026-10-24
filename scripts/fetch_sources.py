"""Download source documents for the Agro-analyst project and extract their text.

Sources (two languages, same kind of information: crop conditions, soil moisture, weather risks):
  * uk: decadal agrometeorological bulletins of the Ukrainian Hydrometeorological Center
        (mirrored as PDFs on agro.od.gov.ua, the Odesa Regional Administration agro department)
  * en: JRC MARS Bulletin - Global outlook - Crop monitoring in Ukraine (European Commission),
        full PDF bulletins plus the short JRC news articles that summarise them (plain prose)

Files already downloaded are not fetched again, so the script can be re-run safely.

Usage:
    pip install pypdf
    python scripts/fetch_sources.py            # discover + download + extract text
    python scripts/fetch_sources.py --list     # only show what would be downloaded

Output:
    data/raw/pdf/<doc_id>.pdf      original PDF files
    data/raw/html/<doc_id>.html    original web pages (JRC news)
    data/raw/text/<doc_id>.txt     full text extracted from the PDF
    data/sources.csv               doc_id, language, source, period, url, downloaded_at
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "pdf"
HTML_DIR = ROOT / "data" / "raw" / "html"
TEXT_DIR = ROOT / "data" / "raw" / "text"
SOURCES_CSV = ROOT / "data" / "sources.csv"

USER_AGENT = "Mozilla/5.0 (agro-analyst course project; contact via GitHub)"
TIMEOUT = 60

# How many Hydromet bulletins to take (spread over seasons and years).
HYDROMET_TARGET = 22

# Hydromet bulletins found by hand; used if the WordPress API search does not work.
HYDROMET_KNOWN = [
    "https://agro.od.gov.ua/wp-content/uploads/2021/08/agrometeorologichnyj_byuleten_08_01_2021.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/02/agrometeorologichnyj_byuleten_02_01_2022.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2022/09/agrometeorologichnyj_byuleten_08_03_2022.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2022/10/agrometeorologichnyj_byuleten_10_02_2022.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/04/agrometeorologichnyj_byuleten_03_03_2023.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/05/agrometeorologichnyj_byuleten_04_03_2023.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/07/agrometeorologichnyj_byuleten_07_01_2023.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/10/agrometeorologichnyj_byuleten_10_01_2023.pdf",
    "https://agro.od.gov.ua/wp-content/uploads/2023/10/agrometeorologichnyj_byuleten_10_02_2023.pdf",
]

# JRC MARS Global outlook bulletins on Ukraine (checked in the JRC Publications Repository).
JRC_BULLETINS = [
    ("JRC127973", "2022-06"),
    ("JRC133091", "2023-04"),
    ("JRC133193", "2023-06"),
    ("JRC133194", "2023-09"),
    ("JRC136677", "2024-06"),
    ("JRC136678", "2024-09"),
    ("JRC141670", "2025-06"),
    ("JRC141671", "2025-09"),
    ("JRC146592", "2026-06"),
    ("JRC146602", "2026-09"),
]
JRC_PDF = "https://publications.jrc.ec.europa.eu/repository/bitstream/{id}/{id}_01.pdf"

# Short JRC news articles (plain prose, no tables) that summarise the Ukraine bulletins.
JRC_NEWS_BASE = "https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/"
JRC_NEWS = [
    ("mediocre-yield-outlook-winter-crops-ukraine-2022-06-13_en", "2022-06"),
    ("fair-yield-outlook-reduced-production-areas-ukraine-2022-09-12_en", "2022-09"),
    ("fair-positive-outlook-winter-crops-ukraine-2023-04-03_en", "2023-04"),
    ("below-average-outlook-winter-crops-ukraine-2024-06-17_en", "2024-06"),
    ("average-yield-outlook-winter-crops-ukraine-june-2025-2025-06-16_en", "2025-06"),
    ("contrasting-yield-outlooks-summer-crops-ukraine-september-2025-2025-09-15_en", "2025-09"),
    ("favourable-conditions-winter-crops-2026-06-15_en", "2026-06"),
    ("fair-summer-crop-yields-expected-ukraine-2026-09-21_en", "2026-09"),
]

# Text shorter than this means the PDF is a scan (images only) and needs OCR.
MIN_TEXT_CHARS = 1000

# File name pattern: agrometeorologichnyj_byuleten_<month>_<decade>_<year>.pdf
HYDROMET_NAME = re.compile(r"agrometeorologichnyj_byuleten_(\d{2})_(\d{2})_(\d{4})\.pdf$", re.I)


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def discover_hydromet() -> list[str]:
    """Ask the WordPress REST API of agro.od.gov.ua for every uploaded bulletin PDF."""
    found: set[str] = set(HYDROMET_KNOWN)
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"search": "agrometeorologichnyj_byuleten", "per_page": 100, "page": page,
             "media_type": "application", "_fields": "source_url"}
        )
        url = f"https://agro.od.gov.ua/wp-json/wp/v2/media?{query}"
        try:
            items = json.loads(http_get(url))
        except Exception as e:  # API closed, page out of range, network error
            if page == 1:
                print(f"  WordPress API not available ({type(e).__name__}); using the known list only")
            break
        if not items:
            break
        for item in items:
            src = item.get("source_url", "")
            if HYDROMET_NAME.search(src):
                found.add(src)
        page += 1
        time.sleep(0.5)
    return sorted(found)


def pick_spread(urls: list[str], n: int) -> list[tuple[str, str]]:
    """Pick n bulletins spread over years and seasons. Returns (url, period 'YYYY-MM-dD')."""
    parsed = []
    for u in urls:
        m = HYDROMET_NAME.search(u)
        if m:
            month, decade, year = m.groups()
            parsed.append((u, f"{year}-{month}-d{int(decade)}", int(year), int(month)))
    # Round-robin over (year, month): first one bulletin per month, then add more.
    by_key: dict[tuple[int, int], list] = {}
    for item in sorted(parsed, key=lambda x: x[1]):
        by_key.setdefault((item[2], item[3]), []).append(item)
    chosen = []
    while len(chosen) < n and any(by_key.values()):
        for key in sorted(by_key):
            if by_key[key] and len(chosen) < n:
                chosen.append(by_key[key].pop(0))
    return [(u, period) for u, period, _, _ in sorted(chosen, key=lambda x: x[1])]


class _ParagraphParser(HTMLParser):
    """Collect the text of <h1>, <h2>, <h3> and <p> elements of a web page."""

    BLOCKS = {"h1", "h2", "h3", "p", "li"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._depth = 0
        self._buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip += 1
        elif tag in self.BLOCKS:
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCKS and self._depth:
            self._depth -= 1
            text = " ".join("".join(self._buf).split())
            if text:
                self.parts.append(text)
            self._buf = []

    def handle_data(self, data):
        if self._depth and not self._skip:
            self._buf.append(data)


def html_to_text(html: str) -> str:
    """Keep the article: from the first heading to the end, skipping short menu items."""
    parser = _ParagraphParser()
    parser.feed(html)
    parts = [p for p in parser.parts if len(p) > 30 or p.endswith(".")]
    return "\n\n".join(parts)


def pdf_to_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [f"--- page {i} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages, 1)]
    return "\n".join(pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="only list the documents")
    args = parser.parse_args()

    print("Looking for Hydromet bulletins...")
    hydromet_all = discover_hydromet()
    hydromet = pick_spread(hydromet_all, HYDROMET_TARGET)
    print(f"  found {len(hydromet_all)}, taking {len(hydromet)}")

    docs = [
        (f"uk_hydromet_{period}", "uk", "Ukrhydrometcenter bulletin", period, url)
        for url, period in hydromet
    ] + [
        (f"en_jrc_{period}", "en", "JRC MARS Global outlook Ukraine", period, JRC_PDF.format(id=jid))
        for jid, period in JRC_BULLETINS
    ] + [
        (f"en_jrcnews_{period}", "en", "JRC news (bulletin summary)", period, JRC_NEWS_BASE + slug)
        for slug, period in JRC_NEWS
    ]

    if args.list:
        for doc_id, lang, _, _, url in docs:
            print(f"{doc_id:<28} {lang}  {url}")
        print(f"\n{len(docs)} documents")
        return

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc_id, lang, source, period, url in docs:
        is_html = not url.lower().endswith(".pdf")
        raw_path = (HTML_DIR / f"{doc_id}.html") if is_html else (PDF_DIR / f"{doc_id}.pdf")
        try:
            if not raw_path.exists():  # already downloaded files are not fetched again
                raw_path.write_bytes(http_get(url))
                time.sleep(1)
            if is_html:
                text = html_to_text(raw_path.read_text(encoding="utf-8", errors="replace"))
            else:
                text = pdf_to_text(raw_path)
            (TEXT_DIR / f"{doc_id}.txt").write_text(text, encoding="utf-8")
            chars = len(text.replace("--- page", "").strip())
            status = f"ok, {len(text)} chars"
            if not is_html and chars < MIN_TEXT_CHARS:
                status = f"SCAN (no text layer, {len(text)} chars) - skip or OCR"
        except Exception as e:
            status = f"FAILED: {type(e).__name__}: {e}"
        print(f"{doc_id:<28} {status}")
        rows.append({
            "doc_id": doc_id, "language": lang, "source": source, "period": period, "url": url,
            "downloaded_at": datetime.now(timezone.utc).date().isoformat(), "status": status,
        })

    with SOURCES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {SOURCES_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())

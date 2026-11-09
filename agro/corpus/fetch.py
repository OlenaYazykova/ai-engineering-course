"""Download every document listed in data/sources.csv into data/raw/<format>/<doc_id>.<ext>.

    make fetch                          # or: python -m agro.corpus.fetch
    python -m agro.corpus.fetch --list  # only list the documents

Already downloaded files are not fetched again. Documents that can only be downloaded by hand
(an export from a web interface) are reported with instructions.

For homework 1 the script also writes the plain text of every PDF / HTML document into
data/raw/text/<doc_id>.txt (with `--- page N ---` markers); `make extract-texts` cuts those into
the texts of homework 1. Homework 2 parses the originals itself (agro/corpus/ingest.py).

Sources (see data/sources.csv for every URL):
  * Ukrhydrometcenter decadal agrometeorological bulletins (uk, PDF): mirror on the site of the
    agro department of the Odesa oblast administration, agro.od.gov.ua
  * Ukrhydrometcenter annual weather reviews (uk, PDF / DOCX / DOC): open data portal data.gov.ua
  * JRC MARS Bulletin - Global outlook: Ukraine (en, PDF): JRC Publications Repository
  * JRC news articles summarising those bulletins (en, HTML)
  * Odesa oblast statistics office, crop production (uk, XLSX)
  * State Statistics Service of Ukraine, areas / gross harvests / yields by region (en, CSV, manual)
"""

import argparse
import sys
import time
import urllib.request
from html.parser import HTMLParser

from ..common.settings import RAW, ROOT
from .registry import load_registry

TEXT_DIR = RAW / "text"
USER_AGENT = "Mozilla/5.0 (agro-analyst course project; contact via GitHub)"
TIMEOUT = 60

# Text shorter than this means the PDF is a scan (images only) and needs OCR.
MIN_TEXT_CHARS = 1000

# Documents that are not plain downloads: what to do by hand.
MANUAL = {
    "en_derzhstat_crops_annual": (
        "open the URL in a browser (Dataset Explorer of the State Statistics Service), "
        "export the whole dataset as CSV and save it as {path}"
    ),
}


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


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


def pdf_to_text(pdf_path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [f"--- page {i} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages, 1)]
    return "\n".join(pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="only list the documents")
    args = parser.parse_args()

    docs = load_registry()
    if args.list:
        for d in docs:
            print(f"{d.doc_id:<30} {d.format:<5} {d.language}  {d.url}")
        print(f"\n{len(docs)} documents")
        return

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    missing = 0
    for d in docs:
        path = d.raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not path.exists():  # already downloaded files are not fetched again
                if d.doc_id in MANUAL:
                    missing += 1
                    print(f"{d.doc_id:<30} MANUAL: " + MANUAL[d.doc_id].format(path=path.relative_to(ROOT)))
                    print(f"{'':<30} {d.url}")
                    continue
                path.write_bytes(http_get(d.url))
                time.sleep(1)
            status = f"ok, {path.stat().st_size // 1024} KB"
            if d.format in ("pdf", "html"):  # plain text for homework 1
                if d.format == "html":
                    text = html_to_text(path.read_text(encoding="utf-8", errors="replace"))
                else:
                    text = pdf_to_text(path)
                (TEXT_DIR / f"{d.doc_id}.txt").write_text(text, encoding="utf-8")
                if d.format == "pdf" and len(text.replace("--- page", "").strip()) < MIN_TEXT_CHARS:
                    status += ", SCAN (no text layer): read with OCR"
        except Exception as e:
            missing += 1
            status = f"FAILED: {type(e).__name__}: {e}"
        print(f"{d.doc_id:<30} {status}")
    print(f"\n{len(docs) - missing} of {len(docs)} documents in {RAW.relative_to(ROOT)}/")


if __name__ == "__main__":
    sys.exit(main())

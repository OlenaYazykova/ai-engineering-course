"""The registry of documents: data/sources.csv, one row per document.

Columns: doc_id, format (pdf/html/docx/doc/xlsx/csv), language, source, title, period, effective
(the date the document describes or was published; the newer document wins when two disagree),
topic, ocr ('' / 'all' / 'all except:2,9' / 'pages:12,13'), url, downloaded_at, note.
"""

import csv
import re
from dataclasses import dataclass

from ..common.settings import RAW, SOURCES_CSV

EXTENSIONS = {"pdf": "pdf", "html": "html", "docx": "docx", "doc": "doc", "xlsx": "xlsx", "csv": "csv"}


@dataclass(frozen=True)
class DocMeta:
    doc_id: str
    format: str
    language: str
    source: str
    title: str
    period: str
    effective: str
    topic: str
    ocr: str
    url: str
    downloaded_at: str = ""
    note: str = ""

    @property
    def raw_path(self):
        return RAW / self.format / f"{self.doc_id}.{EXTENSIONS[self.format]}"

    @property
    def year(self) -> int | None:
        m = re.match(r"(\d{4})", self.period)
        return int(m.group(1)) if m else None

    @property
    def month(self) -> int | None:
        m = re.match(r"\d{4}-(\d{2})(?!\d)", self.period)       # "2019-2025" is a span of years, not a month
        return int(m.group(1)) if m else None

    @property
    def decade(self) -> int | None:
        m = re.search(r"-d(\d)$", self.period)
        return int(m.group(1)) if m else None

    @property
    def ocr_whole_scan(self) -> bool:
        """The whole document is a scan ('all' / 'all except:...'), not single table pages."""
        return self.ocr.startswith("all")

    def ocr_pages(self, n_pages: int) -> set[int]:
        """1-based page numbers to read with OCR."""
        if self.ocr == "all":
            return set(range(1, n_pages + 1))
        if self.ocr.startswith("all except:"):
            skip = {int(p) for p in self.ocr[len("all except:"):].split(",") if p.strip()}
            return set(range(1, n_pages + 1)) - skip
        if self.ocr.startswith("pages:"):
            return {int(p) for p in self.ocr[len("pages:"):].split(",") if p.strip()}
        return set()


def load_registry() -> list[DocMeta]:
    with SOURCES_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    docs = [DocMeta(**{k: (v or "") for k, v in row.items()}) for row in rows]
    ids = [d.doc_id for d in docs]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"duplicate doc_id in {SOURCES_CSV.name}: {sorted(dup)}")
    bad = [d.doc_id for d in docs if d.format not in EXTENSIONS]
    if bad:
        raise SystemExit(f"unknown format in {SOURCES_CSV.name}: {bad}")
    return docs

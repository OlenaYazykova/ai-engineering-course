"""OCR for PDF pages that have no text layer (a scanned bulletin) or keep a table as a picture.

EasyOCR (Ukrainian + English) reads a page rendered at 200 dpi. Its models are downloaded once
into MODELS_DIR/easyocr (about 100 MB). Results are cached by the ingestion step, so OCR runs only
when the file or the pipeline version changes.

Which pages to read is set in data/sources.csv, column `ocr`: 'all' for a scan, 'pages:12' for
single pages (then the page is read as a table: words are grouped into rows by their position).
"""

import re
import statistics

from ..common.settings import MODELS_DIR, use_local_model_dirs
from .extract import Block, _known_heading

DPI = 200              # 300 dpi was tried for the tables: more digits misread as letters (6 -> Б)
MIN_CONFIDENCE = 0.35  # words read with less confidence are dropped (mostly labels on maps)
# The language model of the reader follows the document: Ukrainian + English for a Ukrainian scan,
# English only for the JRC tables (with Cyrillic on, digits were read as Cyrillic letters).
LANGUAGES = {"uk": ("uk", "en"), "en": ("en",)}


def is_map_labels(line: str) -> bool:
    """A line of place names and numbers read from a map, not a sentence ("27 26 Черніаів 27 8 Рівне 18")."""
    tokens = line.split()
    numbers = sum(1 for t in tokens if any(ch.isdigit() for ch in t))
    return len(tokens) >= 4 and numbers / len(tokens) >= 0.4 and not any(t.endswith(".") for t in tokens[-1:])


def is_map_place_names(text: str) -> bool:
    """A paragraph of only place names read from a map, without numbers ("Чернав Пуцьк Сун": Чернігів,
    Луцьк, Суми): 3-6 capitalised words, no digit, no punctuation. Applied to OCR text blocks when
    cleaning (a heading always has a lower-case word)."""
    tokens = text.split()
    return 3 <= len(tokens) <= 6 and all(t[0].isupper() for t in tokens) and not re.search(r"[\d.,:;!?()%°]", text)


class OcrReader:
    def __init__(self, languages=("uk", "en")) -> None:
        use_local_model_dirs()
        import easyocr  # heavy import (torch): only when OCR is needed

        model_dir = MODELS_DIR / "easyocr"
        model_dir.mkdir(parents=True, exist_ok=True)
        self.reader = easyocr.Reader(list(languages), gpu=False, model_storage_directory=str(model_dir),
                                     user_network_directory=str(model_dir / "user_network"), verbose=False)

    def _words(self, page, dpi: int = DPI, min_conf: float = 0.0):
        import numpy as np

        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        words = []
        for box, text, conf in self.reader.readtext(img, detail=1, paragraph=False):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            if text.strip() and conf >= min_conf:
                words.append({"text": text.strip(), "x0": min(xs), "x1": max(xs), "top": min(ys),
                              "bottom": max(ys), "conf": float(conf)})
        return words

    @staticmethod
    def _rows(words):
        """Group words into lines by their vertical position, left to right inside a line."""
        if not words:
            return [], 0.0
        height = statistics.median(w["bottom"] - w["top"] for w in words)
        rows = []
        for w in sorted(words, key=lambda w: (w["top"] + w["bottom"]) / 2):
            mid = (w["top"] + w["bottom"]) / 2
            if rows and abs(mid - rows[-1]["mid"]) < 0.6 * height:
                rows[-1]["words"].append(w)
            else:
                rows.append({"mid": mid, "words": [w], "top": w["top"]})
        for r in rows:
            r["words"].sort(key=lambda w: w["x0"])
        return rows, height

    def read_page(self, page, page_no: int, as_table: bool = False) -> list[Block]:
        words = self._words(page) if as_table else self._words(page, min_conf=MIN_CONFIDENCE)
        if not words:
            return []
        rows, height = self._rows(words)
        if as_table:
            # A picture of a table: each line is a row; cells are split where the gap is wide.
            table = []
            for r in rows:
                cells, cur = [], [r["words"][0]]
                for a, b in zip(r["words"], r["words"][1:]):
                    if b["x0"] - a["x1"] > 1.2 * height:
                        cells.append(" ".join(w["text"] for w in cur))
                        cur = []
                    cur.append(b)
                cells.append(" ".join(w["text"] for w in cur))
                table.append(cells)
            return [Block("table", rows=table, page=page_no, ocr=True)]
        # A scanned page of text: lines -> paragraphs at wide vertical gaps.
        blocks, para, prev = [], [], None
        for r in rows:
            line = " ".join(w["text"] for w in r["words"])
            if is_map_labels(line):
                continue
            if _known_heading(line) and len(line) <= 80:
                if para:
                    blocks.append(Block("text", " ".join(para), page=page_no, ocr=True))
                    para = []
                blocks.append(Block("heading", line, page=page_no, ocr=True))
                prev = r
                continue
            if prev is not None and r["top"] - prev["mid"] > 1.6 * height and para:
                blocks.append(Block("text", " ".join(para), page=page_no, ocr=True))
                para = []
            if para and para[-1].endswith("-") and line[:1].islower():
                para[-1] = para[-1][:-1] + line
            else:
                para.append(line)
            prev = r
        if para:
            blocks.append(Block("text", " ".join(para), page=page_no, ocr=True))
        return blocks

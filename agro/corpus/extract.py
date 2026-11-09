"""Read one original document into a list of blocks: headings, paragraphs and tables.

One reader per format:
  * PDF  (pdfplumber): lines with their font size and position -> headings and paragraphs; tables
         are found on the page, kept as tables and cut out of the running text; pages listed in
         the `ocr` column of the registry are read with OCR (agro/corpus/ocr.py)
  * HTML (BeautifulSoup): the article body; menus, footers and the "subscribe" tail are dropped
  * DOCX (python-docx): paragraphs and tables in document order, Word heading styles -> headings
  * DOC  (LibreOffice converts it to DOCX, then as DOCX)
  * XLSX (openpyxl): title rows -> heading, the header row + data rows -> a table, notes -> text
  * CSV  (pandas): the State Statistics Service export; only the subset described by DERZHSTAT_*
         is taken (the export has 65k rows, most of them not about crops)

Blocks keep the page number (PDF) so that a citation can point to the page.
"""

import re
import statistics
import subprocess
from dataclasses import asdict, dataclass, field

from ..common.settings import CACHE
from .registry import DocMeta


@dataclass
class Block:
    kind: str                 # heading | text | table
    text: str = ""            # heading or paragraph text
    level: int = 2            # heading level (1 = document title)
    rows: list = field(default_factory=list)   # table: list of rows, row 0 is the header
    page: int | None = None
    ocr: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- helpers

def _clean_cell(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def _is_number(s: str) -> bool:
    return bool(re.fullmatch(r"[-+–]?\d[\d\s.,]*%?|[-–]|\.\.|…", s.strip()))


def _good_table(rows: list[list[str]]) -> bool:
    """A real table, not text set in columns: several rows and columns, short cells, some numbers."""
    rows = [r for r in rows if any(r)]
    if len(rows) < 2 or max(len(r) for r in rows) < 2:
        return False
    cells = [c for r in rows for c in r if c]
    if not cells:
        return False
    numeric = sum(_is_number(c) for c in cells) / len(cells)
    avg_len = sum(len(c) for c in cells) / len(cells)
    cols = max(len(r) for r in rows)
    if _is_toc(rows):
        return False
    return (numeric >= 0.25 and avg_len <= 40) or (len(rows) >= 3 and cols >= 3 and avg_len <= 80)


def _is_toc(rows: list[list[str]]) -> bool:
    """A table of contents set as a table ("Огляд погоди ....... 5")."""
    return sum(bool(re.search(r"\.{6,}|…{3,}", c)) for r in rows for c in r if c) >= 2


def _merge_title_headings(blocks: list["Block"]) -> list["Block"]:
    """A title set in capitals over several lines ("ОГЛЯД" / "ПОГОДИ ТА СТИХІЙНИХ" / ...) -> one heading."""
    out: list[Block] = []
    for b in blocks:
        prev = out[-1] if out else None
        if b.kind == "heading" and prev is not None and prev.kind == "heading" and prev.page == b.page \
                and prev.text.isupper() and b.text.isupper():
            prev.text = f"{prev.text} {b.text}"
            continue
        out.append(b)
    return out


def _drop_empty_columns(rows: list[list[str]]) -> list[list[str]]:
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(r[j] for r in rows)]
    return [[r[j] for j in keep] for r in rows if any(r[j] for j in keep)]


# ---------------------------------------------------------------- PDF

# Section titles of the Hydromet bulletins: they are set in the same font as the body text, so the
# font size alone does not find them. Spaces inside words are allowed (the PDFs have "Зволо ження").
HYDROMET_HEADINGS = [
    "Метеорологічні умови", "Вплив погодних умов", "Теплозабезпечення", "Зволоження ґрунту",
    "Ріст і розвиток", "Ріст, розвиток та вологозабезпечення", "Агрометеорологічні умови",
    "Стан посівів", "Небезпечні явища", "Стихійні явища", "Огляд погоди",
    "Агрометеорологічні умови перезимівлі", "Стан озимих культур",
]
_HEADING_RES = [re.compile(r"^\s*" + r"\s*".join(map(re.escape, h.replace(" ", ""))) + r"\b", re.I)
                for h in HYDROMET_HEADINGS]
ROMAN_HEADING = re.compile(r"^\s*[IІVХX]{1,4}\.\s+\S")            # "ІІ. Стихійні явища"
NUMBERED_HEADING = re.compile(r"^\s*\d{1,2}(\.\d{1,2}){0,2}\.?\s+[A-ZА-ЯІЇЄҐ]")   # "1.1. Autumn/winter"
TOC_LINE = re.compile(r"(\.{4,}|…{2,}|_{4,})\s*\d+\s*$")           # table of contents
BOILERPLATE = re.compile(
    r"Відповідальний\s+(за\s+випуск|редактор)|©|Копіювання\s+матеріалів|тел\.\s*\d|"
    r"\b\d{5},\s*Київ|ISSN|ISBN|Видається\s+з\s+\d{4}|mars-stat@|doi\.org|"
    r"All\s+rights\s+reserved|Reproduction\s+is\s+authorised|e-mail:|^Web:|Факс|^Тел\.?:", re.I)


def _known_heading(text: str) -> bool:
    return text[:1].isupper() and any(r.match(text) for r in _HEADING_RES)


def _line_is_heading(text: str, size: float, body: float, max_width_ratio: float) -> bool:
    t = text.strip()
    if not t or len(t) > 110 or TOC_LINE.search(t):
        return False
    if _known_heading(t) and len(t) <= 80 and not t.endswith(".") and max_width_ratio < 0.8:
        return True
    if size >= body + 1.5 and len(t) <= 110 and not (t.endswith(".") and len(t) > 40):
        return True
    if (ROMAN_HEADING.match(t) or NUMBERED_HEADING.match(t)) and len(t) <= 90 and max_width_ratio < 0.85 \
            and not t.endswith("."):
        return True
    return False


_PRIVATE = re.compile(r"[\ue000-\uf8ff\u200b\ufeff]")   # icon fonts, zero-width characters


def _page_lines(page, tables) -> list[dict]:
    """Text lines of a PDF page outside the tables: text, bbox, font size."""
    mid = float(page.rect.width) / 2
    def in_table(x0, y0, x1, y1):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return any(tx0 <= cx <= tx1 and ty0 <= cy <= ty1 for (tx0, ty0, tx1, ty1), _ in tables)

    lines = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        parts = []
        for line in block["lines"]:
            spans = [s for s in line["spans"] if _PRIVATE.sub("", s["text"]).strip()]
            if not spans:
                continue
            # One PDF "line" may run over both columns: cut it at a wide gap over the middle of the page.
            segments, cur = [], [spans[0]]
            for a, b in zip(spans, spans[1:]):
                if a["bbox"][2] < mid < b["bbox"][0] and b["bbox"][0] - a["bbox"][2] > 1.0 * b["size"]:
                    segments.append(cur)
                    cur = []
                cur.append(b)
            segments.append(cur)
            for seg in segments:
                x0 = min(s["bbox"][0] for s in seg)
                x1 = max(s["bbox"][2] for s in seg)
                y0 = min(s["bbox"][1] for s in seg)
                y1 = max(s["bbox"][3] for s in seg)
                if in_table(x0, y0, x1, y1):
                    continue
                text = ""
                for k, s in enumerate(seg):            # spans of one line: keep the spaces between them
                    if k and s["bbox"][0] - seg[k - 1]["bbox"][2] > 0.15 * s["size"] and not text.endswith(" "):
                        text += " "
                    text += s["text"]
                text = " ".join(_PRIVATE.sub("", text).split())
                if text:
                    parts.append({"text": text, "x0": x0, "top": y0, "x1": x1, "bottom": y1,
                                  "size": max(s["size"] for s in seg)})
        # Justified text comes as one "line" per word: glue the pieces of one block on the same baseline.
        parts.sort(key=lambda p: (round(p["top"]), p["x0"]))
        for p in parts:
            last = lines[-1] if lines and lines[-1].get("_block") == id(block) else None
            gap = p["x0"] - last["x1"] if last else 0
            crosses_gutter = last is not None and last["x1"] < mid < p["x0"] and gap > 3.5 * p["size"]
            if last and abs(p["top"] - last["top"]) < 2.5 and gap >= -1 and not crosses_gutter:
                last["text"] += " " + p["text"]
                last["x1"] = max(last["x1"], p["x1"])
                last["bottom"] = max(last["bottom"], p["bottom"])
                last["size"] = max(last["size"], p["size"])
            else:
                p["_block"] = id(block)
                lines.append(p)
    return lines


def _reading_order(lines: list[dict], page_width: float) -> list[dict]:
    """Two-column pages (JRC bulletins): left column first, then the right one, between full-width lines."""
    mid = page_width / 2
    for l in lines:
        l["col"] = "L" if l["x1"] < mid + 6 else ("R" if l["x0"] > mid - 6 else "F")
    lines = sorted(lines, key=lambda l: (round(l["top"]), l["x0"]))
    if sum(l["col"] == "L" for l in lines) < 3 or sum(l["col"] == "R" for l in lines) < 3:
        for l in lines:
            l["col"] = "F"
        return lines
    out, run = [], []
    for l in lines:
        if l["col"] == "F":
            out += [x for x in run if x["col"] == "L"] + [x for x in run if x["col"] == "R"]
            run = []
            out.append(l)
        else:
            run.append(l)
    return out + [x for x in run if x["col"] == "L"] + [x for x in run if x["col"] == "R"]


def _table_rows(table, words) -> list[list[str]]:
    """Cell texts from the words inside every cell box.

    The table's own text extraction puts a decimal point on the wrong line when it is set a little
    lower than the digits ("4.22" came out as "422\n."); the words of the page keep "4.22".
    """
    rows = []
    for row in table.rows:
        cells = []
        for box in row.cells:
            if box is None:
                cells.append("")
                continue
            x0, y0, x1, y1 = box
            inside = [w for w in words
                      if x0 - 1 <= (w[0] + w[2]) / 2 <= x1 + 1 and y0 - 1 <= (w[1] + w[3]) / 2 <= y1 + 1]
            inside.sort(key=lambda w: (round(w[1]), w[0]))
            cells.append(_clean_cell(" ".join(w[4] for w in inside)))
        rows.append(cells)
    return rows


def _pdf_page_blocks(page, page_no: int) -> list[Block]:
    tables = []
    try:
        found = page.find_tables().tables
    except Exception:          # damaged drawings on a page: no tables then
        found = []
    words = page.get_text("words") if found else []
    for t in found:
        rows = _table_rows(t, words)
        if _good_table(rows):
            tables.append((tuple(t.bbox), _drop_empty_columns(rows)))
    lines = _reading_order(_page_lines(page, tables), float(page.rect.width))
    blocks: list[Block] = []
    if not lines and not tables:
        return blocks
    sizes = [round(l["size"], 1) for l in lines]
    body = statistics.mode(sizes) if sizes else 10.0
    lefts = {c: min((l["x0"] for l in lines if l["col"] == c), default=0) for c in "LRF"}
    width = max((l["x1"] - lefts[l["col"]] for l in lines), default=1) or 1
    gaps = [b["top"] - a["bottom"] for a, b in zip(lines, lines[1:])
            if a["col"] == b["col"] and 0 <= b["top"] - a["bottom"] < 30]
    gap = statistics.median(gaps) if gaps else 3.0

    pending = sorted(tables, key=lambda t: t[0][1])    # tables go between the lines by their top
    para: list[str] = []
    prev = None

    def flush():
        if para:
            blocks.append(Block("text", " ".join(para), page=page_no))
            para.clear()

    for line in lines:
        while pending and pending[0][0][1] < line["top"] and line["col"] == "F":
            flush()
            blocks.append(Block("table", rows=pending.pop(0)[1], page=page_no))
        text = line["text"]
        left = lefts[line["col"]]
        if _line_is_heading(text, line["size"], body, (line["x1"] - left) / width):
            flush()
            if blocks and blocks[-1].kind == "heading" and blocks[-1].page == page_no and prev is not None \
                    and prev.get("heading") and (0 <= line["top"] - prev["bottom"] < 2 * gap + 6 or text[:1].islower()):
                blocks[-1].text += " " + text          # a heading set on two lines
            else:
                blocks.append(Block("heading", text, level=2, page=page_no))
            line["heading"] = True
            prev = line
            continue
        bullet = re.match(r"^[•▪●◦‣]\s*", text)
        if bullet:                                 # a list item: its own paragraph, Markdown "- "
            flush()
            text = "- " + text[bullet.end():]
            para.append(text)
            prev = line
            continue
        new_para = prev is None or prev.get("heading") or line["col"] != prev["col"] \
            or not (0 <= line["top"] - prev["bottom"] <= max(1.6 * gap, gap + 3)) \
            or (line["x0"] - left > 12 and (prev["x1"] - lefts[prev["col"]]) / width < 0.9)
        if new_para and not (para and para[-1].endswith("-") and line["col"] != prev["col"]):
            flush()
        if para and para[-1].endswith("-") and text[:1].islower():
            para[-1] = para[-1][:-1] + text            # word broken by a hyphen at the line end
        else:
            para.append(text)
        prev = line
    flush()
    for _, rows in pending:
        blocks.append(Block("table", rows=rows, page=page_no))
    return blocks


def _repeated_lines(pages_text: list[list[str]]) -> set[str]:
    """Running headers and footers: the same line (digits ignored) on many pages."""
    if len(pages_text) < 4:
        return set()
    seen: dict[str, int] = {}
    for lines in pages_text:
        for key in {re.sub(r"\d+", "#", l.strip()) for l in lines if 3 < len(l.strip()) < 120}:
            seen[key] = seen.get(key, 0) + 1
    limit = max(3, int(0.3 * len(pages_text)))
    return {k for k, n in seen.items() if n >= limit}


def read_pdf(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    import pymupdf

    blocks: list[Block] = []
    info = {"pages": 0, "ocr_pages": [], "dropped_lines": 0}
    with pymupdf.open(meta.raw_path) as pdf:
        info["pages"] = pdf.page_count
        ocr_pages = meta.ocr_pages(pdf.page_count)
        per_page = []
        for i, page in enumerate(pdf, 1):
            if i in ocr_pages and ocr_reader is not None:
                try:
                    per_page.append(ocr_reader.read_page(page, i, as_table=meta.ocr != "all",
                                                         language=meta.language))
                    info["ocr_pages"].append(i)
                except Exception as e:      # no OCR installed: the rest of the document is still read
                    info.setdefault("ocr_failed", []).append(i)
                    info["ocr_error"] = f"{type(e).__name__}: {e}"
                    per_page.append(_pdf_page_blocks(page, i))
            else:
                per_page.append(_pdf_page_blocks(page, i))
    repeated = _repeated_lines([[b.text for b in pb if b.kind != "table"] for pb in per_page])
    for page_blocks in per_page:
        for b in page_blocks:
            if b.kind != "table" and not b.ocr:
                key = re.sub(r"\d+", "#", b.text.strip())
                if key in repeated or re.fullmatch(r"\d{1,3}", b.text.strip()) or BOILERPLATE.search(b.text) \
                        or TOC_LINE.search(b.text):
                    info["dropped_lines"] += 1
                    continue
            # A paragraph cut by a page or column break goes on with a small letter: glue it back.
            prev = blocks[-1] if blocks else None
            if b.kind == "text" and prev is not None and prev.kind == "text" and b.text[:1].islower() \
                    and not prev.text.rstrip().endswith((".", ":", "!", "?")):
                prev.text = (prev.text[:-1] + b.text) if prev.text.endswith("-") else (prev.text + " " + b.text)
                continue
            blocks.append(b)
    return _merge_title_headings(blocks), info


# ---------------------------------------------------------------- HTML

JRC_NEWS_TAIL = re.compile(
    r"We need your help|Subscribe to the JRC MARS|For comprehensive agricultural insights|"
    r"The latest information about global agricultural|Related content|Share this page|"
    r"^Further (agricultural )?information$", re.I)
JRC_NEWS_SKIP = re.compile(r"Bulletin survey|user survey|survey takes only", re.I)   # invitation to a survey


def read_html(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(meta.raw_path.read_bytes(), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "button"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks: list[Block] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]):
        if el.name != "table" and el.find_parent("table"):
            continue
        if el.name == "table":
            rows = [[_clean_cell(c.get_text(" ")) for c in tr.find_all(["th", "td"])] for tr in el.find_all("tr")]
            rows = [r for r in rows if any(r)]
            if len(rows) >= 2:
                blocks.append(Block("table", rows=_drop_empty_columns(rows)))
            continue
        text = " ".join(el.get_text(" ").split())
        if not text:
            continue
        if JRC_NEWS_TAIL.search(text):
            break                                       # the end of the article
        if JRC_NEWS_SKIP.search(text):
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            blocks.append(Block("heading", text, level=int(el.name[1])))
        elif len(text) > 30 or text.endswith("."):      # skip menu items and buttons
            blocks.append(Block("text", ("- " + text) if el.name == "li" else text))
    return blocks, {"pages": None}


# ---------------------------------------------------------------- DOCX / DOC

def read_docx(meta: DocMeta, ocr_reader=None, path=None) -> tuple[list[Block], dict]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path or meta.raw_path))
    blocks: list[Block] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, document)
            text = " ".join(p.text.split())
            if not text:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            m = re.match(r"(Heading|Заголовок)\s*(\d)", style)
            # Some files set whole paragraphs in a heading style: a heading is short and has no full stop.
            short = len(text) <= 120 and not (text.endswith(".") and len(text) > 40)
            if (style == "Title" or m) and short or (len(text) <= 80 and not text.endswith(".")
                                                     and (ROMAN_HEADING.match(text) or NUMBERED_HEADING.match(text)
                                                          or _known_heading(text))):
                level = 1 if style == "Title" else (int(m.group(2)) + 1 if m else 2)
                blocks.append(Block("heading", text, level=min(level, 4)))
            elif not BOILERPLATE.search(text) and not TOC_LINE.search(text):
                is_list = "List" in style or p._p.pPr is not None and p._p.pPr.numPr is not None
                blocks.append(Block("text", ("- " + text.lstrip("•–-▪ ")) if is_list else text))
        elif tag == "tbl":
            rows = []
            for row in Table(child, document).rows:
                cells, last = [], None
                for c in row.cells:                       # merged cells repeat: keep one copy
                    if c._tc is last:
                        continue
                    last = c._tc
                    cells.append(_clean_cell(c.text))
                rows.append(cells)
            rows = [r for r in rows if any(r)]
            if _is_toc(rows):
                continue
            if len(rows) >= 2:
                blocks.append(Block("table", rows=_drop_empty_columns(rows)))
            elif rows:
                blocks.append(Block("text", " ".join(c for c in rows[0] if c)))
    # Title pages repeat the title several times: drop exact repeats of short lines.
    out, seen = [], set()
    for b in blocks:
        key = (b.kind, b.text.lower()) if b.kind != "table" and len(b.text) < 120 else None
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(b)
    return _merge_title_headings(out), {"pages": None}


def read_doc(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    """Old Word format: LibreOffice converts it to DOCX (cached), then it is read as DOCX."""
    out_dir = CACHE / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{meta.doc_id}.docx"
    if not target.exists() or target.stat().st_mtime < meta.raw_path.stat().st_mtime:
        subprocess.run(["soffice", "--headless", "--convert-to", "docx", "--outdir", str(out_dir),
                        str(meta.raw_path)], check=True, capture_output=True, timeout=300)
    blocks, info = read_docx(meta, path=target)
    info["converted_with"] = "libreoffice"
    return blocks, info


# ---------------------------------------------------------------- XLSX

def read_xlsx(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    import openpyxl

    wb = openpyxl.load_workbook(meta.raw_path, data_only=True, read_only=True)
    blocks: list[Block] = []
    for ws in wb.worksheets:
        rows = [[_clean_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        i = 0
        while i < len(rows) and sum(1 for c in rows[i] if c) == 1:   # title lines above the table
            blocks.append(Block("heading", next(c for c in rows[i] if c), level=2))
            i += 1
        table, notes, group = [], [], ""
        for r in rows[i:]:
            filled = [c for c in r if c]
            if len(filled) == 1 and len(filled[0]) > 60 and table:    # footnote under the table
                notes.append(filled[0])
            elif len(filled) == 1 and table and r[0] and not _is_number(r[0]):
                if r[0][:1].isupper():                                # a group: "Підприємства"
                    group = r[0]
                    table.append(r)
                # "у тому числі" adds nothing once the group is in every row
            else:
                if group and table and r[0]:
                    r = [f"{group}: {r[0]}"] + r[1:]                 # keep the group in every row
                table.append(r)
        if table:
            table = _drop_empty_columns(table)
            # The header of these sheets often starts with an empty cell: name it.
            if table and not table[0][0]:
                table[0][0] = "Показник"
            blocks.append(Block("table", rows=table))
        for n in notes:
            blocks.append(Block("text", n))
    return blocks, {"pages": None, "sheets": len(wb.worksheets)}


# ---------------------------------------------------------------- CSV

# The export of the State Statistics Service has every indicator of the dataset (land, greenhouses,
# planting material, ...). Only these rows are taken into the corpus.
DERZHSTAT_INDICATORS = {
    "Harvested area of one-year and two-year agricultural crops": "Harvested area",
    "Volume of production (gross collection) of one-year and two-year agricultural crops": "Production",
    "Yield of one-year and two-year agricultural crops": "Yield",
}
DERZHSTAT_CROPS = ["Wheat", "Winter wheat", "Barley", "Maize", "Sunflower seeds", "Soya beans",
                   "Winter rapeseed and colza (spring rapeseed)"]
DERZHSTAT_YEARS = [str(y) for y in range(2019, 2026)]
DERZHSTAT_FILTER = {"Farm type": "All agricultural holdings", "Land type": "On all lands", "Size area": "Total"}


# Region names of the export (English transliteration) with the Ukrainian name, so that a question in
# Ukrainian ("Одеська область") finds the row too.
REGIONS_UK = {
    "Ukraine": "Україна", "Vinnytska": "Вінницька", "Volynska": "Волинська", "Dnipropetrovska": "Дніпропетровська",
    "Donetska": "Донецька", "Zhytomyrska": "Житомирська", "Zakarpatska": "Закарпатська", "Zaporizka": "Запорізька",
    "Ivano-Frankivska": "Івано-Франківська", "Kyivska": "Київська", "Kirovohradska": "Кіровоградська",
    "Luhanska": "Луганська", "Lvivska": "Львівська", "Mykolaivska": "Миколаївська", "Odeska": "Одеська",
    "Poltavska": "Полтавська", "Rivnenska": "Рівненська", "Sumska": "Сумська", "Ternopilska": "Тернопільська",
    "Kharkivska": "Харківська", "Khersonska": "Херсонська", "Khmelnytska": "Хмельницька", "Cherkaska": "Черкаська",
    "Chernivetska": "Чернівецька", "Chernihivska": "Чернігівська",
}


def derzhstat_subset(df):
    """Rows of the export kept in the corpus (also used by the tests)."""
    keep = df["Indicator"].isin(DERZHSTAT_INDICATORS) & df["Breakdown"].isin(DERZHSTAT_CROPS)
    for col, value in DERZHSTAT_FILTER.items():
        keep &= df[col] == value
    return df[keep]


def _unit(row) -> str:
    unit = {"Hundredweight": "centners", "Hectare": "ha", "Ton": "t"}.get(row["Unit of measure"], row["Unit of measure"])
    if row["Indicator"].startswith("Yield"):
        return "centners per ha"
    return f"thousand {unit}" if row["Scaling"] == "Thousands" else unit


def read_csv(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    import pandas as pd

    df = pd.read_csv(meta.raw_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    sub = derzhstat_subset(df)
    blocks = [Block("text", (
        "Areas, gross harvests and yields of the main crops by region of Ukraine, all agricultural holdings, "
        f"{DERZHSTAT_YEARS[0]}-{DERZHSTAT_YEARS[-1]}. Source: State Statistics Service of Ukraine. "
        + (sub["Dataset notes"].iloc[0] if len(sub) else "")))]
    regions = ["Ukraine"] + sorted(r for r in sub["Region"].unique() if r != "Ukraine")
    for crop in DERZHSTAT_CROPS:
        for indicator, short in DERZHSTAT_INDICATORS.items():
            part = sub[(sub["Breakdown"] == crop) & (sub["Indicator"] == indicator)]
            if part.empty:
                continue
            unit = _unit(part.iloc[0])
            blocks.append(Block("heading", f"{crop}: {short.lower()}, {unit}", level=2))
            rows = [["Region"] + DERZHSTAT_YEARS]
            by_region = {r["Region"]: r for _, r in part.iterrows()}
            for region in regions:
                if region in by_region:
                    r = by_region[region]
                    name = f"{region} ({REGIONS_UK[region]})" if region in REGIONS_UK else region
                    rows.append([name] + [r[y] or "n/a" for y in DERZHSTAT_YEARS])
            blocks.append(Block("table", rows=rows))
    return blocks, {"pages": None, "rows_in_export": len(df), "rows_taken": len(sub)}


READERS = {"pdf": read_pdf, "html": read_html, "docx": read_docx, "doc": read_doc,
           "xlsx": read_xlsx, "csv": read_csv}


def read_document(meta: DocMeta, ocr_reader=None) -> tuple[list[Block], dict]:
    return READERS[meta.format](meta, ocr_reader=ocr_reader)

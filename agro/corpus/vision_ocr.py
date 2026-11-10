"""OCR of scanned pages with a vision model through OpenRouter (lecture 6, section 3.3: "modern vision
models can read pages too").

EasyOCR, the first reader, misread many words of the Ukrainian scan ("Вплие поzоdних умое" for "Вплив
погодних умов") and lost the +/- signs of the JRC tables. A vision model reads the page image and returns
Markdown with headings and tables.

    page -> PNG (200 dpi) -> model (prompts/ocr/<version>.txt) -> data/ocr/<doc_id>/page-NNN.md -> blocks

The transcripts are kept in git (data/ocr/): the corpus is rebuilt from them without a key and without
calling the model again, and anyone can compare a transcript with the page. A model can "complete" a text
instead of reading it, so the numbers of every page are compared with what EasyOCR read on the same page
(`make rag-ocr-compare`, results/rag/ocr_compare.md) and pages are checked by eye.
"""

import base64
import re
import tomllib

from ..common.settings import CACHE, DATA, ROOT
from .extract import Block

OCR_DIR = DATA / "ocr"
PROMPTS = ROOT / "prompts" / "ocr"
PROMPT_VERSION = "v1"           # prompts/ocr/CHANGELOG.md
MODEL_KEY = "gemini_flash"          # config.toml [models.gemini_flash]
DPI = 200
MAX_TOKENS = 8192
LANGUAGE_NAMES = {"uk": "Ukrainian", "en": "English"}


def transcript_path(doc_id: str, page_no: int):
    return OCR_DIR / doc_id / f"page-{page_no:03d}.md"


def markdown_to_blocks(md: str, page_no: int) -> list[Block]:
    """Markdown of one page -> blocks: '#' headings, '|' tables (separator row dropped), '- ' list items,
    paragraphs split by empty lines. Comment lines (<!-- -->) are skipped."""
    blocks, para, table = [], [], []

    def flush_para():
        if para:
            blocks.append(Block("text", " ".join(para), page=page_no, ocr=True))
            para.clear()

    def flush_table():
        if table:
            blocks.append(Block("table", rows=[list(r) for r in table], page=page_no, ocr=True))
            table.clear()

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("<!--"):
            continue
        if s.startswith("|"):
            flush_para()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            table.append(cells)
            continue
        flush_table()
        if not s:
            flush_para()
        elif s.startswith("#"):
            flush_para()
            blocks.append(Block("heading", s.lstrip("#").strip(), page=page_no, ocr=True))
        elif re.match(r"[-*•]\s", s):
            flush_para()
            blocks.append(Block("text", "- " + s[2:].strip(), page=page_no, ocr=True))
        else:
            para.append(s)
    flush_para()
    flush_table()
    return blocks


def _body(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("<!--"))


class VisionOcr:
    """read_page() has the interface of the EasyOCR reader (agro/corpus/ocr.py)."""

    def __init__(self) -> None:
        self._provider = None
        self.calls = 0
        self.cost_usd = 0.0

    def provider(self):
        if self._provider is None:
            from ..common.providers import CachedProvider, make_provider

            with (ROOT / "config.toml").open("rb") as f:
                cfg = tomllib.load(f)["models"][MODEL_KEY]
            self._provider = CachedProvider(make_provider(cfg), CACHE / "responses")
        return self._provider

    def transcribe(self, page, language: str) -> str:
        png = page.get_pixmap(dpi=DPI).tobytes("png")
        prompt = (PROMPTS / f"{PROMPT_VERSION}.txt").read_text(encoding="utf-8")
        prompt = prompt.replace("{language}", LANGUAGE_NAMES.get(language, language))
        messages = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
        ]}]
        p = self.provider()
        c = p.complete(messages, schema={}, sampling={"temperature": 0.0, "top_p": 1.0}, max_tokens=MAX_TOKENS)
        if c.finish_reason == "length":
            runaway = re.search(r"-{200,}", c.content)
            raise RuntimeError(f"the transcript was cut at {MAX_TOKENS} tokens"
                               + (" (a run of dashes: the model looped copying a printed rule)" if runaway else ""))
        self.calls += 1
        self.cost_usd += p.cost_usd(c)
        md = c.content.strip()
        if md.startswith("```"):                       # a model sometimes wraps the answer in a code fence
            md = re.sub(r"^```[a-z]*\n|\n```$", "", md)
        return re.sub(r"-{21,}", "---", md)           # a printed rule of dashes copied too long

    def read_page(self, page, page_no: int, as_table: bool = False, language: str = "uk",
                  doc_id: str = "") -> list[Block]:
        path = transcript_path(doc_id, page_no)
        if not path.exists():
            md = self.transcribe(page, language)
            path.parent.mkdir(parents=True, exist_ok=True)
            model = self.provider().model
            path.write_text(f"<!-- ocr: {model}, prompt ocr/{PROMPT_VERSION}, {DPI} dpi, {doc_id} page {page_no} -->\n"
                            + md + "\n", encoding="utf-8")
        return markdown_to_blocks(_body(path.read_text(encoding="utf-8")), page_no)

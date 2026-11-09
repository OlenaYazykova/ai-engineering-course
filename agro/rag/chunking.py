"""Chunking: data/corpus/text/*.md -> data/rag/chunks.jsonl (+ the fixed-size baseline).

    make rag-chunk            # or: python main.py rag chunk

Structural chunking (the one used by the RAG):
  * a chunk never crosses a heading: every chunk belongs to one section of one document
  * paragraphs of a section are packed together up to MAX_TOKENS; a paragraph longer than that is
    split at sentence ends; a short tail (< MIN_TOKENS) is added to the previous chunk of the section
  * a table is its own chunk (or several, split by rows); the header row is repeated in every part,
    so every part can be read alone
  * every chunk gets a short context header (document title, period, section), used for the
    embeddings and shown to the model; the header is not counted in `text`

Baseline for comparison: fixed windows of FIXED_SIZE tokens with FIXED_OVERLAP overlap over the
whole document text, no regard to headings or tables (data/rag/chunks_fixed.jsonl).

chunk_stats() measures both: size, chunks that start in the middle of a sentence, tables cut
across chunks, chunks with text of two sections (results/rag/chunking.md).
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from ..common.settings import CACHE, CORPUS, RAG_DATA, RESULTS_RAG, ROOT
from ..corpus.ingest import PIPELINE_VERSION as CORPUS_PIPELINE, read_markdown
from .tokens import count_tokens, split_tokens

CHUNKER_VERSION = "struct-1"
MAX_TOKENS = 450          # default; the size used is config.toml [rag] chunk_tokens (chosen by the evaluation)
SIZES = (300, 450)        # structural sizes compared by the retrieval evaluation (results/rag/retrieval_dev.md, part D)
MIN_TOKENS = 60
TABLE_MAX_TOKENS = 600
FIXED_SIZE = 450
FIXED_OVERLAP = 50

CHUNKS = RAG_DATA / "chunks.jsonl"
CHUNKS_FIXED = RAG_DATA / "chunks_fixed.jsonl"
SIZE_VARIANTS = CACHE / "chunks"          # structural chunks of the other sizes (re-creatable, not in git)


def chunk_size() -> int:
    """The structural chunk size used for answers: config.toml [rag] chunk_tokens."""
    import tomllib

    with (ROOT / "config.toml").open("rb") as f:
        return int(tomllib.load(f).get("rag", {}).get("chunk_tokens", MAX_TOKENS))


def chunk_file(chunker: str):
    """structural | fixed | structural_<size> -> its chunks file."""
    if chunker == "structural":
        return CHUNKS
    if chunker == "fixed":
        return CHUNKS_FIXED
    return SIZE_VARIANTS / f"{chunker}.jsonl"

MONTHS_UK = ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень",
             "вересень", "жовтень", "листопад", "грудень"]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    chunk_index: int
    kind: str               # text | table
    section: str
    page: int | None
    header: str             # context line: document, period, section
    text: str
    n_tokens: int
    title: str
    source: str
    format: str
    language: str
    topic: str
    period: str
    year: int | None
    month: int | None
    decade: int | None
    effective: str
    url: str
    doc_hash: str
    ocr: bool
    chunker: str
    pipeline_version: str
    dataset_version: str
    ingested_at: str

    def for_embedding(self) -> str:
        return f"{self.header}\n{self.text}"


# ---------------------------------------------------------------- parsing the Markdown

def parse_sections(body: str):
    """Yield (section, page, kind, text) items: kind = text | table; headings set the section."""
    section, page = "", None
    for part in re.split(r"\n{2,}", body.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"<!-- page (\d+) -->", part)
        if m:
            page = int(m.group(1))
            continue
        if part.startswith("<!--"):
            continue
        if part.startswith("# "):
            continue                                   # the document title: in the header already
        if re.match(r"#{2,4} ", part):
            section = part.lstrip("#").strip()
            yield section, page, "heading", section
            continue
        kind = "table" if part.startswith("|") else "text"
        yield section, page, kind, part


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+(?=[A-ZА-ЯІЇЄҐ0-9(«\"])", text) if s]


def _split_long(text: str, limit: int) -> list[str]:
    parts, cur = [], ""
    for s in _sentences(text):
        candidate = f"{cur} {s}".strip()
        if cur and count_tokens(candidate) > limit:
            parts.append(cur)
            cur = s
        else:
            cur = candidate
    if cur:
        parts.append(cur)
    out = []
    for p in parts:                                   # a "sentence" longer than the limit: by tokens
        out += split_tokens(p, limit, 0) if count_tokens(p) > limit else [p]
    return out


def _split_table(table: str, limit: int) -> list[str]:
    lines = table.splitlines()
    head, rows = lines[:2], lines[2:]
    parts, cur = [], []
    head_tokens = count_tokens("\n".join(head))
    used = head_tokens
    for r in rows:
        t = count_tokens(r)
        if cur and used + t > limit:
            parts.append("\n".join(head + cur))
            cur, used = [], head_tokens
        cur.append(r)
        used += t
    if cur or not parts:
        parts.append("\n".join(head + cur))
    return parts


def _period_label(meta: dict) -> str:
    p = meta.get("period", "")
    m = re.fullmatch(r"(\d{4})-(\d{2})-d(\d)", p)
    if m and meta.get("language") == "uk":
        return f"{['перша', 'друга', 'третя'][int(m.group(3)) - 1]} декада, {MONTHS_UK[int(m.group(2)) - 1]} {m.group(1)}"
    return p


def _header(meta: dict, section: str) -> str:
    parts = [meta.get("title", ""), f"period: {_period_label(meta)}"]
    if section:
        parts.append(f"section: {section}")
    return " | ".join(parts)


# ---------------------------------------------------------------- chunkers

def structural_chunks(meta: dict, body: str, max_tokens: int | None = None) -> list[tuple[str, int | None, str, str]]:
    """(section, page, kind, text) of every chunk of one document."""
    max_tokens = max_tokens or MAX_TOKENS
    table_max = TABLE_MAX_TOKENS + (max_tokens - MAX_TOKENS)     # tables a little longer: a row is never cut
    out: list[list] = []                     # [section, page, kind, text]
    buf, buf_page, buf_section = [], None, None

    def flush():
        nonlocal buf, buf_page
        if buf:
            text = "\n\n".join(buf)
            if out and out[-1][2] == "text" and out[-1][0] == buf_section and count_tokens(text) < MIN_TOKENS \
                    and count_tokens(out[-1][3] + "\n\n" + text) <= max_tokens + MIN_TOKENS:
                out[-1][3] += "\n\n" + text      # a short tail joins the previous chunk of the section
            else:
                out.append([buf_section, buf_page, "text", text])
        buf, buf_page = [], None

    for section, page, kind, text in parse_sections(body):
        if section != buf_section:
            flush()
            buf_section = section
        if kind == "heading":
            continue
        if kind == "table":
            flush()
            for part in _split_table(text, table_max):
                out.append([section, page, "table", part])
            continue
        pieces = _split_long(text, max_tokens) if count_tokens(text) > max_tokens else [text]
        for piece in pieces:
            if buf and count_tokens("\n\n".join(buf + [piece])) > max_tokens:
                flush()
            if not buf:
                buf_page = page
            buf.append(piece)
    flush()
    return [tuple(x) for x in out]


def fixed_chunks(meta: dict, body: str) -> list[tuple[str, int | None, str, str]]:
    """Fixed windows over the whole text (headings and tables included as plain text)."""
    text = re.sub(r"<!--.*?-->\n*", "", body)
    return [("", None, "text", piece.strip()) for piece in split_tokens(text, FIXED_SIZE, FIXED_OVERLAP)
            if piece.strip()]


def _to_chunks(meta: dict, items, chunker: str, dataset_version: str, now: str) -> list[Chunk]:
    out = []
    ocr_pages = {int(p) for p in meta.get("ocr_pages", "").split(",") if p.strip()}
    for i, (section, page, kind, text) in enumerate(items):
        year = re.match(r"(\d{4})", meta.get("period", ""))
        month = re.match(r"\d{4}-(\d{2})(?!\d)", meta.get("period", ""))
        decade = re.search(r"-d(\d)$", meta.get("period", ""))
        out.append(Chunk(
            chunk_id=f"{meta['doc_id']}#{i:03d}", doc_id=meta["doc_id"], chunk_index=i, kind=kind,
            section=section, page=page, header=_header(meta, section), text=text, n_tokens=count_tokens(text),
            title=meta.get("title", ""), source=meta.get("source", ""), format=meta.get("format", ""),
            language=meta.get("language", ""), topic=meta.get("topic", ""), period=meta.get("period", ""),
            year=int(year.group(1)) if year else None, month=int(month.group(1)) if month else None,
            decade=int(decade.group(1)) if decade else None, effective=meta.get("effective", ""),
            url=meta.get("url", ""), doc_hash=meta.get("doc_hash", ""), ocr=page in ocr_pages,
            chunker=chunker, pipeline_version=meta.get("pipeline_version", CORPUS_PIPELINE),
            dataset_version=dataset_version, ingested_at=now))
    return out


def load_documents():
    for path in sorted((CORPUS / "text").glob("*.md")):
        yield read_markdown(path)


def build(chunker: str = "structural", max_tokens: int | None = None) -> list[Chunk]:
    dataset_version = (CORPUS / "dataset_version.txt").read_text(encoding="utf-8").strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    size = max_tokens or chunk_size()
    chunks = []
    for meta, body in load_documents():
        if chunker == "structural":
            items, name = structural_chunks(meta, body, size), f"{CHUNKER_VERSION}-{size}"
        else:
            items, name = fixed_chunks(meta, body), f"fixed-{FIXED_SIZE}-{FIXED_OVERLAP}"
        chunks += _to_chunks(meta, items, name, dataset_version, now)
    return chunks


def save(chunks: list[Chunk], path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def load_chunks(path=CHUNKS) -> list[Chunk]:
    with path.open(encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]


# ---------------------------------------------------------------- statistics

_SENTENCE_START = re.compile(r"^[\s\"«(]*([A-ZА-ЯІЇЄҐ0-9#|•\-–])")


def chunk_stats(chunks: list[Chunk]) -> dict:
    """Quality of a chunking: the numbers of results/rag/chunking.md."""
    n = len(chunks)
    tokens = [c.n_tokens for c in chunks]
    mid_sentence = sum(1 for c in chunks if not _SENTENCE_START.match(c.text))
    # A table is cut when a chunk has table rows but not the header line (|---|) right after the first row,
    # or a table runs to the end of a chunk and continues in the next one without its header.
    cut_tables = 0
    for c in chunks:
        lines = [l for l in c.text.splitlines() if l.startswith("|")]
        if lines and not any(re.fullmatch(r"\|(---\|)+", l) for l in lines):
            cut_tables += 1
    tiny = sum(1 for t in tokens if t < MIN_TOKENS)
    return {
        "chunks": n, "avg_tokens": round(sum(tokens) / n) if n else 0, "max_tokens": max(tokens, default=0),
        "starts_mid_sentence_%": round(100 * mid_sentence / n, 1) if n else 0,
        "table_parts_without_header": cut_tables, "chunks_under_min_tokens": tiny,
        "table_chunks": sum(c.kind == "table" for c in chunks),
    }


def run() -> None:
    size = chunk_size()
    variants = {size: build("structural", size)}
    fixed = build("fixed")
    save(variants[size], CHUNKS)
    save(fixed, CHUNKS_FIXED)
    for other in SIZES:
        if other != size:
            variants[other] = build("structural", other)
            save(variants[other], chunk_file(f"structural_{other}"))
    columns = [(f"structural, max {n}" + (" (used)" if n == size else ""), chunk_stats(variants[n]))
               for n in sorted(variants)] + [(f"fixed {FIXED_SIZE} / overlap {FIXED_OVERLAP}", chunk_stats(fixed))]
    keys = list(columns[0][1])
    rows = "\n".join(f"| {k} | " + " | ".join(str(c[k]) for _, c in columns) + " |" for k in keys)
    used = variants[size]
    report = (
        "# Chunking: structural (two sizes) vs fixed-size\n\n"
        f"Corpus: {len({c.doc_id for c in used})} documents, dataset version "
        f"{used[0].dataset_version if used else '-'}. Tokens: tiktoken o200k_base. "
        f"Size used: config.toml [rag] chunk_tokens = {size}.\n\n"
        "| metric | " + " | ".join(n for n, _ in columns) + " |\n"
        "|---|" + "---|" * len(columns) + "\n" + rows + "\n\n"
        "starts_mid_sentence_%: chunks whose text does not start at a sentence, heading, list item or table row.\n"
        "table_parts_without_header: chunks with table rows but no table header (the table was cut).\n"
        "Retrieval quality of each chunking (recall@k, MRR) and the share of chunks longer than the input\n"
        "window of each embedding model: results/rag/retrieval_dev.md.\n")
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    (RESULTS_RAG / "chunking.md").write_text(report, encoding="utf-8")
    for name, c in columns:
        print(f"{name:<28} {c}")
    print(f"Saved {CHUNKS.relative_to(ROOT)} (max {size}), {CHUNKS_FIXED.relative_to(ROOT)}, "
          f"{SIZE_VARIANTS.relative_to(ROOT)}/, results/rag/chunking.md")

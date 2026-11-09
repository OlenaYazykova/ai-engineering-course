"""Ingestion: originals in data/raw/ -> cleaned Markdown documents in data/corpus/ + manifest.

    make rag-ingest            # or: python main.py rag ingest [--force] [--only DOC_ID ...]

Steps for every document of data/sources.csv:
  1. read the original by its format (agro/corpus/extract.py; OCR for the pages set in the registry)
  2. clean the text (agro/corpus/clean.py), with a vocabulary built from the whole corpus, and mask
     personal data and contacts (agro/corpus/pii.py)
  3. find exact / near duplicates and related documents (agro/corpus/dedup.py)
  4. write data/corpus/text/<doc_id>.md: metadata header, headings, paragraphs, tables, page marks

Outputs (all in git, so that the next steps and CI work without the originals):
  data/corpus/text/<doc_id>.md   one cleaned document
  data/corpus/manifest.csv       every document: status, hashes, sizes, duplicates, OCR pages
  data/corpus/audit.jsonl        what happened to every document in the last run
  data/corpus/clean_log.csv      every word glued by the cleaning step, with counts
  data/corpus/letters_log.csv    every word with Latin look-alike letters made Cyrillic, with counts
  data/corpus/pii_log.csv        how many e-mails, phones and names were masked in each document (no values)
  data/corpus/dataset_version.txt one id of the whole corpus (changes when any document changes)

Incremental: reading a document (the slow part, OCR above all) is cached in .cache/extract/ by the
hash of the original file and PIPELINE_VERSION; unchanged files are not read again.
"""

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from ..common.settings import CACHE, CORPUS, ROOT
from .clean import build_vocabulary, clean_blocks, fix_homoglyphs, normalize
from .dedup import find_duplicates
from .extract import Block, read_document
from .pii import PiiMasker, lowercase_words
from .registry import DocMeta, load_registry

PIPELINE_VERSION = "corpus-6"
TEXT_DIR = CORPUS / "text"
MANIFEST = CORPUS / "manifest.csv"
AUDIT = CORPUS / "audit.jsonl"
CLEAN_LOG = CORPUS / "clean_log.csv"
LETTERS_LOG = CORPUS / "letters_log.csv"
PII_LOG = CORPUS / "pii_log.csv"
DATASET_VERSION = CORPUS / "dataset_version.txt"
EXTRACT_CACHE = CACHE / "extract"

MANIFEST_FIELDS = [
    "doc_id", "status", "format", "language", "source", "topic", "title", "period", "effective", "url",
    "raw_file", "raw_hash", "doc_hash", "duplicate_of", "related", "pages", "ocr_pages", "blocks",
    "headings", "tables", "chars", "pipeline_version", "ingested_at",
]


def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- Markdown

def _cell(text: str) -> str:
    return text.replace("|", "/").strip()


def table_to_markdown(rows: list[list[str]]) -> str:
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |",
             "|" + "---|" * width]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def to_markdown(meta: DocMeta, blocks: list[Block]) -> str:
    """The body of the document (without the metadata header)."""
    out = [f"# {meta.title}"]
    page = None
    for b in blocks:
        if b.page is not None and b.page != page:
            page = b.page
            out.append(f"<!-- page {page} -->")
        if b.kind == "heading":
            out.append("#" * max(2, min(b.level, 4)) + " " + b.text)
        elif b.kind == "table":
            if b.ocr:
                out.append("<!-- table read with OCR: cell borders are approximate -->")
            out.append(table_to_markdown(b.rows))
        else:
            out.append(b.text)
    return "\n\n".join(out) + "\n"


def front_matter(meta: DocMeta, doc_hash: str, related: list[str], ocr_pages: str = "") -> str:
    fields = {
        "doc_id": meta.doc_id, "title": meta.title, "source": meta.source, "format": meta.format,
        "language": meta.language, "topic": meta.topic, "period": meta.period, "effective": meta.effective,
        "url": meta.url, "related": ",".join(related), "ocr_pages": ocr_pages.replace(" ", ","), "doc_hash": doc_hash,
        "pipeline_version": PIPELINE_VERSION,
    }
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n---\n\n"


def read_markdown(path) -> tuple[dict, str]:
    """(metadata, body) of a data/corpus/text/*.md file."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---\n"):
        head, text = text[4:].split("\n---\n", 1)
        for line in head.splitlines():
            k, _, v = line.partition(": ")
            meta[k] = v
    return meta, text.lstrip("\n")


# ---------------------------------------------------------------- pipeline

class _LazyOcr:
    """Create an OCR reader (loads torch and the models) only if a page really needs it, one per language."""

    def __init__(self):
        self._readers = {}
        self._error = None

    def read_page(self, page, page_no, as_table=False, language="uk"):
        if self._error:
            raise RuntimeError(self._error)
        if language not in self._readers:
            print(f"    loading the OCR model ({language}; first time: download ~100 MB)...")
            try:
                from .ocr import LANGUAGES, OcrReader
                self._readers[language] = OcrReader(LANGUAGES.get(language, ("uk", "en")))
            except Exception as e:     # easyocr / torch not installed: say it once
                self._error = f"OCR not available: {type(e).__name__}: {e}"
                print(f"    {self._error}")
                raise
        return self._readers[language].read_page(page, page_no, as_table=as_table)


def _extract(meta: DocMeta, raw_hash: str, ocr, force: bool) -> tuple[list[Block], dict, bool]:
    cache = EXTRACT_CACHE / f"{meta.doc_id}.json"
    if cache.exists() and not force:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data["raw_hash"] == raw_hash and data["pipeline_version"] == PIPELINE_VERSION:
            return [Block(**b) for b in data["blocks"]], data["info"], True
    blocks, info = read_document(meta, ocr_reader=ocr)
    EXTRACT_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"raw_hash": raw_hash, "pipeline_version": PIPELINE_VERSION, "info": info,
                                 "blocks": [b.to_dict() for b in blocks]}, ensure_ascii=False), encoding="utf-8")
    return blocks, info, False


def run(force: bool = False, only: list[str] | None = None) -> None:
    docs = load_registry()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    ocr = _LazyOcr()
    audit, rows = [], {}
    extracted: dict[str, list[Block]] = {}

    print(f"Reading {len(docs)} documents...")
    for meta in docs:
        row = {k: getattr(meta, k, "") for k in ("doc_id", "format", "language", "source", "topic", "title",
                                                   "period", "effective", "url")}
        row.update(raw_file=str(meta.raw_path.relative_to(ROOT)), pipeline_version=PIPELINE_VERSION,
                   ingested_at=now)
        rows[meta.doc_id] = row
        if not meta.raw_path.exists():
            row["status"] = "missing"
            audit.append({"doc_id": meta.doc_id, "action": "missing", "detail": "run `make fetch`"})
            print(f"  {meta.doc_id:<30} MISSING ({row['raw_file']}): run `make fetch`")
            continue
        raw_hash = file_hash(meta.raw_path)
        row["raw_hash"] = raw_hash[:16]
        try:
            blocks, info, cached = _extract(meta, raw_hash, ocr, force or meta.doc_id in (only or []))
        except Exception as e:
            row["status"] = "error"
            audit.append({"doc_id": meta.doc_id, "action": "error", "detail": f"{type(e).__name__}: {e}"})
            print(f"  {meta.doc_id:<30} ERROR {type(e).__name__}: {e}")
            continue
        extracted[meta.doc_id] = blocks
        row.update(pages=info.get("pages") or "", ocr_pages=" ".join(map(str, info.get("ocr_pages", []))))
        audit.append({"doc_id": meta.doc_id, "action": "cached" if cached else "extracted",
                      "detail": {k: v for k, v in info.items() if v not in (None, [], "")}})
        print(f"  {meta.doc_id:<30} {'cached' if cached else 'read'}: {len(blocks)} blocks"
              + (f", OCR pages {row['ocr_pages']}" if row["ocr_pages"] else "")
              + (f", OCR FAILED on pages {info['ocr_failed']}" if info.get("ocr_failed") else ""))
        if not blocks:
            row["status"] = "error"
            audit.append({"doc_id": meta.doc_id, "action": "error", "detail": "no text"})
            del extracted[meta.doc_id]

    # Cleaning: the vocabulary for gluing broken words comes from the whole corpus.
    vocab = build_vocabulary(fix_homoglyphs(normalize(b.text), Counter(), b.ocr)
                             for blocks in extracted.values() for b in blocks if b.kind != "table")
    glued: Counter = Counter()
    letters: Counter = Counter()
    bodies = {}
    for doc_id, blocks in extracted.items():
        extracted[doc_id] = clean_blocks(blocks, vocab, glued, letters)
    # Personal data: masked by Presidio (spaCy NER + our rules) before anything is written.
    lower = lowercase_words(c for blocks in extracted.values() for b in blocks
                            for c in ([b.text] if b.kind != "table" else [x for r in b.rows for x in r]))
    print("masking personal data (Presidio + spaCy)...")
    masker = PiiMasker(lower)
    for doc_id, blocks in extracted.items():
        meta = next(d for d in docs if d.doc_id == doc_id)
        blocks = masker.mask_blocks(blocks, doc_id, meta.language)
        extracted[doc_id] = blocks
        bodies[doc_id] = to_markdown(meta, blocks)
        left = masker.find(bodies[doc_id], meta.language)
        if left:
            audit.append({"doc_id": doc_id, "action": "pii_left", "detail": dict(Counter(left))})
            print(f"  {doc_id:<30} WARNING: personal data left after masking: {dict(Counter(left))}")

    # Duplicates are compared without the title line (the registry gives a copy its own title).
    dups = find_duplicates([(d, bodies[d].split("\n", 1)[1]) for d in bodies])
    for old in TEXT_DIR.glob("*.md"):           # rebuild: no stale documents
        old.unlink()
    kept = []
    for doc_id, body in bodies.items():
        meta = next(d for d in docs if d.doc_id == doc_id)
        d = dups[doc_id]
        blocks = extracted[doc_id]
        rows[doc_id].update(
            status=d["status"], doc_hash=d["doc_hash"][:16], duplicate_of=d["duplicate_of"],
            related=" ".join(d["related"]), blocks=len(blocks),
            headings=sum(b.kind == "heading" for b in blocks), tables=sum(b.kind == "table" for b in blocks),
            chars=len(body))
        if d["status"] != "ok":
            audit.append({"doc_id": doc_id, "action": d["status"], "detail": f"of {d['duplicate_of']}"})
            print(f"  {doc_id:<30} {d['status'].upper()} of {d['duplicate_of']}: not written")
            continue
        (TEXT_DIR / f"{doc_id}.md").write_text(front_matter(meta, d["doc_hash"][:16], d["related"],
                                                          rows[doc_id].get("ocr_pages", "")) + body,
                                              encoding="utf-8")
        kept.append(f"{doc_id}:{d['doc_hash']}")

    version = hashlib.sha256(("\n".join(sorted(kept)) + PIPELINE_VERSION).encode()).hexdigest()[:12]
    DATASET_VERSION.write_text(version + "\n", encoding="utf-8")
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        w.writeheader()
        for meta in docs:
            w.writerow({k: rows[meta.doc_id].get(k, "") for k in MANIFEST_FIELDS})
    with AUDIT.open("w", encoding="utf-8") as f:
        for a in audit:
            f.write(json.dumps({"at": now, **a}, ensure_ascii=False) + "\n")
    with CLEAN_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["glued", "count"])
        for pair, n in glued.most_common():
            w.writerow([pair, n])

    with PII_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "kind", "masked"])
        for (doc_id, kind), n in sorted(masker.counts.items()):
            w.writerow([doc_id, kind, n])
    with LETTERS_LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["changed", "count"])
        for pair, n in letters.most_common():
            w.writerow([pair, n])

    status = Counter(r.get("status", "") for r in rows.values())
    formats = Counter(rows[d]["format"] for d in rows if rows[d].get("status") == "ok")
    print(f"\n{status['ok']} documents in {TEXT_DIR.relative_to(ROOT)}/ ({dict(formats)}); "
          f"other statuses: { {k: v for k, v in status.items() if k != 'ok'} }")
    print(f"glued broken words: {sum(glued.values())} ({len(glued)} distinct), see {CLEAN_LOG.relative_to(ROOT)}")
    pii = Counter()
    for (_, kind), n in masker.counts.items():
        pii[kind] += n
    print(f"personal data masked: {dict(pii)} (no values kept), see {PII_LOG.relative_to(ROOT)}")
    print(f"  found by: {dict(masker.found_by)}; spaCy PERSON hits rejected as not a person: {dict(masker.rejected())}")
    print(f"Latin look-alike letters fixed in {sum(letters.values())} words ({len(letters)} distinct), "
          f"see {LETTERS_LOG.relative_to(ROOT)}")
    print(f"dataset version: {version}; manifest: {MANIFEST.relative_to(ROOT)}")

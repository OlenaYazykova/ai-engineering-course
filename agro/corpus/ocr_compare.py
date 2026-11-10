"""The vision transcripts (data/ocr/) against EasyOCR on the same scanned pages: `make rag-ocr-compare`.

Per page:
  known words   share of words (3+ letters) that occur in the documents read without OCR: a misread word
                ("умое", "краіни") is usually not in that vocabulary
  numbers       how many numbers each reader found; the share of the vision numbers that EasyOCR also read;
                the numbers only the vision model has are listed: a model can "complete" a value, so these
                are the ones to check on the page
  signed        numbers written with + or - (the JRC tables of deviations: EasyOCR loses the signs)
Report: results/rag/ocr_compare.md. EasyOCR runs here again (it needs easyocr and torch; minutes on a CPU).
"""

import re

from ..common.settings import CORPUS, RESULTS_RAG
from .registry import load_registry
from .vision_ocr import _body, markdown_to_blocks, transcript_path

# A sign belongs to a number when it does not follow a digit ("1295-1325" is a range, not -1325);
# the JRC tables print it apart from the number ("- 17", "+ 35").
NUMBER = re.compile(r"(?:(?<![\d\w])[+\-−–]\s?)?\d+(?:[.,]\d+)?")


def blocks_text(blocks) -> str:
    parts = []
    for b in blocks:
        parts += [" ".join(r) for r in b.rows] if b.kind == "table" else [b.text]
    return "\n".join(parts)


def numbers(text: str) -> list[str]:
    return [re.sub(r"\s", "", n).replace(",", ".").replace("−", "-").replace("–", "-") for n in NUMBER.findall(text)]


def compare(easy: str, vision: str, vocab: set[str]) -> dict:
    def known(t):
        words = re.findall(r"[^\W\d_]{3,}", t.lower())
        return round(100 * sum(w in vocab for w in words) / len(words), 1) if words else 0.0

    ne, nv = numbers(easy), numbers(vision)
    unsigned = lambda ns: {n.lstrip("+-") for n in ns}
    ue = unsigned(ne)
    only_vision = sorted({n for n in nv if n.lstrip("+-") not in ue}, key=lambda n: float(n))
    return {
        "words": (len(re.findall(r"[^\W\d_]{3,}", easy)), len(re.findall(r"[^\W\d_]{3,}", vision))),
        "known_%": (known(easy), known(vision)),
        "numbers": (len(ne), len(nv)),
        "vision_numbers_also_in_easyocr_%": round(100 * sum(n.lstrip("+-") in ue for n in nv) / len(nv), 1) if nv else 0.0,
        "signed": (sum(n[0] in "+-" for n in ne), sum(n[0] in "+-" for n in nv)),
        "only_vision": only_vision,
    }


def run() -> None:
    import pymupdf

    from .ocr import LANGUAGES, OcrReader

    docs = load_registry()
    plain = {m.doc_id for m in docs if not m.ocr}
    vocab = set()
    for p in (CORPUS / "text").glob("*.md"):
        if p.stem in plain:
            vocab.update(re.findall(r"[^\W\d_]{3,}", p.read_text(encoding="utf-8").lower()))
    readers, rows = {}, []
    for meta in docs:
        if not meta.ocr or meta.format != "pdf":
            continue
        with pymupdf.open(meta.raw_path) as pdf:
            for i in sorted(meta.ocr_pages(pdf.page_count)):
                path = transcript_path(meta.doc_id, i)
                if not path.exists():
                    print(f"  {meta.doc_id} page {i}: no transcript, run `make rag-ingest` first")
                    continue
                if meta.language not in readers:
                    readers[meta.language] = OcrReader(LANGUAGES.get(meta.language, ("uk", "en")))
                easy = blocks_text(readers[meta.language].read_page(pdf[i - 1], i, as_table=not meta.ocr_whole_scan))
                vision = blocks_text(markdown_to_blocks(_body(path.read_text(encoding="utf-8")), i))
                rows.append((meta.doc_id, i, compare(easy, vision, vocab)))
                c = rows[-1][2]
                print(f"  {meta.doc_id} page {i}: known words {c['known_%']}, numbers {c['numbers']}, "
                      f"vision numbers also in EasyOCR {c['vision_numbers_also_in_easyocr_%']}%")
    lines = ["# OCR: vision model (data/ocr/) vs EasyOCR on the same pages", "",
             "Every pair is EasyOCR / vision. Known words: share of words found in the documents read without "
             "OCR. Numbers also in EasyOCR: share of the vision numbers that EasyOCR read too (signs ignored). "
             "Signed: numbers written with + or -. Code: agro/corpus/ocr_compare.py.", "",
             "| document | page | words | known words, % | numbers | vision numbers also in EasyOCR, % | signed |",
             "|---|---|---|---|---|---|---|"]
    for doc_id, i, c in rows:
        lines.append(f"| {doc_id} | {i} | {c['words'][0]} / {c['words'][1]} | {c['known_%'][0]} / {c['known_%'][1]} "
                     f"| {c['numbers'][0]} / {c['numbers'][1]} | {c['vision_numbers_also_in_easyocr_%']} "
                     f"| {c['signed'][0]} / {c['signed'][1]} |")
    lines += ["", "## Numbers only in the vision transcript (to check on the page)", ""]
    for doc_id, i, c in rows:
        lines.append(f"- {doc_id} page {i}: " + (", ".join(c["only_vision"]) or "none"))
    RESULTS_RAG.mkdir(parents=True, exist_ok=True)
    (RESULTS_RAG / "ocr_compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Saved results/rag/ocr_compare.md")

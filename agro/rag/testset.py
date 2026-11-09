"""The test set: loading and checks of the set itself (`make rag-lint-testset`, also run in CI).

A check fails (exit 1) when:
  * a field is missing, an id repeats, the split or the kind is unknown
  * a source document is not in the corpus, or its evidence phrase is not in the document text
    (the phrase must be copied from data/corpus/text/<doc_id>.md; spaces do not matter)
  * a question with an answer has no key facts, or a no-answer question has sources
  * a kind has fewer than MIN_PER_KIND questions over both splits, or a split has no no-answer
    question or no trap (outdated version / similar documents)
"""

import json
import re
from collections import Counter

from ..common.settings import CORPUS, ROOT

EVALS = ROOT / "evals"
KINDS = {"exact", "paraphrase", "cross_lingual", "table", "stale", "similar", "multi_chunk", "yes_no", "no_answer"}
FIELDS = {"id", "split", "kind", "language", "question", "expected_answer", "key_facts", "sources"}
MIN_PER_KIND = 2


def load(split: str) -> list[dict]:
    with (EVALS / f"testset_{split}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def lint() -> list[str]:
    problems = []
    texts = {p.stem: _norm(p.read_text(encoding="utf-8")) for p in (CORPUS / "text").glob("*.md")}
    items = load("dev") + load("test")
    ids = Counter(q.get("id") for q in items)
    problems += [f"{i}: the id repeats" for i, n in ids.items() if n > 1]
    for q in items:
        qid = q.get("id", "?")
        missing = FIELDS - set(q)
        if missing:
            problems.append(f"{qid}: missing fields {sorted(missing)}")
            continue
        if q["kind"] not in KINDS:
            problems.append(f"{qid}: unknown kind {q['kind']}")
        if q["split"] not in ("dev", "test") or not qid.startswith(q["split"][0]):
            problems.append(f"{qid}: split {q['split']} does not match the id")
        if q["kind"] == "no_answer":
            if q["sources"] or q["key_facts"]:
                problems.append(f"{qid}: a no-answer question has sources or key facts")
            continue
        if not q["key_facts"]:
            problems.append(f"{qid}: no key facts")
        if not q["sources"]:
            problems.append(f"{qid}: no sources")
        for s in q["sources"]:
            if s["doc_id"] not in texts:
                problems.append(f"{qid}: document {s['doc_id']} is not in the corpus")
            elif not s["evidence"].strip() or _norm(s["evidence"]) not in texts[s["doc_id"]]:
                problems.append(f"{qid}: evidence not found in {s['doc_id']}: {s['evidence'][:60]!r}")
    kinds = Counter(q["kind"] for q in items)
    problems += [f"kind {k}: {kinds[k]} questions, at least {MIN_PER_KIND} needed" for k in KINDS if kinds[k] < MIN_PER_KIND]
    for split in ("dev", "test"):
        part = [q for q in items if q["split"] == split]
        if not any(q["kind"] == "no_answer" for q in part):
            problems.append(f"{split}: no question without an answer in the corpus")
        if not any(q["kind"] in ("stale", "similar") for q in part):
            problems.append(f"{split}: no trap question (outdated version / similar documents)")
    return problems


def run() -> None:
    items = load("dev") + load("test")
    problems = lint()
    by = Counter((q["split"], q["kind"]) for q in items)
    print(f"{len(items)} questions: " + ", ".join(f"{s} {sum(v for (sp, _), v in by.items() if sp == s)}"
                                                  for s in ("dev", "test")))
    for k in sorted(KINDS):
        print(f"  {k:<14} dev {by[('dev', k)]}  test {by[('test', k)]}")
    if problems:
        print("\n".join(["PROBLEMS:"] + problems))
        raise SystemExit(1)
    print("test set OK: every evidence phrase is in its document")

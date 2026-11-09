"""Duplicates between documents.

  * exact duplicate: the same normalised text (sha256), e.g. one file published twice
  * near duplicate: almost the same text (Jaccard similarity of word 5-grams >= NEAR_DUP)
  * related: a large share of one document is repeated in another (containment >= RELATED), e.g. a
    JRC news article that retells its bulletin; both are kept, the link is written to the manifest

The first document in registry order is kept, the later one is marked and left out of the index.
"""

import hashlib
import re

SHINGLE = 5
NEAR_DUP = 0.85
RELATED = 0.2


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shingles(text: str, k: int = SHINGLE) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def compare(a: set[str], b: set[str]) -> tuple[float, float]:
    """(Jaccard, containment of the smaller set in the larger one)."""
    if not a or not b:
        return 0.0, 0.0
    inter = len(a & b)
    return inter / len(a | b), inter / min(len(a), len(b))


def find_duplicates(docs: list[tuple[str, str]]) -> dict[str, dict]:
    """docs: (doc_id, full text) in registry order -> {doc_id: {status, duplicate_of, related}}."""
    out: dict[str, dict] = {}
    seen_hash: dict[str, str] = {}
    kept: list[tuple[str, set[str]]] = []
    for doc_id, text in docs:
        h = text_hash(text)
        info = {"status": "ok", "duplicate_of": "", "related": [], "doc_hash": h}
        if h in seen_hash:
            info.update(status="exact_duplicate", duplicate_of=seen_hash[h])
            out[doc_id] = info
            continue
        seen_hash[h] = doc_id
        sh = shingles(text)
        for other_id, other_sh in kept:
            jaccard, containment = compare(sh, other_sh)
            if jaccard >= NEAR_DUP:
                info.update(status="near_duplicate", duplicate_of=other_id)
                break
            if containment >= RELATED:
                info["related"].append(other_id)
        if info["status"] == "ok":
            kept.append((doc_id, sh))
        out[doc_id] = info
    # related links in both directions
    for doc_id, info in out.items():
        for other in info["related"]:
            if doc_id not in out[other]["related"]:
                out[other]["related"].append(doc_id)
    return out

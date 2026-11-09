"""Embeddings (fastembed, ONNX on CPU, no torch) with a disk cache.

The cache key is sha256(model + text): rebuilding the index after a change embeds only the new or
changed chunks. Cache: .cache/embeddings/<model>.npz (re-creatable, not in git).
"""

import hashlib
import re
from functools import lru_cache

import numpy as np

from ..common.settings import CACHE, MODELS_DIR, use_local_model_dirs

EMB_CACHE = CACHE / "embeddings"

# Models compared in the retrieval evaluation (results/rag/retrieval.md).
MODELS = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",   # 384 dim, 0.2 GB: the lecture's
    "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",    # 768 dim, 1.0 GB
    "e5": "intfloat/multilingual-e5-large",                                    # 1024 dim, 2.2 GB
}
# E5 was trained with these prefixes; the paraphrase models without any.
PREFIXES = {"e5": ("query: ", "passage: ")}


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name)


@lru_cache(maxsize=4)
def _model(key: str):
    use_local_model_dirs()
    from fastembed import TextEmbedding

    return TextEmbedding(MODELS[key], cache_dir=str(MODELS_DIR / "fastembed"))


def _hash(key: str, text: str) -> str:
    return hashlib.sha256(f"{MODELS[key]}\n{text}".encode("utf-8")).hexdigest()


class Embedder:
    def __init__(self, key: str) -> None:
        if key not in MODELS:
            raise SystemExit(f"unknown embedding model {key!r}; known: {', '.join(MODELS)}")
        self.key = key
        self.name = MODELS[key]
        self.query_prefix, self.passage_prefix = PREFIXES.get(key, ("", ""))
        self.path = EMB_CACHE / f"{_slug(self.name)}.npz"
        self._cache: dict[str, np.ndarray] = {}
        if self.path.exists():
            data = np.load(self.path)
            self._cache = dict(zip(data["keys"].tolist(), data["vectors"]))

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.array(list(_model(self.key).embed(texts, batch_size=16)), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def passages(self, texts: list[str]) -> np.ndarray:
        """Vectors of chunks (from the cache when possible); new ones are added to the cache."""
        keys = [_hash(self.key, self.passage_prefix + t) for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self._cache]
        if missing:
            print(f"    embedding {len(missing)} new chunks with {self.key} (cached: {len(keys) - len(missing)})...")
            vecs = self._embed([self.passage_prefix + texts[i] for i in missing])
            for i, v in zip(missing, vecs):
                self._cache[keys[i]] = v
            self.save()
        return np.stack([self._cache[k] for k in keys]) if keys else np.zeros((0, 1), np.float32)

    def query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]

    def save(self) -> None:
        EMB_CACHE.mkdir(parents=True, exist_ok=True)
        keys = list(self._cache)
        np.savez(self.path, keys=np.array(keys), vectors=np.stack([self._cache[k] for k in keys]))


def window_stats(key: str, texts: list[str]) -> dict | None:
    """How many chunks are longer than the input window of the model (the rest of such a chunk is cut
    off before embedding and cannot be found by vector search). Tokens of the model's own tokenizer."""
    try:
        from tokenizers import Tokenizer

        tok = _model(key).model.tokenizer
        window = int(tok.truncation["max_length"])
        full = Tokenizer.from_str(tok.to_str())
        full.no_truncation()
        full.no_padding()
    except Exception as e:                      # another fastembed version: the statistic is skipped
        print(f"    no tokenizer statistics for {key}: {e}")
        return None
    prefix = PREFIXES.get(key, ("", ""))[1]
    lengths = sorted(len(full.encode(prefix + t).ids) for t in texts)
    over = sum(n > window for n in lengths)
    return {"window": window, "median_tokens": lengths[len(lengths) // 2],
            "over_window_%": round(100 * over / len(lengths), 1)}

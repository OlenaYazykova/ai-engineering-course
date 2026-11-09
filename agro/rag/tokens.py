"""Token counting with the tokenizer of the generation model family (tiktoken o200k_base).

The tokenizer file (~3.6 MB) is downloaded once into MODELS_DIR/tiktoken.
"""

from functools import lru_cache

from ..common.settings import use_local_model_dirs

ENCODING = "o200k_base"


@lru_cache(maxsize=1)
def _encoder():
    use_local_model_dirs()
    import tiktoken

    return tiktoken.get_encoding(ENCODING)


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


def split_tokens(text: str, size: int, overlap: int) -> list[str]:
    """Fixed-size windows of `size` tokens with `overlap` tokens repeated (the baseline chunker)."""
    enc = _encoder()
    ids = enc.encode(text)
    out, start = [], 0
    while start < len(ids):
        out.append(enc.decode(ids[start:start + size]))
        if start + size >= len(ids):
            break
        start += size - overlap
    return out

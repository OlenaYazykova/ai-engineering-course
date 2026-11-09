"""Paths shared by every stage, and where downloaded models and caches live.

Models (OCR, embeddings, the tokenizer file) are downloaded on first use into MODELS_DIR. By default
it is `.models/` inside the project folder, so it stays on the same disk as the project and never
lands in the home folder; override with AGRO_MODELS_DIR in .env.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"                      # downloaded originals (not in git)
SOURCES_CSV = DATA / "sources.csv"      # the registry of every document of the project
CORPUS = DATA / "corpus"                # homework 2: cleaned documents + manifest
RAG_DATA = DATA / "rag"                 # homework 2: chunks
CACHE = ROOT / ".cache"                 # re-creatable caches (not in git)
RESULTS_RAG = ROOT / "results" / "rag"

MODELS_DIR = Path(os.getenv("AGRO_MODELS_DIR", ROOT / ".models"))


def use_local_model_dirs() -> None:
    """Point the libraries' download folders to MODELS_DIR (call before importing them)."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(MODELS_DIR / "tiktoken"))
    os.environ.setdefault("FASTEMBED_CACHE_PATH", str(MODELS_DIR / "fastembed"))
    os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
    os.environ.setdefault("EASYOCR_MODULE_PATH", str(MODELS_DIR / "easyocr"))

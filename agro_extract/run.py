"""Run a model x prompt x sampling over every text and log every result.

results/<model>__<prompt>__<sampling>.jsonl, one JSON line per text:
  text_id, source, language, model_key, model, prompt_version, prompt_hash, temperature, top_p,
  status (ok / fixed / failed), attempts, seconds, input_tokens, output_tokens, cost_usd,
  raw (first answer), raw_fixed (answer after the correction attempt), parsed (after removing
  unsupported values), removed (those values), error, ts
A run writes to <name>.jsonl.partial first, so an interrupted run continues where it stopped.
"""

import hashlib
import json
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .providers import CachedProvider, Completion, Provider, ProviderError, make_provider
from .checks import clean_lists
from .schema import AgroReport, json_schema

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.toml"
TEXTS = ROOT / "data" / "texts"
PROMPTS = ROOT / "prompts"
RESULTS = ROOT / "results"
CACHE = ROOT / ".cache" / "responses"

REPAIR_MESSAGE = (
    "Your JSON does not pass validation:\n{error}\n"
    "Fix these problems using only facts from the document and return the corrected JSON only."
)


def load_config() -> dict:
    with CONFIG.open("rb") as f:
        return tomllib.load(f)


def source_of(text_id: str) -> tuple[str, str]:
    """(source group, language) from the text id."""
    if text_id.startswith("uk_hydromet"):
        return "hydromet", "uk"
    if text_id.startswith("en_jrcnews"):
        return "jrc_news", "en"
    if text_id.startswith("en_jrc"):
        return "jrc_bulletin", "en"
    return "other", "?"


def load_texts(ids: list[str] | None = None) -> dict[str, str]:
    texts = {p.stem: p.read_text(encoding="utf-8") for p in sorted(TEXTS.glob("*.txt"))}
    if not texts:
        raise SystemExit(f"No texts in {TEXTS.relative_to(ROOT)}/ (run scripts/build_texts.py first)")
    if ids:
        missing = [i for i in ids if i not in texts]
        if missing:
            raise SystemExit(f"Unknown text ids: {missing}")
        texts = {i: texts[i] for i in ids}
    return texts


def load_prompt(version: str) -> tuple[str, str]:
    """Prompt text with the schema filled in, and a short hash of the prompt file."""
    path = PROMPTS / f"{version}.txt"
    if not path.exists():
        raise SystemExit(f"No prompt {path.relative_to(ROOT)}")
    template = path.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(template.encode()).hexdigest()[:8]
    schema = json.dumps(json_schema(), ensure_ascii=False, separators=(",", ":"))
    return template.replace("{schema}", schema), prompt_hash


def build_messages(system: str, text: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"<document>\n{text.strip()}\n</document>"},
    ]


def validate(content: str, text: str) -> AgroReport:
    """Schema + strict checks of numbers and dates (raises ValidationError)."""
    return AgroReport.model_validate_json(content, context={"text": text})


def validate_and_clean(content: str, text: str) -> tuple[dict, list[str]]:
    """Validate strictly, then remove or reset values the text does not support."""
    return clean_lists(validate(content, text).model_dump(), text)


def short_error(e: ValidationError) -> str:
    lines = []
    for err in e.errors()[:8]:
        loc = ".".join(str(x) for x in err["loc"]) or "(root)"
        lines.append(f"- {loc}: {err['msg']}")
    return "\n".join(lines)


def extract_one(provider: Provider, messages: list[dict], text: str, sampling: dict,
                max_tokens: int) -> dict:
    """Call the model; an invalid answer gets one correction attempt, then status 'failed'."""
    schema = json_schema()
    res = {"status": "failed", "attempts": 0, "seconds": 0.0, "input_tokens": 0,
           "output_tokens": 0, "cost_usd": 0.0, "raw": None, "raw_fixed": None,
           "parsed": None, "removed": [], "error": None, "cached": False}

    def call(msgs) -> Completion:
        start = time.perf_counter()
        c = None
        try:
            c = provider.complete(msgs, schema, sampling, max_tokens)
        finally:
            res["attempts"] += 1
            if c is not None and c.cached_seconds is not None:   # replayed: report original latency
                res["seconds"] += c.cached_seconds
                res["cached"] = True
            else:
                res["seconds"] += time.perf_counter() - start
        res["input_tokens"] += c.input_tokens
        res["output_tokens"] += c.output_tokens
        res["cost_usd"] += provider.cost_usd(c)
        return c

    try:
        first = call(messages)
        res["raw"] = first.content
        if first.finish_reason == "length":
            res["error"] = f"answer cut at max_tokens={max_tokens}"
            return res
        try:
            res["parsed"], res["removed"] = validate_and_clean(first.content, text)
            res["status"] = "ok"
            return res
        except ValidationError as e:
            error = short_error(e)

        repair = messages + [
            {"role": "assistant", "content": first.content},
            {"role": "user", "content": REPAIR_MESSAGE.format(error=error)},
        ]
        second = call(repair)
        res["raw_fixed"] = second.content
        try:
            res["parsed"], res["removed"] = validate_and_clean(second.content, text)
            res["status"] = "fixed"
        except ValidationError as e:
            res["error"] = "invalid after correction:\n" + short_error(e)
    except ProviderError as e:
        res["error"] = f"provider: {e}"
    return res


def run_name(model_key: str, prompt: str, sampling_key: str) -> str:
    return f"{model_key}__{prompt}__{sampling_key}"


def run_experiment(model_key: str, prompt: str, sampling_key: str, *, force: bool = False,
                   ids: list[str] | None = None, config: dict | None = None,
                   provider: Provider | None = None, subdir: str = "smoke") -> Path:
    cfg = config or load_config()
    model_cfg = cfg["models"][model_key]
    sampling = cfg["sampling"][sampling_key]
    max_tokens = int(cfg["run"].get("max_tokens", 1500))

    RESULTS.mkdir(exist_ok=True)
    name = run_name(model_key, prompt, sampling_key)
    out = RESULTS / f"{name}.jsonl"
    if ids:  # a partial run (smoke test, regression check) never overwrites a full result file
        out = RESULTS / subdir / f"{name}.jsonl"
        out.parent.mkdir(exist_ok=True)
        force = True
    if out.exists() and not force:
        print(f"skip {name}: {out.relative_to(ROOT)} exists (use --force to redo)")
        return out

    partial = out.with_suffix(".jsonl.partial")
    done: set[str] = set()
    if force and partial.exists():
        partial.unlink()
    if partial.exists():
        done = {json.loads(line)["text_id"] for line in partial.read_text(encoding="utf-8").splitlines() if line}
        print(f"continue {name}: {len(done)} texts already done")

    system, prompt_hash = load_prompt(prompt)
    texts = load_texts(ids)
    provider = provider or make_provider(model_cfg)
    if cfg["run"].get("cache", True) and sampling["temperature"] == 0 and not isinstance(provider, CachedProvider):
        provider = CachedProvider(provider, CACHE)
    print(f"run {name}: {model_cfg['model']}, prompt {prompt} ({prompt_hash}), "
          f"T={sampling['temperature']} top_p={sampling['top_p']}, {len(texts)} texts")

    with partial.open("a", encoding="utf-8") as f:
        for i, (text_id, text) in enumerate(texts.items(), 1):
            if text_id in done:
                continue
            res = extract_one(provider, build_messages(system, text), text, sampling, max_tokens)
            source, language = source_of(text_id)
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "text_id": text_id, "source": source, "language": language,
                "model_key": model_key, "model": model_cfg["model"],
                "prompt_version": prompt, "prompt_hash": prompt_hash,
                "sampling": sampling_key, "temperature": sampling["temperature"],
                "top_p": sampling["top_p"],
                **res,
                "seconds": round(res["seconds"], 3),
                "cost_usd": round(res["cost_usd"], 8),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            note = f"  {(res['error'] or '').splitlines()[0][:80]}" if res["error"] else ""
            print(f"  [{i}/{len(texts)}] {text_id:<40} {res['status']:<6} {res['seconds']:6.1f}s{note}")

    partial.replace(out)
    hits = getattr(provider, "hits", 0)
    if hits:
        print(f"  {hits} answers replayed from the cache (.cache/responses/)")
    return out


def run_all(force: bool = False) -> list[Path]:
    cfg = load_config()
    outs = []
    for model_key, prompt, sampling_key in cfg["run"]["experiments"]:
        try:
            outs.append(run_experiment(model_key, prompt, sampling_key, force=force, config=cfg))
        except ProviderError as e:  # e.g. missing key: report and go on with the other runs
            print(f"skip {run_name(model_key, prompt, sampling_key)}: {e}")
    return outs

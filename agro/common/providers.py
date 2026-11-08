"""One interface for every model: Provider.complete(messages, schema, sampling) -> Completion.

Implementations:
  * OpenAICompatibleProvider: OpenRouter (cloud models) with strict structured output
  * OllamaProvider: a local model through the native Ollama API (JSON-schema "format", num_ctx)
  * CachedProvider: wraps any provider and replays identical requests from a disk cache
All network providers have a timeout and retries on network errors, timeouts, rate limits and
server errors.
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx


@dataclass
class Completion:
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    cached_seconds: float | None = None   # set when the answer comes from the cache


class ProviderError(Exception):
    """The call failed after all retries."""


class Provider:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = cfg["model"]
        self.timeout = float(cfg.get("timeout_s", 60))
        self.max_retries = int(cfg.get("max_retries", 2))

    def complete(self, messages: list[dict], schema: dict, sampling: dict, max_tokens: int) -> Completion:
        raise NotImplementedError

    def cost_usd(self, c: Completion) -> float:
        return (c.input_tokens * self.cfg.get("price_in", 0.0)
                + c.output_tokens * self.cfg.get("price_out", 0.0)) / 1_000_000

    def _with_retries(self, call):
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                return call()
            except RetryableError as e:
                if attempt == self.max_retries:
                    raise ProviderError(f"{e} (after {attempt + 1} attempts)") from e
                time.sleep(delay)
                delay *= 2


class RetryableError(Exception):
    pass


def _retryable_status(code: int) -> bool:
    return code == 429 or code >= 500


class OpenAICompatibleProvider(Provider):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        from openai import OpenAI

        key = os.getenv(cfg.get("api_key_env", "OPENROUTER_API_KEY"))
        if not key:
            raise ProviderError(f"{cfg.get('api_key_env')} is missing in .env")
        # Retries are done here, not inside the SDK, so every attempt is counted the same way.
        self.client = OpenAI(base_url=cfg["base_url"], api_key=key, timeout=self.timeout, max_retries=0)

    def _response_format(self, schema: dict) -> dict:
        # "json_schema": strict structured output; "json_object": valid JSON only, the schema is
        # in the prompt (fallback for models without strict schema support)
        if self.cfg.get("response_format", "json_schema") == "json_object":
            return {"type": "json_object"}
        return {"type": "json_schema",
                "json_schema": {"name": "agro_report", "strict": True, "schema": schema}}

    def complete(self, messages, schema, sampling, max_tokens):
        import openai

        def call():
            try:
                r = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=sampling["temperature"],
                    top_p=sampling["top_p"],
                    max_tokens=max_tokens,
                    response_format=self._response_format(schema),
                    # OpenRouter: route only to providers that support every parameter we send
                    extra_body={"provider": {"require_parameters": True}},
                )
            except (openai.APITimeoutError, openai.APIConnectionError) as e:
                raise RetryableError(type(e).__name__) from e
            except openai.APIStatusError as e:
                if _retryable_status(e.status_code):
                    raise RetryableError(f"HTTP {e.status_code}") from e
                raise ProviderError(f"HTTP {e.status_code}: {e.message}") from e
            choice = r.choices[0]
            return Completion(
                content=choice.message.content or "",
                input_tokens=r.usage.prompt_tokens if r.usage else 0,
                output_tokens=r.usage.completion_tokens if r.usage else 0,
                finish_reason=choice.finish_reason or "",
            )

        return self._with_retries(call)


class OllamaProvider(Provider):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.url = cfg.get("base_url", "http://localhost:11434").rstrip("/") + "/api/chat"
        self.num_ctx = int(cfg.get("num_ctx", 8192))

    def complete(self, messages, schema, sampling, max_tokens):
        body = {
            "model": self.model,
            "messages": messages,
            "format": _inline_refs(schema),   # decoding is constrained to the JSON schema
            "stream": False,
            "options": {
                "temperature": sampling["temperature"],
                "top_p": sampling["top_p"],
                "num_ctx": self.num_ctx,
                "num_predict": max_tokens,
            },
        }

        def call():
            try:
                r = httpx.post(self.url, json=body, timeout=self.timeout)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                raise RetryableError(f"{type(e).__name__} (is `ollama serve` running?)") from e
            if _retryable_status(r.status_code):
                raise RetryableError(f"HTTP {r.status_code}")
            if r.status_code != 200:
                raise ProviderError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            prompt_tokens = int(data.get("prompt_eval_count", 0))
            if prompt_tokens >= self.num_ctx:
                raise ProviderError(f"input of {prompt_tokens} tokens does not fit num_ctx={self.num_ctx}")
            return Completion(
                content=data.get("message", {}).get("content", ""),
                input_tokens=prompt_tokens,
                output_tokens=int(data.get("eval_count", 0)),
                finish_reason="length" if data.get("done_reason") == "length" else "stop",
            )

        return self._with_retries(call)


class CachedProvider(Provider):
    """Replays identical requests from .cache/responses/ instead of calling the model again.

    The key is a hash of model, messages (prompt + text), schema, sampling and max_tokens, so any
    change in the prompt, the text or the parameters is a new request. The original latency is
    stored with the answer and reported again, so cached runs keep honest latency numbers.
    Only used for deterministic sampling (temperature 0): repeating a T>0 answer would hide its
    variance.
    """

    def __init__(self, inner: Provider, cache_dir: Path):
        super().__init__(inner.cfg)
        self.inner = inner
        self.dir = cache_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0

    def _key(self, messages, schema, sampling, max_tokens) -> str:
        blob = json.dumps({"model": self.model, "messages": messages, "schema": schema,
                           "sampling": sampling, "max_tokens": max_tokens},
                          ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def complete(self, messages, schema, sampling, max_tokens):
        path = self.dir / f"{self._key(messages, schema, sampling, max_tokens)}.json"
        if path.exists():
            self.hits += 1
            data = json.loads(path.read_text(encoding="utf-8"))
            return Completion(**data)
        start = time.perf_counter()
        c = self.inner.complete(messages, schema, sampling, max_tokens)
        data = asdict(c)
        data["cached_seconds"] = round(time.perf_counter() - start, 3)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return c


def _inline_refs(schema: dict) -> dict:
    defs = schema.get("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


def make_provider(cfg: dict) -> Provider:
    kind = cfg["provider"]
    if kind == "openai_compatible":
        return OpenAICompatibleProvider(cfg)
    if kind == "ollama":
        return OllamaProvider(cfg)
    raise ValueError(f"unknown provider {kind!r}")

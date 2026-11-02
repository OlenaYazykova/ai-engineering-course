# Agro-analyst, stage 1: Structured Extraction Service

The service extracts structured data on crop conditions and soil moisture from "dirty" texts of
agrometeorological bulletins (Ukrainian Hydrometeorological Center, in Ukrainian) and JRC MARS bulletins
(in English), and compares cloud models (gpt-4o-mini and gemini-2.5-flash-lite via OpenRouter) with a local one
(qwen2.5:3b via Ollama) on quality, cost and speed.

This is the first stage of the course capstone project, plan: [PROJECT_PLAN.md](PROJECT_PLAN.md).
Comparison report: [REPORT.md](REPORT.md).

## Run

```bash
pip install -r requirements.txt
cp .env.example .env            # add OPENROUTER_API_KEY
ollama pull qwen2.5:3b          # local model (Ollama: https://ollama.com)
make run                        # or: python main.py
```

`make run` runs every experiment from `config.toml` (model × prompt × sampling) over all texts in
`data/texts/`, skips the ones that are already done, and builds the metrics table `results/metrics.md`.
A cloud run takes a few minutes and costs cents; a local run on a laptop takes about 3–5 min per text
(2–3 hours per run). The finished runs are committed in `results/`, so the table can be rebuilt without
models or a key: `make metrics`.

| Command | What it does |
|---|---|
| `make run` | all experiments + metrics |
| `make run-all` | everything from scratch (`--force`) |
| `make metrics` | metrics tables and error lists only |
| `make smoke MODEL=qwen3b ID=uk_hydromet_2023-07-d1__moisture` | one text with one model |
| `python main.py run --model gpt4o_mini --prompt v2 --sampling t0` | one experiment |
| `make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2` | new prompt vs baseline on the golden set (exit code 1 if worse) |
| `make revalidate` | re-check the saved answers with the current checks, then metrics (no model calls) |
| `make check-golden` | validate the golden set with the same checks as the model answers |
| `make test` | unit tests, no network |
| `make fetch` / `make texts` | download the documents / cut them into texts |

## How it works

```
data/texts/<id>.txt ── prompts/<version>.txt (+ JSON schema) ──> model ──> JSON
                                                                   │
   schema.py + checks.py: types, enums, mm / Mt next to units ─────────┤  strict
        invalid answer → one correction attempt → ok / fixed / failed
                                                                   │
   checks.clean_lists: values not supported by the text ──────────┤  soft: removed / reset + logged
                                                                   ▼
        results/<model>__<prompt>__<sampling>.jsonl ──> metrics.py against data/golden/
```

- `agro_extract/schema.py`: the `AgroReport` schema (single source of truth for fields, types and enums)
  and checks a JSON schema cannot express: ranges, min ≤ max, every crop once.
- `agro_extract/checks.py`: deterministic checks against the source text.
  **Strict** (the answer is invalid → one correction attempt → `failed`): `min_mm` / `max_mm` must be
  written in the text followed by "мм / mm" (not any number anywhere, e.g. a date or a %),
  `production_mt` followed by "Mt / млн т"; mm values always need a soil layer.
  **Soft** (the value is removed or reset and logged in `removed`; the answer stays valid, so one wrong
  detail does not throw away the correct fields):
  - every oblast in `deficit_oblasts`, every crop in `crops` / `yield_outlook` and every hazard must be
    supported by a keyword in the text (Ukrainian and English stems; words split by PDF extraction are
    found too), duplicates are removed;
  - year, month name and decade ("першу / другу / третю декаду") must be written in the text → else null;
  - soil layer: "орний шар / 0-20 см / arable" for `0-20cm`, "метровий шар / 0-100 см / metre" for
    `0-100cm` → else the layer the text does mention, or `not_stated`;
  - moisture status: words of that class ("недостатні / посуха / dry", "оптимальні / достатні / adequate",
    "перезволоження / excess"), `mixed` needs two classes → else `not_stated`;
  - crop condition and BBCH stage (keywords of the phase: "кущіння", "цвітіння", "воскова стиглість",
    "heading", ...) must stand within 250 characters of the crop name → else `not_stated` / null;
    `vs_5yr_average` needs "5-year average", "середн..." → else `not_stated`;
  - a crop with neither a stage nor a condition and a yield entry with neither a comparison nor a
    production figure are removed (they carry no information).
- `agro_extract/providers.py`: the common interface `Provider.complete()` and two implementations:
  OpenRouter with strict structured output and Ollama (native API with the JSON schema in `format` and
  `num_ctx`). Both have a timeout and retries with backoff on network errors, 429 and 5xx.
  `CachedProvider` wraps either one and replays identical T=0 requests from `.cache/responses/`
  (no second payment; the original latency is kept).
- `agro_extract/run.py`: the run loop, validation, one correction attempt, and a log line for every
  result: model, prompt version and hash, temperature, top_p, status, time, tokens, cost, raw and parsed
  answer, removed or reset values. An interrupted run continues where it stopped.
- `agro_extract/revalidate.py`: re-applies the current checks to the answers saved in `results/`
  (no model calls; the previous result is kept in `status_before` / `parsed_before`).
- `agro_extract/metrics.py`: field accuracy on the golden set (overall, Hydromet, JRC), set F1,
  hallucinations, removed or reset values, valid %, latency p50/p95, cost per 1000 documents; errors per
  field in `results/errors/`.
- `agro_extract/regress.py`: regression check of a new prompt against a baseline on the golden set,
  report in `results/regression/`.
- `config.toml`: models (prices, timeout, retries), sampling configurations, experiment matrix.
- `prompts/`: prompt versions and `CHANGELOG.md`.

## Data

- `data/texts/`: texts for the model: sections "Зволоження ґрунту" (soil moisture), "Ріст і розвиток"
  (crop growth) and others from Hydromet bulletins (2021–2023), first pages of JRC MARS Global outlook:
  Ukraine bulletins (2022–2026) and the JRC news articles on them. PDF text is kept as is: broken words
  and table fragments are the "dirtiness" the task is about.
- `data/golden/`: 10 manually labelled answers (golden set), list in `data/golden_ids.txt`.
- `data/sources.csv`: URL and download date of every document.
- `data/raw/` (not in git): original PDF/HTML, reproduced with `make fetch && make texts`.

The texts contain no personal data: they are public bulletins of Ukrainian and European institutions.

## Golden set

Every file `data/golden/<text_id>.json` is the correct `AgroReport` for `data/texts/<text_id>.txt`.
`make check-golden` validates each file with the same strict and soft checks as the model answers
and fails if any golden value would be removed or reset (all 10 files pass: the checks never remove a
correct value). Labelling rules for ambiguous cases are described in `prompts/CHANGELOG.md` (v2).

## Troubleshooting

- `OPENROUTER_API_KEY is missing`: no `.env` with the key.
- `ConnectError ... is ollama serve running?`: Ollama is not running.
- `does not fit num_ctx`: the text is longer than the local model context; increase `num_ctx` in `config.toml`.
- Local runs are too slow: remove extra `qwen3b` rows from `experiments` in `config.toml`.

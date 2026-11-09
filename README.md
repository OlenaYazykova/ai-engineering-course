# Agro-analyst

An assistant for agro analysts over the agrometeorological bulletins of the Ukrainian Hydrometeorological
Center (in Ukrainian) and the JRC MARS bulletins on Ukraine (in English). This is the course capstone project
of the AI Engineering course; it grows stage by stage, plan: [PROJECT_PLAN.md](PROJECT_PLAN.md).

| Stage | What it does | Code | Commands | Git tag | Report |
|---|---|---|---|---|---|
| 1. Structured extraction (homework 1) | bulletin text → JSON (soil moisture, crops, hazards, yield outlook) | `agro/extract/` | `make extract-…` | `hw1` | [reports/hw1.md](reports/hw1.md) |
| 2. RAG + evals (homework 2) | question → answer with sources, evals in CI | `agro/rag/` | `make rag-…` | in progress | — |

Shared code: `agro/common/` (model providers, response cache, paths), `agro/corpus/` (the documents:
download, reading every format, OCR, cleaning, duplicates). `make test` runs the unit tests of every stage,
`make run` the pipeline of the current stage.

## Stage 2: RAG over the bulletins + evals (in progress)

Step 1 (done): corpus, ingestion, personal data masking, chunking. Steps 2-4 (index and hybrid search, answers with
citations, evals in CI) follow.

### Run

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # OCR needs torch; CPU build
make install
make fetch          # originals into data/raw/ (one CSV is exported by hand: the command says how)
make run            # = make rag-ingest rag-chunk
```

Models (OCR, tokenizer, later embeddings) are downloaded on first use into `.models/` in the project
folder (or `AGRO_MODELS_DIR` from `.env`), never into the home folder. LibreOffice (`soffice`) is needed
for the one `.doc` file.

### Corpus

48 documents, 6 formats (PDF, HTML, DOCX, DOC, XLSX, CSV), Ukrainian and English: Hydromet decadal
bulletins and annual reviews, JRC MARS bulletins and news, Odesa oblast and national crop statistics.
Sources, licences, the reading of every format and the traps of the corpus (a duplicate, outdated
versions, similar documents, an off-topic document): [data/corpus/README.md](data/corpus/README.md).
Every document: `data/corpus/manifest.csv`.

Personal data (names of analysts and staff, e-mails, phones) is masked before the corpus is written, by
Microsoft Presidio with spaCy NER (Ukrainian and English) and our rules as a Presidio recognizer; every
document is checked again after masking: [data/corpus/README.md](data/corpus/README.md#personal-data).

### Chunking

Structural (`agro/rag/chunking.py`): a chunk never crosses a heading; paragraphs of one section are packed
up to 450 tokens (`chunk_tokens` in config.toml; a longer paragraph is split at sentence ends); a table is its own chunk, split by rows
with the header row repeated in every part; every chunk carries a context line (document, period,
section) for the embeddings and for the model. Compared with fixed windows of 450 tokens / 50 overlap
on the same corpus, and with structural chunks of 300 tokens: [results/rag/chunking.md](results/rag/chunking.md)
(chunks starting mid-sentence, tables cut without their header); retrieval quality of all three: step 2.

## Stage 1: Structured Extraction Service

The service extracts structured data on crop conditions and soil moisture from "dirty" texts of
agrometeorological bulletins (Ukrainian Hydrometeorological Center, in Ukrainian) and JRC MARS bulletins
(in English), and compares cloud models (gpt-4o-mini and gemini-2.5-flash-lite via OpenRouter) with a local one
(qwen2.5:3b via Ollama) on quality, cost and speed.

Comparison report: [reports/hw1.md](reports/hw1.md). The version submitted for homework 1 is the git tag `hw1`.

### Run

```bash
pip install -r requirements.txt
cp .env.example .env            # add OPENROUTER_API_KEY
ollama pull qwen2.5:3b          # local model (Ollama: https://ollama.com)
make extract-run                # or: python main.py extract all
```

`make extract-run` runs every experiment from `config.toml` (model × prompt × sampling) over all texts in
`data/extract/texts/`, skips the ones that are already done, and builds the metrics table `results/extract/metrics.md`.
A cloud run takes a few minutes and costs cents; a local run on a laptop takes about 3–5 min per text
(2–3 hours per run). The finished runs are committed in `results/extract/`, so the table can be rebuilt without
models or a key: `make extract-metrics`.

| Command | What it does |
|---|---|
| `make extract-run` | all experiments + metrics |
| `make extract-run-all` | everything from scratch (`--force`) |
| `make extract-metrics` | metrics tables and error lists only |
| `make extract-smoke MODEL=qwen3b ID=uk_hydromet_2023-07-d1__moisture` | one text with one model |
| `python main.py extract run --model gpt4o_mini --prompt v2 --sampling t0` | one experiment |
| `make extract-regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2` | new prompt vs baseline on the dev golden set (exit code 1 if worse) |
| `make extract-revalidate` | re-check the saved answers with the current checks, then metrics (no model calls) |
| `make extract-before-checks` | accuracy of the answers before the fact checks (git tag `hw1-initial`) on dev and test, no model calls |
| `make extract-check-golden` | validate the dev and test golden sets with the same checks as the model answers |
| `make test` | unit tests, no network |
| `make fetch` / `make extract-texts` | download the documents / cut them into texts |

### How it works

```
data/extract/texts/<id>.txt ── prompts/extract/<version>.txt (+ JSON schema) ──> model ──> JSON
                                                                   │
   schema.py + checks.py: types, enums, mm / Mt next to units ─────────┤  strict
        invalid answer → one correction attempt → ok / fixed / failed
                                                                   │
   checks.clean_lists: values not supported by the text ──────────┤  soft: removed / reset + logged
                                                                   ▼
        results/extract/<model>__<prompt>__<sampling>.jsonl ──> metrics.py against data/extract/golden/ + golden_test/
```

- `agro/extract/schema.py`: the `AgroReport` schema (single source of truth for fields, types and enums)
  and checks a JSON schema cannot express: ranges, min ≤ max, every crop once.
- `agro/extract/checks.py`: deterministic checks against the source text.
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
- `agro/common/providers.py`: the common interface `Provider.complete()` and two implementations:
  OpenRouter with strict structured output and Ollama (native API with the JSON schema in `format` and
  `num_ctx`). Both have a timeout and retries with backoff on network errors, 429 and 5xx.
  `CachedProvider` wraps either one and replays identical T=0 requests from `.cache/responses/`
  (no second payment; the original latency is kept).
- `agro/extract/run.py`: the run loop, validation, one correction attempt, and a log line for every
  result: model, prompt version and hash, temperature, top_p, status, time, tokens, cost, raw and parsed
  answer, removed or reset values. An interrupted run continues where it stopped.
- `agro/extract/revalidate.py`: re-applies the current checks to the answers saved in `results/extract/`
  (no model calls; the previous result is kept in `status_before` / `parsed_before`).
- `agro/extract/metrics.py`: field accuracy on the dev and test golden sets (overall, Hydromet, JRC,
  95 % bootstrap interval), set F1,
  hallucinations, removed or reset values, valid %, latency p50/p95, cost per 1000 documents; errors per
  field in `results/extract/errors/`.
- `agro/extract/regress.py`: regression check of a new prompt against a baseline on the golden set,
  report in `results/extract/regression/`.
- `agro/extract/before_checks.py`: scores the answers of the first version (before the fact checks, git tag
  `hw1-initial`) on the dev and test golden sets, for the before / after comparison in [reports/hw1.md](reports/hw1.md).
- `config.toml`: models (prices, timeout, retries), sampling configurations, experiment matrix.
- `prompts/extract/`: prompt versions and `CHANGELOG.md`.

### Data

- `data/extract/texts/`: texts for the model: sections "Зволоження ґрунту" (soil moisture), "Ріст і розвиток"
  (crop growth) and others from Hydromet bulletins (2021–2023), first pages of JRC MARS Global outlook:
  Ukraine bulletins (2022–2026) and the JRC news articles on them. PDF text is kept as is: broken words
  and table fragments are the "dirtiness" the task is about.
- `data/extract/golden/` and `data/extract/golden_test/`: dev and held-out test golden sets (see below).
- `data/sources.csv`: URL and download date of every document.
- `data/raw/` (not in git): original PDF/HTML, reproduced with `make fetch && make extract-texts`; homework 1 uses only the documents listed in
  `data/extract/doc_ids.txt`.

The texts contain no personal data: they are public bulletins of Ukrainian and European institutions.

### Golden set

Two sets of manually checked answers, `data/extract/<set>/<text_id>.json` = the correct `AgroReport` for
`data/extract/texts/<text_id>.txt`:

- `data/extract/golden/` (**dev**, 10 texts, list in `data/extract/golden_ids.txt`): used for the error analysis,
  prompt v2 / v3 and the deterministic checks. Labelling rules for ambiguous cases are in
  `prompts/extract/CHANGELOG.md` (v2). `make extract-regress` uses only this set.
- `data/extract/golden_test/` (**held-out test**, 10 other texts of the same kinds): labelled after the
  prompt and the checks were finalised and committed, and never used to change them. It shows how the
  results transfer to texts that nothing was tuned on.

`make extract-metrics` reports accuracy on both sets with a 95 % bootstrap confidence interval.
`make extract-check-golden` validates both sets with the same strict and soft checks as the model answers:
every dev file must pass all of them; on the test set a correct value that the soft checks would
remove is reported (a false removal of the unchanged checks), not fixed.

### Troubleshooting

- `OPENROUTER_API_KEY is missing`: no `.env` with the key.
- `ConnectError ... is ollama serve running?`: Ollama is not running.
- `does not fit num_ctx`: the text is longer than the local model context; increase `num_ctx` in `config.toml`.
- Local runs are too slow: remove extra `qwen3b` rows from `experiments` in `config.toml`.

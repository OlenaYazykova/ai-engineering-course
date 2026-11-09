# Agro-analyst

An assistant for agro analysts over the agrometeorological bulletins of the Ukrainian Hydrometeorological
Center (in Ukrainian) and the JRC MARS bulletins on Ukraine (in English). This is the course capstone project
of the AI Engineering course; it grows stage by stage, plan: [PROJECT_PLAN.md](PROJECT_PLAN.md).

| Stage | What it does | Code | Commands | Git tag | Report |
|---|---|---|---|---|---|
| 1. Structured extraction (homework 1) | bulletin text → JSON (soil moisture, crops, hazards, yield outlook) | `agro/extract/` | `make extract-…` | `hw1` | [reports/hw1.md](reports/hw1.md) |
| 2. RAG + evals (homework 2) | question → answer with sources, evals in CI | `agro/rag/` | `make rag-…` | `hw2-v1` (steps 1-2), in progress | — |

Shared code: `agro/common/` (model providers, response cache, paths), `agro/corpus/` (the documents:
download, reading every format, OCR, cleaning, duplicates). `make test` runs the unit tests of every stage,
`make run` the pipeline of the current stage.

## Stage 2: RAG over the bulletins + evals (in progress)

Step 1 (done): corpus, ingestion, personal data masking, chunking. Step 2 (done): index, hybrid search, reranking,
filters, retrieval metrics. Steps 3-4 (answers with citations, evals in CI) follow.

### Run

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # OCR needs torch; CPU build
make install
make fetch          # originals into data/raw/ (one CSV is exported by hand: the command says how)
make run            # = make rag-ingest rag-chunk rag-lint-testset rag-index rag-retrieval-eval
python main.py rag search "Запаси вологи під кукурудзою на 31 липня 2023" --auto-filters
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
up to `chunk_tokens` (config.toml, 450) tokens, a longer paragraph is split at sentence ends; a table is
its own chunk, split by rows with the header row repeated in every part; every chunk carries a context
line (document, period, section) that is embedded with the text and shown to the model.

Why structural: the bulletins are written section by section ("Зволоження ґрунту", "Стан посівів"), and a
question is about one section of one decade; a fixed window glues the end of one section to the start of
the next and cuts tables away from their header row, so a cut table part no longer says which column
is which. Measured on the same corpus of 47 documents
([chunking.md](results/rag/chunking.md), [retrieval_dev.md](results/rag/retrieval_dev.md), 17 dev questions):

| | structural 300 | **structural 450 (used)** | fixed 450 / overlap 50 |
|---|---|---|---|
| chunks (avg tokens) | 2153 (277) | 1537 (373) | 1369 (443) |
| chunks starting mid-sentence | 2.4% | 3.2% | 52.6% |
| table parts without their header row | 0 | 0 | 537 |
| chunks longer than the e5 window (512 e5 tokens) | 0.3% | 32.5% | - |
| MRR, vector (e5) | 0.480 | **0.517** | 0.458 |
| MRR, hybrid + reranker (bge) | 0.561 | **0.565** | 0.503 |

Why 450: the window of e5 is 512 of its own tokens; a third of the 450-chunks is longer (tables up to
600 tokens, dense Ukrainian text) and is cut before embedding, while 300-chunks fit. Even so, 450 gives the
better vector search (0.517 vs 0.480) and the same quality after the reranker, which reads the whole chunk:
a longer chunk keeps a paragraph with its context (oblast, crop, period). Within 17 questions 0.561 vs
0.565 is no difference, so the smaller index (1537 chunks, not 2153) decides. Tables are allowed up to 600
tokens so that a row is never cut.

One chunk as it is in `data/rag/chunks.jsonl` (one line there; the text keeps the defects of the PDF:
"сумиефективних" without a space, "+5 С" without the degree sign):

```json
{"chunk_id": "uk_hydromet_2023-07-d3#010", "doc_id": "uk_hydromet_2023-07-d3", "chunk_index": 10,
 "kind": "text", "section": "Теплозабезпечення", "page": 8,
 "header": "Агрометеорологічний бюлетень по території України, третя декада липня 2023 р. | period: третя декада, липень 2023 | section: Теплозабезпечення",
 "text": "Станом на 31 липня сумиефективних температур повітря вище +5 С у більшості областей були на 25-30 °С вищими за середні багаторічні показники, в Івано-Франківській області – на 20 °С нижчими від них; суми температур повітря вище +10 С були близькими або на 25-45 °С нижчими від багаторічних показників і у розрізі агрокліматичних зон України відповідали таким показникам (табл.1):\n\nТаблиця 1",
 "n_tokens": 133, "title": "Агрометеорологічний бюлетень по території України, третя декада липня 2023 р.",
 "source": "Ukrhydrometcenter bulletin", "format": "pdf", "language": "uk", "topic": "agromet",
 "period": "2023-07-d3", "year": 2023, "month": 7, "decade": 3, "effective": "2023-07-31",
 "url": "https://agro.od.gov.ua/wp-content/uploads/2023/08/agrometeorologichnyj_byuleten_07_03_2023.pdf",
 "doc_hash": "490d83168bf36218", "ocr": false, "chunker": "struct-1-450", "pipeline_version": "corpus-6",
 "dataset_version": "8bf29b4d937e", "ingested_at": "2026-11-09T14:36:29+00:00"}
```

`chunk_id` = document + number (stable while the document does not change); `title`, `section` and `page`
are what a citation points to; `period` / `year` / `month` / `decade` / `effective` serve the filters;
`doc_hash`, `dataset_version` and `pipeline_version` tell which version of the corpus a chunk (and later an
answer) came from.

### Search

`agro/rag/search.py`: dense vectors (multilingual embeddings, fastembed on CPU) in Qdrant + BM25 over
crudely stemmed words (first 6 letters: Ukrainian endings), fused by reciprocal rank fusion (k = 60, top 30
of each list), then a multilingual cross-encoder reorders the top `rerank_top` (config.toml) candidates
(the reranker is the slow part on CPU: its time grows with the number of candidates).

* **Why hybrid + reranker**: questions name exact things that embeddings blur (oblast names, "0-100 см",
  numbers, "MARS"); BM25 finds those, embeddings find paraphrases and the other language (a Ukrainian
  question about an English JRC bulletin). The reranker reads question and chunk together and decides the
  order. Measured: fusing the two lists alone is *worse* than vectors alone (MRR 0.376 vs 0.517: BM25 is weak
  on this corpus, 0.232, and pulls good vector hits down); with the reranker on top it is the best (0.565),
  but BM25 adds little to the reranker's candidates (vector + reranker without BM25: 0.559). Hybrid is kept
  for exact names and numbers; a weighted fusion is a next step.
* **Why Qdrant** (the store of the lecture): filters on the payload are applied inside the vector search
  (not after it, so the top k is not emptied by a filter), including "month = 7 or no month" for
  documents that cover a whole year; local mode (a folder, `.cache/qdrant`) needs no server, and the same
  code works with a Qdrant server later. FAISS stores vectors only (metadata filtering has to be built
  around it); with Chroma "or no month" needs a placeholder value; pgvector would need a PostgreSQL server
  for 1,500 chunks.
* **Embedding model**: `intfloat/multilingual-e5-large` (MRR 0.517) over the MiniLM of the lecture (0.197)
  and mpnet (0.137). MiniLM reads 128 tokens: 91% of the chunks are cut, and the context header
  (document, period, section) takes a large part of those 128.
* **Reranker**: `BAAI/bge-reranker-v2-m3` (MRR 0.565) over `jina-reranker-v2-base-multilingual` (0.525),
  20 candidates (10 candidates: 0.500). The price is time on a CPU: ~40 s per question (jina ~14 s).
  The chosen values are in `config.toml` `[rag]`.
* **Filters**: year (a document covering 2019-2025 matches 2023), month, decade, source, language, topic,
  chunk kind, date range; given explicitly or read from the question, applied in the vector search and in
  BM25 alike:

```bash
python main.py rag search "Запаси вологи під кукурудзою на 31 липня 2023" --auto-filters
#   reads from the question: year 2023, month 7 (chunks of July or without a month)
python main.py rag search "maize yield forecast" --year 2025 --source JRC --kind table
```

Retrieval quality on the 17 dev questions that have an answer (a chunk is relevant if it is from the
expected document and contains its evidence phrase; all 26 configurations, recall@1/3/5/10 and per question:
[results/rag/retrieval_dev.md](results/rag/retrieval_dev.md)):

| configuration (structural chunks, e5) | recall@1 | recall@5 | recall@10 | MRR | s/question |
|---|---|---|---|---|---|
| vector | 0.47 | 0.59 | 0.65 | 0.517 | 0.2 |
| BM25 | 0.12 | 0.41 | 0.41 | 0.232 | 0.01 |
| hybrid (RRF) | 0.35 | 0.35 | 0.53 | 0.376 | 0.2 |
| hybrid + reranker bge | 0.47 | 0.65 | 0.68 | 0.565 | 41 |
| **hybrid + reranker bge + filters from the question** | **0.59** | **0.82** | **0.85** | **0.687** | 40 |

With filters 14 of 17 questions have a relevant chunk in the top 5. Not found: d06 (cross-lingual: an
English question about frozen soil in Kyiv oblast in March 2024; the reranker prefers the annual Derzhstat
table with "Kyivska | 2024") and the two multi-document questions d13 and d14 (two sources each: the
reranker fills the top with chunks of one of them). The set is small: one question moves MRR by about 0.06,
so only large differences (e5 vs the other models, reranker vs none, filters) are conclusions.

### Test set

`evals/testset_dev.jsonl` (tuning) and `evals/testset_test.jsonl` (measured once, at the end): 38
questions, Ukrainian and English, 9 kinds: exact, paraphrase, cross-lingual, table, outdated version,
similar documents, several documents, yes/no, no answer in the corpus. Each has the expected answer,
key facts and the source (document + evidence phrase). The questions were compiled by the author 
(an agronomic data scientist) from the documents of the
corpus; how the set was made and checked: [evals/README.md](evals/README.md).

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

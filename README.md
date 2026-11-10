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
filters, retrieval metrics. Step 3 (done): answers with sources, "not in the documents", checks of numbers
and citations; prompts v1 and v2 measured on dev. Step 4 (evals in CI) follows.

### Run

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # EasyOCR (comparison) needs torch
make install
make fetch          # originals into data/raw/ (one CSV is exported by hand: the command says how)
make run            # = make rag-ingest rag-chunk rag-lint-testset rag-index rag-retrieval-eval rag-threshold rag-answer-eval
make rag-ask Q="Яку максимальну температуру повітря зафіксували в Миколаєві в першій декаді липня 2023 року?"
python main.py rag search "Запаси вологи під кукурудзою на 31 липня 2023" --auto-filters
```

Models (tokenizer, embeddings, rerankers, EasyOCR) are downloaded on first use into `.models/` in the
project folder (or `AGRO_MODELS_DIR` from `.env`), never into the home folder. Scanned pages are read by a
vision model through OpenRouter; its transcripts are in git (`data/ocr/`), so the corpus is rebuilt without
a key. LibreOffice (`soffice`) is needed for the one `.doc` file. `make rag-ocr-compare` compares the
transcripts with EasyOCR ([results/rag/ocr_compare.md](results/rag/ocr_compare.md)).

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
([chunking.md](results/rag/chunking.md), [retrieval_dev.md](results/rag/retrieval_dev.md), 19 dev questions):

| | structural 300 | **structural 450 (used)** | fixed 450 / overlap 50 |
|---|---|---|---|
| chunks (avg tokens) | 2150 (277) | 1537 (372) | 1367 (443) |
| chunks starting mid-sentence | 2.4% | 3.3% | 52.6% |
| table parts without their header row | 0 | 0 | 537 |
| chunks longer than the e5 window (512 e5 tokens) | 0.3% | 32.4% | - |
| MRR, vector (e5) | 0.570 | **0.603** | 0.523 |
| MRR, hybrid + reranker (bge) | 0.615 | **0.632** | 0.604 |

Why 450: the window of e5 is 512 of its own tokens; a third of the 450-chunks is longer (tables up to
600 tokens, dense Ukrainian text) and is cut before embedding, while 300-chunks fit. Even so, 450 gives the
better vector search (0.603 vs 0.570) and the better result after the reranker, which reads the whole
chunk (0.632 vs 0.615): a longer chunk keeps a paragraph with its context (oblast, crop, period), and the
index is smaller (1537 chunks, not 2150). Tables are allowed up to 600 tokens so that a row is never cut.

Honest note: after a reranker the chunking matters less. With jina the fixed chunks even come out a little
ahead (0.636 vs 0.565), with bge structural is ahead (0.632 vs 0.604); one question moves MRR by ~0.05.
Structural chunks are chosen for what holds in every measure: vector search (0.603 vs 0.523), no cut
tables, sentences and sections kept whole, which also matters for the answers of step 3.

One chunk as it is in `data/rag/chunks.jsonl` (one line there; the text keeps the defects of the PDF:
"+5 С" without the degree sign, no space in "показникам(табл.1)"):

```json
{"chunk_id": "uk_hydromet_2023-07-d3#010", "doc_id": "uk_hydromet_2023-07-d3", "chunk_index": 10,
 "kind": "text", "section": "Теплозабезпечення", "page": 8,
 "header": "Агрометеорологічний бюлетень по території України, третя декада липня 2023 р. | period: третя декада, липень 2023 | section: Теплозабезпечення",
 "text": "Станом на 31 липня суми ефективних температур повітря вище +5 С у більшості областей були на 25-30 °С вищими за середні багаторічні показники, в Івано-Франківській області – на 20 °С нижчими від них; суми температур повітря вище +10 С були близькими або на 25-45 °С нижчими від багаторічних показників і у розрізі агрокліматичних зон України відповідали таким показникам(табл.1):\n\nТаблиця 1",
 "n_tokens": 133, "title": "Агрометеорологічний бюлетень по території України, третя декада липня 2023 р.",
 "source": "Ukrhydrometcenter bulletin", "format": "pdf", "language": "uk", "topic": "agromet",
 "period": "2023-07-d3", "year": 2023, "month": 7, "decade": 3, "effective": "2023-07-31",
 "url": "https://agro.od.gov.ua/wp-content/uploads/2023/08/agrometeorologichnyj_byuleten_07_03_2023.pdf",
 "doc_hash": "490d83168bf36218", "ocr": false, "chunker": "struct-1-450", "pipeline_version": "corpus-7",
 "dataset_version": "7b87b35ca6a9", "ingested_at": "2026-11-09T20:23:23+00:00"}
```

`chunk_id` = document + number (stable while the document does not change); `title`, `section` and `page`
are what a citation points to; `period` / `year` / `month` / `decade` / `effective` serve the filters;
`doc_hash`, `dataset_version` and `pipeline_version` tell which version of the corpus a chunk (and later an
answer) came from.

### Search

`agro/rag/search.py`: dense vectors (multilingual embeddings, fastembed on CPU) in Qdrant + BM25 over the
dictionary forms of Ukrainian words (pymorphy3; English words cut to 6 letters), the two lists joined by
reciprocal rank fusion (k = 60, top 30 of each list, BM25 with weight 0.3), then a multilingual
cross-encoder reorders the top 20 candidates. The settings are in `config.toml` `[rag]`.

* **Why Qdrant** (the store of the lecture): filters on the payload are applied inside the vector search
  (not after it, so the top k is not emptied by a filter), including "month = 7 or no month" for
  documents that cover a whole year; local mode (a folder, `.cache/qdrant`) needs no server, and the same
  code works with a Qdrant server later. FAISS stores vectors only (metadata filtering has to be built
  around it); with Chroma "or no month" needs a placeholder value; pgvector would need a PostgreSQL server
  for 1,500 chunks.
* **Filters**: year (a document covering 2019-2025 matches 2023), month, decade, source, language, topic,
  chunk kind, date range; given explicitly or read from the question, applied in the vector search and in
  BM25 alike:

```bash
python main.py rag search "Запаси вологи під кукурудзою на 31 липня 2023" --auto-filters
#   reads from the question: year 2023, month 7 (chunks of July or without a month)
python main.py rag search "maize yield forecast" --year 2025 --source JRC --kind table
```

Retrieval quality on the 19 dev questions that have an answer (a chunk is relevant if it is from the
expected document and contains its evidence phrase; every configuration with recall@1/3/5/10, hit@5,
MRR, recall before the reranker and time, and every question:
[results/rag/retrieval_dev.md](results/rag/retrieval_dev.md)):

| configuration (structural chunks, e5) | recall@1 | recall@5 | hit@5 | MRR | recall before rerank | s/question |
|---|---|---|---|---|---|---|
| vector | 0.58 | 0.63 | 0.63 | 0.603 | - | 0.2 |
| BM25 (dictionary forms) | 0.26 | 0.32 | 0.32 | 0.312 | - | 0.01 |
| hybrid (RRF, BM25 weight 0.3) | 0.42 | 0.53 | 0.53 | 0.479 | - | 0.2 |
| hybrid + filters from the question | 0.58 | 0.71 | 0.74 | 0.625 | - | 0.2 |
| hybrid + reranker bge | 0.58 | 0.66 | 0.68 | 0.632 | 0.71 | 38 |
| **hybrid + reranker bge + filters (the system)** | **0.74** | **0.87** | **0.89** | **0.808** | **0.92** | 37 |
| the same at the checkpoint `hw2-v1` (BM25 on 6-letter stems, weight 1.0) | 0.68 | 0.84 | 0.84 | 0.746 | 0.89 | 36 |

With the system 17 of 19 questions have a relevant chunk in the top 5. Not found: d12 (similar documents:
the sums of temperatures on 20 October 2022, the reranker keeps the neighbouring chunks of the same
bulletin) and d14 (two JRC bulletins, June and September 2025, with nearly the same tables; the first
relevant chunk is 10th); d13 (two documents) has one of its two sources in the top 5. The set is small: one
question moves MRR by about 0.05, so only large differences are conclusions.

### Experiments and decisions (step 2)

| experiment | compared | result (MRR on dev) | decision |
|---|---|---|---|
| embedding model | MiniLM of the lecture / mpnet / multilingual e5-large | 0.176 / 0.158 / **0.603** | e5. MiniLM reads 128 tokens: 91% of the chunks are cut, and the context header takes a large part of those 128 |
| chunking | structural 450 / structural 300 / fixed 450 + 50 | see Chunking above | structural 450 |
| reranker | jina v2 / bge v2 m3 (hybrid, 20 candidates) | 0.565 / **0.632** | bge; the price is time on a CPU: ~38 s per question (jina ~13 s), scores cached in `.cache/rerank/` |
| candidates for the reranker | 20 / 10 | 0.632 / 0.605 (recall before rerank 0.71 / 0.63) | 20: the reranker cannot find what is not among the candidates |
| reranker on vector only (no BM25) | vector + bge / hybrid + bge, no filters | 0.632 / 0.632 (recall before rerank 0.71 / 0.71) | hybrid: equal without filters; with filters the hybrid gives more candidates than the order of the vector list (below) |
| words of BM25 | as they are / first 6 letters / dictionary forms (pymorphy3) | 0.226 / 0.245 / **0.312** | dictionary forms ("вологою", "вологи" -> "волога") |
| fusion of the lists | RRF with BM25 weight 1.0 ... 0.1; relative score fusion alpha 0.9 / 0.8 / 0.7 (18 variants of the hybrid, part F) | hybrid alone: 0.446 ... 0.545 (RRF), 0.572 ... 0.603 (relative); whole chain with filters: RRF 1.0 0.746, **RRF 0.3 0.808**, relative 0.9 0.756 | RRF, BM25 weight 0.3, chosen by the whole chain: the reranker only reorders the candidates it gets, so the order of the hybrid alone decides little |
| metadata filters read from the question | without / with | 0.632 / **0.808** | with: year, month, decade, source |

**Hybrid alone is not better than vector search alone here** (lecture 7 expects it to be: there BM25 alone
reaches 0.88, because the questions contain exact codes such as `BV-2013-02`). On this corpus BM25 alone
reaches 0.31: 6 of the 19 dev questions ask in one language about a document in the other (d05, d06, d07,
d13, d16, d19), where words cannot match, and several are traps with a bulletin of the same month of another
year (d04: March 2024 vs March 2023), where the words are the same. In RRF a chunk ranked 10th in both
lists (2/70) outvotes the first hit of the vector list (1/61), so BM25 pushes the right vector hits down.
A lower weight of BM25 and the relative fusion reduce this, but the hybrid alone at
best equals the vector list (0.603). BM25 pays off in the whole chain with filters: there RRF with weight
0.3 gives the reranker 92% of the expected sources among its 20 candidates, against 87% for the relative
fusion with alpha 0.9 (in effect the order of the vector list), and the whole chain reaches MRR 0.808
against 0.756.

### Answers with sources (step 3)

`agro/rag/answer.py`, the chain of the lecture example (autoparts-rag-evals, `pipeline.py`), settings in
`config.toml` `[answer]`, prompts in `prompts/rag/` ([CHANGELOG](prompts/rag/CHANGELOG.md)):

1. **Search**: the system of step 2 (hybrid + bge + filters), the best 10 chunks.
2. **Threshold**: the reranker score of the best chunk turned into 0..1; below 0.3 the answer is
   "У документах цього немає" at once, without a model call.
3. **Context**: chunks with at least half the threshold, at most 3 of one document in a first pass (room
   for the second document of a question), then the places left filled with the chunks that limit
   skipped; the best k = 5, within a budget of 3000 tokens. Each chunk is numbered [n] and starts with its
   document, period and section.
4. **Answer** (gpt-4o-mini, temperature 0, prompt v2): in the language of the question (named in the
   prompt by the code), only facts of the chunks, a [n] after every sentence with a fact, numbers copied
   with their units, or the marker `НЕМАЄ_ВІДПОВІДІ` when no part of the question has an answer.
5. **Checks without a model** (`agro/rag/verify.py`): every number of the answer is in the chunks it cites
   (with the same unit; "24 769" = "24,769", "22-50 мм" = 22 мм and 50 мм), every [n] is a chunk that was
   given, every sentence with a fact has a [n]. A failed check gets one more try with the problems listed;
   if the numbers or citations are still wrong, the answer is withdrawn: a wrong number is worse than none.
6. **Sources** under the answer: document, period, section and page of every chunk cited.

An answer of the dev set (d14, prompt v1) as `make rag-ask` prints it:

```text
У червні 2025 року прогноз виробництва пшениці в Україні становив 24 769 тис. т [4]. У вересні 2025 року
прогноз виробництва пшениці зріс до 27 863 тис. т [2]. Таким чином, прогноз виробництва пшениці змінився з
червня на вересень 2025 року.

Sources:
[4] JRC MARS Bulletin - Global outlook: Crop monitoring in Ukraine, June 2025 (2025-06, Ukraine yield forecasts for total wheat - 16 June 2025 Bulletin, p. 13) — en_jrc_2025-06
[2] JRC MARS Bulletin - Global outlook: Crop monitoring in Ukraine, September 2025 (2025-09, Ukraine yield forecasts for total wheat - 15 September 2025 Bulletin, p. 13) — en_jrc_2025-09
```

The first answer of the model to this question had "прогноз зріс на 3 094 тис. т": a difference it computed
itself, a number that is in no chunk. The check of numbers caught it, and the retry answered without it. The
answer is in Ukrainian, though the question is in English: an error of prompt v1 (below).

**Threshold** ([results/rag/threshold_dev.md](results/rag/threshold_dev.md), `make rag-threshold`, no model
calls): the best chunk of every dev question with an answer scores 0.89 ... 1.00; of the 4 questions without
an answer, two score 0.041 (lentils, d20) and 0.000 (2016, d23), two are near misses that score 0.70 (d17:
a bulletin of March 2024 for February 2024) and 0.58 (d18: a JRC bulletin for another country). The
threshold is half the lowest score of an answerable question (0.89 / 2, rounded down to the candidate
0.3): it refuses d20 and d23 without a model call; d17 and d18 go to the model, which has to say
`НЕМАЄ_ВІДПОВІДІ`. A threshold of 0.8 would refuse all four on dev, but it rests on two questions and
leaves no room for a new answerable question that scores lower (d07: 0.89).

**Prompt v1 on the dev set** (23 questions, 19 with an answer; metrics without a judge, `correct` = every key
fact of the test set is in the answer; [results/rag/answers_dev_v1.md](results/rag/answers_dev_v1.md), every
answer with its context and checks in `answers_dev_v1.jsonl`):

| k chunks | correct | cited source | false abstain | no-answer abstained | retried | context tokens | $ / 1000 questions |
|---|---|---|---|---|---|---|---|
| 3 | 12 / 19 (0.63) | 0.89 | 2 / 19 | 4 / 4 | 0.17 | 1273 | 0.41 |
| **5 (used)** | **14 / 19 (0.74)** | **0.95** | **1 / 19** | **4 / 4** | 0.17 | 1736 | 0.51 |
| 10 | 14 / 19 (0.74) | 0.95 | 1 / 19 | 4 / 4 | 0.17 | 1846 | 0.53 |

k = 5: 3 chunks lose two questions, 10 add nothing and cost more (the floor of half the threshold and the
limit per document leave few more chunks: ~1850 tokens, not the budget of 3000). No answer was withdrawn, no invented number reached a final answer. Time: the
search 36.5 s per question (the bge reranker on a CPU; its scores are cached), the answer 1.3 s.

The 5 wrong answers of v1, the input of prompt v2:

| id | what happened | cause |
|---|---|---|
| d06, d16 | an English question answered in Ukrainian (d16: "Ні, снігу на полях не було" is right, the key fact "No" is not found); d09 and d14 too, right in content | the rule "answer in the language of the question" is in a Ukrainian prompt, and the model follows the language of the prompt |
| d06 | the chunk says "1-5 см, в окремих районах … Київської … – 7-10 см", the answer took the general 1-5 cm for Kyiv oblast | reading: a value given for the named oblast is not preferred to the general one |
| d07 | the chunk with the answer (wheat, all holdings) was the 4th of the same document; the limit of 3 chunks per document dropped it though the context had room, and the model took the table of winter wheat (209867.9 instead of 217538.5) | the limit per document |
| d13 | the yield of 27 c/ha (Mykolaiv oblast, 2020) was in the context, the model refused the whole question because the second part (the reason) was not | the rule of the marker outweighs the rule of a partial answer |
| d12 | the chunk with the answer was not found (a trap of similar chunks of one bulletin, known from step 2) | search |

The checks of citations also split "24 769 тис. т" after "тис." and took the rest for a sentence without a
citation: part of the retries (0.17) are false.

**Prompt v2** ([CHANGELOG](prompts/rag/CHANGELOG.md)): the language of the answer named in the prompt;
the marker only when no part of the question has an answer; the value of the named oblast preferred to
the general one; wheat / winter wheat, area / production told apart. In the code: the two passes of the
limit per document (above) and no sentence end after "тис.", "млн", "р.", "обл.". The test set is the
same as for v1 ([results/rag/answers_dev_v2.md](results/rag/answers_dev_v2.md)):

| k chunks | correct | cited source | false abstain | no-answer abstained | retried | context tokens | $ / 1000 questions |
|---|---|---|---|---|---|---|---|
| 3 | 14 / 19 (0.74) | 0.79 | 4 / 19 | 4 / 4 | 0.26 | 1273 | 0.49 |
| **5 (used)** | **17 / 19 (0.89)** | **0.89** | **2 / 19** | **4 / 4** | 0.17 | 1991 | 0.58 |
| 10 | 17 / 19 (0.89) | 0.95 | 1 / 19 | 4 / 4 | 0.26 | 2303 | 0.70 |

k = 5 again: 10 chunks give the same 17 correct answers for 20% more; the one more answer they give (d12)
is wrong, where k = 5 refuses.

v1 -> v2 at k = 5, question by question:

| id | v1 | v2 |
|---|---|---|
| d06 | 1-5 cm, in Ukrainian | **7-10 cm in some districts of Kyiv oblast, in English** |
| d07 | 209867.9 (winter wheat) | **217538.5** (wheat, from the 4th chunk of the document, now in the context) |
| d16 | "Ні, снігу не було" | **"No, there was no snow on the fields"** |
| d09, d14 | right, in Ukrainian | right, in English |
| d12 | a wrong value: the sum of temperatures since 1 October (15-20 °С above the norm) instead of the sum since September (20-70 °С below, chunk #007, not found) | refusal: the chunk with the answer is not found, and the model no longer answers from the neighbouring one; counted as a false abstain, but a refusal is better than a wrong number |
| d13 | refusal, 27 c/ha in the context | the same: the rule of a partial answer did not help. The value is in a table with one column per year (2019 ... 2025), the 2020 column is the second; open for step 4 |

Correct 14 -> 17 of 19, in context 0.82 -> 0.87, no-answer questions 4 of 4 refused in both, no answer
withdrawn, no invented number in a final answer. Cost $0.51 -> $0.58 per 1000 questions (a longer prompt,
a fuller context). Left for step 4: d13; two answers (d04, d14) keep an opening sentence without [n]
after the retry (their numbers are verified, so they are kept and counted as `uncited`); a sentence like
"Документи не надають конкретних значень" is not yet recognised as a statement of what is missing, so
it asks for a citation. The rules of v2 for d06 and d07 come from single dev questions; the held-out test
set checks whether they hold.

### Test set

`evals/testset_dev.jsonl` (tuning) and `evals/testset_test.jsonl` (measured once, at the end): 45
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

# Evals of stage 2 (RAG)

## Test set

`testset_dev.jsonl` (23 questions) is used for tuning: search configuration, prompts, thresholds.
`testset_test.jsonl` (22) is held out and measured once, for the final report.

Every line: `id`, `split`, `kind`, `language` (uk / en), `question`, `expected_answer`, `key_facts`
(must be in a correct answer: numbers or words), `sources` (document + evidence phrase copied from
`data/corpus/text/<doc_id>.md`), `match` (`all` sources needed, or `any` one of them), `note`
(for traps: the wrong answer).

| | dev | test | total |
|---|---|---|---|
| questions | 23 | 22 | 45 |
| in Ukrainian | 18 | 17 | 35 |
| in English | 5 | 5 | 10 |
| source documents behind the questions | 16 | 15 | 22 |

No model is trained, so there is no train split: dev is the tuning set, test is held out.

| kind | what it checks | dev | test |
|---|---|---|---|
| exact | a fact stated in one place | 3 | 4 |
| paraphrase | the same fact asked in other words | 3 | 2 |
| cross_lingual | an English question about a Ukrainian document or the other way round | 3 | 2 |
| table | a number from a table (PDF, XLSX, CSV) | 2 | 2 |
| stale | **trap**: an outdated version exists (JRC June vs September, 1 October vs the full year) | 2 | 2 |
| similar | **trap**: a similar document of another year or decade says something else | 2 | 2 |
| multi_chunk | the answer needs two places or two documents | 2 | 2 |
| yes_no | a yes / no question | 2 | 2 |
| no_answer | **the corpus has no answer**: the right reply is "not in the documents" | 4 | 4 |

Every format of the corpus is behind at least one question: PDF, HTML (d19, t19), DOCX (d13, d15, d21, t05),
DOC (d22, t02), XLSX (d10, t10, t14), CSV (d07, d13, t07, t14, t16). The questions cover 16 oblasts and
the country level.

## How it was made and checked

The questions were compiled by the author (an agronomic data scientist) from the agronomic documents
of the corpus. Each question was checked against its source document: the question, the expected
answer, the key facts and the evidence phrase. The set is balanced across oblasts, formats and
question kinds.

`make rag-lint-testset` checks the set itself (and in CI, step 4): fields, ids, kinds (at least 2 each),
no-answer and trap questions in both splits, and that every evidence phrase is in its document.

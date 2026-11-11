# Metrics of the evals

Every metric of `make evals-run` (`evals/run.py`): what it measures, why, and who computes it. **Code**:
deterministic, no model (`evals/scoring.py`, `agro/rag/verify.py`). **Judge**: the LLM judge
(`evals/judge.py`, Gemini 2.5 Flash-Lite, another family than the generator), calibrated against manual
labels (`evals/calibration/agreement.md`). **Human**: the manual labels of the calibration.

Shares are over the questions **with an answer** in the corpus, unless said otherwise. With several runs a
metric is the mean over the runs (min ... max in the report).

## The answer of one question passes

| question | passes when | who |
|---|---|---|
| has an answer in the corpus | the system answers (no refusal), the judge finds the answer **correct** and **grounded**, and the answer cites a chunk of the expected document (`match: all`: of every expected document) | code + judge |
| has no answer in the corpus | the system refuses ("У документах цього немає"), by the threshold or by the model | code |

`pass` is the share of all questions (with and without an answer) that pass; **pass@1** is the share that
passes in one run, the mean over the runs. A question that passes in some runs only is **unstable**.

## Answers

| metric | what it measures | why | who |
|---|---|---|---|
| `pass` | see above | the one number of the system: right, supported, cited, or "not in the documents" where nothing is there | code + judge |
| `judge_correct` | the answer agrees with the expected answer of the test set in meaning (language, wording and number format do not matter); a refusal is not correct | the key facts miss answers that say the right thing in other words or in the other language (d16: "Ні" for "No") | judge |
| `judge_grounded` | **faithfulness**: every statement of the answer is supported by the chunks the model got; over the answered questions | an answer can be right by chance or from the model's own knowledge; a value of another row, year or region presented as the asked one is caught here | judge |
| `correct` | every key fact of the test set (numbers or words in their dictionary forms) is in the answer | a check of the facts that needs no model and does not drift | code |
| `cited_source` | the answer cites a chunk of the expected document | the source is the point of a RAG answer; a right number from another document is not a sourced answer | code |
| `abstained_no_answer` | share of the questions **without** an answer that get a refusal | the system must say "not in the documents" instead of inventing | code |
| `false_abstain` | share of the questions with an answer that get a refusal | the price of the threshold and of the marker: a refusal where the answer is there | code |
| `unsupported_numbers` | number of final answers with a number that is not in the chunk its sentence cites, or stands there only in table cells of another crop, oblast or year than the sentence names (a count, not a share) | an invented or misattributed number must not reach the user; the checks of `agro/rag/verify.py` retry or withdraw such an answer, so this should be 0 | code |
| `uncited` | answers with a sentence that states something but has no [n] | every statement should point to its source | code |
| `retried` / `retracted` | the checks failed and the model answered again / the answer was withdrawn (share of all questions) | how often the checks of numbers and citations act | code |
| `cost_per_1000` / `judge_cost_per_1000` | $ of the generator (retries too) / of the judge, per 1000 questions, by the tokens and the prices of `config.toml` | the cost the assignment asks for | code |

## Search (of the system: hybrid + reranker + filters)

| metric | what it measures | who |
|---|---|---|
| `recall@5` | share of the expected sources among the 5 best chunks (a chunk is relevant when it is from the expected document and contains the evidence phrase of the test set) | code |
| `hit@5` | share of the questions with a relevant chunk among the 5 best | code |
| `MRR` | mean of 1 / rank of the first relevant chunk (0 when there is none among the 10 found) | code |

All configurations of the search compared in step 2: `results/rag/retrieval_dev.md`.

## The judge itself

| metric | what it measures | who |
|---|---|---|
| agreement, Cohen's kappa, false pass, false fail | the verdicts of the judge against the manual labels of 23 dev answers, for `correct` and `grounded` | human labels + code (`make evals-calibrate`) |

## The gate of CI

`evals/gate.py` compares the summary of a run (`evals/results/<split>.json`) with `evals/baseline.json`
and fails the CI run when a metric is worse than the baseline by more than its tolerance (in
`evals/baseline.json`).

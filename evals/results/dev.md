# Evals: dev (23 questions, 19 with an answer, 4 without; 3 run(s))

System: openai/gpt-4o-mini, prompt rag/v3, k 5, threshold 0.3, context 3000 tokens. Judge: google/gemini-2.5-flash-lite, prompt judge/v1. Metrics: evals/METRICS.md. With several runs: the mean, and min ... max over the runs.

| metric | value | min ... max |
|---|---|---|
| pass | **0.87** | 0.87 ... 0.87 |
| judge_correct | **0.84** | 0.84 ... 0.84 |
| judge_grounded | **1.00** | 1.00 ... 1.00 |
| correct | **0.84** | 0.84 ... 0.84 |
| cited_source | **0.89** | 0.89 ... 0.89 |
| abstained_no_answer | **1.00** | 1.00 ... 1.00 |
| false_abstain | **0.09** | 0.05 ... 0.11 |
| unsupported_numbers | **0** | 0 ... 0 |
| uncited | **0.07** | 0.05 ... 0.11 |
| retried | **0.17** | 0.17 ... 0.17 |
| retracted | **0.00** | 0.00 ... 0.00 |
| recall@5 | **0.87** | 0.87 ... 0.87 |
| hit@5 | **0.89** | 0.89 ... 0.89 |
| MRR | **0.808** | 0.808 ... 0.808 |
| cost_per_1000 | **0.588** | 0.586 ... 0.590 |
| judge_cost_per_1000 | **0.270** | 0.264 ... 0.281 |

pass@1 (the share of questions that pass in one run, mean over the runs): **0.87**. Unstable questions (pass in some runs only): none.

## Per kind (pass@1)

| kind | pass@1 |
|---|---|
| cross_lingual | 0.67 |
| exact | 1.00 |
| multi_chunk | 0.50 |
| no_answer | 1.00 |
| paraphrase | 1.00 |
| similar | 0.50 |
| stale | 1.00 |
| table | 1.00 |
| yes_no | 1.00 |

## Per question

| id | kind | passed runs | outcomes |
|---|---|---|---|
| d01 | exact | 3 / 3 | answer |
| d02 | exact | 3 / 3 | answer |
| d03 | paraphrase | 3 / 3 | answer |
| d04 | paraphrase | 3 / 3 | answer |
| d05 | cross_lingual | 3 / 3 | answer |
| d06 | cross_lingual | 3 / 3 | answer |
| d07 | table | 3 / 3 | answer |
| d08 | table | 3 / 3 | answer |
| d09 | stale | 3 / 3 | answer |
| d10 | stale | 3 / 3 | answer |
| d11 | similar | 3 / 3 | answer |
| d12 | similar | 0 / 3 | refused_model |
| d13 | multi_chunk | 0 / 3 | answer, refused_model |
| d14 | multi_chunk | 3 / 3 | answer |
| d15 | paraphrase | 3 / 3 | answer |
| d16 | yes_no | 3 / 3 | answer |
| d17 | no_answer | 3 / 3 | refused_model |
| d18 | no_answer | 3 / 3 | refused_model |
| d19 | cross_lingual | 0 / 3 | answer |
| d20 | no_answer | 3 / 3 | refused_threshold |
| d21 | yes_no | 3 / 3 | answer |
| d22 | exact | 3 / 3 | answer |
| d23 | no_answer | 3 / 3 | refused_threshold |

## Failed in run 1, with the reasons of the judge

* **d12** (similar): refused_model (the source was not in the context)
* **d13** (multi_chunk): refused_model (the source was in the context)
* **d19** (cross_lingual): not correct: The expected answer states that 4% of grain maize production was in conflict zones, while the system's answer states 22%. The expected answer is correct according to chunk 1.

Every answer of every run: evals/results/dev.jsonl

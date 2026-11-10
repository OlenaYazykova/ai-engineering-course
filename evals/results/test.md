# Evals: test (22 questions, 18 with an answer, 4 without; 3 run(s))

System: openai/gpt-4o-mini, prompt rag/v3, k 5, threshold 0.3, context 3000 tokens. Judge: google/gemini-2.5-flash-lite, prompt judge/v1. Metrics: evals/METRICS.md. With several runs: the mean, and min ... max over the runs.

| metric | value | min ... max |
|---|---|---|
| pass | **0.73** | 0.73 ... 0.73 |
| judge_correct | **0.67** | 0.67 ... 0.67 |
| judge_grounded | **1.00** | 1.00 ... 1.00 |
| correct | **0.72** | 0.72 ... 0.72 |
| cited_source | **0.83** | 0.83 ... 0.83 |
| abstained_no_answer | **1.00** | 1.00 ... 1.00 |
| false_abstain | **0.17** | 0.17 ... 0.17 |
| unsupported_numbers | **0** | 0 ... 0 |
| uncited | **0.02** | 0.00 ... 0.06 |
| retried | **0.18** | 0.18 ... 0.18 |
| retracted | **0.00** | 0.00 ... 0.00 |
| recall@5 | **0.67** | 0.67 ... 0.67 |
| hit@5 | **0.67** | 0.67 ... 0.67 |
| MRR | **0.547** | 0.547 ... 0.547 |
| cost_per_1000 | **0.542** | 0.542 ... 0.542 |
| judge_cost_per_1000 | **0.265** | 0.263 ... 0.267 |

pass@1 (the share of questions that pass in one run, mean over the runs): **0.73**. Unstable questions (pass in some runs only): none.

## Per kind (pass@1)

| kind | pass@1 |
|---|---|
| cross_lingual | 0.50 |
| exact | 1.00 |
| multi_chunk | 0.50 |
| no_answer | 1.00 |
| paraphrase | 0.50 |
| similar | 0.50 |
| stale | 1.00 |
| table | 0.50 |
| yes_no | 0.50 |

## Per question

| id | kind | passed runs | outcomes |
|---|---|---|---|
| t01 | exact | 3 / 3 | answer |
| t02 | exact | 3 / 3 | answer |
| t03 | paraphrase | 0 / 3 | answer |
| t04 | paraphrase | 3 / 3 | answer |
| t05 | cross_lingual | 0 / 3 | refused_threshold |
| t06 | cross_lingual | 3 / 3 | answer |
| t07 | table | 3 / 3 | answer |
| t08 | table | 0 / 3 | answer |
| t09 | stale | 3 / 3 | answer |
| t10 | stale | 3 / 3 | answer |
| t11 | similar | 0 / 3 | refused_model |
| t12 | similar | 3 / 3 | answer |
| t13 | multi_chunk | 3 / 3 | answer |
| t14 | multi_chunk | 0 / 3 | refused_model |
| t15 | yes_no | 3 / 3 | answer |
| t16 | yes_no | 0 / 3 | answer |
| t17 | no_answer | 3 / 3 | refused_threshold |
| t18 | no_answer | 3 / 3 | refused_model |
| t19 | exact | 3 / 3 | answer |
| t20 | no_answer | 3 / 3 | refused_threshold |
| t21 | no_answer | 3 / 3 | refused_threshold |
| t22 | exact | 3 / 3 | answer |

## Failed in run 1, with the reasons of the judge

* **t03** (paraphrase): not correct: The expected answer states that the sum of effective temperatures was 75-140 °C higher than the long-term average, while the system's answer states it was 20-25 °C higher. The provided chunks do not contain the information about the difference being 75-140 °C higher than the long-term average, but they do mention that the sum of effective temperatures was generally close to or 20-25 °C higher than the norm for the period up to October 20th.
* **t05** (cross_lingual): refused_threshold (the source was not in the context)
* **t08** (table): not correct: The answer correctly identifies the forecasted soybean area for Ukraine in 2025 as 3,003 thousand ha, which is directly stated in the provided document. It also correctly notes that this is a +7% increase compared to 2024, as indicated in the same row of the table. However, it omits the comparison to the 5-year average, which was part of the expected answer.
* **t11** (similar): refused_model (the source was in the context)
* **t14** (multi_chunk): refused_model (the source was not in the context)
* **t16** (yes_no): not correct: The answer correctly states that the yield in Kharkiv region (36.9 c/ha) was lower than the average for Ukraine (46 c/ha) in 2024. However, it incorrectly starts with "Так" (Yes) instead of "Ні" (No), contradicting the expected answer and the data presented.

Every answer of every run: evals/results/test.jsonl

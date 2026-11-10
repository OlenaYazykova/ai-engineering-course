# Answers with sources (dev set)

Model openai/gpt-4o-mini (t0), prompt rag/v2, search: hybrid + reranker + filters, 10 chunks found; threshold 0.3, context budget 3000 tokens, at most 3 chunks of one document. Metrics without a judge (agro/rag/answer_eval.py); `correct` = every key fact of the test set is in the answer.

## Size of the context (k chunks)

| k | retrieved | in context | answered | correct | cited source | cited evidence | uncited | false abstain | no-answer abstained | retried | retracted | context tokens | tokens / question | $ / 1000 questions | s search | s generation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 0.82 | 0.82 | 0.79 | 0.74 | 0.79 | 0.74 | 0.05 | 0.21 | 1.00 | 0.26 | 0.00 | 1273 | 3007 | 0.486 | 36.5 | 1.5 |
| 5 (used) | 0.87 | 0.87 | 0.89 | 0.89 | 0.89 | 0.84 | 0.11 | 0.11 | 1.00 | 0.17 | 0.00 | 1991 | 3685 | 0.584 | 36.5 | 1.4 |
| 10 | 0.89 | 0.87 | 0.95 | 0.89 | 0.95 | 0.84 | 0.16 | 0.05 | 1.00 | 0.26 | 0.00 | 2303 | 4426 | 0.698 | 36.5 | 1.5 |

19 questions with an answer, 4 without; 0 calls failed.

## Threshold

Probability of the best chunk = sigmoid of the reranker score (hybrid + reranker + filters). "Source found": an expected source is among the 5 chunks the model would get. Below the threshold the answer is "not in the documents" without a model call.

| threshold | answerable refused, source found (errors) | answerable refused, source not found | no-answer refused |
|---|---|---|---|
| 0.0 | 0  | 0  | 0 of 4  |
| 0.01 | 0  | 0  | 1 of 4 d23 |
| 0.02 | 0  | 0  | 1 of 4 d23 |
| 0.05 | 0  | 0  | 2 of 4 d20, d23 |
| 0.1 | 0  | 0  | 2 of 4 d20, d23 |
| 0.2 | 0  | 0  | 2 of 4 d20, d23 |
| 0.3 | 0  | 0  | 2 of 4 d20, d23 |
| 0.5 | 0  | 0  | 2 of 4 d20, d23 |
| 0.7 | 0  | 0  | 4 of 4 d17, d18, d20, d23 |
| 0.8 | 0  | 0  | 4 of 4 d17, d18, d20, d23 |
| 0.9 | 1 d07 | 0  | 4 of 4 d17, d18, d20, d23 |

Suggested (the highest candidate not above half of the lowest best-chunk probability of the answerable questions with the source found): **0.3**; config.toml [answer] threshold = 0.3.

| id | kind | best chunk p | source found |
|---|---|---|---|
| d01 | exact | 1.000 | yes |
| d02 | exact | 0.999 | yes |
| d03 | paraphrase | 0.996 | yes |
| d04 | paraphrase | 0.992 | yes |
| d05 | cross_lingual | 0.923 | yes |
| d06 | cross_lingual | 0.911 | yes |
| d07 | table | 0.891 | yes |
| d08 | table | 0.975 | yes |
| d09 | stale | 0.997 | yes |
| d10 | stale | 0.995 | yes |
| d11 | similar | 1.000 | yes |
| d12 | similar | 0.993 | no |
| d13 | multi_chunk | 0.927 | yes |
| d14 | multi_chunk | 0.962 | no |
| d15 | paraphrase | 0.991 | yes |
| d16 | yes_no | 0.997 | yes |
| d17 | no_answer | 0.696 | - |
| d18 | no_answer | 0.578 | - |
| d19 | cross_lingual | 0.974 | yes |
| d20 | no_answer | 0.041 | - |
| d21 | yes_no | 1.000 | yes |
| d22 | exact | 1.000 | yes |
| d23 | no_answer | 0.000 | - |

## Per question (k = 5)

| id | kind | outcome | correct | key facts | cited source | uncited | retried |
|---|---|---|---|---|---|---|---|
| d01 | exact | answer | yes | + | yes |  |  |
| d02 | exact | answer | yes | + | yes |  |  |
| d03 | paraphrase | answer | yes | ++ | yes |  | yes |
| d04 | paraphrase | answer | yes | ++ | yes | yes | yes |
| d05 | cross_lingual | answer | yes | + | yes |  |  |
| d06 | cross_lingual | answer | yes | + | yes |  |  |
| d07 | table | answer | yes | + | yes |  |  |
| d08 | table | answer | yes | + | yes |  |  |
| d09 | stale | answer | yes | + | yes |  | yes |
| d10 | stale | answer | yes | + | yes |  |  |
| d11 | similar | answer | yes | ++ | yes |  |  |
| d12 | similar | refused_model | no | - | no |  |  |
| d13 | multi_chunk | refused_model | no | -- | no |  |  |
| d14 | multi_chunk | answer | yes | ++ | yes | yes | yes |
| d15 | paraphrase | answer | yes | ++ | yes |  |  |
| d16 | yes_no | answer | yes | + | yes |  |  |
| d17 | no_answer | refused_model | yes (abstained) | | | |  |
| d18 | no_answer | refused_model | yes (abstained) | | | |  |
| d19 | cross_lingual | answer | yes | ++ | yes |  |  |
| d20 | no_answer | refused_threshold | yes (abstained) | | | |  |
| d21 | yes_no | answer | yes | ++ | yes |  |  |
| d22 | exact | answer | yes | + | yes |  |  |
| d23 | no_answer | refused_threshold | yes (abstained) | | | |  |

Every answer with its sources, context and checks: results/rag/answers_dev_v2.jsonl

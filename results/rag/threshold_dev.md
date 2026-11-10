# Threshold of "not in the documents" (dev set)

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

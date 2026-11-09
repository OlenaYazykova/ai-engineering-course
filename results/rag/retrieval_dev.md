# Retrieval quality (dev set)

17 questions with an expected source (no-answer questions excluded). A chunk is relevant if it is from the expected document and contains the evidence phrase (agro/rag/retrieval_eval.py). recall@k: share of expected sources found in the top k; MRR: 1 / rank of the first relevant chunk.

## A. Embedding models (vector search, structural chunks)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |
|---|---|---|---|---|---|---|
| vector, structural, minilm | 0.12 | 0.24 | 0.29 | 0.41 | 0.197 | 63 |
| vector, structural, mpnet | 0.12 | 0.18 | 0.18 | 0.18 | 0.137 | 107 |
| vector, structural, e5 | 0.47 | 0.59 | 0.59 | 0.65 | 0.517 | 161 |

## B. Methods and chunking (embeddings: e5)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |
|---|---|---|---|---|---|---|
| vector, structural, e5 | 0.47 | 0.59 | 0.59 | 0.65 | 0.517 | 156 |
| bm25, structural | 0.12 | 0.29 | 0.41 | 0.41 | 0.232 | 7 |
| bm25 without stemming, structural | 0.12 | 0.29 | 0.29 | 0.41 | 0.223 | 3 |
| hybrid, structural, e5 | 0.35 | 0.35 | 0.35 | 0.53 | 0.376 | 160 |
| hybrid + rerank jina, structural, e5 | 0.47 | 0.53 | 0.68 | 0.71 | 0.525 | 14376 |
| hybrid + rerank bge, structural, e5 | 0.47 | 0.65 | 0.65 | 0.68 | 0.565 | 41352 |
| vector, fixed, e5 | 0.29 | 0.65 | 0.65 | 0.68 | 0.458 | 166 |
| bm25, fixed | 0.29 | 0.29 | 0.44 | 0.44 | 0.332 | 5 |
| hybrid, fixed, e5 | 0.41 | 0.53 | 0.53 | 0.59 | 0.478 | 156 |
| hybrid + rerank jina, fixed, e5 | 0.41 | 0.59 | 0.68 | 0.68 | 0.526 | 9809 |
| hybrid + rerank bge, fixed, e5 | 0.41 | 0.59 | 0.59 | 0.68 | 0.503 | 32139 |

## C. Metadata filters read from the question

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |
|---|---|---|---|---|---|---|
| hybrid + filters, structural, e5 | 0.41 | 0.47 | 0.68 | 0.74 | 0.500 | 176 |
| hybrid + rerank bge + filters, structural, e5 | 0.59 | 0.76 | 0.82 | 0.85 | 0.687 | 40467 |

## D. Structural chunk size (embeddings: e5, reranker: bge)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |
|---|---|---|---|---|---|---|
| vector, max 300, e5 | 0.41 | 0.59 | 0.59 | 0.59 | 0.480 | 159 |
| hybrid + rerank bge, max 300, e5 | 0.47 | 0.65 | 0.71 | 0.71 | 0.561 | 28905 |
| vector, max 450 (used), e5 | 0.47 | 0.59 | 0.59 | 0.65 | 0.517 | 162 |
| hybrid + rerank bge, max 450 (used), e5 | 0.47 | 0.65 | 0.65 | 0.68 | 0.565 | 40923 |

## E. Reranker: candidates reordered (top 20 / 10), with and without BM25 (embeddings: e5, no filters)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | ms/query |
|---|---|---|---|---|---|---|
| hybrid + rerank jina, top 20, structural, e5 | 0.47 | 0.53 | 0.68 | 0.71 | 0.525 | 14376 |
| hybrid + rerank jina, top 10, structural, e5 | 0.53 | 0.53 | 0.53 | 0.53 | 0.529 | 6414 |
| hybrid + rerank bge, top 20, structural, e5 | 0.47 | 0.65 | 0.65 | 0.68 | 0.565 | 41352 |
| hybrid + rerank bge, top 10, structural, e5 | 0.47 | 0.53 | 0.53 | 0.53 | 0.500 | 18820 |
| vector + rerank bge, top 20 (no BM25), structural, e5 | 0.47 | 0.62 | 0.62 | 0.62 | 0.559 | 38057 |
| vector + rerank bge, top 10 (no BM25), structural, e5 | 0.47 | 0.59 | 0.59 | 0.65 | 0.538 | 17645 |

## Chunks longer than the input window of the embedding model

Tokens of the model's own tokenizer (with the e5 prefix). The part of a chunk after the window
is cut off before embedding: vector search cannot find it (BM25 and the reranker still see it).

| model | chunks | window, tokens | median chunk, tokens | chunks over the window, % |
|---|---|---|---|---|
| minilm | structural | 128 | 343 | 90.8 |
| mpnet | structural | 512 | 343 | 32.3 |
| e5 | structural | 512 | 345 | 32.5 |
| e5 | structural_300 | 512 | 251 | 0.3 |

Structural chunk size used: 450 tokens (config.toml [rag] chunk_tokens).

Chosen: embeddings **e5**, reranker **bge** (best MRR on dev).

## Per question (best configuration with filters)

| id | kind | first relevant rank | recall@5 | top 3 chunks |
|---|---|---|---|---|
| d01 | exact | 1 | 1.00 | uk_hydromet_2023-07-d1#003, uk_hydromet_2023-07-d1#002, uk_hydromet_year_2023#035 |
| d02 | exact | 1 | 1.00 | uk_hydromet_2023-07-d3#012, uk_hydromet_2023-07-d2#011, uk_hydromet_2023-07-d2#010 |
| d03 | paraphrase | 1 | 1.00 | uk_hydromet_2023-03-d3#010, uk_hydromet_year_2023#095, uk_hydromet_year_2023#162 |
| d04 | paraphrase | 1 | 1.00 | uk_hydromet_2024-03-d1#005, uk_hydromet_2024-03-d1#007, uk_hydromet_2024-03-d1#006 |
| d05 | cross_lingual | 2 | 1.00 | en_jrcnews_2022-09#002, en_jrc_2022-06#002, en_jrcnews_2022-06#003 |
| d06 | cross_lingual | - | 0.00 | en_derzhstat_crops_annual#056, en_derzhstat_crops_annual#059, en_derzhstat_crops_annual#014 |
| d07 | table | 4 | 1.00 | en_derzhstat_crops_annual#001, en_derzhstat_crops_annual#010, en_derzhstat_crops_annual#013 |
| d08 | table | 1 | 1.00 | uk_hydromet_year_2022#048, uk_hydromet_year_2022#071, uk_hydromet_year_2022#056 |
| d09 | stale | 2 | 1.00 | en_jrc_2025-06#036, en_jrc_2025-09#034, en_jrc_2025-06#018 |
| d10 | stale | 1 | 1.00 | uk_odstat_crops_2024#000, uk_odstat_crops_2024-10#000, uk_odstat_crops_2024-10#001 |
| d11 | similar | 1 | 1.00 | uk_hydromet_2022-08-d3#014, uk_hydromet_2022-08-d3#013, uk_hydromet_2022-08-d3#002 |
| d12 | similar | 3 | 1.00 | uk_hydromet_2022-10-d2#011, uk_hydromet_2022-10-d2#009, uk_hydromet_2022-10-d2#007 |
| d13 | multi_chunk | - | 0.00 | en_derzhstat_crops_annual#035, en_derzhstat_crops_annual#029, en_derzhstat_crops_annual#014 |
| d14 | multi_chunk | 10 | 0.00 | en_jrc_2025-09#010, en_jrc_2025-09#001, en_jrc_2025-09#018 |
| d15 | paraphrase | 1 | 1.00 | uk_hydromet_year_2020#003, uk_hydromet_year_2020#027, uk_hydromet_year_2020#004 |
| d16 | yes_no | 1 | 1.00 | uk_hydromet_2024-03-d1#004, uk_hydromet_2024-03-d1#005, uk_hydromet_year_2024#102 |
| d19 | cross_lingual | 1 | 1.00 | en_jrcnews_2022-09#002, en_jrcnews_2022-09#001, en_jrcnews_2022-09#000 |

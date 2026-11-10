# Retrieval quality (dev set)

19 questions with an expected source (no-answer questions excluded). A chunk is relevant if it is from the expected document and contains the evidence phrase (agro/rag/retrieval_eval.py). recall@k: share of expected sources found in the top k; hit@5: share of questions with a relevant chunk in the top 5 (recall@5 of lesson 7); MRR: 1 / rank of the first relevant chunk; recall before rerank: share of expected sources among the 20 candidates the reranker gets.

## A. Embedding models (vector search, structural chunks)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| vector, structural, minilm | 0.11 | 0.21 | 0.26 | 0.37 | 0.26 | 0.176 | - | 58 |
| vector, structural, mpnet | 0.16 | 0.16 | 0.16 | 0.16 | 0.16 | 0.158 | - | 144 |
| vector, structural, e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.603 | - | 236 |

## B. Methods and chunking (embeddings: e5)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| vector, structural, e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.603 | - | 206 |
| bm25 (lemma), structural | 0.26 | 0.32 | 0.32 | 0.47 | 0.32 | 0.312 | - | 6 |
| bm25 (stem6), structural | 0.11 | 0.32 | 0.47 | 0.47 | 0.47 | 0.245 | - | 4 |
| bm25 (none), structural | 0.11 | 0.32 | 0.32 | 0.47 | 0.32 | 0.226 | - | 4 |
| hybrid, structural, e5 | 0.42 | 0.53 | 0.53 | 0.63 | 0.53 | 0.479 | - | 284 |
| hybrid + rerank jina, structural, e5 | 0.53 | 0.53 | 0.61 | 0.71 | 0.63 | 0.565 | 0.71 | 13000 |
| hybrid + rerank bge, structural, e5 | 0.58 | 0.66 | 0.66 | 0.66 | 0.68 | 0.632 | 0.71 | 37884 |
| vector, fixed, e5 | 0.37 | 0.68 | 0.68 | 0.76 | 0.68 | 0.523 | - | 207 |
| bm25 (lemma), fixed | 0.42 | 0.47 | 0.50 | 0.50 | 0.53 | 0.449 | - | 7 |
| hybrid, fixed, e5 | 0.47 | 0.58 | 0.58 | 0.68 | 0.58 | 0.541 | - | 210 |
| hybrid + rerank jina, fixed, e5 | 0.53 | 0.71 | 0.76 | 0.79 | 0.79 | 0.636 | 0.79 | 10261 |
| hybrid + rerank bge, fixed, e5 | 0.53 | 0.68 | 0.68 | 0.74 | 0.68 | 0.604 | 0.79 | 30613 |

## C. Metadata filters read from the question

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| hybrid + filters, structural, e5 | 0.58 | 0.66 | 0.71 | 0.71 | 0.74 | 0.625 | - | 254 |
| hybrid + rerank bge + filters, structural, e5 | 0.74 | 0.82 | 0.87 | 0.89 | 0.89 | 0.808 | 0.92 | 36474 |

## D. Structural chunk size (embeddings: e5, reranker: bge)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| vector, max 300, e5 | 0.53 | 0.63 | 0.63 | 0.63 | 0.63 | 0.570 | - | 202 |
| hybrid + rerank bge, max 300, e5 | 0.58 | 0.63 | 0.68 | 0.71 | 0.68 | 0.615 | 0.74 | 29123 |
| vector, max 450 (used), e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.603 | - | 199 |
| hybrid + rerank bge, max 450 (used), e5 | 0.58 | 0.66 | 0.66 | 0.66 | 0.68 | 0.632 | 0.71 | 37895 |

## E. Reranker: candidates reordered (top 20 / 10), with and without BM25 (embeddings: e5, no filters)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| hybrid + rerank jina, top 20, structural, e5 | 0.53 | 0.53 | 0.61 | 0.71 | 0.63 | 0.565 | 0.71 | 13000 |
| hybrid + rerank jina, top 10, structural, e5 | 0.53 | 0.58 | 0.63 | 0.63 | 0.63 | 0.566 | 0.63 | 6606 |
| hybrid + rerank bge, top 20, structural, e5 | 0.58 | 0.66 | 0.66 | 0.66 | 0.68 | 0.632 | 0.71 | 37884 |
| hybrid + rerank bge, top 10, structural, e5 | 0.58 | 0.63 | 0.63 | 0.63 | 0.63 | 0.605 | 0.63 | 19310 |
| vector + rerank bge, top 20 (no BM25), structural, e5 | 0.58 | 0.66 | 0.66 | 0.66 | 0.68 | 0.632 | 0.71 | 37321 |
| vector + rerank bge, top 10 (no BM25), structural, e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.613 | 0.68 | 18997 |

## F. Fusion of the lists (RRF with a BM25 weight / relative score fusion) and words of BM25 (embeddings: e5, structural chunks)

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | hit@5 | MRR | recall before rerank | ms/query |
|---|---|---|---|---|---|---|---|---|
| hybrid, bm25 stem6, rrf, bm25 weight 1.0, e5 | 0.42 | 0.42 | 0.47 | 0.58 | 0.47 | 0.446 | - | 202 |
| hybrid, bm25 stem6, rrf, bm25 weight 0.5, e5 | 0.42 | 0.42 | 0.47 | 0.58 | 0.47 | 0.447 | - | 208 |
| hybrid, bm25 stem6, rrf, bm25 weight 0.3, e5 | 0.42 | 0.47 | 0.53 | 0.63 | 0.53 | 0.462 | - | 206 |
| hybrid, bm25 stem6, rrf, bm25 weight 0.2, e5 | 0.42 | 0.53 | 0.53 | 0.63 | 0.53 | 0.472 | - | 207 |
| hybrid, bm25 stem6, rrf, bm25 weight 0.15, e5 | 0.42 | 0.53 | 0.63 | 0.68 | 0.63 | 0.494 | - | 219 |
| hybrid, bm25 stem6, rrf, bm25 weight 0.1, e5 | 0.47 | 0.53 | 0.63 | 0.68 | 0.63 | 0.530 | - | 228 |
| hybrid, bm25 lemma, rrf, bm25 weight 1.0, e5 | 0.42 | 0.47 | 0.53 | 0.63 | 0.53 | 0.470 | - | 231 |
| hybrid, bm25 lemma, rrf, bm25 weight 0.5, e5 | 0.42 | 0.47 | 0.53 | 0.63 | 0.53 | 0.470 | - | 206 |
| hybrid, bm25 lemma, rrf, bm25 weight 0.3, e5 | 0.42 | 0.53 | 0.53 | 0.63 | 0.53 | 0.479 | - | 207 |
| hybrid, bm25 lemma, rrf, bm25 weight 0.2, e5 | 0.47 | 0.53 | 0.58 | 0.63 | 0.58 | 0.511 | - | 210 |
| hybrid, bm25 lemma, rrf, bm25 weight 0.15, e5 | 0.47 | 0.53 | 0.63 | 0.68 | 0.63 | 0.523 | - | 213 |
| hybrid, bm25 lemma, rrf, bm25 weight 0.1, e5 | 0.47 | 0.58 | 0.63 | 0.68 | 0.63 | 0.545 | - | 211 |
| hybrid, bm25 stem6, relative, alpha 0.9, e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.603 | - | 222 |
| hybrid, bm25 stem6, relative, alpha 0.8, e5 | 0.53 | 0.58 | 0.63 | 0.68 | 0.63 | 0.572 | - | 244 |
| hybrid, bm25 stem6, relative, alpha 0.7, e5 | 0.53 | 0.58 | 0.63 | 0.68 | 0.63 | 0.572 | - | 229 |
| hybrid, bm25 lemma, relative, alpha 0.9, e5 | 0.58 | 0.63 | 0.63 | 0.68 | 0.63 | 0.603 | - | 215 |
| hybrid, bm25 lemma, relative, alpha 0.8, e5 | 0.58 | 0.58 | 0.63 | 0.68 | 0.63 | 0.599 | - | 205 |
| hybrid, bm25 lemma, relative, alpha 0.7, e5 | 0.58 | 0.58 | 0.63 | 0.68 | 0.63 | 0.599 | - | 203 |
| hybrid + rerank bge + filters, bm25 stem6, rrf, bm25 weight 1.0 (checkpoint hw2-v1), e5 | 0.68 | 0.79 | 0.84 | 0.87 | 0.84 | 0.746 | 0.89 | 35900 |
| hybrid + rerank bge + filters, bm25 lemma, rrf, bm25 weight 0.3 (chosen), e5 | 0.74 | 0.82 | 0.87 | 0.89 | 0.89 | 0.808 | 0.92 | 36522 |
| hybrid + rerank bge + filters, bm25 stem6, relative, alpha 0.9, e5 | 0.68 | 0.76 | 0.82 | 0.87 | 0.84 | 0.756 | 0.87 | 36551 |

## Chunks longer than the input window of the embedding model

Tokens of the model's own tokenizer (with the e5 prefix). The part of a chunk after the window
is cut off before embedding: vector search cannot find it (BM25 and the reranker still see it).

| model | chunks | window, tokens | median chunk, tokens | chunks over the window, % |
|---|---|---|---|---|
| minilm | structural | 128 | 342 | 90.7 |
| mpnet | structural | 512 | 342 | 32.2 |
| e5 | structural | 512 | 344 | 32.4 |
| e5 | structural_300 | 512 | 252 | 0.3 |

Structural chunk size used: 450 tokens (config.toml [rag] chunk_tokens).

Chosen: embeddings **e5**, reranker **bge** (best MRR on dev); BM25 **lemma**, fusion **rrf, bm25 weight 0.3** (config.toml [rag], part F).

## Per question (best configuration with filters)

| id | kind | first relevant rank | recall@5 | top 3 chunks |
|---|---|---|---|---|
| d01 | exact | 1 | 1.00 | uk_hydromet_2023-07-d1#003, uk_hydromet_2023-07-d1#002, uk_hydromet_year_2023#037 |
| d02 | exact | 1 | 1.00 | uk_hydromet_2023-07-d3#012, uk_hydromet_2023-07-d2#011, uk_hydromet_2023-07-d2#010 |
| d03 | paraphrase | 1 | 1.00 | uk_hydromet_2023-03-d3#010, uk_hydromet_year_2023#095, uk_hydromet_year_2023#162 |
| d04 | paraphrase | 1 | 1.00 | uk_hydromet_2024-03-d1#005, uk_hydromet_2024-03-d1#007, uk_hydromet_2024-03-d1#006 |
| d05 | cross_lingual | 1 | 1.00 | en_jrcnews_2022-09#002, en_jrc_2022-06#002, en_jrcnews_2022-06#003 |
| d06 | cross_lingual | 1 | 1.00 | uk_hydromet_2024-03-d1#004, en_derzhstat_crops_annual#056, en_derzhstat_crops_annual#011 |
| d07 | table | 4 | 1.00 | en_derzhstat_crops_annual#001, en_derzhstat_crops_annual#010, en_derzhstat_crops_annual#013 |
| d08 | table | 1 | 1.00 | uk_hydromet_year_2022#048, uk_hydromet_year_2022#071, uk_hydromet_year_2022#056 |
| d09 | stale | 2 | 1.00 | en_jrc_2025-06#036, en_jrc_2025-09#034, en_jrc_2025-06#018 |
| d10 | stale | 1 | 1.00 | uk_odstat_crops_2024#000, uk_odstat_crops_2024-10#000, uk_odstat_crops_2024-10#001 |
| d11 | similar | 1 | 1.00 | uk_hydromet_2022-08-d3#014, uk_hydromet_2022-08-d3#013, uk_hydromet_2022-08-d3#002 |
| d12 | similar | - | 0.00 | uk_hydromet_2022-10-d2#011, uk_hydromet_2022-10-d2#009, uk_hydromet_2022-10-d2#006 |
| d13 | multi_chunk | 2 | 0.50 | en_derzhstat_crops_annual#056, en_derzhstat_crops_annual#008, en_derzhstat_crops_annual#035 |
| d14 | multi_chunk | 10 | 0.00 | en_jrc_2025-09#001, en_jrc_2025-09#018, en_jrc_2025-06#021 |
| d15 | paraphrase | 1 | 1.00 | uk_hydromet_year_2020#003, uk_hydromet_year_2020#027, uk_hydromet_year_2020#004 |
| d16 | yes_no | 1 | 1.00 | uk_hydromet_2024-03-d1#004, uk_hydromet_year_2024#017, uk_hydromet_2024-03-d1#005 |
| d19 | cross_lingual | 1 | 1.00 | en_jrcnews_2022-09#002, en_jrcnews_2022-09#001, en_jrcnews_2022-09#000 |
| d21 | yes_no | 1 | 1.00 | uk_hydromet_year_2019#035, uk_hydromet_year_2019#005, uk_hydromet_year_2019#031 |
| d22 | exact | 1 | 1.00 | uk_hydromet_year_2024_annex#016, uk_hydromet_year_2024_annex#014, uk_hydromet_year_2024#041 |

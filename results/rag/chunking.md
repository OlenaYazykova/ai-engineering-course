# Chunking: structural (two sizes) vs fixed-size

Corpus: 47 documents, dataset version 7b87b35ca6a9. Tokens: tiktoken o200k_base. Size used: config.toml [rag] chunk_tokens = 450.

| metric | structural, max 300 | structural, max 450 (used) | fixed 450 / overlap 50 |
|---|---|---|---|
| chunks | 2150 | 1537 | 1367 |
| avg_tokens | 277 | 372 | 443 |
| max_tokens | 450 | 600 | 452 |
| starts_mid_sentence_% | 2.4 | 3.3 | 52.6 |
| table_parts_without_header | 0 | 0 | 537 |
| chunks_under_min_tokens | 100 | 97 | 2 |
| table_chunks | 871 | 618 | 0 |

starts_mid_sentence_%: chunks whose text does not start at a sentence, heading, list item or table row.
table_parts_without_header: chunks with table rows but no table header (the table was cut).
Retrieval quality of each chunking (recall@k, MRR) and the share of chunks longer than the input
window of each embedding model: results/rag/retrieval_dev.md.

# Metrics

Texts per run: 41. Golden set: 10 texts × 14 fields. Accuracy, F1 and hallucinations are measured on the golden set; valid %, latency and cost on all texts. Removed: values the text does not support, removed or reset by checks.clean_lists on all texts (oblasts, crops, hazards, yield entries; condition, BBCH stage, vs 5-year average, layer, moisture status, year, month, decade; duplicates).

| Model | Prompt | T | top_p | Valid % | Fixed | Failed | Field acc % | Acc Hydromet % | Acc JRC % | Set F1 % | Halluc. | Removed | p50 s | p95 s | $ / 1000 docs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| google/gemini-2.5-flash-lite | v2 | 0.0 | 1.0 | 97.6 | 12 | 1 | 73.6 | 65.5 | 85.7 | 77.8 | 8 | 244 | 1.5 | 3.4 | 0.6752 |
| openai/gpt-4o-mini | v1 | 0.0 | 1.0 | 82.9 | 10 | 7 | 67.9 | 58.3 | 82.1 | 61.2 | 10 | 353 | 6.7 | 11.9 | 0.9588 |
| openai/gpt-4o-mini | v1 | 0.7 | 0.9 | 85.4 | 12 | 6 | 67.9 | 58.3 | 82.1 | 57.6 | 10 | 316 | 6.5 | 13.9 | 0.9818 |
| openai/gpt-4o-mini | v2 | 0.0 | 1.0 | 95.1 | 6 | 2 | 80.7 | 75.0 | 89.3 | 66.7 | 3 | 195 | 3.6 | 7.7 | 0.8969 |
| qwen2.5:3b | v1 | 0.0 | 1.0 | 26.8 | 7 | 30 | 31.4 | 39.3 | 19.6 | 33.3 | 3 | 396 | 259.0 | 404.2 | 0.0000 |
| qwen2.5:3b | v2 | 0.0 | 1.0 | 92.7 | 23 | 3 | 65.7 | 71.4 | 57.1 | 48.4 | 9 | 661 | 149.7 | 345.4 | 0.0000 |
| qwen2.5:3b | v2 | 0.7 | 0.9 | 70.7 | 15 | 12 | 57.1 | 46.4 | 73.2 | 38.5 | 10 | 412 | 153.4 | 348.4 | 0.0000 |

## Accuracy per field, %

| Field | gemini_flash_lite__v2__t0 | gpt4o_mini__v1__t0 | gpt4o_mini__v1__t07 | gpt4o_mini__v2__t0 | qwen3b__v1__t0 | qwen3b__v2__t0 | qwen3b__v2__t07 |
|---|---|---|---|---|---|---|---|
| year | 90 | 90 | 90 | 100 | 50 | 90 | 80 |
| month | 90 | 80 | 80 | 100 | 30 | 70 | 70 |
| decade | 90 | 90 | 90 | 100 | 50 | 90 | 80 |
| moisture_status | 40 | 50 | 50 | 50 | 0 | 40 | 50 |
| moisture_layer | 90 | 80 | 80 | 90 | 40 | 80 | 70 |
| min_mm | 90 | 80 | 80 | 90 | 20 | 70 | 70 |
| max_mm | 90 | 80 | 80 | 80 | 30 | 70 | 70 |
| deficit_oblasts | 70 | 80 | 80 | 80 | 30 | 80 | 70 |
| crops | 40 | 40 | 40 | 70 | 40 | 40 | 20 |
| crop_condition | 80 | 50 | 50 | 90 | 40 | 70 | 40 |
| crop_bbch | 50 | 60 | 60 | 70 | 40 | 40 | 30 |
| hazards | 50 | 40 | 40 | 40 | 0 | 50 | 30 |
| yield_vs_avg | 70 | 40 | 40 | 70 | 20 | 40 | 40 |
| yield_mt | 90 | 90 | 90 | 100 | 50 | 90 | 80 |

# Metrics

Texts per run: 41. Golden set: 10 texts × 14 fields. Accuracy, F1 and hallucinations are measured on the golden set; valid %, latency and cost on all texts.

| Model | Prompt | T | top_p | Valid % | Fixed | Failed | Field acc % | Acc Hydromet % | Acc JRC % | Set F1 % | Halluc. | p50 s | p95 s | $ / 1000 docs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| google/gemini-2.5-flash-lite | v2 | 0.0 | 1.0 | 100.0 | 6 | 0 | 74.3 | 73.8 | 75.0 | 63.7 | 18 | 1.4 | 2.7 | 0.5827 |
| openai/gpt-4o-mini | v1 | 0.0 | 1.0 | 92.7 | 11 | 3 | 62.9 | 60.7 | 66.1 | 42.3 | 28 | 5.9 | 11.6 | 0.9098 |
| openai/gpt-4o-mini | v1 | 0.7 | 0.9 | 90.2 | 11 | 4 | 65.0 | 64.3 | 66.1 | 45.2 | 27 | 6.1 | 11.6 | 0.9319 |
| openai/gpt-4o-mini | v2 | 0.0 | 1.0 | 95.1 | 3 | 2 | 74.3 | 75.0 | 73.2 | 53.5 | 14 | 2.9 | 6.5 | 0.8445 |
| qwen2.5:3b | v1 | 0.0 | 1.0 | 36.6 | 9 | 26 | 20.0 | 26.2 | 10.7 | 13.9 | 18 | 259.0 | 404.2 | 0.0000 |
| qwen2.5:3b | v2 | 0.0 | 1.0 | 92.7 | 22 | 3 | 48.6 | 57.1 | 35.7 | 24.1 | 29 | 179.3 | 410.0 | 0.0000 |
| qwen2.5:3b | v2 | 0.7 | 0.9 | 85.4 | 19 | 6 | 45.7 | 46.4 | 44.6 | 19.7 | 35 | 153.4 | 348.4 | 0.0000 |

## Accuracy per field, %

| Field | gemini_flash_lite__v2__t0 | gpt4o_mini__v1__t0 | gpt4o_mini__v1__t07 | gpt4o_mini__v2__t0 | qwen3b__v1__t0 | qwen3b__v2__t0 | qwen3b__v2__t07 |
|---|---|---|---|---|---|---|---|
| year | 100 | 100 | 100 | 90 | 50 | 80 | 80 |
| month | 100 | 90 | 90 | 100 | 30 | 70 | 80 |
| decade | 100 | 90 | 90 | 100 | 50 | 90 | 90 |
| moisture_status | 50 | 50 | 50 | 50 | 0 | 30 | 30 |
| moisture_layer | 90 | 70 | 70 | 90 | 30 | 40 | 20 |
| min_mm | 90 | 90 | 100 | 100 | 20 | 70 | 70 |
| max_mm | 100 | 90 | 90 | 80 | 30 | 70 | 70 |
| deficit_oblasts | 60 | 40 | 40 | 60 | 10 | 40 | 20 |
| crops | 10 | 0 | 0 | 10 | 0 | 10 | 0 |
| crop_condition | 60 | 0 | 10 | 70 | 0 | 10 | 20 |
| crop_bbch | 60 | 70 | 70 | 80 | 10 | 10 | 10 |
| hazards | 40 | 40 | 40 | 40 | 0 | 30 | 20 |
| yield_vs_avg | 80 | 50 | 60 | 70 | 0 | 40 | 40 |
| yield_mt | 100 | 100 | 100 | 100 | 50 | 90 | 90 |

# Regression check: gpt4o_mini__v3__t0 vs v2

Golden set: 10 texts. Tolerance: 2 pp overall, 10 pp per field.

| Metric | v2 | v3 | Δ |
|---|---|---|---|
| Field accuracy % | 74.3 | 71.4 | -2.9 |
| Accuracy Hydromet % | 75.0 | 69.0 | -6.0 |
| Accuracy JRC % | 73.2 | 75.0 | 1.8 |
| Valid % | 100.0 | 100.0 | 0.0 |
| Hallucinations | 14 | 16 | 2 |
| Set F1 % | 53.5 | 53.1 | -0.4 |

| Field | v2 | v3 | Δ |
|---|---|---|---|
| year | 90 | 100 | 10 |
| month | 100 | 100 | 0 |
| decade | 100 | 100 | 0 |
| moisture_status | 50 | 50 | 0 |
| moisture_layer | 90 | 90 | 0 |
| min_mm | 100 | 100 | 0 |
| max_mm | 80 | 90 | 10 |
| deficit_oblasts | 60 | 60 | 0 |
| crops | 10 | 0 | -10 |
| crop_condition | 70 | 40 | -30 ⚠ |
| crop_bbch | 80 | 70 | -10 |
| hazards | 40 | 30 | -10 |
| yield_vs_avg | 70 | 70 | 0 |
| yield_mt | 100 | 100 | 0 |

**Result: FAIL: field accuracy dropped by 2.9 pp; fields worse by more than 10 pp: crop_condition**

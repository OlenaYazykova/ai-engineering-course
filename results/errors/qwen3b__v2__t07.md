# Errors: qwen3b__v2__t07

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

### en_jrc_2023-04 (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| crops | [] | [winter_rapeseed] |
| crop_condition | [] | [('winter_rapeseed', 'good')] |
| hazards | [hostilities] | [frost] |
| yield_vs_avg | [('winter_barley', 'below'), ('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2024-06 (12/14)

| field | expected | got |
|---|---|---|
| hazards | [drought, heat, hostilities] | [drought, heat, heavy_rain] |
| yield_vs_avg | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2022-06 (10/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'satisfactory'), ('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'satisfactory')] |
| crop_bbch | [] | [('winter_barley', 6)] |
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2025-09 (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | deficit |
| crops | [] | [maize, soybean, sunflower] |
| crop_bbch | [] | [('maize', 6), ('soybean', 6), ('sunflower', 6)] |
| yield_vs_avg | [('maize', 'above'), ('soybean', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'above'), ('winter_wheat', 'above')] | [('maize', 'above'), ('soybean', 'near'), ('spring_barley', 'near'), ('sunflower', 'below'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-09-d1__growth_moisture (7/14)

| field | expected | got |
|---|---|---|
| month | 9 | null |
| moisture_status | deficit | adequate |
| min_mm | 10 | 21 |
| deficit_oblasts | [kherson] | [cherkasy, dnipropetrovsk, kharkiv, kherson, kirovohrad, kyiv, odesa, sumy] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [soybean, sunflower] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('soybean', 'good'), ('sunflower', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [] |

### uk_hydromet_2022-10-d2__conditions: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=10 is not written in the text as a value in mm; soil_moisture.max_mm=20 is not written in the text as a value in mm
```

### uk_hydromet_2023-02-d2 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [] | [('winter_barley', 2), ('winter_rapeseed', 2), ('winter_wheat', 2)] |
| hazards | [] | [frost] |

### uk_hydromet_2023-03-d3__moisture (11/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 170 | 20 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth (10/14)

| field | expected | got |
|---|---|---|
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [maize, spring_barley, sunflower, winter_wheat] |
| crop_condition | [('spring_barley', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('maize', 'good'), ('spring_barley', 'good'), ('sunflower', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('spring_barley', 1), ('winter_wheat', 2)] |
| hazards | [frost, waterlogging] | [] |

### uk_hydromet_2023-07-d3__moisture: FAILED

```
invalid after revalidation:
- (root): Value error, crops: every crop must appear once
```

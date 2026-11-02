# Errors: gpt4o_mini__v1__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

## Dev set (data/golden/)

### en_jrc_2023-04 (12/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| hazards | [hostilities] | [drought] |

### en_jrc_2024-06 (10/14)

| field | expected | got |
|---|---|---|
| crops | [] | [soybean] |
| crop_condition | [] | [('soybean', 'good')] |
| hazards | [drought, heat, hostilities] | [drought, heat] |
| yield_vs_avg | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('soybean', 'above'), ('winter_barley', 'near'), ('winter_rapeseed', 'below'), ('winter_wheat', 'near')] |

### en_jrcnews_2022-06 (12/14)

| field | expected | got |
|---|---|---|
| month | 6 | null |
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2025-09 (12/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'satisfactory')] |

### uk_hydromet_2022-09-d1__growth_moisture (8/14)

| field | expected | got |
|---|---|---|
| moisture_status | deficit | mixed |
| deficit_oblasts | [kherson] | [dnipropetrovsk, kharkiv, kherson, kirovohrad, kyiv, odesa, vinnytsia] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, sugar_beet, sunflower, winter_rapeseed, winter_wheat] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('maize', 'good'), ('soybean', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 9), ('soybean', 8), ('sunflower', 9), ('winter_rapeseed', 1), ('winter_wheat', 1)] |
| yield_vs_avg | [] | [('maize', 'above'), ('soybean', 'near'), ('sunflower', 'above'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-10-d2__conditions (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| hazards | [frost, waterlogging] | [drought, frost] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('sunflower', 'below')] |

### uk_hydromet_2023-02-d2 (12/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_wheat] |
| crop_bbch | [] | [('winter_wheat', 3)] |

### uk_hydromet_2023-03-d3__moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| min_mm | 11 | 22 |
| max_mm | 170 | 50 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth (8/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | mixed |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [spring_barley, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [('spring_barley', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('spring_barley', 3), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] |
| hazards | [frost, waterlogging] | [frost] |
| yield_vs_avg | [] | [('spring_barley', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'above'), ('winter_wheat', 'near')] |

### uk_hydromet_2023-07-d3__moisture: FAILED

```
invalid after revalidation:
- (root): Value error, crops: every crop must appear once
```

## Test set (data/golden_test/)

### en_jrc_2022-06 (11/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [] | [khmelnytskyi, odesa, vinnytsia] |
| hazards | [drought, hostilities] | [hostilities] |
| yield_vs_avg | [] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2026-09: FAILED

```
invalid after revalidation:
- (root): Value error, yield_outlook[soybean].production_mt=3683.0 is not written in the text as a value in Mt / млн т; yield_outlook[sunflower].production_mt=14000.0 is not written in the text as a value in Mt / млн т; yield_outlook[maize].production_mt=35100.0 is not written in the text as a value in Mt / млн т
```

### en_jrcnews_2023-04 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_wheat] |
| crop_condition | [] | [('winter_wheat', 'satisfactory')] |
| yield_vs_avg | [('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2026-06 (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| crops | [] | [winter_barley, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'good'), ('winter_wheat', 'good')] |
| hazards | [drought, frost, hostilities] | [drought, frost] |
| yield_vs_avg | [('winter_barley', 'above'), ('winter_rapeseed', 'near'), ('winter_wheat', 'above')] | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'above'), ('winter_rapeseed', 'near'), ('winter_wheat', 'above')] |

### uk_hydromet_2021-08-d1__moisture (10/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [cherkasy, chernihiv, donetsk, kharkiv, kherson, kirovohrad, kyiv, luhansk, poltava, sumy, vinnytsia, zaporizhzhia] | [cherkasy, chernihiv, donetsk, kharkiv, kyiv, luhansk, poltava, sumy, vinnytsia, zaporizhzhia] |
| crops | [] | [maize, soybean, sunflower] |
| crop_condition | [] | [('maize', 'satisfactory'), ('soybean', 'poor'), ('sunflower', 'satisfactory')] |
| hazards | [drought] | [] |

### uk_hydromet_2022-08-d3__growth_moisture (6/14)

| field | expected | got |
|---|---|---|
| min_mm | 10 | 11 |
| max_mm | 31 | 30 |
| deficit_oblasts | [] | [chernihiv, kyiv, vinnytsia, zhytomyr] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, sugar_beet, sunflower, winter_rapeseed] |
| crop_condition | [('sugar_beet', 'good'), ('winter_rapeseed', 'good')] | [('maize', 'good'), ('sugar_beet', 'good'), ('sunflower', 'satisfactory'), ('winter_rapeseed', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 8), ('winter_rapeseed', 1)] |
| hazards | [drought] | [] |
| yield_vs_avg | [] | [('maize', 'above'), ('soybean', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_rapeseed', 'near')] |

### uk_hydromet_2023-01-d1 (13/14)

| field | expected | got |
|---|---|---|
| hazards | [] | [frost] |

### uk_hydromet_2023-04-d3__moisture (11/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 200 | 40 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-10-d1__growth: FAILED

```
invalid after revalidation:
- (root): Value error, crops: every crop must appear once
```

### uk_hydromet_2023-10-d2__conditions (13/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |

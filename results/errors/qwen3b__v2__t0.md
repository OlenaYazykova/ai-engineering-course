# Errors: qwen3b__v2__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

## Dev set (data/golden/)

### en_jrc_2023-04 (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | not_stated |
| hazards | [hostilities] | [drought] |
| yield_vs_avg | [('winter_barley', 'below'), ('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2024-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=11 is not written in the text as a value in mm; soil_moisture.max_mm=20 is not written in the text as a value in mm
```

### en_jrcnews_2022-06 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley] |
| crop_bbch | [] | [('winter_barley', 6)] |
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2025-09 (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | deficit |
| crops | [] | [maize, soybean, sunflower] |
| crop_bbch | [] | [('maize', 6), ('soybean', 6), ('sunflower', 6)] |
| yield_vs_avg | [('maize', 'above'), ('soybean', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'above'), ('winter_wheat', 'above')] | [('maize', 'above'), ('soybean', 'near'), ('spring_barley', 'near'), ('sunflower', 'below'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-09-d1__growth_moisture (8/14)

| field | expected | got |
|---|---|---|
| month | 9 | null |
| moisture_status | deficit | adequate |
| min_mm | 10 | 21 |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [sugar_beet, sunflower] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('sugar_beet', 'good'), ('sunflower', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('sugar_beet', 4), ('sunflower', 4)] |

### uk_hydromet_2022-10-d2__conditions (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| hazards | [frost, waterlogging] | [drought, frost] |
| yield_vs_avg | [] | [('winter_wheat', 'below')] |

### uk_hydromet_2023-03-d3__moisture (11/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 170 | 50 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | mixed |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [maize, soybean, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [('spring_barley', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('maize', 'satisfactory'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('maize', 1), ('soybean', 1), ('spring_barley', 1), ('sunflower', 1), ('winter_barley', 2), ('winter_wheat', 2)] |
| yield_vs_avg | [] | [('maize', 'near'), ('soybean', 'near'), ('spring_barley', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2023-07-d3__moisture (7/14)

| field | expected | got |
|---|---|---|
| month | 7 | null |
| min_mm | 26 | 31 |
| max_mm | 200 | 160 |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [dnipropetrovsk, kherson, odesa] |
| crops | [] | [sunflower] |
| crop_bbch | [] | [('sunflower', 4)] |
| hazards | [waterlogging] | [] |

## Test set (data/golden_test/)

### en_jrc_2022-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=11 is not written in the text as a value in mm; soil_moisture.max_mm=20 is not written in the text as a value in mm
```

### en_jrc_2026-09: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=11 is not written in the text as a value in mm; soil_moisture.max_mm=20 is not written in the text as a value in mm; yield_outlook[winter_wheat].production_mt=6529.0 is not written in the text as a value in Mt / млн т; yield_outlook[winter_barley].production_mt=1755.0 is not written in the text as a value in Mt / млн т; yield_outlook[spring_barley].production_mt=1019.0 is not written in the text as a value in Mt / млн т; yield_outlook[maize].production_mt=4451.0 is not written in the text as a value in Mt / млн т; yield_outlook[sunflower].production_mt=6087.0 is not written in the text as a value in Mt / млн т; yield_outlook[soybean].production_mt=1570.0 is not written in the text as a value in Mt / млн т
```

### en_jrcnews_2023-04 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_wheat] |
| crop_condition | [] | [('winter_wheat', 'satisfactory')] |
| yield_vs_avg | [('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2026-06 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'good'), ('winter_wheat', 'good')] |
| hazards | [drought, frost, hostilities] | [drought, frost] |

### uk_hydromet_2021-08-d1__moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | adequate |
| min_mm | 14 | 52 |
| max_mm | 193 | 160 |
| deficit_oblasts | [cherkasy, chernihiv, donetsk, kharkiv, kherson, kirovohrad, kyiv, luhansk, poltava, sumy, vinnytsia, zaporizhzhia] | [chernihiv, kherson, zaporizhzhia] |

### uk_hydromet_2022-08-d3__growth_moisture (5/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | adequate |
| min_mm | 10 | 11 |
| max_mm | 31 | 30 |
| deficit_oblasts | [] | [cherkasy, chernihiv, kirovohrad, kyiv, poltava, vinnytsia, zhytomyr] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, sugar_beet, sunflower, winter_rapeseed] |
| crop_condition | [('sugar_beet', 'good'), ('winter_rapeseed', 'good')] | [('maize', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_rapeseed', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('sugar_beet', 4), ('sunflower', 4)] |
| hazards | [drought] | [] |
| yield_vs_avg | [] | [('maize', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_rapeseed', 'near')] |

### uk_hydromet_2023-04-d3__moisture (12/14)

| field | expected | got |
|---|---|---|
| min_mm | 21 | 139 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-10-d1__growth (7/14)

| field | expected | got |
|---|---|---|
| min_mm | 10 | 11 |
| max_mm | 49 | 20 |
| deficit_oblasts | [cherkasy, kharkiv, mykolaiv, odesa, vinnytsia] | [cherkasy, chernihiv, chernivtsi, kharkiv, khmelnytskyi, odesa] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed, winter_wheat] | [maize, sugar_beet, sunflower, winter_wheat] |
| crop_condition | [('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('maize', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 9), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1), ('winter_wheat', 1)] | [('winter_wheat', 1)] |
| yield_vs_avg | [] | [('maize', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2023-10-d2__conditions (13/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |

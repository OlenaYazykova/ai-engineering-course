# Errors: gpt4o_mini__v2__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in reports/hw1.md.

## Dev set (data/extract/golden/)

### en_jrc_2023-04 (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| hazards | [hostilities] | [drought] |
| yield_vs_avg | [('winter_barley', 'below'), ('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2024-06 (12/14)

| field | expected | got |
|---|---|---|
| hazards | [drought, heat, hostilities] | [drought, heat] |
| yield_vs_avg | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'near')] |

### en_jrcnews_2022-06 (13/14)

| field | expected | got |
|---|---|---|
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2022-09-d1__growth_moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | deficit | mixed |
| deficit_oblasts | [kherson] | [kherson, odesa] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, sunflower, winter_rapeseed, winter_wheat] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 8), ('soybean', 8), ('sunflower', 8), ('winter_rapeseed', 1), ('winter_wheat', 0)] |

### uk_hydromet_2022-10-d2__conditions (12/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| hazards | [frost, waterlogging] | [drought, frost] |

### uk_hydromet_2023-02-d2 (12/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [] | [('winter_barley', 1), ('winter_rapeseed', 1), ('winter_wheat', 1)] |

### uk_hydromet_2023-03-d3__moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| min_mm | 11 | 22 |
| max_mm | 170 | 50 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | mixed |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [spring_barley, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [('spring_barley', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('spring_barley', 1), ('winter_barley', 2), ('winter_rapeseed', 6), ('winter_wheat', 2)] |
| hazards | [frost, waterlogging] | [waterlogging] |

### uk_hydromet_2023-07-d3__moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| max_mm | 200 | 161 |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [chernihiv, dnipropetrovsk, kharkiv, kherson, kirovohrad, mykolaiv, odesa, ternopil, vinnytsia, volyn] |
| hazards | [waterlogging] | [] |

## Test set (data/extract/golden_test/)

### en_jrc_2022-06 (12/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [] | [khmelnytskyi, odesa, vinnytsia] |
| yield_vs_avg | [] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2026-09 (13/14)

| field | expected | got |
|---|---|---|
| hazards | [drought, heavy_rain] | [drought] |

### en_jrcnews_2023-04 (12/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | not_stated |
| hazards | [hostilities] | [] |

### en_jrcnews_2026-06 (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'good'), ('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'good')] |
| hazards | [drought, frost, hostilities] | [drought, frost] |

### uk_hydromet_2021-08-d1__moisture (10/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [cherkasy, chernihiv, donetsk, kharkiv, kherson, kirovohrad, kyiv, luhansk, poltava, sumy, vinnytsia, zaporizhzhia] | [cherkasy, chernihiv, donetsk, kharkiv, kirovohrad, kyiv, luhansk, lviv, poltava, sumy, vinnytsia, volyn, zaporizhzhia] |
| crops | [] | [soybean, sunflower] |
| crop_condition | [] | [('soybean', 'poor'), ('sunflower', 'satisfactory')] |
| hazards | [drought] | [] |

### uk_hydromet_2022-08-d3__growth_moisture (9/14)

| field | expected | got |
|---|---|---|
| max_mm | 31 | 30 |
| deficit_oblasts | [] | [cherkasy, chernihiv, kirovohrad, kyiv, vinnytsia, zhytomyr] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, sugar_beet, sunflower, winter_rapeseed] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 7), ('sunflower', 8), ('winter_rapeseed', 0)] |
| hazards | [drought] | [] |

### uk_hydromet_2023-01-d1 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [] | [('winter_barley', 2), ('winter_rapeseed', 2), ('winter_wheat', 2)] |
| hazards | [] | [frost] |

### uk_hydromet_2023-04-d3__moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 200 | 40 |
| deficit_oblasts | [] | [odesa] |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-10-d1__growth (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | deficit | mixed |
| max_mm | 49 | 20 |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed, winter_wheat] | [winter_rapeseed, winter_wheat] |
| crop_bbch | [('maize', 9), ('soybean', 9), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1), ('winter_wheat', 1)] | [('winter_rapeseed', 1), ('winter_wheat', 1)] |
| hazards | [drought] | [] |

### uk_hydromet_2023-10-d2__conditions (13/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |

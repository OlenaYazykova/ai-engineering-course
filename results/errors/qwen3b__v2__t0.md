# Errors: qwen3b__v2__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

### en_jrc_2023-04 (8/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | not_stated |
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'satisfactory'), ('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'satisfactory')] |
| crop_bbch | [] | [('winter_barley', 4), ('winter_rapeseed', 4), ('winter_wheat', 4)] |
| hazards | [hostilities] | [drought] |
| yield_vs_avg | [('winter_barley', 'below'), ('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2024-06: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.min_mm=11 is not written in the text; soil_moisture.max_mm=20 is not written in the text
```

### en_jrcnews_2022-06 (5/14)

| field | expected | got |
|---|---|---|
| year | null | 2021 |
| moisture_status | not_stated | mixed |
| moisture_layer | not_stated | both |
| deficit_oblasts | [] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| crop_bbch | [] | [('winter_barley', 6), ('winter_rapeseed', 6), ('winter_wheat', 6)] |
| hazards | [hostilities] | [drought, frost, hail, heat, heavy_rain, hostilities, waterlogging] |
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2025-09 (7/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | deficit |
| moisture_layer | not_stated | 0-20cm |
| deficit_oblasts | [] | [kherson, odesa] |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'good'), ('soybean', 'good'), ('spring_barley', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [] | [('maize', 6), ('soybean', 6), ('spring_barley', 6), ('sugar_beet', 6), ('sunflower', 6), ('winter_barley', 6), ('winter_rapeseed', 6), ('winter_wheat', 6)] |
| yield_vs_avg | [('maize', 'above'), ('soybean', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'above'), ('winter_wheat', 'above')] | [('maize', 'above'), ('soybean', 'near'), ('spring_barley', 'near'), ('sunflower', 'below'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-09-d1__growth_moisture (7/14)

| field | expected | got |
|---|---|---|
| month | 9 | 8 |
| moisture_status | deficit | adequate |
| moisture_layer | 0-20cm | 0-100cm |
| min_mm | 10 | 21 |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [sugar_beet, sunflower, winter_rapeseed, winter_wheat] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('sugar_beet', 4), ('sunflower', 4), ('winter_rapeseed', 4), ('winter_wheat', 4)] |

### uk_hydromet_2022-10-d2__conditions (7/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| deficit_oblasts | [kherson, odesa, zaporizhzhia] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| crop_bbch | [] | [('maize', 0), ('soybean', 0), ('spring_barley', 0), ('sugar_beet', 0), ('sunflower', 0), ('winter_barley', 4), ('winter_rapeseed', 4), ('winter_wheat', 4)] |
| hazards | [frost, waterlogging] | [drought, frost] |
| yield_vs_avg | [] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2023-03-d3__moisture (8/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 170 | 50 |
| crops | [] | [winter_barley, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [] | [('winter_barley', 1), ('winter_wheat', 1)] |
| hazards | [waterlogging] | [drought] |

### uk_hydromet_2023-04-d3__growth (6/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | mixed |
| moisture_layer | not_stated | 0-20cm |
| deficit_oblasts | [] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [('spring_barley', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] | [('maize', 'satisfactory'), ('soybean', 'satisfactory'), ('spring_barley', 'satisfactory'), ('sugar_beet', 'satisfactory'), ('sunflower', 'satisfactory'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('maize', 1), ('soybean', 1), ('spring_barley', 1), ('sugar_beet', 1), ('sunflower', 1), ('winter_barley', 2), ('winter_rapeseed', 2), ('winter_wheat', 2)] |
| hazards | [frost, waterlogging] | [drought, frost, hail, heat, heavy_rain, waterlogging] |
| yield_vs_avg | [] | [('maize', 'near'), ('soybean', 'near'), ('spring_barley', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2023-07-d3__moisture (6/14)

| field | expected | got |
|---|---|---|
| month | 7 | 8 |
| min_mm | 26 | 31 |
| max_mm | 200 | 160 |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [dnipropetrovsk, kherson, odesa] |
| crops | [] | [maize, soybean, sunflower] |
| crop_condition | [] | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] |
| crop_bbch | [] | [('maize', 4), ('soybean', 4), ('sunflower', 4)] |
| hazards | [waterlogging] | [] |

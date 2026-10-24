# Errors: qwen3b__v1__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

### en_jrc_2023-04: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text; soil_moisture.max_mm=40 is not written in the text
```

### en_jrc_2024-06: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.max_mm=40 is not written in the text
```

### en_jrcnews_2022-06: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.min_mm=25 is not written in the text; soil_moisture.max_mm=30 is not written in the text
```

### en_jrcnews_2025-09 (6/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | excess |
| moisture_layer | not_stated | 0-100cm |
| deficit_oblasts | [] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'good'), ('soybean', 'good'), ('spring_barley', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [] | [('maize', 8), ('soybean', 8), ('spring_barley', 8), ('sugar_beet', 8), ('sunflower', 8), ('winter_barley', 8), ('winter_rapeseed', 8), ('winter_wheat', 8)] |
| hazards | [drought, heavy_rain] | [drought, frost, hail, heat, heavy_rain, hostilities, waterlogging] |
| yield_vs_avg | [('maize', 'above'), ('soybean', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'above'), ('winter_wheat', 'above')] | [('maize', 'above'), ('soybean', 'below'), ('spring_barley', 'above'), ('sugar_beet', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2022-09-d1__growth_moisture (5/14)

| field | expected | got |
|---|---|---|
| month | 9 | 8 |
| moisture_status | deficit | adequate |
| min_mm | 10 | 21 |
| deficit_oblasts | [kherson] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('maize', 'good'), ('soybean', 'good'), ('spring_barley', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 6), ('soybean', 6), ('spring_barley', 6), ('sugar_beet', 6), ('sunflower', 6), ('winter_barley', 6), ('winter_rapeseed', 6), ('winter_wheat', 6)] |
| hazards | [] | [drought] |
| yield_vs_avg | [] | [('maize', 'near'), ('soybean', 'near'), ('spring_barley', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-10-d2__conditions (7/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| deficit_oblasts | [kherson, odesa, zaporizhzhia] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'poor'), ('soybean', 'poor'), ('spring_barley', 'poor'), ('sugar_beet', 'poor'), ('sunflower', 'poor'), ('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| crop_bbch | [] | [('maize', 4), ('soybean', 4), ('spring_barley', 4), ('sugar_beet', 4), ('sunflower', 4), ('winter_barley', 4), ('winter_rapeseed', 4), ('winter_wheat', 4)] |
| hazards | [frost, waterlogging] | [drought] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('spring_barley', 'below'), ('sugar_beet', 'below'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2023-02-d2: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.max_mm=25 is not written in the text
```

### uk_hydromet_2023-03-d3__moisture (5/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| moisture_layer | both | 0-20cm |
| min_mm | 11 | 50 |
| max_mm | 170 | 109 |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'poor'), ('soybean', 'poor'), ('spring_barley', 'poor'), ('sugar_beet', 'poor'), ('sunflower', 'poor'), ('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| crop_bbch | [] | [('maize', 3), ('soybean', 3), ('spring_barley', 3), ('sugar_beet', 3), ('sunflower', 3), ('winter_barley', 3), ('winter_rapeseed', 3), ('winter_wheat', 3)] |
| hazards | [waterlogging] | [drought] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('spring_barley', 'below'), ('sugar_beet', 'below'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2023-04-d3__growth: FAILED

```
invalid after correction:
- (root): Value error, soil_moisture.min_mm=150 is not written in the text; soil_moisture.max_mm=250 is not written in the text
```

### uk_hydromet_2023-07-d3__moisture (5/14)

| field | expected | got |
|---|---|---|
| month | 7 | 8 |
| moisture_status | adequate | deficit |
| min_mm | 26 | 31 |
| max_mm | 200 | 60 |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [cherkasy, chernihiv, chernivtsi, crimea, kharkiv, kherson, khmelnytskyi, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil] |
| crops | [] | [maize, soybean, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'good'), ('soybean', 'satisfactory'), ('sunflower', 'good'), ('winter_barley', 'satisfactory'), ('winter_rapeseed', 'good'), ('winter_wheat', 'poor')] |
| hazards | [waterlogging] | [drought] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('spring_barley', 'below'), ('sugar_beet', 'below'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

# Errors: qwen3b__v1__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

## Dev set (data/golden/)

### en_jrc_2023-04: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text as a value in mm; soil_moisture.max_mm=40 is not written in the text as a value in mm
```

### en_jrc_2024-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=25 is not written in the text as a value in mm; soil_moisture.max_mm=40 is not written in the text as a value in mm
```

### en_jrcnews_2022-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=25 is not written in the text as a value in mm; soil_moisture.max_mm=30 is not written in the text as a value in mm
```

### en_jrcnews_2025-09 (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | excess |
| hazards | [drought, heavy_rain] | [drought, heat, heavy_rain] |
| yield_vs_avg | [('maize', 'above'), ('soybean', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'above'), ('winter_wheat', 'above')] | [('maize', 'above'), ('soybean', 'below'), ('spring_barley', 'above'), ('sunflower', 'below'), ('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2022-09-d1__growth_moisture (5/14)

| field | expected | got |
|---|---|---|
| month | 9 | null |
| moisture_status | deficit | adequate |
| min_mm | 10 | 21 |
| deficit_oblasts | [kherson] | [cherkasy, dnipropetrovsk, kharkiv, kherson, kirovohrad, kyiv, odesa, sumy, vinnytsia] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, sugar_beet, sunflower] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('maize', 'good'), ('soybean', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [] |
| hazards | [] | [drought] |
| yield_vs_avg | [] | [('maize', 'near'), ('soybean', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-10-d2__conditions (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| hazards | [frost, waterlogging] | [drought] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('sunflower', 'below'), ('winter_wheat', 'below')] |

### uk_hydromet_2023-02-d2: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=15 is not written in the text as a value in mm; soil_moisture.max_mm=25 is not written in the text as a value in mm
```

### uk_hydromet_2023-03-d3__moisture (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| moisture_layer | both | 0-20cm |
| min_mm | 11 | 50 |
| max_mm | 170 | 109 |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=150 is not written in the text as a value in mm; soil_moisture.max_mm=250 is not written in the text as a value in mm
```

### uk_hydromet_2023-07-d3__moisture (8/14)

| field | expected | got |
|---|---|---|
| month | 7 | null |
| moisture_status | adequate | deficit |
| min_mm | 26 | 31 |
| max_mm | 200 | 60 |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [chernihiv, kharkiv, kherson, mykolaiv, odesa, poltava, sumy, ternopil] |
| hazards | [waterlogging] | [] |

## Test set (data/golden_test/)

### en_jrc_2022-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text as a value in mm; soil_moisture.max_mm=40 is not written in the text as a value in mm
```

### en_jrc_2026-09: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text as a value in mm; soil_moisture.max_mm=35 is not written in the text as a value in mm; yield_outlook[winter_wheat].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[winter_barley].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[winter_rapeseed].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[spring_barley].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[maize].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[sunflower].production_mt=1000.0 is not written in the text as a value in Mt / млн т; yield_outlook[soybean].production_mt=1000.0 is not written in the text as a value in Mt / млн т
```

### en_jrcnews_2023-04: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=35 is not written in the text as a value in mm; soil_moisture.max_mm=45 is not written in the text as a value in mm
```

### en_jrcnews_2026-06: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=25 is not written in the text as a value in mm; soil_moisture.max_mm=35 is not written in the text as a value in mm
```

### uk_hydromet_2021-08-d1__moisture: FAILED

```
answer cut at max_tokens=1500
```

### uk_hydromet_2022-08-d3__growth_moisture (5/14)

| field | expected | got |
|---|---|---|
| moisture_status | mixed | deficit |
| min_mm | 10 | 11 |
| max_mm | 31 | 20 |
| deficit_oblasts | [] | [cherkasy, chernihiv, kirovohrad, kyiv, poltava, vinnytsia, zhytomyr] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, sugar_beet, sunflower, winter_rapeseed] |
| crop_condition | [('sugar_beet', 'good'), ('winter_rapeseed', 'good')] | [('maize', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_rapeseed', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 7), ('winter_rapeseed', 7)] |
| hazards | [drought] | [] |
| yield_vs_avg | [] | [('maize', 'near'), ('soybean', 'near'), ('sugar_beet', 'near'), ('sunflower', 'near'), ('winter_rapeseed', 'near')] |

### uk_hydromet_2023-01-d1: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text as a value in mm; soil_moisture.max_mm=30 is not written in the text as a value in mm
```

### uk_hydromet_2023-04-d3__moisture: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=0 is not written in the text as a value in mm; soil_moisture.max_mm=20 is not written in the text as a value in mm
```

### uk_hydromet_2023-10-d1__growth: FAILED

```
invalid after revalidation:
- (root): Value error, crops: every crop must appear once
```

### uk_hydromet_2023-10-d2__conditions: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=20 is not written in the text as a value in mm; soil_moisture.max_mm=40 is not written in the text as a value in mm
```

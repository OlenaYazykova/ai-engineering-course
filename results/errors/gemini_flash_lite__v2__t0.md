# Errors: gemini_flash_lite__v2__t0

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

### en_jrc_2023-04 (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| crops | [] | [winter_rapeseed] |
| crop_condition | [] | [('winter_rapeseed', 'good')] |
| yield_vs_avg | [('winter_barley', 'below'), ('winter_wheat', 'below')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrc_2024-06 (10/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_wheat] |
| crop_bbch | [] | [('winter_wheat', 6)] |
| hazards | [drought, heat, hostilities] | [drought, heat] |
| yield_vs_avg | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_wheat', 'near')] |

### uk_hydromet_2022-09-d1__growth_moisture (10/14)

| field | expected | got |
|---|---|---|
| moisture_status | deficit | mixed |
| deficit_oblasts | [kherson] | [dnipropetrovsk, kharkiv, kherson, kirovohrad, kyiv, odesa, vinnytsia] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, sunflower, winter_rapeseed, winter_wheat] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 8), ('soybean', 8), ('sunflower', 8), ('winter_rapeseed', 1), ('winter_wheat', 0)] |

### uk_hydromet_2022-10-d2__conditions (12/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| hazards | [frost, waterlogging] | [frost, heavy_rain, waterlogging] |

### uk_hydromet_2023-02-d2 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [] | [('winter_barley', 2), ('winter_rapeseed', 2), ('winter_wheat', 2)] |
| hazards | [] | [frost] |

### uk_hydromet_2023-03-d3__moisture: FAILED

```
invalid after revalidation:
- (root): Value error, soil_moisture.min_mm=0 is not written in the text as a value in mm
```

### uk_hydromet_2023-04-d3__growth (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | excess |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [maize, soybean, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('maize', 0), ('soybean', 0), ('spring_barley', 1), ('sunflower', 1), ('winter_barley', 3), ('winter_rapeseed', 6), ('winter_wheat', 3)] |

### uk_hydromet_2023-07-d3__moisture (11/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [dnipropetrovsk, kharkiv, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, ternopil, vinnytsia, volyn] |
| hazards | [waterlogging] | [] |

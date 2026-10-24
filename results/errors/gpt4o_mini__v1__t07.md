# Errors: gpt4o_mini__v1__t07

Every golden-set field where the model differs from the gold value (expected = gold). Use these for the error analysis in REPORT.md.

### en_jrc_2023-04 (7/14)

| field | expected | got |
|---|---|---|
| decade | null | 1 |
| moisture_status | adequate | deficit |
| moisture_layer | not_stated | 0-20cm |
| deficit_oblasts | [] | [odesa] |
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'satisfactory'), ('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'satisfactory')] |
| hazards | [hostilities] | [drought] |

### en_jrc_2024-06 (9/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [] | [cherkasy, chernihiv, chernivtsi, crimea, dnipropetrovsk, donetsk, ivano_frankivsk, kharkiv, kherson, khmelnytskyi, kirovohrad, kyiv, luhansk, lviv, mykolaiv, odesa, poltava, rivne, sumy, ternopil, vinnytsia, volyn, zakarpattia, zaporizhzhia, zhytomyr] |
| crops | [] | [soybean, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('soybean', 'good'), ('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| hazards | [drought, heat, hostilities] | [drought, heat] |
| yield_vs_avg | [('maize', 'near'), ('soybean', 'near'), ('sunflower', 'near'), ('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('soybean', 'above'), ('winter_barley', 'near'), ('winter_rapeseed', 'below'), ('winter_wheat', 'near')] |

### en_jrcnews_2022-06 (10/14)

| field | expected | got |
|---|---|---|
| month | 6 | null |
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'poor'), ('winter_rapeseed', 'poor'), ('winter_wheat', 'poor')] |
| yield_vs_avg | [('winter_barley', 'near'), ('winter_rapeseed', 'near'), ('winter_wheat', 'near')] | [('winter_barley', 'below'), ('winter_rapeseed', 'below'), ('winter_wheat', 'below')] |

### en_jrcnews_2025-09 (11/14)

| field | expected | got |
|---|---|---|
| deficit_oblasts | [] | [dnipropetrovsk, donetsk, kharkiv, kherson, sumy, vinnytsia, zhytomyr] |
| crops | [] | [maize, soybean, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'poor'), ('winter_barley', 'poor'), ('winter_rapeseed', 'satisfactory'), ('winter_wheat', 'satisfactory')] |

### uk_hydromet_2022-09-d1__growth_moisture (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | deficit | mixed |
| deficit_oblasts | [kherson] | [dnipropetrovsk, kharkiv, kherson, kirovohrad, kyiv, odesa, vinnytsia] |
| crops | [maize, soybean, sugar_beet, sunflower, winter_rapeseed] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_rapeseed, winter_wheat] |
| crop_condition | [('maize', 'good'), ('soybean', 'good'), ('sunflower', 'good')] | [('maize', 'good'), ('soybean', 'good'), ('sugar_beet', 'good'), ('sunflower', 'good'), ('winter_rapeseed', 'good')] |
| crop_bbch | [('maize', 9), ('soybean', 8), ('sugar_beet', 4), ('sunflower', 9), ('winter_rapeseed', 1)] | [('maize', 9), ('sunflower', 9)] |

### uk_hydromet_2022-10-d2__conditions (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | deficit |
| crops | [] | [maize, soybean, sunflower, winter_wheat] |
| crop_condition | [] | [('winter_wheat', 'poor')] |
| hazards | [frost, waterlogging] | [drought, frost] |
| yield_vs_avg | [] | [('maize', 'below'), ('soybean', 'below'), ('sunflower', 'below')] |

### uk_hydromet_2023-02-d2 (11/14)

| field | expected | got |
|---|---|---|
| crops | [] | [winter_barley, winter_rapeseed, winter_wheat] |
| crop_condition | [] | [('winter_barley', 'good'), ('winter_rapeseed', 'good'), ('winter_wheat', 'good')] |
| crop_bbch | [] | [('winter_wheat', 3)] |

### uk_hydromet_2023-03-d3__moisture (9/14)

| field | expected | got |
|---|---|---|
| moisture_layer | both | 0-20cm |
| max_mm | 170 | 50 |
| crops | [] | [winter_wheat] |
| crop_condition | [] | [('winter_wheat', 'satisfactory')] |
| hazards | [waterlogging] | [] |

### uk_hydromet_2023-04-d3__growth (7/14)

| field | expected | got |
|---|---|---|
| moisture_status | not_stated | mixed |
| moisture_layer | not_stated | 0-20cm |
| deficit_oblasts | [] | [ivano_frankivsk, kherson, kyiv, lviv, mykolaiv, odesa, poltava, sumy, ternopil, vinnytsia, zhytomyr] |
| crops | [maize, spring_barley, sunflower, winter_barley, winter_rapeseed, winter_wheat] | [maize, soybean, spring_barley, sugar_beet, sunflower, winter_barley, winter_rapeseed, winter_wheat] |
| crop_bbch | [('maize', 0), ('spring_barley', 1), ('sunflower', 0), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] | [('spring_barley', 1), ('winter_barley', 3), ('winter_rapeseed', 5), ('winter_wheat', 3)] |
| hazards | [frost, waterlogging] | [frost] |
| yield_vs_avg | [] | [('winter_barley', 'near'), ('winter_rapeseed', 'above'), ('winter_wheat', 'near')] |

### uk_hydromet_2023-07-d3__moisture (9/14)

| field | expected | got |
|---|---|---|
| moisture_status | adequate | mixed |
| deficit_oblasts | [dnipropetrovsk, kherson, kirovohrad, mykolaiv, odesa, poltava, sumy, vinnytsia, volyn] | [chernihiv, dnipropetrovsk, kharkiv, kherson, kirovohrad, mykolaiv, odesa, ternopil, vinnytsia, volyn] |
| crops | [] | [maize, soybean, spring_barley, sugar_beet, sunflower] |
| crop_condition | [] | [('maize', 'satisfactory'), ('soybean', 'good'), ('spring_barley', 'satisfactory'), ('sugar_beet', 'good'), ('sunflower', 'satisfactory')] |
| hazards | [waterlogging] | [] |

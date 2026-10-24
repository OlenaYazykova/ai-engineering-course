# Report: structured extraction from agrometeorological bulletins (HW1)

## 1. Task and data

- **Corpus:** 41 texts (`data/texts/`): 23 fragments of decadal bulletins of the Ukrainian
  Hydrometeorological Center 2021–2023 (uk; sections "Зволоження ґрунту", "Ріст і розвиток", etc.),
  10 fragments of JRC MARS Global outlook: Ukraine bulletins 2022–2026 and 8 JRC news articles on them
  (en). Sources and dates: `data/sources.csv`.
  The texts are "dirty": words and numbers broken by PDF extraction ("2 2 мм", "14 7-160"), fragments of
  tables and figure captions, typos in the originals ("200 мл" instead of mm), two languages, and every
  text fills only part of the fields.
- **Golden set:** 10 texts (6 uk, 4 en; list in `data/golden_ids.txt`), 14 fields per text = 140 fields.
  The golden set was labelled manually: each of the 140 fields was filled in and checked against the
  text. For ambiguous cases (typos, generic wording such as "winter crops", several soil layers in one
  text) labelling rules were defined; these rules were added to prompt v2 so that the model and the
  golden set interpret the text the same way (see `prompts/CHANGELOG.md`).
- **Schema `AgroReport`** (`agro_extract/schema.py`), one record per text:

| Field | Type | Values |
|---|---|---|
| `year` | int / null | year of the bulletin (only if stated in the text) |
| `month` | 1–12 / null | month |
| `decade` | 1–3 / null | ten-day period (Hydromet bulletins only) |
| `soil_moisture` | object | soil moisture: |
| ├ `status` | enum | `deficit` / `adequate` / `excess` / `mixed` / `not_stated` |
| ├ `layer` | enum | `0-20cm` (arable layer) / `0-100cm` (metre layer) / `both` / `not_stated` |
| ├ `min_mm`, `max_mm` | int / null | smallest and largest productive soil moisture, mm |
| └ `deficit_oblasts` | list of enum | oblasts with insufficient moisture or drought (24 oblasts + Crimea) |
| `crops` | list of objects | crops whose growth stage or condition is described: |
| ├ `crop` | enum | `winter_wheat`, `winter_barley`, `winter_rapeseed`, `spring_barley`, `maize`, `sunflower`, `soybean`, `sugar_beet` |
| ├ `bbch_stage` | 0–9 / null | principal BBCH growth stage |
| └ `condition` | enum | `good` / `satisfactory` / `poor` / `not_stated` |
| `hazards` | list of enum | `drought`, `frost`, `heat`, `heavy_rain`, `waterlogging`, `hail`, `hostilities` |
| `yield_outlook` | list of objects | yield outlook: |
| ├ `crop` | enum | the same 8 crops |
| ├ `vs_5yr_average` | enum | `above` / `near` / `below` / `not_stated` (compared with the 5-year average) |
| └ `production_mt` | float / null | national production forecast, million tonnes |

  Additional checks that a JSON schema cannot express: ranges of month, decade and BBCH;
  `min_mm` ≤ `max_mm`; every crop appears once; values in mm and Mt must be written in the text.
- **Models:** `openai/gpt-4o-mini` via OpenRouter (strict structured output) and `qwen2.5:3b` locally
  via Ollama (JSON schema in `format`), both behind the common `Provider` interface; as a third,
  cheaper cloud model, `google/gemini-2.5-flash-lite` through the same OpenRouter interface.
  qwen2.5:3b was chosen as the local model because it runs on an ordinary laptop (~2 GB), supports
  multilingual text including Ukrainian, and reliably produces JSON that follows a schema.

## 2. Comparison: model × prompt version × sampling

| Model | Prompt | T | top_p | Valid % | Fixed | Failed | Field acc % | Hydromet % | JRC % | Set F1 % | Halluc. | p50, s | p95, s | $ / 1000 docs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | v1 | 0.0 | 1.0 | 92.7 | 11 | 3 | 62.9 | 60.7 | 66.1 | 42.3 | 28 | 5.9 | 11.6 | 0.91 |
| gpt-4o-mini | v1 | 0.7 | 0.9 | 90.2 | 11 | 4 | 65.0 | 64.3 | 66.1 | 45.2 | 27 | 6.1 | 11.6 | 0.93 |
| gpt-4o-mini | v2 | 0.0 | 1.0 | 95.1 | 3 | 2 | 74.3 | 75.0 | 73.2 | 53.5 | 14 | 2.9 | 6.5 | 0.84 |
| qwen2.5:3b | v1 | 0.0 | 1.0 | 36.6 | 9 | 26 | 20.0 | 26.2 | 10.7 | 13.9 | 18 | 259.0 | 404.2 | 0 |
| qwen2.5:3b | v2 | 0.0 | 1.0 | 92.7 | 22 | 3 | 48.6 | 57.1 | 35.7 | 24.1 | 29 | 179.3 | 410.0 | 0 |
| qwen2.5:3b | v2 | 0.7 | 0.9 | 85.4 | 19 | 6 | 45.7 | 46.4 | 44.6 | 19.7 | 35 | 153.4 | 348.4 | 0 |
| **gemini-2.5-flash-lite** | **v2** | **0.0** | **1.0** | **100.0** | **6** | **0** | **74.3** | **73.8** | **75.0** | **63.7** | **18** | **1.4** | **2.7** | **0.58** |

**Accuracy per field, %** (golden set, 10 texts):

| Field | gpt-4o-mini v1 T=0 | gpt-4o-mini v1 T=0.7 | gpt-4o-mini v2 T=0 | qwen2.5:3b v1 T=0 | qwen2.5:3b v2 T=0 | qwen2.5:3b v2 T=0.7 | gemini-2.5-flash-lite v2 T=0 |
|---|---|---|---|---|---|---|---|
| year | 100 | 100 | 90 | 50 | 80 | 80 | 100 |
| month | 90 | 90 | 100 | 30 | 70 | 80 | 100 |
| decade | 90 | 90 | 100 | 50 | 90 | 90 | 100 |
| moisture_status | 50 | 50 | 50 | 0 | 30 | 30 | 50 |
| moisture_layer | 70 | 70 | 90 | 30 | 40 | 20 | 90 |
| min_mm | 90 | 100 | 100 | 20 | 70 | 70 | 90 |
| max_mm | 90 | 90 | 80 | 30 | 70 | 70 | 100 |
| deficit_oblasts | 40 | 40 | 60 | 10 | 40 | 20 | 60 |
| crops | 0 | 0 | 10 | 0 | 10 | 0 | 10 |
| crop_condition | 0 | 10 | 70 | 0 | 10 | 20 | 60 |
| crop_bbch | 70 | 70 | 80 | 10 | 10 | 10 | 60 |
| hazards | 40 | 40 | 40 | 0 | 30 | 20 | 40 |
| yield_vs_avg | 50 | 60 | 70 | 0 | 40 | 40 | 80 |
| yield_mt | 100 | 100 | 100 | 50 | 90 | 90 | 100 |

`crop_condition`, `crop_bbch`, `yield_vs_avg` and `yield_mt` are "crop → value" pairs from `crops` and
`yield_outlook`, compared as sets. Errors per text and field: `results/errors/`.

How the metrics are computed:
- **Valid %**: share of the 41 texts whose answer passed the schema and the fact checks (on the first
  attempt or after one correction attempt); **Fixed**: how many of them needed the correction;
- **Field accuracy**: share of the 140 golden-set fields that exactly match the gold value (lists as
  sets); an invalid answer counts as all fields wrong;
- **Set F1**: partial credit for list fields (oblasts, crops, hazards, outlooks);
- **Hallucinations**: the gold field is empty (null / [] / not_stated) but the model filled it
  (an invented crop counts in `crops`, `crop_condition` and `crop_bbch`);
- **Latency**: time per text including the correction attempt; **cost**: tokens × OpenRouter price
  ($0.15 / $0.60 per 1M tokens), local model = 0 (hardware and electricity not included).

Key findings:
- **Prompt v2 beats v1 for both models:** gpt-4o-mini 62.9 → 74.3 %, hallucinations 28 → 14,
  corrections 11 → 3 (hence also faster: p50 5.9 → 2.9 s); qwen2.5:3b 20.0 → 48.6 %, valid answers
  36.6 → 92.7 %. The largest gains are in fields that v2 defines: `crop_condition` 0 → 70 %,
  `deficit_oblasts` 40 → 60 %, `moisture_layer` 70 → 90 % (gpt-4o-mini).
- **Temperature:** for gpt-4o-mini T=0.7 gave +2 pp accuracy but more failures (4 vs 3), within the
  noise on 10 texts. For qwen2.5:3b T=0.7 is worse: valid 85.4 vs 92.7 %, accuracy 45.7 vs 48.6 %,
  hallucinations 35 vs 29. Conclusion for both models: T=0.
- **The cloud models are much more accurate and 60–130 times faster** than the local one
  (1.4–2.9 s vs ~3 min per text).
- **Third model:** gemini-2.5-flash-lite with v2 has the same field accuracy as gpt-4o-mini (74.3 %),
  no invalid answers (0 failed vs 2), higher set F1 (63.7 vs 53.5 %), is twice as fast (p50 1.4 vs
  2.9 s) and 30 % cheaper ($0.58 vs $0.84 per 1000 docs), but has more hallucinations (18 vs 14):
  it expands "southern and eastern oblasts" into a list of oblasts and adds crops from generic phrases.
- The weakest fields in all runs are `crops` (0–10 %), `moisture_status` (30–50 %) and `hazards`
  (30–40 %): exactly the fields where the text has to be interpreted rather than a number copied.

## 3. Error analysis

**1. Crops invented from moisture text or from generic phrases** (all runs, 4–8 of 10 texts).
`uk_hydromet_2023-07-d3__moisture`: the text only describes moisture reserves "під кукурудзою"
(under maize), "під соняшником" (under sunflower); gold `crops: []`. gpt-4o-mini v1 returns 5 crops with
condition `satisfactory`: the word "задовільне" refers to the **moisture class**, but the model assigned
it to the **crop condition**. v2 removed most of these conditions (`crop_condition` 0 → 70 %), but crops
are still added (`crops` 0 → 10 %), as with "winter crops" phrases in JRC texts. Why: the model reads
`crops` as "which crops are mentioned" rather than "which crops are described". Fix: a prompt rule
"moisture under a crop is not the crop condition", or a separate `moisture_by_crop` field in the schema.

**2. All 25 oblasts in `deficit_oblasts`.** `en_jrc_2024-06` (gpt-4o-mini v1): "a significant rain
deficit impacted winter crops ... across the country" → the model lists every oblast from cherkasy to
zhytomyr, although none is named; gold `[]`. qwen2.5:3b repeats this in 3–4 texts even with v2
(`uk_hydromet_2022-10-d2`: all 25 instead of odesa, kherson, zaporizhzhia). Why: a macro-region or "the
whole country" is expanded into the full enum. The v2 rule "do not convert macro-regions into oblasts"
removed this for gpt-4o-mini (0 cases) but not for the small local model; gemini-2.5-flash-lite does a
milder version of it ("southern and eastern oblasts" in `en_jrcnews_2025-09` → 8 oblasts).

**3. Partial reading: only the first soil layer.** `uk_hydromet_2023-03-d3__moisture`: the text first
gives the arable layer (22–50 mm), then the metre layer (121–170 mm). All models return
`layer: 0-20cm` and `max_mm: 50` instead of `both` and 170. Why: the model looks for "the largest value"
in the first paragraph where "mm" appears next to a layer. Fix: split `soil_moisture` into two objects
(arable and metre layer), which is also more precise for comparison with ERA5-Land.

**4. An invented year that is not in the text.** `en_jrcnews_2022-06`: the news text has no year
(gold `null`). gpt-4o-mini v2 writes 2023, qwen2.5:3b writes 2021, although v2 explicitly says "never
guess it". With v1 gpt-4o-mini returned `null` here: the longer v2 prompt with date examples ("June 2025
→ 2025") pushes the model to fill the field. So `year` is the only field where gpt-4o-mini got worse with
v2 (100 → 90 %). Fix: remove concrete years from the examples, or take the year from metadata
(`data/sources.csv`) instead of the text.

**5. The local model "switches on the whole enum" and invents numbers.** qwen2.5:3b v2: in
`en_jrcnews_2022-06` it returns all 7 hazards (gold: only `hostilities`) and the same BBCH stage 6 for
every crop; in `en_jrc_2024-06` it writes moisture of 11–20 mm that does not exist in the English text.
The fact check catches this, the model repeats the error after the correction attempt, and the answer
is marked `failed`. With v1 there were 26 such failures out of 41; all 5 failures in the golden set are
invented moisture values in mm (25–30, 150–250, etc.) that are not in the text: without rules for
`min_mm/max_mm` the model fills them with "typical" numbers. Why: a 3B model handles the long context
(schema + rules + text, ~4–5k tokens) poorly and fills fields "by template".

Separately, two cases are ambiguous for the golden set as well: `en_jrcnews_2022-06` ("Close to the
5-year average, but below the historical trend": gold `near`, all models `below`) and `max_mm` in
`uk_hydromet_2023-07-d3` (typo "200 мл" in the text). These cases should be covered by prompt rules or
excluded from the golden set.

## 4. Prompt v3 and the regression check

After the error analysis a prompt v3 was written to fix errors 1–4 (rules for the year, both soil
layers, moisture "under a crop", oblasts, hazards, comparison with the 5-year average; details in
`prompts/CHANGELOG.md`). Before adding it to the experiment matrix it was checked against v2 on the
golden set (`make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2`):

| gpt-4o-mini, T=0 | v2 | v3 |
|---|---|---|
| Field accuracy % | 74.3 | 71.4 |
| Hydromet / JRC % | 75.0 / 73.2 | 69.0 / 75.0 |
| Hallucinations | 14 | 16 |
| `year` / `max_mm` | 90 / 80 | 100 / 90 |
| `crop_condition` / `hazards` | 70 / 40 | 40 / 30 |

v3 fixed the invented year and the partial reading of soil layers, but made the model add winter
crops with a condition in texts that only describe overwintering or weather
(`uk_hydromet_2023-02-d2`, `uk_hydromet_2022-10-d2`) and lose `heavy_rain` for "excess July rain".
The check failed (−2.9 pp overall, −30 pp on `crop_condition`), so **v3 was rejected** and v2 stays.
The v3 rules were derived from errors on the same 10 golden texts; further tuning on them would
overfit, so a separate test set is needed before the next prompt version.

## 5. Additional (stretch) features

- **Third model:** gemini-2.5-flash-lite (cheap cloud model) through the same `Provider` interface,
  see section 2.
- **Automatic regression run of prompts on the golden set:** `make regress` runs a new prompt only on
  the golden texts, compares overall and per-field accuracy, valid answers and hallucinations with the
  baseline prompt, writes `results/regression/<model>__<new>_vs_<baseline>.md` and exits with code 1
  if the new prompt is worse than the tolerance (2 pp overall, 10 pp per field), so it can be used as
  a gate in a script or CI. It rejected v3 (section 4).
- **Response caching:** identical requests at T=0 (same model, prompt, text, schema and parameters)
  are replayed from `.cache/responses/` instead of being sent and paid for again; the original latency
  is stored with the answer, so cached runs keep honest latency numbers. Answers at T>0 are not cached
  so that their variance stays visible.

## 6. Choice for production

**gemini-2.5-flash-lite + prompt v2 + T=0.** It has the same field accuracy as gpt-4o-mini (74.3 %),
no invalid answers out of 41 (gpt-4o-mini: 2), the best set F1 (63.7 %), the lowest latency (p50
1.4 s) and the lowest cost ($0.58 per 1000 documents, cents for a few dozen decadal bulletins per
year). Its weak point is more hallucinations (18 vs 14), mainly oblasts expanded from macro-regions
and crops added from generic phrases; the oblast part can be reduced by a post-check that every
oblast name occurs in the text. qwen2.5:3b is free, but takes ~3 min per text and is much less
accurate (48.6 %), so it is not suitable for production.

The stage 1 target from the project plan (field accuracy ≥ 80 %, valid answers ≥ 95 %) is partly met:
100 % valid, 74.3 % accuracy. The gap comes from `crops`, `moisture_status` and `hazards`; prompt
rules alone did not close it (v3, section 4), so the next step is a schema change (errors 1 and 3).

The decision would change if: (1) a wrong value is more costly than a missing one: then gpt-4o-mini
+ v2, which has the fewest hallucinations (14); (2) the data may not be sent to an external provider
(for example, internal agronomist reports): then a local model, but a larger one (qwen2.5:7b or
above) on a GPU, measured again; (3) ≥ 90 % accuracy is needed for `crops`, `moisture_status` and
`hazards`: first change the schema, then compare a stronger cloud model; (4) the volume grows to
millions of documents: recalculate the cost and compare with an own GPU server.

## 7. Limitations

- The golden set is small (10 texts, 4 in English) and every configuration was run once: differences
  of 2–3 pp may be noise.
- The T=0 / T=0.7 comparison for qwen2.5:3b was done with prompt v2 as the better version;
  gemini-2.5-flash-lite was run with v2 at T=0 only.
- The English JRC texts are mostly from June and September; one Hydromet bulletin (September 2023) is
  a scan without a text layer and was skipped.

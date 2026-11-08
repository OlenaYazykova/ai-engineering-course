# Report: structured extraction from agrometeorological bulletins (HW1)

> This report was written for the git tag `hw1`, where it was `REPORT.md` and the commands had no prefix.
> In the current version of the project the same commands are `make extract-…` (`make metrics` → `make extract-metrics`),
> and the files of stage 1 moved to `agro/extract/`, `data/extract/`, `prompts/extract/`, `results/extract/`.

## 1. Task and data

- **Corpus:** 41 texts (`data/texts/`): 23 fragments of decadal bulletins of the Ukrainian
  Hydrometeorological Center 2021–2023 (uk; sections "Зволоження ґрунту", "Ріст і розвиток", etc.),
  10 fragments of JRC MARS Global outlook: Ukraine bulletins 2022–2026 and 8 JRC news articles on them
  (en). Sources and dates: `data/sources.csv`.
  The texts are "dirty": words and numbers broken by PDF extraction ("2 2 мм", "14 7-160"), fragments of
  tables and figure captions, typos in the originals ("200 мл" instead of mm), two languages, and every
  text fills only part of the fields.
- **Golden sets:** 14 fields per text.
  - **Dev** (`data/golden/`, 10 texts: 6 uk, 4 en; list in `data/golden_ids.txt`): labelled manually,
    each of the 140 fields filled in and checked against the text. For ambiguous cases (typos, generic
    wording such as "winter crops", several soil layers in one text) labelling rules were defined and
    added to prompt v2 so that the model and the golden set interpret the text the same way (see
    `prompts/CHANGELOG.md`). The error analysis, prompt v3 and the fact checks were all derived from
    this set.
  - **Held-out test** (`data/golden_test/`): 10 more texts of the same kinds (6 uk, 4 en), labelled
    with the same rules as the dev set. The prompt and the checks were not changed after the test
    results.
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
  `min_mm` ≤ `max_mm`; every crop appears once. Deterministic checks of every value against the
  source text: section 3.
- **Models:** `openai/gpt-4o-mini` via OpenRouter (strict structured output) and `qwen2.5:3b` locally
  via Ollama (JSON schema in `format`), both behind the common `Provider` interface; as a third,
  cheaper cloud model, `google/gemini-2.5-flash-lite` through the same OpenRouter interface.
  qwen2.5:3b was chosen as the local model because it runs on an ordinary laptop (~2 GB), supports
  multilingual text including Ukrainian, and reliably produces JSON that follows a schema.

## 2. Comparison: model × prompt version × sampling

All runs with the deterministic fact checks of section 3 (both stages). Field accuracy, set F1 and
hallucinations in the first table: dev golden set; the held-out test set is compared below.

| Model | Prompt | T | top_p | Valid % | Fixed | Failed | Field acc % | Hydromet % | JRC % | Set F1 % | Halluc. | Removed | p50, s | p95, s | $ / 1000 docs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | v1 | 0.0 | 1.0 | 82.9 | 10 | 7 | 67.9 | 58.3 | 82.1 | 61.2 | 10 | 353 | 6.7 | 11.9 | 0.96 |
| gpt-4o-mini | v1 | 0.7 | 0.9 | 85.4 | 12 | 6 | 67.9 | 58.3 | 82.1 | 57.6 | 10 | 316 | 6.5 | 13.9 | 0.98 |
| **gpt-4o-mini** | **v2** | **0.0** | **1.0** | **95.1** | **6** | **2** | **80.7** | **75.0** | **89.3** | **66.7** | **3** | **195** | **3.6** | **7.7** | **0.90** |
| qwen2.5:3b | v1 | 0.0 | 1.0 | 26.8 | 7 | 30 | 31.4 | 39.3 | 19.6 | 33.3 | 3 | 396 | 259.0 | 404.2 | 0 |
| qwen2.5:3b | v2 | 0.0 | 1.0 | 92.7 | 23 | 3 | 65.7 | 71.4 | 57.1 | 48.4 | 9 | 661 | 149.7 | 345.4 | 0 |
| qwen2.5:3b | v2 | 0.7 | 0.9 | 70.7 | 15 | 12 | 57.1 | 46.4 | 73.2 | 38.5 | 10 | 412 | 153.4 | 348.4 | 0 |
| gemini-2.5-flash-lite | v2 | 0.0 | 1.0 | 97.6 | 12 | 1 | 73.6 | 65.5 | 85.7 | 77.8 | 8 | 244 | 1.5 | 3.4 | 0.68 |

The cloud runs and qwen2.5:3b v2 T=0 were run again with the stage 1 checks (each answer had one
correction attempt); the stage 2 rules were then applied to these answers with `python main.py
revalidate`. qwen2.5:3b v1 T=0 and v2 T=0.7 (~2–3 h each) were not run again: their saved answers were
re-checked with `revalidate` without calling the model, where an answer that fails a strict check gets
no new correction attempt, so their valid % and accuracy are a lower bound.

**Accuracy per field, %** (dev golden set, 10 texts):

| Field | gpt-4o-mini v1 T=0 | gpt-4o-mini v1 T=0.7 | gpt-4o-mini v2 T=0 | qwen2.5:3b v1 T=0 | qwen2.5:3b v2 T=0 | qwen2.5:3b v2 T=0.7 | gemini-2.5-flash-lite v2 T=0 |
|---|---|---|---|---|---|---|---|
| year | 90 | 90 | 100 | 50 | 90 | 80 | 90 |
| month | 80 | 80 | 100 | 30 | 70 | 70 | 90 |
| decade | 90 | 90 | 100 | 50 | 90 | 80 | 90 |
| moisture_status | 50 | 50 | 50 | 0 | 40 | 50 | 40 |
| moisture_layer | 80 | 80 | 90 | 40 | 80 | 70 | 90 |
| min_mm | 80 | 80 | 90 | 20 | 70 | 70 | 90 |
| max_mm | 80 | 80 | 80 | 30 | 70 | 70 | 90 |
| deficit_oblasts | 80 | 80 | 80 | 30 | 80 | 70 | 70 |
| crops | 40 | 40 | 70 | 40 | 40 | 20 | 40 |
| crop_condition | 50 | 50 | 90 | 40 | 70 | 40 | 80 |
| crop_bbch | 60 | 60 | 70 | 40 | 40 | 30 | 50 |
| hazards | 40 | 40 | 40 | 0 | 50 | 30 | 50 |
| yield_vs_avg | 40 | 40 | 70 | 20 | 40 | 40 | 70 |
| yield_mt | 90 | 90 | 100 | 50 | 90 | 80 | 90 |

`crop_condition`, `crop_bbch`, `yield_vs_avg` and `yield_mt` are "crop → value" pairs from `crops` and
`yield_outlook`, compared as sets. Errors per text and field, dev and test: `results/errors/`.

**Dev vs held-out test set** (95 % CI: bootstrap over texts; per-field test accuracy in
`results/metrics.md`):

| Model | Prompt | T | Dev acc % | Dev 95 % CI | Test acc % | Test 95 % CI | Test Hydromet % | Test JRC % | Dev F1 % | Test F1 % | Dev halluc. | Test halluc. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | v1 | 0.0 | 67.9 | 51–80 | 60.0 | 39–79 | 63.1 | 55.4 | 61.2 | 47.8 | 10 | 11 |
| gpt-4o-mini | v1 | 0.7 | 67.9 | 51–80 | 68.6 | 50–83 | 63.1 | 76.8 | 57.6 | 49.0 | 10 | 12 |
| **gpt-4o-mini** | **v2** | **0.0** | **80.7** | **74–87** | **77.9** | **71–84** | **73.8** | **83.9** | **66.7** | **62.7** | **3** | **11** |
| qwen2.5:3b | v1 | 0.0 | 31.4 | 12–53 | 3.6 | 0–11 | 6.0 | 0.0 | 33.3 | 13.0 | 3 | 2 |
| qwen2.5:3b | v2 | 0.0 | 65.7 | 49–79 | 59.3 | 36–79 | 72.6 | 39.3 | 48.4 | 48.9 | 9 | 7 |
| qwen2.5:3b | v2 | 0.7 | 57.1 | 36–74 | 50.0 | 26–71 | 72.6 | 16.1 | 38.5 | 48.9 | 10 | 6 |
| gemini-2.5-flash-lite | v2 | 0.0 | 73.6 | 55–87 | 83.6 | 79–89 | 83.3 | 83.9 | 77.8 | 63.3 | 8 | 13 |

How the metrics are computed:
- **Valid %**: share of the 41 texts whose answer passed the schema and the fact checks (on the first
  attempt or after one correction attempt); **Fixed**: how many of them needed the correction;
- **Field accuracy**: share of the 140 golden-set fields that exactly match the gold value (lists as
  sets); an invalid answer counts as all fields wrong;
- **Set F1**: partial credit for list fields (oblasts, crops, hazards, outlooks);
- **Hallucinations**: the gold field is empty (null / [] / not_stated) but the model filled it
  (an invented crop counts in `crops`, `crop_condition` and `crop_bbch`);
- **Removed**: values removed or reset by the soft checks of section 3, on all 41 texts. An extra
  oblast or hazard in a list whose gold value is not empty is not a "hallucination" by the definition
  above (it lowers field accuracy and set F1 instead); Removed shows how many such items the checks drop;
- **Latency**: time per text including the correction attempt; **cost**: tokens × OpenRouter price
  ($0.15 / $0.60 per 1M tokens), local model = 0 (hardware and electricity not included).

Key findings:
- **Prompt v2 beats v1 for both models:** gpt-4o-mini 67.9 → 80.7 %, hallucinations 10 → 3, valid
  82.9 → 95.1 %, corrections 10 → 6 (hence also faster: p50 6.7 → 3.6 s); qwen2.5:3b 31.4 → 65.7 %,
  valid 26.8 → 92.7 %. The largest gains are in fields that v2 defines: `crop_condition` 50 → 90 %,
  `crops` 40 → 70 %, `yield_vs_avg` 40 → 70 % (gpt-4o-mini).
- **Temperature:** for gpt-4o-mini T=0.7 gave the same accuracy (67.9 %) and a lower set F1; for
  qwen2.5:3b T=0.7 is worse: valid 70.7 vs 92.7 %, accuracy 57.1 vs 65.7 %. Conclusion for both: T=0.
- **The cloud models are much more accurate and 40–100 times faster** than the local one
  (1.5–3.6 s vs ~2.5 min per text).
- **Third model:** gemini-2.5-flash-lite with v2 has the most valid answers (97.6 %), the best set F1
  (77.8 %), is the fastest (p50 1.5 s) and cheapest ($0.68 per 1000 docs), but is less accurate than
  gpt-4o-mini v2 (73.6 vs 80.7 %) and has more hallucinations (8 vs 3). Part of the gap is one golden
  text marked `failed` (section 3).
- The weakest fields in all runs are `moisture_status` (40–50 %) and `hazards` (40–50 %): the text has
  to be interpreted, and the keyword checks cannot tell which interpretation is right.
- **Held-out test set: accuracy transfers, hallucinations only partly.** gpt-4o-mini v2: 80.7 % on
  dev, 77.9 % on test (−2.8 pp, the intervals overlap); qwen2.5:3b v2: 65.7 → 59.3 %. But
  hallucinations of gpt-4o-mini v2 are 3 on dev and 11 on test: the dev number is optimistic, because
  the stage 2 rules were chosen on the dev errors (section 3). gemini-2.5-flash-lite is better on
  test than on dev (83.6 vs 73.6 %): on dev it lost one whole text to a `failed` answer, the narrow
  test interval (79–89 %) is the more reliable estimate. Prompt v2 beats v1 on test as well
  (gpt-4o-mini 60.0 → 77.9 %), so the v2 labelling rules are not specific to the dev texts.

## 3. Deterministic fact checks

Added after the review of the first version. There, a number counted as found if it occurred
anywhere in the text, and oblasts, crops and hazards were not checked against the text at all, so
the most frequent hallucinations of section 4 (oblasts, crops and hazards that the bulletin does not
mention) passed as valid answers. Every answer is now checked against its source text in code
(`agro_extract/checks.py`), in two ways:

**A. Strict, for numbers** (the answer is invalid → one correction attempt with the list of errors →
`failed`):
- `min_mm` / `max_mm` must be written in the text followed by "мм / mm" within 30 characters
  ("11-20 мм", "від 173 до 282 мм"); a number from a date ("20 липня") or a percentage does not count.
  Numbers split by PDF extraction ("8 0 мм") are joined first;
- `production_mt` must be followed by "Mt / млн т";
- if mm values are given, the soil layer cannot be `not_stated`.

**B. Soft, for lists and single facts** (the value is removed or reset to `null` / `not_stated`, logged
in the result row as `removed`; the answer stays valid, so one wrong detail does not discard the
correct fields):
- every oblast in `deficit_oblasts`, every crop in `crops` / `yield_outlook` and every hazard must be
  supported by a keyword in the text (Ukrainian and English stems for all 25 oblasts, 8 crops,
  7 hazards; names split by PDF extraction, such as "Кіровогр адської", are found too); duplicates are
  removed;
- year, month name and decade ("третю декаду") must be written in the text;
- soil layer: "орний шар / 0-20 см / arable" for `0-20cm`, "метровий шар / 0-100 см / metre" for
  `0-100cm`; moisture status: words of that class ("недостатні / посуха / dry", "оптимальні / достатні",
  "перезволоження / excess"), `mixed` needs words of two classes;
- crop condition, BBCH stage (words of the growth phase: "кущіння", "цвітіння", "heading", ...) and
  the comparison with the 5-year average need their keywords in the text.

The checks were added in two stages:

- **Stage 1** — checks A and B above, with keywords looked up anywhere in the text. The cloud models
  and qwen2.5:3b v2 T=0 were run again with them.
- **Stage 2** — after analysing the hallucinations left after stage 1: almost all of them were crops
  that are mentioned in the text, but whose condition came from a general phrase or from moisture
  ("задовільне" about the soil). Two more soft rules:
  - a crop condition and a BBCH stage must stand **within 250 characters of the crop name**, not
    anywhere in the text;
  - a crop with neither a stage nor a condition, and a yield entry with neither a comparison nor a
    production figure, carry no information and are removed (the v2 prompt rule, now checked in code).

  Stage 2 rules are soft, so they were applied to the saved answers of stage 1
  (`python main.py revalidate`): the model answers are the same, only the checks changed.
  The 250-character window is the smallest that keeps every golden value (100–150 characters would
  reset 2 correct conditions), so it was chosen on the golden set itself.

The dev golden set passes all checks (`make check-golden`: 10/10, no golden value is removed or
reset); on the held-out test set the checks make a few false removals (see below). 28 unit tests
cover them (`make test`).

**Before the checks → stage 1 → stage 2** (dev golden set; runs of section 2):

| Run | Field acc % | Hallucinations | Valid % |
|---|---|---|---|
| gpt-4o-mini v1 T=0 | 62.9 → 63.6 → 67.9 | 28 → 16 → 10 | 92.7 → 82.9 → 82.9 |
| gpt-4o-mini v1 T=0.7 | 65.0 → 63.6 → 67.9 | 27 → 16 → 10 | 90.2 → 85.4 → 85.4 |
| **gpt-4o-mini v2 T=0** | **74.3 → 74.3 → 80.7** | **14 → 11 → 3** | **95.1 → 95.1 → 95.1** |
| qwen2.5:3b v2 T=0 | 48.6 → 62.1 → 65.7 | 29 → 14 → 9 | 92.7 → 92.7 → 92.7 |
| gemini-2.5-flash-lite v2 T=0 | 74.3 → 68.6 → 73.6 | 18 → 15 → 8 | 100 → 97.6 → 97.6 |

- On dev, hallucinations fell in every run, by 56–79 % in total (gpt-4o-mini v2: 14 → 3); field accuracy
  grew in every run except gemini (see below): gpt-4o-mini v2 74.3 → 80.7 %, qwen2.5:3b v2
  48.6 → 65.7 %. Stage 2 gave the largest gain on crops: `crops` 10 → 70 %, `crop_condition`
  60 → 90 % (gpt-4o-mini v2).
- Valid % fell where the strict check found invented numbers that used to pass: such an answer is
  now `failed` and all its 14 fields count as wrong. Example: gemini-2.5-flash-lite,
  `uk_hydromet_2023-03-d3__moisture`: the text gives "11-20 мм", gold `min_mm: 11`; the model wrote
  `min_mm: 0`, got the error "min_mm=0 is not written in the text as a value in mm", repeated 0 after
  the correction attempt, and the answer was rejected. Before the checks this answer was "valid" with
  one wrong field; this is why gemini's accuracy fell from 74.3 to 68.6 % at stage 1 (73.6 % after
  stage 2).

**Check on the held-out test set.** The checks were applied to the test texts without any changes.
"Before" = the answers of the same runs before any fact checks, from the first version (git tag
`hw1-initial`; for gpt-4o-mini at T=0 the first answers are identical, they are replayed from the
cache); reproduced with `make before-checks`, "after" with `make metrics`:

| Run | Test acc % before → after | Test hallucinations before → after |
|---|---|---|
| gpt-4o-mini v1 T=0 | 56.4 → 60.0 | 29 → 11 |
| gpt-4o-mini v1 T=0.7 | 57.1 → 68.6 | 28 → 12 |
| **gpt-4o-mini v2 T=0** | **65.7 → 77.9** | **21 → 11** |
| qwen2.5:3b v2 T=0 | 49.3 → 59.3 | 31 → 7 |
| gemini-2.5-flash-lite v2 T=0 | 76.4 → 83.6 | 21 → 13 |

- On texts that nothing was tuned on, the checks still raise accuracy (gpt-4o-mini v2 +12.2 pp) and
  cut hallucinations by about half (21 → 11; 38–77 % for the other runs). The effect is real, but
  smaller than on dev (14 → 3), where the stage 2 window was chosen.
- False removals: on the test set the unchanged checks would remove 4 correct golden values
  (`make check-golden`): "засушливі умови" is not in the drought keywords, "вологозапаси значно
  поповнилися" is not in the adequate-moisture keywords, and the harvest of sugar beet (BBCH stage 4)
  is not near a stage-4 keyword. On dev there were none, because the keyword lists were written on
  the dev texts. These values were not added to the keyword lists: that would be tuning on the test
  set.
- Limitation: a keyword check proves that a word is in the text (stage 2: near the crop), not that
  it refers to this value. "Removed" also counts values on the 31 texts without a golden answer,
  where a reset cannot be checked; it grew at stage 2 (gpt-4o-mini v2 76 → 195), mostly crops without
  a stage or condition.

## 4. Error analysis

The examples below are from the runs before the fact checks; "After the checks" says what section 3
does with each error now.

**1. Crops invented from moisture text or from generic phrases** (all runs, 4–8 of 10 texts).
`uk_hydromet_2023-07-d3__moisture`: the text only describes moisture reserves "під кукурудзою"
(under maize), "під соняшником" (under sunflower); gold `crops: []`. gpt-4o-mini v1 returns 5 crops with
condition `satisfactory`: the word "задовільне" refers to the **moisture class**, but the model assigned
it to the **crop condition**. v2 removed most of these conditions (`crop_condition` 0 → 70 %), but crops
are still added (`crops` 0 → 10 %), as with "winter crops" phrases in JRC texts. Why: the model reads
`crops` as "which crops are mentioned" rather than "which crops are described". Fix: a prompt rule
"moisture under a crop is not the crop condition", or a separate `moisture_by_crop` field in the schema.
*After the checks:* mostly solved at stage 2. The condition word must stand near the crop name, and
crops without a stage or condition are removed (gpt-4o-mini v2: `crops` 10 → 70 %, `crop_condition`
60 → 90 %).

**2. All 25 oblasts in `deficit_oblasts`.** `en_jrc_2024-06` (gpt-4o-mini v1): "a significant rain
deficit impacted winter crops ... across the country" → the model lists every oblast from cherkasy to
zhytomyr, although none is named; gold `[]`. qwen2.5:3b repeats this in 3–4 texts even with v2
(`uk_hydromet_2022-10-d2`: all 25 instead of odesa, kherson, zaporizhzhia). Why: a macro-region or "the
whole country" is expanded into the full enum. The v2 rule "do not convert macro-regions into oblasts"
removed this for gpt-4o-mini (0 cases) but not for the small local model; gemini-2.5-flash-lite does a
milder version of it ("southern and eastern oblasts" in `en_jrcnews_2025-09` → 8 oblasts).
*After the checks:* solved. Every oblast that is not named in the text is removed; this is the largest
group of removed values (`deficit_oblasts` accuracy of qwen2.5:3b v2 40 → 80 %).

**3. Partial reading: only the first soil layer.** `uk_hydromet_2023-03-d3__moisture`: the text first
gives the arable layer (22–50 mm), then the metre layer (121–170 mm). All models return
`layer: 0-20cm` and `max_mm: 50` instead of `both` and 170. Why: the model looks for "the largest value"
in the first paragraph where "mm" appears next to a layer. Fix: split `soil_moisture` into two objects
(arable and metre layer), which is also more precise for comparison with ERA5-Land.
*After the checks:* not caught: 50 mm and the arable layer are written in the text, so the answer is
consistent with it, only incomplete. A check cannot find a value the model did not return.

**4. An invented year that is not in the text.** `en_jrcnews_2022-06`: the news text has no year
(gold `null`). gpt-4o-mini v2 writes 2023, qwen2.5:3b writes 2021, although v2 explicitly says "never
guess it". With v1 gpt-4o-mini returned `null` here: the longer v2 prompt with date examples ("June 2025
→ 2025") pushes the model to fill the field. So `year` is the only field where gpt-4o-mini got worse with
v2 (100 → 90 %). Fix: remove concrete years from the examples, or take the year from metadata
(`data/sources.csv`) instead of the text.
*After the checks:* solved. A year that is not written in the text is reset to `null`
(gpt-4o-mini v2 `year` 90 → 100 %).

**5. The local model "switches on the whole enum" and invents numbers.** qwen2.5:3b v2: in
`en_jrcnews_2022-06` it returns all 7 hazards (gold: only `hostilities`) and the same BBCH stage 6 for
every crop; in `en_jrc_2024-06` it writes moisture of 11–20 mm that does not exist in the English text.
The fact check catches this, the model repeats the error after the correction attempt, and the answer
is marked `failed`. With v1 there were 26 such failures out of 41; all 5 failures in the golden set are
invented moisture values in mm (25–30, 150–250, etc.) that are not in the text: without rules for
`min_mm/max_mm` the model fills them with "typical" numbers. Why: a 3B model handles the long context
(schema + rules + text, ~4–5k tokens) poorly and fills fields "by template".
*After the checks:* invented mm values are still rejected (now also mm taken from dates or percentages),
and hazards without a keyword in the text are removed (`hazards` of qwen2.5:3b v2 30 → 50 %).

**Remaining hallucinations after the checks.** gpt-4o-mini v2 has 3 left (gemini-2.5-flash-lite v2: 8),
all of two kinds:
- *Crops from a general description.* `uk_hydromet_2023-02-d2` describes overwintering of winter crops;
  gold `crops: []`. gpt-4o-mini adds winter wheat, barley and rapeseed with BBCH stage 1 (gemini: 2,
  plus `frost`, although the text reports no frost damage). The crop names and the phase words are in
  the text and near each other, so the checks keep them.
- *Moisture status from a text about crop growth.* `uk_hydromet_2023-04-d3__growth` mentions moisture
  only in passing (gold `not_stated` by the v2 rule); the model returns `mixed` (gemini: `excess`).

Both are errors of interpretation: the words are in the text, but the model reads them wrongly. A
keyword check cannot tell these cases apart, and rules written for these two phrases would be fitted
to the 10 golden texts, so they were not added. The other remaining errors are wrong or missing values
rather than invented ones: `moisture_status` (`mixed` instead of `adequate`), a missing `hostilities`
or `waterlogging`, and the first soil layer only (error 3).

**Hallucinations on the held-out test set.** gpt-4o-mini v2 has 11 (gemini-2.5-flash-lite: 13).
They are of the same kinds as on dev, which confirms that they are general weaknesses, not
peculiarities of the dev texts:
- *Crops and conditions from general descriptions or moisture classes* (7 of 11). `uk_hydromet_2023-01-d1`
  describes overwintering, like the dev text `2023-02-d2`: the model adds winter wheat, barley and
  rapeseed with BBCH 2 and `frost`, although the text says the cold "will have no negative
  consequences". `uk_hydromet_2021-08-d1__moisture`: soil moisture under sunflower "задовільними" and
  under soybean "незадовільним" becomes the crop condition (error 1): the moisture word stands right
  next to the crop name, so the stage 2 proximity rule does not catch it.
- *Oblasts named in the text, but not with a deficit* (3 of 11). `uk_hydromet_2022-08-d3`: the oblasts
  of the sentence about "достатні та оптимальні" moisture are put into `deficit_oblasts`;
  `uk_hydromet_2023-04-d3`: Odesa with "достатніми (до 100 мм)". The oblast check only proves that
  the oblast is named, not in which context.
- *Yield comparison from a regional or trend statement* (1 of 11): `en_jrc_2022-06`, "below-average
  yield outlook for winter crops in central and western oblasts" → `below` for the whole country.

A check that would catch the second kind (the oblast must stand near a deficit word) is the obvious
next step, but it should be designed on dev and measured on a new test set, not on this one.

Separately, two cases are ambiguous for the golden set as well: `en_jrcnews_2022-06` ("Close to the
5-year average, but below the historical trend": gold `near`, all models `below`) and `max_mm` in
`uk_hydromet_2023-07-d3` (typo "200 мл" in the text). These cases should be covered by prompt rules or
excluded from the golden set.

## 5. Prompt v3 and the regression check

After the error analysis a prompt v3 was written to fix errors 1–4 (rules for the year, both soil
layers, moisture "under a crop", oblasts, hazards, comparison with the 5-year average; details in
`prompts/CHANGELOG.md`). Before adding it to the experiment matrix it was checked against v2 on the
golden set (`make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2`; run before the fact checks of
section 3):

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
overfit, which is why the held-out test set was added (section 2).

## 6. Additional (stretch) features

- **Third model:** gemini-2.5-flash-lite (cheap cloud model) through the same `Provider` interface,
  see section 2.
- **Automatic regression run of prompts on the dev golden set:** `make regress` runs a new prompt only
  on the dev golden texts, compares overall and per-field accuracy, valid answers and hallucinations with the
  baseline prompt, writes `results/regression/<model>__<new>_vs_<baseline>.md` and exits with code 1
  if the new prompt is worse than the tolerance (2 pp overall, 10 pp per field), so it can be used as
  a gate in a script or CI. It rejected v3 (section 5).
- **Held-out test set and confidence intervals** (added after the review): a second golden set that
  nothing was tuned on, metrics reported separately for dev and test with a 95 % bootstrap interval
  over texts (`make metrics`); `make regress` uses only dev, so the test set stays out of tuning.
- **Response caching:** identical requests at T=0 (same model, prompt, text, schema and parameters)
  are replayed from `.cache/responses/` instead of being sent and paid for again; the original latency
  is stored with the answer, so cached runs keep honest latency numbers. Answers at T>0 are not cached
  so that their variance stays visible.

## 7. Choice for production

**gpt-4o-mini + prompt v2 + T=0.** Over both golden sets (20 texts) it has the highest accuracy
together with gemini-2.5-flash-lite (dev 80.7 %, test 77.9 %; gemini 73.6 % and 83.6 %, both about
79 % on average), the fewest hallucinations (3 + 11 = 14 vs 8 + 13 = 21 for gemini), 95.1 % valid
answers, p50 3.6 s and $0.90 per 1000 documents (cents for a few dozen decadal bulletins per year).
Hallucinations decide between the two, because a wrong value that looks valid is the most harmful
error for an analyst.

Before the checks the choice was gemini-2.5-flash-lite (same accuracy, 100 % valid, cheaper and
faster). It remains the alternative if latency and cost matter more than hallucinations: p50 1.5 s,
$0.68 per 1000 documents, 97.6 % valid, and the best test accuracy. qwen2.5:3b is free, but takes
~2.5 min per text and is less accurate (65.7 % dev, 59.3 % test), so it is not suitable for
production.

The stage 1 target from the project plan (field accuracy ≥ 80 %, valid answers ≥ 95 %) is met on dev
(80.7 %, 95.1 %), but not on the held-out test set (77.9 %, 95 % CI 71–84 %): the honest estimate for
new bulletins is just below the target. The weakest fields are still `moisture_status` and `hazards`;
prompt rules alone did not improve them (v3, section 5).

The decision would change if: (1) latency or cost is the priority: gemini-2.5-flash-lite + v2;
(2) the data may not be sent to an external provider (for example, internal agronomist reports): a
local model, but a larger one (qwen2.5:7b or above) on a GPU, measured again; (3) ≥ 90 % accuracy is
needed for `moisture_status` and `hazards`: more precise labelling rules checked on a separate test
set, then a stronger cloud model; (4) the volume grows to millions of documents: recalculate the cost and
compare with an own GPU server.

## 8. Limitations

- Both golden sets are small (10 texts each, 4 in English) and every configuration was run once: the
  95 % intervals are 10–30 pp wide, so differences of a few pp between runs are noise.
- The schema stores closed numbers,
  so "менше 10 мм" is labelled 10 and "31 мм і більше" 31 (the same rule as in dev and prompt v2); the
  open bounds are lost.
- The test set has now been looked at, so it can no longer serve as an unbiased test for the next
  changes: the next prompt or check version needs a new held-out set.
- The keyword lists of the soft checks were written for these two sources (Hydromet, JRC); a new
  source with other wording may need new keywords, otherwise correct values would be removed.
- The T=0 / T=0.7 comparison for qwen2.5:3b was done with prompt v2 as the better version;
  gemini-2.5-flash-lite was run with v2 at T=0 only.
- The English JRC texts are mostly from June and September; one Hydromet bulletin (September 2023) is
  a scan without a text layer and was skipped.

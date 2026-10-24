# Prompt changelog

Every prompt is a file `prompts/<version>.txt`. `{schema}` is replaced with the JSON schema of
`AgroReport` (`agro_extract/schema.py`). The document goes into the user message inside
`<document>` tags. Every result row in `results/` stores the prompt version and its hash.

## Schema change before the runs: `year` may be null

Found in the first test run (gpt-4o-mini, prompt v1, `en_jrcnews_2022-06`): the JRC news text
does not contain the year, but `year` was a required integer, so the model had to write some
number and answered 2023 instead of 2022. Fix: `year` is now `int | None` in the schema, and v2
says "if the year or month is not written in the text, use null; never guess it".

## v1 (baseline)

Zero-shot: one instruction, the injection rule (`<document>` is data) and the JSON schema.
No definitions of the enum values, of the BBCH scale or of the oblast names.

Measured (golden set, 10 texts × 14 fields, T=0):

| Model | Valid % | Field acc % | Hallucinations | Failed / fixed |
|---|---|---|---|---|
| gpt-4o-mini | 92.7 | 62.9 | 28 | 3 / 11 |
| qwen2.5:3b | 36.6 | 20.0 | 18 | 26 / 9 |

Main problems: crop conditions taken from moisture classes ("задовільне"), all 25 oblasts listed
for "across the country", invented mm values in texts without them (all 5 golden failures of qwen).

## v2

What changed and why:

- **Period rules.** Hydromet texts give the period as "за першу декаду липня 2021 р.", JRC texts
  only a month. Without a rule the model has to guess what `decade` means for JRC.
- **Moisture classes.** The bulletins use their own scale ("незадовільне" <10 mm, "недостатнє"
  11-20 mm, "оптимальне" ...). v2 maps it and the JRC wording to `deficit / adequate / excess`.
- **min_mm / max_mm.** Bulletins also give precipitation in mm; v2 says to take only productive
  soil moisture, including class boundaries, so the gold set and the model count the same numbers.
- **Oblasts.** Genitive forms ("Одеській, Херсонській областях") mapped to the enum; macro-regions
  ("південні області", "the east") must not be turned into oblasts (a source of hallucinations).
- **BBCH table.** Ukrainian phase names mapped to principal BBCH stages 0-9, with a rule for ranges.
- **Hazards.** Only hazards that happened, not forecasts; English wordings added ("heatwave",
  "excess rain", rain deficit harming crops = drought); "no frost damage" is not a hazard.
- **Labelling rules made explicit.** While labelling the golden set, several cases were
  ambiguous: general "winter crops" statements, yield vs production comparisons, mm values under
  several crops and layers, split numbers from PDF ("2 2 мм"), ice crust thickness in mm. v2 states
  the same rules that were used for the golden set, so the model and the gold count the same thing.

Measured (golden set, T=0):

| Model | Valid % | Field acc % | Hallucinations | Failed / fixed | p50, s |
|---|---|---|---|---|---|
| gpt-4o-mini | 92.7 → 95.1 | 62.9 → **74.3** | 28 → 14 | 3 / 11 → 2 / 3 | 5.9 → 2.9 |
| qwen2.5:3b | 36.6 → 92.7 | 20.0 → **48.6** | 18 → 29 | 26 / 9 → 3 / 22 | 259 → 179 |

Per field (gpt-4o-mini): `crop_condition` 0 → 70 %, `deficit_oblasts` 40 → 60 %, `moisture_layer`
70 → 90 %, `month` / `decade` 90 → 100 %. Worse: `year` 100 → 90 % (in a news text without a year the
model now writes 2023: the date examples in v2 push it to fill the field) and `max_mm` 90 → 80 %.
Still weak: `crops` 10 %, `moisture_status` 50 %, `hazards` 40 % (see REPORT.md, section 3).
qwen2.5:3b: far fewer invalid answers, but more hallucinations, because answers that were failed
under v1 are now valid and get scored field by field.

Next version (v3) would: remove concrete years from the date examples, say that moisture "under a
crop" is not the crop condition, and ask for both soil layers when the text gives both.

## v3

What changed and why (from the v2 error analysis, REPORT.md section 3):

- **Year.** v2 examples with concrete years ("June 2025 -> 2025") made the model write a year that
  is not in the text. v3 has no concrete years in the examples and says the year must be copied
  from the text, otherwise null.
- **Moisture status.** "В окремих районах X ..., на решті площ Y" -> Y prevails; local remarks do not
  set the status; in crop-growth texts that mention moisture in passing the status is `not_stated`.
- **Both layers.** If the text gives values for the arable and the metre layer, `layer = both` and
  `min_mm / max_mm` are taken over the whole text (v2: models stopped at the first paragraph).
- **Crops.** Moisture "під кукурудзою" is about the soil, not the crop; moisture classes
  ("задовільне") are never crop conditions; yield forecasts do not create crop entries.
- **Oblasts.** "Задовільне" moisture is not a deficit; only oblasts written in the text
  ("across the country" never becomes a list of oblasts).
- **Hazards.** Local hazards ("місцями", orchards) count; occupied oblasts and field abandonment
  count as `hostilities`.
- **Yield outlook.** Compare only with the 5-year average, not with the trend or last year.

Checked first with `make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2` (golden set only).
Note: the v3 rules come from errors on the same 10 golden texts, so part of the gain may not
transfer to new texts; a separate test set would be needed to confirm it.

Measured with `make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2` (golden set, T=0):

| | v2 | v3 |
|---|---|---|
| Field accuracy % | 74.3 | 71.4 |
| Hydromet / JRC % | 75.0 / 73.2 | 69.0 / 75.0 |
| Hallucinations | 14 | 16 |
| Valid % | 100 | 100 |

Fixed: `year` 90 → 100 % (no invented year in `en_jrcnews_2022-06`), `max_mm` 80 → 90 %.
Worse: `crop_condition` 70 → 40 %: the model now adds winter crops with a condition in texts that
only describe overwintering or weather (`uk_hydromet_2023-02-d2`, `uk_hydromet_2022-10-d2`); `hazards`
40 → 30 % (lost `heavy_rain` for "excess July rain"). The longer list of crop rules seems to draw the
model's attention to crops instead of keeping it away from them.

**Decision: v3 rejected** (the check failed: −2.9 pp overall, −30 pp on one field); v2 stays the
production prompt and v3 is not in the experiment matrix. Report: `results/regression/`.

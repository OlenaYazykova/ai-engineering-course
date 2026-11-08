# Agro-analyst: course project plan

**Agro-analyst** is an assistant that answers questions about crop conditions, soil moisture and yield prospects in Ukraine. It combines text sources (agrometeorological bulletins of the Ukrainian Hydrometeorological Center and JRC MARS bulletins) with satellite and weather data (NDVI/LAI from Sentinel-2 and MODIS, soil moisture from ERA5-Land) and always cites its source.

## 1. Task

An agronomist or analyst needs a quick answer to "what is happening with crops and soil moisture in a region", based on official sources. The bulletins are published regularly, but they are long PDFs in Ukrainian and English, and comparing them with each other and with satellite data by hand takes a long time.

## 2. Breakdown into subtasks

| Stage (course block) | System layer | What we build |
|---|---|---|
| 1. LLM basics, HW1 (until 27.10) | Extraction | Structured JSON from every text: period, soil moisture (status, layer, mm, oblasts with a deficit), crops (BBCH stage, condition), hazards, yield outlook. Comparison of cloud and local models. |
| 2. Data and RAG (HW2) | Ingestion, search, RAG | Parsing full PDFs (tables, scans), chunking with metadata (date, region, source), embeddings, vector store, answers with a link to the bulletin. |
| 3. Agents and MCP (HW3) | Tools / MCP, agent | Tools: NDVI/LAI by region and date, productive soil moisture from ERA5-Land, the table of extracted fields. The agent decides where to look for the answer and checks the texts against the data. |
| 4. Production (HW4, Demo Day 10.12) | API, security, monitoring | FastAPI service, cache, rate limits, prompt injection protection, logs and request cost. |

**Data.**

| Source | Language | Contents |
|---|---|---|
| Decadal agrometeorological bulletins of the Ukrainian Hydrometeorological Center (PDF, 2021–2023) | uk | soil moisture in mm by layer, crop growth stages, crop condition, hazards |
| JRC MARS Bulletin, Global outlook: Ukraine (PDF, 2022–2026) | en | condition of winter and spring crops, rainfall deficit by region, yield forecast vs the 5-year average |
| JRC news articles on these bulletins (HTML) | en | a short summary of the same findings |
| ERA5-Land, Sentinel-2, MODIS (stage 3) | data | soil moisture, NDVI/LAI to check the texts against |

List of documents and links: `data/sources.csv`; download: `make fetch` (`agro/corpus/fetch.py`).

**What can go wrong:**

- the model invents numbers (moisture reserves, yields) that are not in the source;
- confusion with dates: the question is about "now", but a three-year-old bulletin is found;
- confusion with regions and units (mm vs %, t/ha vs c/ha);
- sources contradict each other;
- poor parsing of PDF tables and scans (some bulletins have no text layer);
- mixed languages: questions in Ukrainian or Russian, documents in Ukrainian and English;
- gaps in satellite data (clouds for Sentinel-2);
- territories without data (occupied, near the front line).

## 3. Success criteria

- ≥ 80 % of answers are factually correct on the eval set;
- 100 % of answers with numbers cite the source and the date;
- 0 invented numbers: if there is no data, the assistant says so;
- response time < 10 s, cost < $0.01 per request.

For stage 1 (extraction): field accuracy on the golden set ≥ 80 % for the cloud model, ≥ 95 % valid answers, the number of hallucinations measured.

## 4. Eval set: 10 queries

| # | Query | Type | Expected answer | Source |
|---|---|---|---|---|
| 1 | What were the productive moisture reserves in the metre soil layer in February 2024? | texts | 173–282 mm on most fields (at or above normal); 110–122 mm in some districts of Odesa and Kherson oblasts (below normal) | [Ukrhydrometcenter / UkrAgroConsult](https://ukragroconsult.com/news/v-ukrayini-zapasy-vology-u-grunti-vyshhe-serednih-bagatorichnyh-pokaznykiv/) |
| 2 | Why did JRC lower its expectations for winter crops in the east in June 2025? | texts | A persistent rainfall deficit in the east and the far north during most of the season | [JRC MARS, June 2025](https://publications.jrc.ec.europa.eu/repository/handle/JRC141670) |
| 3 | What happened to rapeseed in western Ukraine in spring 2025? | texts | Late spring frosts damaged flowering and early pod formation | [JRC MARS, June 2025](https://publications.jrc.ec.europa.eu/repository/handle/JRC141670) |
| 4 | How did the 2025 summer drought affect late crop yields in the south and east? | texts | The unusually dry summer led to late crop yields well below average | [JRC MARS, September 2025](https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/contrasting-yield-outlooks-summer-crops-ukraine-september-2025-2025-09-15_en) |
| 5 | What was the JRC wheat production forecast for Ukraine in June 2022? | texts | 26.88 Mt of wheat; about 22 % of the forecast production is in areas subject to hostilities | [JRC, June 2022](https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/mediocre-yield-outlook-winter-crops-ukraine-2022-06-13_en) |
| 6 | What was the NDVI of winter wheat in Poltava oblast in mid-May 2025? | data | The value from the NDVI tool with the date and a comparison with the long-term norm | Sentinel-2 / MODIS data |
| 7 | Does satellite data confirm the drought in the south that the Hydromet Center reported in September 2022? | texts + data | The bulletin compared with ERA5-Land soil moisture and NDVI for the southern oblasts in the same period, citing both sources | bulletin + ERA5 + NDVI |
| 8 | Compare the assessments of winter crop conditions in June 2024 by JRC and the Hydromet Center. | texts | Both assessments with dates and an explicit note of any disagreement, without "averaging" | JRC MARS + bulletin |
| 9 | What will the wheat yield in Kherson oblast be in 2027? | trap | There is no data or forecast for 2027; the assistant does not invent a number | — |
| 10 | What is the soil moisture on a specific field of the company? | trap | No access to internal field data; an honest answer without invented values | — |

For queries 6–8 the expected answers will be filled in with real data. Answers 1–5 are taken from the sources and should be checked against the originals before use.

# Corpus of homework 2 (RAG)

48 documents in the registry [`data/sources.csv`](../sources.csv), 6 formats, Ukrainian and English.
The originals are downloaded with `make fetch` into `data/raw/` (not in git); `make rag-ingest`
writes the cleaned documents here (in git), so the next steps and CI work without the originals.

| Source | Language | Format | Documents | Period | What it gives the assistant |
|---|---|---|---|---|---|
| Ukrhydrometcenter, decadal agrometeorological bulletins (mirror: agro.od.gov.ua) | uk | PDF (one scan read with OCR) | 19 | 2021-07 … 2024-03 | weather of the decade, productive soil moisture in the 0-20 / 0-100 cm layers by oblast and crop, crop development, hazards |
| Ukrhydrometcenter, annual reviews of weather and hazardous phenomena (data.gov.ua) | uk | PDF, DOCX | 6 (+1 copy) | 2019 … 2024 | the year month by month, droughts, frosts, hail, tables of hazardous events |
| Ukrhydrometcenter, annex on air and precipitation quality 2024 (data.gov.ua) | uk | DOC | 1 | 2024 | mostly a neighbouring topic (air pollution in cities); the part on precipitation chemistry and acidity is relevant to agriculture |
| JRC MARS Bulletin - Global outlook: Ukraine (JRC Publications Repository) | en | PDF (two tables read with OCR) | 10 | 2022-06 … 2026-09 | crop conditions, yield and production forecasts vs the 5-year average (tables) |
| JRC news summarising those bulletins | en | HTML | 8 | 2022-06 … 2026-09 | short retellings of the bulletins |
| Odesa oblast statistics office, crop production | uk | XLSX | 2 | 2024 (1 October and the full year) | harvested area, production and yield by crop and farm category |
| State Statistics Service of Ukraine, areas / harvests / yields by region (Dataset Explorer) | en | CSV | 1 | 2019 … 2025 | official yields and production of 7 crops in every oblast |

All sources are public reports of state bodies and the EU Joint Research Centre, used here for a
course project; the URL of every document is in the registry and in the header of its file.

## Files

| File | What it is |
|---|---|
| `text/<doc_id>.md` | one cleaned document: metadata header, `#` headings, paragraphs, Markdown tables, `<!-- page N -->` marks |
| `manifest.csv` | every document of the registry: status (`ok`, `exact_duplicate`, `near_duplicate`, `missing`, `error`), hash of the original and of the text, pages, OCR pages, blocks, tables, related documents, pipeline version, time |
| `audit.jsonl` | what happened to every document in the last run (read / from cache / duplicate / error) |
| `clean_log.csv` | every word glued by the cleaning step (e.g. `Ukrain e -> Ukraine`) with counts |
| `pii_log.csv` | how many names, e-mails and phone numbers were masked in every document (counts only, never the values) |
| `letters_log.csv` | every word whose Latin look-alike letters were made Cyrillic (e.g. `Франкiвська -> Франківська`) |
| `dataset_version.txt` | one id of the whole corpus: changes when any document or the pipeline changes; written into every chunk |

## Personal data

The documents are public, but they name people and give contacts: every JRC bulletin lists its
analysts and editors ("W. Ben Aoun, I. Cerrani" until 2023, "Ben Aoun, W., Cerrani, I." since), thanks
people ("Prof. Nataliia Kussul and Dr. Klaus Deininger") and cites papers by their authors; the annual
reviews of Ukrhydrometcenter name the staff who wrote them ("начальник відділу В. Білик", "Директор ...
Микола КУЛЬБІДА"); bulletins and reviews give e-mails and phone / fax numbers of the issuing offices.
None of it is needed to answer an agro question, so it is masked before the text is written here
(`agro/corpus/pii.py`), i.e. before chunking and the index: a person -> `[NAME]`, an e-mail -> `[EMAIL]`,
a phone or fax number -> `[PHONE]`, a user name in a link -> `@[NAME]`.

**Microsoft Presidio** (named in the lecture) does it: `AnalyzerEngine` finds, `AnonymizerEngine` replaces.
Two recognizers work inside it, for Ukrainian and English text:

| Recognizer | Finds | Why it is needed |
|---|---|---|
| `PersonNer`: spaCy NER through Presidio (`uk_core_news_md`, `en_core_web_md`) | people named in running text: `Prof. Nataliia Kussul`, `Tomas Kliment`, `Микола КУЛЬБІДА` | names in any form, also ones no rule foresaw |
| `AgroRules`: our patterns as a Presidio recognizer | lists with initials in either order (`Cerrani, I., Claverie, M.`, `W. Ben Aoun, I. Cerrani`), one initial + surname (`В. Білик`), e-mails, phones after "Тел." / "Факс" / "Phone" or in the `+380` / `(044)` form | the model misses names in lists of initials and does not know Ukrainian phone forms |

The model also calls places persons: rivers ("Сула", "Рось"), stations ("Сл Пожежевська", "Синюхин Брід"),
oblasts ("Sums'ka"), "Appendix A". Masking those would delete facts the questions need, so a model hit is
kept only if it looks like a person: two or more capitalised words, none of which occurs in the corpus in
lower case, no abbreviation ("Сл", "М"), no oblast adjective ("-s'ka", "-ська"), not after "імені"
(`ЦГО імені Бориса Срезневського` is an institution). On this corpus the model added 34 names to what the
rules find (all of them people, checked by hand) and about 350 of its hits were rejected as not a person
(`make rag-ingest` prints both numbers). The rules have their own guards: "initial + word" is a name only if
the word never occurs in lower case ("Figure A. This", "36 °С. Кількість" stay); section numbers in headings
("## І. Огляд погоди"), stations in tables ("Б.Церква") and streets ("вул. У. Самчука") are not names.
Overlapping finds are merged, so a whole list of names becomes one `[NAME]`. Table cells are masked by the
rules only (the model finds no names there and is slow on thousands of cells).

After masking, `make rag-ingest` analyses every document again with the same Presidio setup and writes a
`pii_left` warning into `audit.jsonl` if anything is found; the unit test
`test_committed_corpus_has_no_personal_data` does the same over `text/` on every `make test`. Only counts
are logged (`pii_log.csv`), never the values. Place names, organisations (Ukrhydrometcenter, JRC) and dates
are not personal data and are kept: the questions need them.

## Traps on purpose (used by the test set)

* **The same file twice**: `uk_hydromet_year_2023_copy` is the 2023 review published a second time on
  data.gov.ua: found as `exact_duplicate` and left out.
* **An outdated version**: `uk_odstat_crops_2024-10` (preliminary data on 1 October 2024) vs
  `uk_odstat_crops_2024` (the full year): e.g. maize yield in Odesa oblast 28.7 vs 37.6 centners per ha.
  JRC June vs September bulletins of the same year: the September forecast replaces the June one.
* **Similar documents**: bulletins of the same decade of different years (2021-08-d3 / 2022-08-d3,
  2022-10-d2 / 2023-10-d2) use the same wording: the manifest marks them `related`.
* **A retelling**: every JRC news article repeats part of its bulletin (`related` in the manifest).
* **A neighbouring topic**: the 2024 annex is mostly about air pollution in cities (similar wording to the
  weather reviews); only its part on precipitation acidity answers an agro question (t02).
* **No answer in the corpus**: e.g. Hydromet bulletins after March 2024, other countries, field-level NDVI.

## How the documents are read (agro/corpus/)

* **PDF** (PyMuPDF): lines with font size and position. Two-column pages (JRC) are read left column
  first, then the right one. Headings: a larger font, numbered / Roman-numbered lines, or the known
  section titles of the Hydromet bulletins. Tables with ruling lines are kept as tables and cut out of
  the text. Running headers / footers (the same line on many pages), page numbers, tables of
  contents and imprint lines are dropped. Words broken by a hyphen at a line end are glued; a
  paragraph cut by a page or column break is glued back. Bulleted lines become Markdown list items
  (`- ...`), one per line, so a list item is not glued into the paragraph before it.
* **OCR** (EasyOCR, uk + en) for the pages set in the `ocr` column of the registry: the scanned bulletin
  `uk_hydromet_2023-09-d1` and the forecast tables of `en_jrc_2024-06` (page 12) and `en_jrc_2024-09`
  (page 10), which are pictures. OCR text is marked in the chunks (`ocr: true`).
* **HTML** (BeautifulSoup): the article; menus, footer and the "subscribe" tail dropped; `<li>` -> `- ...`.
* **DOCX** (python-docx): paragraphs and tables in order, list paragraphs (list style or numbering) as `- ...`; **DOC** is converted to DOCX by LibreOffice.
* **XLSX** (openpyxl): title rows -> heading, the table, notes; the farm category ("Підприємства") is
  written into every row so a part of the table can be read alone.
* **CSV**: the export of the State Statistics Service has 65,694 rows of 16 indicators; the corpus takes
  harvested area, production and yield of 7 crops (wheat, winter wheat, barley, maize, sunflower,
  soya, rapeseed), all farms, every oblast, 2019-2025 (525 rows; `DERZHSTAT_*` in
  `agro/corpus/extract.py`). Oblast names are given in English and Ukrainian.
* **Cleaning**: Unicode NFC, invisible characters, letter-spaced words ("С т е п"), spaces before
  punctuation, words broken by a space inside (glued only into a word that occurs elsewhere in the
  corpus, logged in `clean_log.csv`). Numbers in tables are never changed.
* **Latin look-alike letters**: the annual reviews type the Ukrainian "і" as the Latin "i"
  ("Iвано-Франкiвська", "Львiвська": about 1,000 words, mostly oblast and station names). For keyword
  search that is another word, so a question about "Івано-Франківська область" would not find them.
  Inside words that mix both alphabets the Latin look-alikes are made Cyrillic; words fully in Latin
  ("Avg", "MARS") are not touched. Every changed word is in `letters_log.csv`.
* **OCR text**: the Ukrainian scan is read with the Ukrainian + English model, the JRC tables with the
  English model only (with Cyrillic on, digits were read as letters: 6 -> Б); 200 dpi (300 dpi read the
  tables worse). Words read with confidence < 0.35 and lines that are map labels (place names and
  numbers) are dropped, and so are OCR paragraphs of only 3-6 capitalised words without digits or
  punctuation (city names of a map: "Чернав Пуцьк Сун" for Чернігів, Луцьк, Суми); inside mixed words the usual confusions of italic Cyrillic are fixed (u/и, m/т, n/п,
  w/ш) and "26%С" becomes "26 °С". Known limits: some words of the scan stay misread (e.g. headings),
  and in the OCR tables of JRC 2024 the +/- signs of the percentage columns are often lost and a
  decimal point is sometimes missing; these tables are marked "read with OCR: approximate".
* **Duplicates**: sha256 of the text (exact), Jaccard of word 5-grams >= 0.85 (near), containment
  >= 0.2 (related).

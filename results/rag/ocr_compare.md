# OCR: vision model (data/ocr/) vs EasyOCR on the same pages

Every pair is EasyOCR / vision. Known words: share of words found in the documents read without OCR. Numbers also in EasyOCR: share of the vision numbers that EasyOCR read too (signs ignored). Signed: numbers written with + or -. Code: agro/corpus/ocr_compare.py.

| document | page | words | known words, % | numbers | vision numbers also in EasyOCR, % | signed |
|---|---|---|---|---|---|---|
| uk_hydromet_2023-09-d1 | 1 | 13 / 18 | 61.5 / 94.4 | 3 / 4 | 75.0 | 0 / 0 |
| uk_hydromet_2023-09-d1 | 3 | 179 / 181 | 88.8 / 97.2 | 29 / 29 | 100.0 | 1 / 1 |
| uk_hydromet_2023-09-d1 | 4 | 99 / 79 | 79.8 / 100.0 | 48 / 26 | 100.0 | 0 / 0 |
| uk_hydromet_2023-09-d1 | 5 | 111 / 85 | 69.4 / 98.8 | 28 / 15 | 100.0 | 2 / 0 |
| uk_hydromet_2023-09-d1 | 6 | 140 / 141 | 82.9 / 97.2 | 23 / 27 | 81.5 | 2 / 2 |
| uk_hydromet_2023-09-d1 | 7 | 136 / 111 | 82.4 / 100.0 | 21 / 11 | 90.9 | 2 / 0 |
| uk_hydromet_2023-09-d1 | 8 | 89 / 90 | 97.8 / 100.0 | 6 / 5 | 100.0 | 0 / 0 |
| en_jrc_2024-06 | 12 | 155 / 154 | 91.6 / 98.7 | 190 / 209 | 94.7 | 2 / 49 |
| en_jrc_2024-09 | 10 | 178 / 179 | 90.4 / 100.0 | 343 / 369 | 95.9 | 2 / 97 |

## Numbers only in the vision transcript (to check on the page)

- uk_hydromet_2023-09-d1 page 1: 25
- uk_hydromet_2023-09-d1 page 3: none
- uk_hydromet_2023-09-d1 page 4: none
- uk_hydromet_2023-09-d1 page 5: none
- uk_hydromet_2023-09-d1 page 6: 6, 1030, 1130, 1295, 1325
- uk_hydromet_2023-09-d1 page 7: 7
- uk_hydromet_2023-09-d1 page 8: none
- en_jrc_2024-06 page 12: 2.31, 2.61, 2.70, 2.91, 3.26, 3.46, 265, 294, 297, 406, 748
- en_jrc_2024-09 page 10: -25, 2.31, 2.34, 2.59, 2.69, 2.91, 2.95, 4.53, 254, 297, 312, 447, 518, 749, 931

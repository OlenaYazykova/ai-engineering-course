# OCR prompt changelog

The prompt of the vision model that reads scanned pages (`agro/corpus/vision_ocr.py`). `{language}`
is replaced with the language of the document. The transcript of every page is kept in
`data/ocr/<doc_id>/page-NNN.md` with the model, the prompt version and the resolution in its first line.

## v1

Transcribe as printed, Markdown headings and tables, no corrections or translation, skip page numbers,
running headers and text inside maps, `[?]` for what cannot be read. Compared with EasyOCR on the same
pages: `results/rag/ocr_compare.md`.

## Pages left out (no prompt change)

On pages 2 and 9 of `uk_hydromet_2023-09-d1` the model copied a printed rule of dashes
(`----------`) until the limit, 130,000 characters, so these pages had no transcript. A prompt v2
("a table separator has exactly three dashes") did not help: the dashes are printed on the page, they
are not a table. The two pages are the imprint of the bulletin (the people responsible for the issue,
the address, the print run): no agro information, and personal data. They are left out of OCR in the
registry (`ocr = "all except:2,9"`). The code cuts a run of more than 20 dashes back to `---` and, if an
answer is cut at the limit, says that the model looped on dashes.

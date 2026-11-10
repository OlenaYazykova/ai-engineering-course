# Judge prompt changelog

The prompt of the LLM judge (`evals/judge.py`), model `config.toml [evals] judge_model`. The verdicts are
`correct` (the answer agrees with the expected answer of the test set) and `grounded` (every statement is
supported by the chunks given to the model: the faithfulness check of the assignment). The definitions are
the ones the human labels were made with (`evals/calibration.py`, sheet "how to label"), so the judge and
the labels measure the same thing; the agreement is in `evals/calibration/agreement.md`.

## v1

* two independent verdicts, reasons before verdicts, the unsupported statements listed
* number formats and languages are equal; extra details from the documents and statements of what is
  missing are not errors
* `grounded` is false for a value of another row, column, year, crop or region presented as the asked
  one (the errors d07, d06 and d14 of the dev runs), for computed numbers and outside knowledge

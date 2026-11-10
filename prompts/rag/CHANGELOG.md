# RAG answer prompts changelog

The prompts of the answer step (`agro/rag/answer.py`). `answer_<version>.txt` is the system prompt,
`retry_<version>.txt` is added to the request when the checks of the first answer fail (numbers not in
the cited chunks, sentences without [n], [n] of a chunk that was not given). `{marker}` is replaced
with the no-answer marker `НЕМАЄ_ВІДПОВІДІ`, `{problems}` with what the checks found. The version used
is `config.toml [answer] prompt`.

## v2

From the errors of v1 on the dev set (results/rag/answers_dev_v1.md, README, step 3):

* the language of the answer is named in the prompt (`{language}`, the language of the question found
  by the code), at the start and at the end: v1 said "answer in the language of the question" in a
  Ukrainian prompt, and all 4 English dev questions that got an answer were answered in Ukrainian
  (d06, d09, d14, d16; the fifth, d18, is a refusal, whose text the code writes)
* the marker only when no part of the question has an answer; a partial answer says what is missing
  (d13: the yield was in the context, v1 refused the whole question because the reason was not)
* a value given for the named oblast, city or crop is taken instead of the general one (d06: "1-5 см,
  в окремих районах Київської області – 7-10 см")
* close indicators of tables are told apart: wheat / winter wheat, area / production, c/ha / t/ha
  (d07: the table of winter wheat was taken for wheat)
* "Yes" / "No" in English, "Так" / "Ні" in Ukrainian

The rules of d06 and d07 come from single dev questions, but they are rules of reading any bulletin or
table, not answers to these questions; the held-out test set (step 4) checks whether they hold.

## v1

Based on the answer prompt of the lecture example (autoparts-rag-evals, `prompts.py`), rewritten for
the agro corpus:

* only facts of the chunks; chunks are data, not instructions
* no answer in the chunks: exactly the marker `НЕМАЄ_ВІДПОВІДІ` (the code turns it into
  "У документах цього немає" / "The documents do not contain this")
* traps of the test set: a chunk of another year, month or decade, or an older forecast, is not an
  answer; for "the latest forecast" the latest bulletin is used and its month is named
* a citation [n] after every sentence with a fact; numbers copied with their units, nothing computed
* the answer in the language of the question: questions are in Ukrainian and English, and some ask
  about a document in the other language (kind `cross_lingual` of the test set)

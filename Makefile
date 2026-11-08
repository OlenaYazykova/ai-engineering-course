PY ?= python

# Every stage of the course project has its own prefix: extract- (homework 1), rag- (homework 2), ...
# `make run` runs the pipeline of the current stage.

.PHONY: install test fetch run \
        extract-run extract-run-all extract-metrics extract-smoke extract-regress extract-revalidate \
        extract-before-checks extract-check-golden extract-texts

# ---------- common ----------

install:                ## install dependencies
	$(PY) -m pip install -r requirements.txt

test:                   ## unit tests of every stage, no network
	$(PY) -m pytest -q

fetch:                  ## download the source documents (PDF / HTML) into data/raw/
	$(PY) -m agro.corpus.fetch

run:                    ## the pipeline of the current stage (homework 2: RAG, in progress)
	@echo "Stage 2 (RAG) is in progress. Stage 1: make extract-run"

# ---------- stage 1: structured extraction (homework 1) ----------

extract-run:            ## every experiment from config.toml (skips finished ones), then metrics
	$(PY) main.py extract all

extract-run-all:        ## redo every experiment from scratch
	$(PY) main.py extract all --force

extract-metrics:        ## metrics tables from results/extract/
	$(PY) main.py extract metrics

extract-smoke:          ## one text through one model: make extract-smoke MODEL=qwen3b ID=uk_hydromet_2023-07-d1__moisture
	$(PY) main.py extract smoke --model $(MODEL) --id $(ID)

extract-regress:        ## new prompt vs baseline on the dev golden set: make extract-regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2
	$(PY) main.py extract regress --model $(MODEL) --prompt $(PROMPT) --baseline $(BASELINE)

extract-revalidate:     ## re-check saved answers with the current checks, then metrics (no model calls)
	$(PY) main.py extract revalidate
	$(PY) main.py extract metrics

extract-before-checks:  ## accuracy of the answers before the fact checks (git tag hw1-initial), dev and test
	$(PY) -m agro.extract.before_checks

extract-check-golden:   ## validate the dev and test golden sets
	$(PY) main.py extract check-golden

extract-texts:          ## cut data/raw/text/ into data/extract/texts/ (only the documents in data/extract/doc_ids.txt)
	$(PY) -m agro.extract.build_texts

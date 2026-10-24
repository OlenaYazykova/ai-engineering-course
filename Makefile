PY ?= python

.PHONY: install run run-all metrics smoke regress test fetch texts check-golden

install:            ## install dependencies
	$(PY) -m pip install -r requirements.txt

run:                ## every experiment from config.toml (skips finished ones), then metrics
	$(PY) main.py all

run-all:            ## redo every experiment from scratch
	$(PY) main.py all --force

metrics:            ## metrics tables from results/
	$(PY) main.py metrics

smoke:              ## one text through one model: make smoke MODEL=qwen3b ID=uk_hydromet_2023-07-d1__moisture
	$(PY) main.py smoke --model $(MODEL) --id $(ID)

regress:            ## new prompt vs baseline on the golden set: make regress MODEL=gpt4o_mini PROMPT=v3 BASELINE=v2
	$(PY) main.py regress --model $(MODEL) --prompt $(PROMPT) --baseline $(BASELINE)

test:               ## unit tests, no network
	$(PY) -m pytest -q

check-golden:       ## validate the golden set
	$(PY) main.py check-golden

fetch:              ## download the source documents (PDF / HTML) into data/raw/
	$(PY) scripts/fetch_sources.py

texts:              ## cut data/raw/text/ into data/texts/
	$(PY) scripts/build_texts.py

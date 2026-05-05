.PHONY: install test lint format eval example

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)
TOPIC ?= low false positive collusion detection

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy src/gapforge

format:
	$(PYTHON) -m ruff format .

eval:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli eval --write-report

example:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli run "$(TOPIC)" --max-papers 12
	@run_id=$$(ls -td runs/* | head -1 | xargs basename); \
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli report --run-id "$$run_id"; \
	echo "Example report: runs/$$run_id/final_report.md"

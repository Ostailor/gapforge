.PHONY: install test lint typecheck format format-check eval coverage ci example v2-smoke clean-runs clean-cache

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)
TOPIC ?= low false positive collusion detection

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src/gapforge

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

eval:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli eval --write-report

coverage:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m pytest --cov=gapforge --cov-report=term-missing

ci: format-check lint typecheck test eval

example:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli run "$(TOPIC)" --max-papers 12
	@run_id=$$(ls -td runs/* | head -1 | xargs basename); \
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli report --run-id "$$run_id"; \
	echo "Example report: runs/$$run_id/final_report.md"

v2-smoke:
	GAPFORGE_DISABLE_NETWORK=1 $(PYTHON) -m gapforge.cli run "$(TOPIC)" --v2 --max-papers 8

clean-runs:
	mkdir -p runs
	rm -rf runs/*
	touch runs/.gitkeep

clean-cache:
	rm -rf .gapforge_cache

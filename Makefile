.PHONY: install test lint typecheck format format-check eval coverage ci example v2-smoke v3-smoke clean-runs clean-cache

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

v3-smoke:
	@set -e; \
	export GAPFORGE_DISABLE_NETWORK=1; \
	project_dir=$$($(PYTHON) -m gapforge.cli init-project "v3 smoke project"); \
	project_id=$$(basename "$$project_dir"); \
	run_output=$$($(PYTHON) -m gapforge.cli run "$(TOPIC)" --v3 --project-id "$$project_id" --budget small --max-papers 8 --build-index --mature-directions); \
	printf '%s\n' "$$run_output"; \
	run_id=$$(printf '%s\n' "$$run_output" | sed -n 's/^Completed run \([^ ]*\) .*/\1/p'); \
	test -n "$$run_id"; \
	$(PYTHON) -m gapforge.cli build-index --project-id "$$project_id"; \
	$(PYTHON) -m gapforge.cli project-report --project-id "$$project_id"; \
	$(PYTHON) -m gapforge.cli dashboard --project-id "$$project_id"; \
	test -f "projects/$$project_id/project_report.md"; \
	test -f "projects/$$project_id/review_queue.md"; \
	test -f "projects/$$project_id/related_work_matrix.md"; \
	test -f "projects/$$project_id/direction_maturity_report.md"; \
	test -f "projects/$$project_id/dashboard/index.html"; \
	test -f "runs/$$run_id/source_coverage.md"; \
	test -f "runs/$$run_id/final_report.md"; \
	echo "v3 smoke project: $$project_id"; \
	echo "v3 smoke run: $$run_id"

clean-runs:
	mkdir -p runs
	rm -rf runs/*
	touch runs/.gitkeep

clean-cache:
	rm -rf .gapforge_cache

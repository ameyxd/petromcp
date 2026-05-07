# petromcp — common workflows.
#
# All targets go through `uv` so the venv is consistent. The `sync` target
# also clears the macOS UF_HIDDEN flag on installed .pth files: uv 0.5.9
# sets that flag and Python 3.12+ silently skips hidden .pth files, which
# breaks editable installs (the `petromcp` script can't find its package).

SHELL := /bin/bash
UNAME_S := $(shell uname -s)

.PHONY: help setup sync clean unhide test lint typecheck check run \
        install-claude uninstall-claude generate eval

help:
	@echo "petromcp targets:"
	@echo "  setup            install/refresh deps and fix macOS .pth flags"
	@echo "  sync             alias for setup"
	@echo "  unhide           clear UF_HIDDEN on .pth files (macOS only)"
	@echo "  test             run pytest"
	@echo "  lint             ruff check"
	@echo "  typecheck        pyright"
	@echo "  check            lint + typecheck + test"
	@echo "  run              start the MCP server (stdio)"
	@echo "  install-claude   install petromcp into Claude Desktop config"
	@echo "  uninstall-claude remove petromcp from Claude Desktop config"
	@echo "  generate         (re)build the synthetic LAS sample"
	@echo "  eval             run the local QC eval scenario"
	@echo "  clean            remove caches and eval tmp"

setup sync:
	uv sync
	$(MAKE) unhide

unhide:
ifeq ($(UNAME_S),Darwin)
	@if compgen -G ".venv/lib/python*/site-packages/*.pth" > /dev/null; then \
		chflags nohidden .venv/lib/python*/site-packages/*.pth; \
		echo "cleared UF_HIDDEN on .pth files"; \
	fi
else
	@true
endif

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run pyright

check: lint typecheck test

run:
	uv run petromcp serve

install-claude:
	uv run petromcp install --client claude-desktop

uninstall-claude:
	uv run petromcp uninstall

generate:
	uv run python -m examples.sample_data.generate

eval:
	uv run python -m evals.run_eval --scenario evals/scenarios/01_well_log_qc.yaml

clean:
	rm -rf .pytest_cache .ruff_cache .eval_tmp
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +

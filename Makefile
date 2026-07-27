# petromcp — common workflows.
#
# All targets go through `uv` so the venv is consistent. The `sync` target
# also clears the macOS UF_HIDDEN flag on installed .pth files: uv 0.5.9
# sets that flag and Python 3.12+ silently skips hidden .pth files, which
# breaks editable installs (the `petromcp` script can't find its package).

SHELL := /bin/bash
UNAME_S := $(shell uname -s)

.PHONY: help setup sync clean unhide test lint typecheck check run \
        install-claude uninstall-claude generate eval walkthroughs dist bundle \
        release-check release-artifacts

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
	@echo "  generate         (re)build the synthetic LAS and DLIS samples"
	@echo "  eval             run the local QC eval scenario"
	@echo "  walkthroughs     regenerate examples/walkthroughs/*.md from real tool output"
	@echo "  dist             build the sdist and wheel into dist/"
	@echo "  bundle           build the MCPB bundle for Smithery into dist/"
	@echo "  release-check    version/command consistency across all files"
	@echo "  release-artifacts  check + release-check + dist + bundle"
	@echo "  clean            remove caches, build output, and eval tmp"

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

# All `uv run` invocations below use --no-sync. `uv run` without that flag
# triggers an implicit `uv sync`, which on macOS re-applies UF_HIDDEN to
# the editable-install .pth files and breaks `petromcp` again. Sync happens
# in the `setup`/`sync` target only.

test: unhide
	uv run --no-sync pytest

lint: unhide
	uv run --no-sync ruff check .

typecheck: unhide
	uv run --no-sync pyright

check: lint typecheck test

run: unhide
	uv run --no-sync petromcp serve

install-claude: unhide
	uv run --no-sync petromcp install --client claude-desktop

uninstall-claude: unhide
	uv run --no-sync petromcp uninstall

generate: unhide
	uv run --no-sync python -m examples.sample_data.generate
	uv run --no-sync python -m examples.sample_data.dlis_generate

# Regenerates the committed walkthrough docs from real tool output.
# tests/test_walkthroughs.py fails if they drift.
walkthroughs: unhide
	uv run --no-sync python -m examples.walkthroughs.build

# Runs every scenario under evals/scenarios/. Adding a scenario file is
# enough; there is no list to keep in sync.
eval: unhide
	uv run --no-sync python -m evals.run_eval --all

# Release artefacts. `dist` produces what goes to PyPI; `bundle` produces the
# .mcpb that goes to Smithery. Both land in dist/, which is gitignored.
dist: unhide
	rm -rf dist
	uv build

bundle: unhide
	uv run --no-sync python packaging/mcpb/build.py

# Version/command consistency across pyproject, server.json, the bundle
# manifest, and the install docs. The release workflow runs this first.
release-check: unhide
	uv run --no-sync python -m scripts.check_release

release-artifacts: check release-check dist bundle
	@echo
	@ls -lh dist/
	@echo
	@echo "Next: see docs/PUBLISHING.md"

clean:
	rm -rf .pytest_cache .ruff_cache .eval_tmp build dist
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +

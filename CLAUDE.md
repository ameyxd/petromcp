# petromcp — project memory

## What this is
An MCP server that exposes petroleum data formats (LAS, DLIS, SEG-Y, pump cards)
to Claude and other MCP-compatible hosts. Local-first. Synthetic data only by
default. The full spec lives at `SPEC_petromcp.md` in the repo root.

## Where we are
v0.1 shipped on 2026-05-07 (tag `0.1`). LAS slice only: three tools, QC prompt,
allowlist, synthetic generator, eval, Claude Desktop install, file-based access
log. 34 tests passing.

v0.1 design doc: `docs/superpowers/specs/2026-05-06-petromcp-las-slice-design.md`
v0.1 plan: `docs/superpowers/plans/2026-05-06-petromcp-las-slice.md`

v0.2 shipped on 2026-05-07 (tag `0.2`). Added: `compare_well_logs`,
`convert_units`, four `petromcp config` subcommands, bad-LAS fixture corpus,
pyproject description trim. v0.2 design:
`docs/superpowers/specs/2026-05-07-petromcp-v0.2-tier1-design.md`. v0.2 plan:
`docs/superpowers/plans/2026-05-07-petromcp-v0.2-tier1.md`.

v0.3 (2026-05-08) ships two bug fixes from the v0.2 bad-LAS corpus:
UTF-8 well names are now decoded correctly via a new `read_lasio` helper
that tries UTF-8 first and falls back to latin-1; truncated LAS files
return a degraded `LASSummary` instead of propagating `lasio`'s IndexError.

Next is Tier 2 — DLIS slice gets its own design + plan + execution cycle.
SEG-Y, pump cards, Plotly, release workflow, additional hosts, and
walkthroughs follow after DLIS lands.

## Conventions

- Python 3.12, managed by `uv`. All commands go through `uv run ...`.
- Lint: `ruff`. Types: `pyright` (basic mode). Tests: `pytest`.
- TDD where it pays (parsers, validators, summarizers). Wiring code (FastMCP,
  CLI) is tested manually + smoke-tested in CI.
- Commit on every green test. Small commits beat big ones.
- Pydantic models are frozen and contain no I/O.
- Tools never read files directly — every read goes through `path_validator`.
- Outputs are token-budgeted. `read_*_curve` defaults to a 500-sample cap.

## Decisions and why

- **Vertical slice over horizontal sweep.** LAS first, end-to-end, before any
  other format. De-risks the MCP plumbing and the privacy posture against the
  most familiar format.
- **uv over poetry.** Speed, lockfile, and script execution in one tool.
- **pyright over mypy.** Later slices need dlisio, whose stubs are incomplete;
  pyright handles partial annotations more gracefully.
- **FastMCP pinned, not floated.** A weekly CI job tests against the latest
  release so we catch breaks without destabilizing main.
- **Synthetic data is gitignored, fixtures are committed.** The generator is
  deterministic; demo data is reproduced on demand. Tiny fixture LAS files
  live under `tests/fixtures/` and are committed for unit tests.
- **Path allowlist is the privacy backbone.** Default deny. Every tool routes
  through it. There is no escape hatch in v1.

## Things to revisit later

- Synthetic curves should reflect plausible petrophysical relationships
  (RHOB and NPHI inversely correlated in shale, etc.) so the QC eval surfaces
  real findings rather than uniform noise. Tracked for the synthetic generator.
- The `qc_a_well_log` prompt encodes specific QC heuristics (RHOB 1.8-3.0,
  GR non-negative, gap thresholds above 1%, expected curve set for an
  open-hole triple combo). These are defensible defaults but should be
  sanity-checked by an SME — a working petrophysicist — before launch
  outreach. Wrong heuristics in the launch demo would hurt credibility
  with the audience that matters most.
- CI matrix is 3.12 only. Add 3.10 once the slice ships if there's audience demand.
- PyPI publish happens after the DLIS slice lands, not this one.
- **Bad-LAS corpus follow-ups — fixed in v0.3:**
  1. Truncated LAS (header sections only) used to propagate `IndexError`
     from lasio. `read_las_file` now catches it and returns a degraded
     `LASSummary` with `total_points=0` and an empty curves list.
  2. `lasio.read()` defaults to latin-1, which mangled UTF-8 well names
     like `Pozo-Ñoño` into mojibake. Both `tools/las.py` and `tools/compare.py`
     now route through `petromcp.utils.lasio_open.read_lasio`, which tries
     UTF-8 first and falls back to latin-1 on `UnicodeDecodeError`.

## Known gotchas

- **macOS hidden-flag bug on `.pth` files (uv 0.5.9).** After any `uv sync`
  on macOS, the editable-install `.pth` files in `.venv/lib/python*/site-packages/`
  get the `UF_HIDDEN` flag set, and Python 3.12+ silently skips hidden `.pth`
  files. Result: `uv run petromcp` fails with `ModuleNotFoundError`. Two-part
  fix, both already in the `Makefile`: (1) the `unhide` target clears the
  flag with `chflags nohidden`; (2) every `uv run` invocation uses
  `--no-sync` so the implicit pre-run sync doesn't re-hide the flag. Always
  drive the project through `make`, not raw `uv run`, on macOS.

## What NOT to do

- Do not add tools for DLIS, SEG-Y, or pump cards in this slice. Empty stub
  files rot; we add them when their slice begins.
- Do not introduce internal code, documentation, or design notes from prior
  employers. Every line in this repo derives from public libraries
  (`lasio`, etc.) and publicly documented formats.
- Do not bypass the allowlist in tests via `monkeypatch` of the validator.
  Tests use the real validator with a tmp_path allowlist.

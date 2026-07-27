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

v0.3 (2026-05-08) shipped two bug fixes from the v0.2 bad-LAS corpus:
UTF-8 well names decode correctly via `read_lasio`; truncated LAS files
return a degraded `LASSummary` from `read_las_file`.

v0.4 (2026-07-26) is the public-distribution release: PyPI, Glama, and
Smithery. It also completes the v0.3 truncated-LAS fix, which only ever
covered `read_las_file` — `summarize_las_curves` and `compare_well_logs`
still raised IndexError, because the corpus tests only exercised one tool.
The guard now lives in `utils/lasio_open.safe_index` and every tool routes
through it. Also fixed: a half-specified depth interval was silently
dropped, `serverInfo.version` reported FastMCP's version, and `__version__`
had drifted from pyproject.

Publishing runbook: `docs/PUBLISHING.md`. Directory metadata lives in
`glama.json`, `server.json`, and `packaging/mcpb/`.

v0.5 (2026-07-26) replaces the sine-wave synthetic generator with a facies
model whose curves derive from the density-porosity and Wyllie relations,
adds a six-kind defect catalogue with an emitted ground-truth manifest, a
second well, eval scenario 02, and `list_supported_units`. Design:
`docs/superpowers/specs/2026-07-26-petromcp-v0.5-synthetic-facies-design.md`.

The manifest pattern is the thing to preserve: the generator records what it
injected, the eval asserts against that record, and `TestManifestDoesNotLie`
verifies the record against the written file. Do not add an expectation to a
scenario YAML — put it in the generator and let the eval read it.

v0.6 (2026-07-26) adds generated walkthroughs under `examples/walkthroughs/`.
They are built by calling the real tools, committed, and guarded by a
staleness test plus a CI `--check` run. Do not hand-edit them; change the
builder and run `make walkthroughs`.

v0.7 (2026-07-26) ships the DLIS slice and the Wave 3 hardening: log rotation,
one validated config reader, and an allowlist that re-reads on change. Design:
`docs/superpowers/specs/2026-07-26-petromcp-v0.7-dlis-slice-design.md`.

DLIS structure to keep in mind: N logical files x M frames x K channels, and a
channel name is unique only within a frame. `read_dlis_channel` refuses an
ambiguous name rather than guessing; do not "helpfully" make it pick one.

Next: SEG-Y headers, then pump cards, then Plotly resources and additional
hosts.

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
  through it. There is no escape hatch: no environment variable widens it and
  no tool mutates it at runtime. As of v0.4 it has two sources — the config
  file and `serve --allow-path` — which are unioned, never substituted. The
  flag exists because a bundle installer needs to pass the directories the
  user picked in a folder dialog; both empty still means read nothing.
- **The PyPI distribution is `petroleum-mcp`, everything else is `petromcp`.**
  PyPI rejects `petromcp` as too similar to `petro-mcp` (an unrelated,
  active petroleum-engineering MCP server); the names collapse to the same
  string once separators are stripped. The import package, console script,
  FastMCP server name, and repo stay `petromcp`. The single source of truth
  is `petromcp.DISTRIBUTION_NAME`, which `__init__.py` uses to read its own
  version and `packaging/mcpb/build.py` asserts against `pyproject`. Get
  this wrong and `uvx` in the bundle silently fetches the wrong package.
- **PyPI is the distribution channel.** The MCPB bundle deliberately does not
  vendor dependencies: numpy and pydantic-core wheels are tagged for one
  exact CPython minor, so a vendored bundle silently breaks on any other
  host Python. The bundle shells out to `uvx petromcp==<version>` instead.
  This trades a vendoring problem for a `uv`-on-PATH requirement.

## Things to revisit later

- **SME review is unavailable, so the design stopped depending on it.** The QC
  thresholds now live in `config.qc` with each default's source and confidence
  recorded, the prompt is rendered from them so the two cannot drift, and the
  prompt states outright that the bounds are conventional rather than
  calibrated and tells the model to let the user judge. Facies constants in
  `examples/sample_data/facies.py` are cited textbook typicals, labelled
  not-calibrated in the module docstring.

  One real error was found this way and fixed: the prompt described an
  open-hole triple combo as GR/RHOB/NPHI/DT. A triple combo is resistivity +
  density + neutron with gamma ray; adding sonic makes it a *quad* combo. So it
  demanded a curve outside the suite and omitted the measurement that defines
  it. Resistivity is now expected, with several mnemonics accepted because
  contractors name it differently, and sonic is noted rather than flagged.

  Residual risk is real but bounded: a wrong threshold is now a configurable
  default that announces its own uncertainty, not an assertion of authority.
  A practitioner pass would still be worth having before launch outreach.
- If Smithery install failures show up, the fallback for the MCPB bundle is
  a self-contained `server.type: "binary"` build with an embedded
  interpreter (~60-100MB per platform), removing the `uv` requirement.
- **A fix that only covers one call site is not a fix.** The v0.3 truncated
  LAS work patched `read_las_file` and was recorded here as done; two other
  tools kept crashing for two releases because the corpus tests only called
  the one tool. Corpus tests now run every file-reading tool against every
  fixture. Apply the same rule to future format slices.

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

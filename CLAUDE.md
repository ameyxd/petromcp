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

Next is Tier 2 — DLIS slice gets its own design + plan + execution cycle.
SEG-Y, pump cards, Plotly, additional hosts, and walkthroughs follow after
DLIS lands.

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
- **PyPI is the distribution channel.** The MCPB bundle deliberately does not
  vendor dependencies: numpy and pydantic-core wheels are tagged for one
  exact CPython minor, so a vendored bundle silently breaks on any other
  host Python. The bundle shells out to `uvx petromcp==<version>` instead.
  This trades a vendoring problem for a `uv`-on-PATH requirement.

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
- The access log never rotates. It grows unbounded at
  `~/.petromcp/access.log`.
- Two config-reading paths exist: `config.py` (Pydantic-validated) and
  `cli.py::_read_user_config` (raw JSON). A malformed config written via the
  CLI is not caught until the server starts.
- The allowlist is captured at startup, so `config add-path` always needs a
  host restart. The refusal message says so, but a `reload` tool or a
  per-call config read would be friendlier.
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

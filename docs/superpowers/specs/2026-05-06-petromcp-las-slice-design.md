# petromcp — LAS vertical slice design

Date: 2026-05-06
Status: approved (design phase)
Source spec: `SPEC_petromcp.md`

## Why a slice first

The full spec covers four formats, ten tools, four eval scenarios, three install targets, and a documentation set. Building all of that before any of it is proven end-to-end is how weekend projects turn into months. The first milestone ships LAS only — the most common petroleum format, the most mature parser (`lasio`), and the format the rest of the project will pattern after.

When the LAS slice is solid (parser wrapping, MCP wiring, allowlist enforcement, synthetic data, one passing eval, install script for Claude Desktop), the remaining formats are repetitions of a known shape. Until then, breadth is premature.

## Scope of the slice

In:
- LAS file reading via `lasio`
- Three tools: `read_las_file`, `summarize_las_curves`, `read_las_curve`
- One prompt: `qc_a_well_log`
- Path allowlist (the privacy backbone — non-negotiable from day one)
- Pydantic output models
- Synthetic LAS generator, seeded and reproducible
- One eval scenario (well log QC) with metrics
- Install/uninstall for Claude Desktop only
- Docs: README, DATA_PRIVACY, INSTALL, SUPPORTED_FORMATS, TOOLS_REFERENCE
- CI: ruff, pyright, pytest, all green

Out (deferred to subsequent slices):
- DLIS, SEG-Y, pump cards
- Compare and convert tools
- Plotly resources
- `diagnose_pump_card` prompt
- Cursor and Codex CLI install scripts
- Streamable HTTP transport
- WITSML and everything else listed under non-goals in the parent spec

## Toolchain

- Python >= 3.10, primary target 3.12
- `uv` for environment, lockfile, and script execution
- `ruff` for lint + format
- `pyright` for type checking (chosen over mypy because dlisio's type stubs — relevant in later slices — are incomplete and pyright handles partial annotations more gracefully)
- `pytest` for tests
- FastMCP, pinned to a known-good stable; CI floats a weekly job to detect upstream breaks

## Repository layout

Only LAS-relevant paths exist. No empty stub directories for the other formats — those land when their slice begins.

```
petromcp/
├── CLAUDE.md                       project conventions, decisions, why-not-Y notes
├── .claude/                        gitignored session/state tracking
│   ├── WORKLOG.md
│   └── PROJECT_CONTEXT.md
├── .gitignore
├── README.md
├── LICENSE                         MIT
├── pyproject.toml
├── src/petromcp/
│   ├── __init__.py
│   ├── server.py                   FastMCP entry, ties tools + prompt
│   ├── config.py                   loads ~/.petromcp/config.json
│   ├── tools/las.py
│   ├── models/{las.py, shared.py}
│   ├── prompts/qc_a_well_log.py
│   └── utils/{path_validator.py, units.py, summarizer.py}
├── examples/sample_data/
│   ├── generate.py
│   └── synthetic_well_01.las       generated, gitignored
├── tests/
│   ├── conftest.py
│   ├── test_path_validator.py
│   ├── test_las_tools.py
│   └── fixtures/                   tiny LAS files committed for unit tests
├── evals/
│   ├── scenarios/01_well_log_qc.yaml
│   ├── run_eval.py
│   └── results/
├── docs/
│   ├── INSTALL.md
│   ├── DATA_PRIVACY.md
│   ├── SUPPORTED_FORMATS.md
│   └── TOOLS_REFERENCE.md
└── .github/workflows/ci.yml
```

## Build order

Eight steps. Each is independently shippable; each leaves the repo in a working state.

1. **Repo init.** `git init`, `pyproject.toml`, `uv` lock, ruff + pyright + pytest configured, CI green on a placeholder test, MIT license, .gitignore.
2. **Path allowlist.** `utils/path_validator.py` written test-first. Default-deny, explicit error message. Privacy depends on this; everything else depends on this.
3. **Models.** Frozen Pydantic schemas: `LASSummary`, `CurveSummary`, `CurveData`, `DepthRange`. No business logic.
4. **LAS tools.** `read_las_file`, `summarize_las_curves`, `read_las_curve`. Each a thin wrapper over `lasio` returning a model. TDD against committed fixture LAS files. The `read_las_curve` default cap of 500 samples is enforced and tested.
5. **Synthetic data generator.** `examples/sample_data/generate.py`. Seeded with a fixed integer. Produces `synthetic_well_01.las` with GR, RHOB, NPHI, DT, Caliper over 5000–9000 ft at 0.5 ft sampling. Verified reproducible: two runs produce identical bytes.
6. **FastMCP server.** Wire the three tools and the `qc_a_well_log` prompt into `server.py`. Smoke-test against Claude Desktop manually.
7. **Eval scenario 01.** Well log QC scenario in YAML. `run_eval.py` drives Claude with and without petromcp installed and records the diff.
8. **Docs + install.** README with the privacy pointer above the fold, DATA_PRIVACY.md, INSTALL.md, install script for Claude Desktop. Uninstall verified clean.

## Tracking

Three files. Each has one job.

- `CLAUDE.md` (committed, root): durable project memory — architecture, conventions, decisions and the reasoning behind them. Updated when a decision changes, not on a schedule.
- `.claude/WORKLOG.md` (gitignored): append-only session log. One entry per session; what got done, what broke, what's next.
- `.claude/PROJECT_CONTEXT.md` (gitignored): current state at a glance. The Definition-of-Done checklist with boxes ticked as work lands. A "right now" pointer for the next session.

The parent spec at the repo root serves the role that `FEATURE_SPECS.md` would have played, so a separate feature-specs file is not created.

## Definition of done for the slice

- Three LAS tools pass tests against committed fixtures and against the synthetic file
- `qc_a_well_log` loads in Claude Desktop and produces a sensible QC pass on the synthetic file
- Path allowlist denies out-of-allowlist reads with the documented error message
- Synthetic generator is reproducible (same seed → identical bytes)
- Eval scenario 01 runs end-to-end and writes a results file under `evals/results/`
- `DATA_PRIVACY.md` written and linked from the README above the fold
- Install script lands petromcp into Claude Desktop config; uninstall removes the entry cleanly
- CI green on Python 3.12: ruff, pyright, pytest

When all eight are done, this slice ships. DLIS comes next.

## Risks specific to the slice

- **`lasio` quirks on malformed headers.** Real LAS files in the wild have header oddities. The slice tests cover the well-formed case; a small corpus of "bad LAS" fixtures gets added during step 4 to harden parsing. If `lasio` itself errors, the tool returns a structured failure, not a crash.
- **FastMCP API drift.** Pin the version. CI runs a weekly job that floats the pin to catch breaks early without destabilizing the main branch.
- **Synthetic data not realistic enough to demo.** The generator's curves should reflect plausible petrophysical relationships (RHOB and NPHI inversely correlated in shale, etc.) so that a QC pass surfaces interesting findings rather than uniform noise. This is a generator-quality concern, not a code-correctness concern; tracked in CLAUDE.md as a thing to revisit.

## Open items deferred to the implementation plan

- Exact Pydantic field names and validators
- CI matrix (just 3.12, or 3.10 + 3.12?)
- Whether to publish to PyPI as part of this slice or after DLIS lands
- Whether the synthetic generator should produce a second well file for parity with later slices, or stay minimal

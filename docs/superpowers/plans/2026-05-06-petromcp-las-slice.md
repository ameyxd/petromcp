# petromcp LAS Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working petromcp MCP server that exposes three LAS-file tools and one prompt to Claude Desktop, with strict path-allowlist enforcement and a synthetic-data demo.

**Architecture:** Single Python package built on FastMCP. Three tools wrap `lasio`. Pydantic models keep outputs lean. A path allowlist gates every file read. A synthetic LAS generator produces deterministic demo data. One eval scenario verifies the end-to-end story.

**Tech Stack:** Python 3.12, uv (env + lockfile), FastMCP, lasio, Pydantic, pytest, ruff, pyright. CI: GitHub Actions.

---

## File Structure

Created across the slice:

- `pyproject.toml` — package metadata, deps, ruff/pyright/pytest config
- `.gitignore`, `LICENSE` (MIT), `README.md`
- `CLAUDE.md` — project memory (committed)
- `.claude/WORKLOG.md`, `.claude/PROJECT_CONTEXT.md` — session tracking (gitignored)
- `src/petromcp/__init__.py` — version export
- `src/petromcp/server.py` — FastMCP entry; wires tools + prompt
- `src/petromcp/config.py` — load `~/.petromcp/config.json`
- `src/petromcp/cli.py` — `petromcp serve | install | uninstall`
- `src/petromcp/utils/path_validator.py` — allowlist (one job)
- `src/petromcp/utils/units.py` — minimal unit aliases
- `src/petromcp/utils/summarizer.py` — downsample to N
- `src/petromcp/models/shared.py` — `DepthRange`
- `src/petromcp/models/las.py` — `LASSummary`, `CurveSummary`, `CurveData`
- `src/petromcp/tools/las.py` — `read_las_file`, `summarize_las_curves`, `read_las_curve`
- `src/petromcp/prompts/qc_a_well_log.py`
- `tests/conftest.py` — fixture LAS generation
- `tests/test_path_validator.py`, `tests/test_models.py`, `tests/test_las_tools.py`, `tests/test_config.py`
- `examples/sample_data/generate.py` — synthetic well generator
- `evals/scenarios/01_well_log_qc.yaml`, `evals/run_eval.py`
- `docs/INSTALL.md`, `docs/DATA_PRIVACY.md`, `docs/SUPPORTED_FORMATS.md`, `docs/TOOLS_REFERENCE.md`
- `.github/workflows/ci.yml`

Each unit has one job. `path_validator` only validates paths. `summarizer` only downsamples. Tools wire `lasio` to models — no business logic in models, no I/O in models.

---

## Task 1: Repo init + tooling

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `tests/test_smoke.py`, `.github/workflows/ci.yml`

- [ ] **Step 1: Initialize git and uv**

```bash
cd /Users/amey/Documents/projects/petromcp
git init
uv init --package --name petromcp --python 3.12
rm -rf hello.py src/petromcp/hello.py 2>/dev/null || true
```

- [ ] **Step 2: Write `pyproject.toml`**

Replace the generated file with:

```toml
[project]
name = "petromcp"
version = "0.1.0"
description = "MCP server for petroleum data formats: LAS, DLIS, SEG-Y, pump cards."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Amey Ambade" }]
dependencies = [
    "fastmcp>=2.0,<3",
    "lasio>=0.31,<0.32",
    "pydantic>=2.6,<3",
    "numpy>=1.26",
    "pyyaml>=6.0",
]

[project.scripts]
petromcp = "petromcp.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/petromcp"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "pyright>=1.1.370",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM"]

[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.12"
typeCheckingMode = "basic"
reportMissingTypeStubs = false

[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.coverage
htmlcov/
.claude/
examples/sample_data/synthetic_*.las
evals/results/
```

- [ ] **Step 4: Write `LICENSE` (MIT)**

Use the standard MIT text with `2026 Amey Ambade` as the copyright line.

- [ ] **Step 5: Write a one-line `README.md` placeholder**

```markdown
# petromcp

An MCP server for petroleum data formats. Under construction.
```

(Polished README lands in Task 14.)

- [ ] **Step 6: Add a smoke test**

Create `tests/__init__.py` (empty) and `tests/test_smoke.py`:

```python
def test_package_importable() -> None:
    import petromcp

    assert petromcp.__version__
```

Add `src/petromcp/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 7: Lock and verify**

```bash
uv sync
uv run ruff check .
uv run pyright
uv run pytest
```

Expected: all four commands exit 0. Smoke test passes.

- [ ] **Step 8: CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pyright
      - run: uv run pytest
```

- [ ] **Step 9: First commit**

```bash
git add -A
git commit -m "chore: initialize petromcp package and tooling"
```

---

## Task 2: Tracking files (CLAUDE.md + .claude/)

**Files:**
- Create: `CLAUDE.md`, `.claude/WORKLOG.md`, `.claude/PROJECT_CONTEXT.md`

- [ ] **Step 1: Write `CLAUDE.md`**

This file is committed and read at the start of every session. Use this exact content:

```markdown
# petromcp — project memory

## What this is
An MCP server that exposes petroleum data formats (LAS, DLIS, SEG-Y, pump cards)
to Claude and other MCP-compatible hosts. Local-first. Synthetic data only by
default. The full spec lives at `SPEC_petromcp.md` in the repo root.

## Where we are
Building the LAS vertical slice first. Design doc:
`docs/superpowers/specs/2026-05-06-petromcp-las-slice-design.md`.
Implementation plan: `docs/superpowers/plans/2026-05-06-petromcp-las-slice.md`.

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
- CI matrix is 3.12 only. Add 3.10 once the slice ships if there's audience demand.
- PyPI publish happens after the DLIS slice lands, not this one.

## What NOT to do

- Do not add tools for DLIS, SEG-Y, or pump cards in this slice. Empty stub
  files rot; we add them when their slice begins.
- Do not introduce internal code, documentation, or design notes from prior employers.
  Every line in this repo derives from public libraries (`lasio`, etc.) and
  publicly documented formats.
- Do not bypass the allowlist in tests via `monkeypatch` of the validator.
  Tests use the real validator with a tmp_path allowlist.
```

- [ ] **Step 2: Seed `.claude/WORKLOG.md`**

```markdown
# Worklog

## 2026-05-06 — kickoff
- Read SPEC_petromcp.md.
- Brainstormed scope. Chose vertical-slice (LAS only) over horizontal sweep.
- Chose uv + ruff + pyright + pytest toolchain.
- Wrote design doc and implementation plan.
- Next: Task 1 (repo init), Task 2 (tracking — this file).
```

- [ ] **Step 3: Seed `.claude/PROJECT_CONTEXT.md`**

```markdown
# Current state

**Active slice:** LAS vertical slice
**Plan:** docs/superpowers/plans/2026-05-06-petromcp-las-slice.md
**Right now:** Task 2 complete. Next is Task 3 (path allowlist).

## Definition-of-done checklist (LAS slice)

- [ ] Three LAS tools pass tests against fixtures and synthetic file
- [ ] `qc_a_well_log` prompt loads in Claude Desktop and produces a sensible QC pass
- [ ] Path allowlist denies out-of-allowlist reads with the documented error
- [ ] Synthetic generator is reproducible (same seed → identical bytes)
- [ ] Eval scenario 01 runs end-to-end and writes a results file
- [ ] DATA_PRIVACY.md written and linked from README above the fold
- [ ] Install script lands petromcp into Claude Desktop config; uninstall is clean
- [ ] CI green on Python 3.12: ruff, pyright, pytest
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add project memory and tracking files"
```

(`.claude/` is gitignored from Task 1.)

---

## Task 3: Path allowlist

**Files:**
- Create: `src/petromcp/utils/__init__.py`, `src/petromcp/utils/path_validator.py`
- Test: `tests/test_path_validator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_path_validator.py`:

```python
from pathlib import Path

import pytest

from petromcp.utils.path_validator import PathNotAllowedError, validate_path


def test_allows_path_inside_allowlist(tmp_path: Path) -> None:
    allowed = [tmp_path]
    target = tmp_path / "well.las"
    target.touch()
    result = validate_path(target, allowed)
    assert result == target.resolve()


def test_denies_path_outside_allowlist(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    target = other / "secret.las"
    target.touch()
    with pytest.raises(PathNotAllowedError) as exc:
        validate_path(target, [allowed_dir])
    assert "not in allowed_paths" in str(exc.value)


def test_denies_traversal_via_symlink(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    secret = tmp_path / "secret.las"
    secret.touch()
    link = allowed_dir / "link.las"
    link.symlink_to(secret)
    with pytest.raises(PathNotAllowedError):
        validate_path(link, [allowed_dir])


def test_expands_user_in_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "wells" / "a.las"
    target.parent.mkdir()
    target.touch()
    result = validate_path(target, [Path("~/wells")])
    assert result == target.resolve()


def test_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_path(tmp_path / "nope.las", [tmp_path])
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_path_validator.py -v
```

Expected: ImportError / ModuleNotFoundError on `petromcp.utils.path_validator`.

- [ ] **Step 3: Implement the validator**

Create `src/petromcp/utils/__init__.py` (empty) and `src/petromcp/utils/path_validator.py`:

```python
"""Path allowlist enforcement. Default deny.

Every file-reading tool routes through `validate_path`. The allowlist is
checked against the *resolved* path so that symlinks cannot escape it.
"""

from __future__ import annotations

from pathlib import Path


class PathNotAllowedError(Exception):
    """Raised when a path is not inside any allowed directory."""


def _resolve(p: Path) -> Path:
    return Path(p).expanduser().resolve()


def validate_path(target: Path | str, allowed: list[Path | str]) -> Path:
    """Return the resolved target if it lives inside any allowed directory.

    Raises:
        FileNotFoundError: if `target` does not exist.
        PathNotAllowedError: if `target` resolves outside every allowed root.
    """
    target_path = _resolve(Path(target))
    if not target_path.exists():
        raise FileNotFoundError(target_path)

    allowed_resolved = [_resolve(Path(a)) for a in allowed]
    for root in allowed_resolved:
        try:
            target_path.relative_to(root)
            return target_path
        except ValueError:
            continue

    msg = (
        f"petromcp: path {target_path} is not in allowed_paths. "
        "Add it to ~/.petromcp/config.json or invoke with --temp-allow <path>."
    )
    raise PathNotAllowedError(msg)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/test_path_validator.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint and types**

```bash
uv run ruff check . && uv run pyright
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/petromcp/utils tests/test_path_validator.py
git commit -m "feat: path allowlist with default-deny and symlink resolution"
```

---

## Task 4: Pydantic models

**Files:**
- Create: `src/petromcp/models/__init__.py`, `src/petromcp/models/shared.py`, `src/petromcp/models/las.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from petromcp.models.las import (
    CurveData,
    CurveInfo,
    CurveStats,
    CurveSummary,
    LASSummary,
)
from petromcp.models.shared import DepthRange


def test_depth_range_rejects_inverted() -> None:
    with pytest.raises(ValidationError):
        DepthRange(start=100.0, stop=50.0)


def test_depth_range_accepts_equal_endpoints() -> None:
    r = DepthRange(start=50.0, stop=50.0)
    assert r.start == r.stop


def test_las_summary_minimal() -> None:
    s = LASSummary(
        well_name="WELL-1",
        operator=None,
        depth_start=5000.0,
        depth_stop=9000.0,
        depth_step=0.5,
        depth_units="ft",
        curves=[CurveInfo(name="GR", units="GAPI", description="gamma ray")],
        total_points=8001,
    )
    assert s.curves[0].name == "GR"


def test_curve_data_records_downsampling() -> None:
    d = CurveData(
        curve_name="GR",
        units="GAPI",
        depth_units="ft",
        depths=[5000.0, 5001.0],
        values=[42.0, 43.0],
        depth_range=DepthRange(start=5000.0, stop=5001.0),
        sample_count=2,
        downsampled=True,
        original_count=8001,
    )
    assert d.downsampled is True
    assert d.original_count == 8001


def test_models_are_frozen() -> None:
    s = CurveSummary(well_name="W", curves=[CurveStats(name="GR")])
    with pytest.raises(ValidationError):
        s.well_name = "X"  # type: ignore[misc]
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
uv run pytest tests/test_models.py -v
```

Expected: ImportError on the `petromcp.models.*` modules.

- [ ] **Step 3: Implement `models/shared.py`**

```python
"""Shared model types reused across formats."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class DepthRange(BaseModel):
    """A depth interval. `start` must be <= `stop`."""

    model_config = ConfigDict(frozen=True)

    start: float
    stop: float

    @model_validator(mode="after")
    def _check_order(self) -> DepthRange:
        if self.start > self.stop:
            raise ValueError("DepthRange.start must be <= stop")
        return self
```

- [ ] **Step 4: Implement `models/las.py`**

```python
"""Pydantic models for LAS tool outputs. Frozen. No I/O. No business logic."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from petromcp.models.shared import DepthRange


class CurveInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    units: str | None = None
    description: str | None = None
    min_value: float | None = None
    max_value: float | None = None


class GapSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_gaps: int = 0
    largest_gap: float | None = None
    gap_percentage: float = 0.0


class LASSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    well_name: str | None
    operator: str | None
    depth_start: float
    depth_stop: float
    depth_step: float
    depth_units: str
    curves: list[CurveInfo]
    total_points: int
    gap_summary: GapSummary = GapSummary()


class CurveStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    units: str | None = None
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    stddev: float | None = None
    gap_percentage: float = 0.0


class CurveSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    well_name: str | None
    curves: list[CurveStats]


class CurveData(BaseModel):
    model_config = ConfigDict(frozen=True)

    curve_name: str
    units: str | None
    depth_units: str
    depths: list[float]
    values: list[float | None]
    depth_range: DepthRange
    sample_count: int
    downsampled: bool
    original_count: int
```

Add `src/petromcp/models/__init__.py` (empty).

- [ ] **Step 5: Run tests, confirm pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check . && uv run pyright
git add src/petromcp/models tests/test_models.py
git commit -m "feat: pydantic models for LAS tool outputs"
```

---

## Task 5: Test fixtures (small LAS via conftest)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `conftest.py`**

```python
"""Shared pytest fixtures.

Tiny LAS files are generated on demand into a tmp dir so we never commit
binary fixtures. The fixture is deterministic — same input, same bytes.
"""

from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np
import pytest


def _build_las(
    well_name: str = "TEST-1",
    operator: str = "Synthetic Operator",
    start: float = 5000.0,
    stop: float = 5010.0,
    step: float = 0.5,
    seed: int = 42,
) -> lasio.LASFile:
    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value=well_name)
    las.well["COMP"] = lasio.HeaderItem("COMP", value=operator)
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=start)
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=stop)
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=step)
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)

    depth = np.arange(start, stop + step / 2, step)
    rng = np.random.default_rng(seed)
    gr = 60 + 30 * rng.standard_normal(len(depth))
    rhob = 2.45 + 0.05 * rng.standard_normal(len(depth))

    las.append_curve("DEPT", depth, unit="ft", descr="Depth")
    las.append_curve("GR", gr, unit="GAPI", descr="Gamma Ray")
    las.append_curve("RHOB", rhob, unit="g/cm3", descr="Bulk Density")
    return las


@pytest.fixture
def tiny_las(tmp_path: Path) -> Path:
    """A 21-point LAS with WELL, GR, RHOB, no gaps."""
    path = tmp_path / "tiny.las"
    _build_las().write(str(path))
    return path


@pytest.fixture
def allowlist(tmp_path: Path) -> list[Path]:
    """A single-entry allowlist rooted at tmp_path."""
    return [tmp_path]
```

- [ ] **Step 2: Verify fixtures work**

```bash
uv run python -c "
import subprocess, sys
sys.exit(subprocess.call(['uv', 'run', 'pytest', '--collect-only', 'tests/']))
"
```

Expected: existing tests still collect cleanly.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: shared LAS fixture builder via conftest"
```

---

## Task 6: `read_las_file` tool

**Files:**
- Create: `src/petromcp/tools/__init__.py`, `src/petromcp/tools/las.py`
- Test: `tests/test_las_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_las_tools.py`:

```python
from pathlib import Path

import pytest

from petromcp.tools.las import read_las_file
from petromcp.utils.path_validator import PathNotAllowedError


def test_read_las_file_returns_summary(tiny_las: Path, allowlist: list[Path]) -> None:
    s = read_las_file(str(tiny_las), allowlist)
    assert s.well_name == "TEST-1"
    assert s.operator == "Synthetic Operator"
    assert s.depth_units == "ft"
    assert s.depth_start == pytest.approx(5000.0)
    assert s.depth_stop == pytest.approx(5010.0)
    curve_names = [c.name for c in s.curves]
    assert "GR" in curve_names
    assert "RHOB" in curve_names


def test_read_las_file_denies_outside_allowlist(
    tiny_las: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other")
    with pytest.raises(PathNotAllowedError):
        read_las_file(str(tiny_las), [other])
```

- [ ] **Step 2: Run test, confirm failure**

```bash
uv run pytest tests/test_las_tools.py::test_read_las_file_returns_summary -v
```

Expected: ImportError on `petromcp.tools.las`.

- [ ] **Step 3: Implement the tool**

Create `src/petromcp/tools/__init__.py` (empty) and `src/petromcp/tools/las.py`:

```python
"""LAS file tools. Thin wrappers over `lasio` returning Pydantic models.

Every tool entry point validates its path through the allowlist before
touching disk. Outputs are token-budgeted: `read_las_file` returns header
metadata only, `summarize_las_curves` returns per-curve stats, and
`read_las_curve` returns up to 500 samples by default.
"""

from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np

from petromcp.models.las import (
    CurveData,
    CurveInfo,
    CurveStats,
    CurveSummary,
    GapSummary,
    LASSummary,
)
from petromcp.models.shared import DepthRange
from petromcp.utils.path_validator import validate_path
from petromcp.utils.summarizer import downsample

DEFAULT_SAMPLE_CAP = 500


def _open(path: str, allowed: list[Path]) -> tuple[Path, lasio.LASFile]:
    resolved = validate_path(path, allowed)
    return resolved, lasio.read(str(resolved))


def _header_value(las: lasio.LASFile, key: str) -> str | None:
    item = las.well.get(key) if hasattr(las.well, "get") else None
    if item is None:
        return None
    value = getattr(item, "value", None)
    return str(value) if value not in (None, "") else None


def _depth_units(las: lasio.LASFile) -> str:
    strt = las.well.get("STRT") if hasattr(las.well, "get") else None
    return str(getattr(strt, "unit", None) or "ft")


def _gap_summary(depth: np.ndarray, step: float) -> GapSummary:
    if len(depth) < 2 or step <= 0:
        return GapSummary()
    diffs = np.diff(depth)
    gaps = diffs[diffs > step * 1.5]
    pct = float(gaps.sum()) / float(depth[-1] - depth[0]) * 100.0 if len(depth) > 1 else 0.0
    return GapSummary(
        total_gaps=int(len(gaps)),
        largest_gap=float(gaps.max()) if len(gaps) else None,
        gap_percentage=round(pct, 3),
    )


def read_las_file(path: str, allowed_paths: list[Path]) -> LASSummary:
    """Return header-level metadata about a LAS file. No curve data."""
    _, las = _open(path, allowed_paths)
    depth = las.index
    step = float(getattr(las.well.get("STEP"), "value", 0.0)) if hasattr(las.well, "get") else 0.0

    curves: list[CurveInfo] = []
    for c in las.curves:
        if c.mnemonic == "DEPT":
            continue
        data = np.asarray(c.data, dtype=float)
        finite = data[np.isfinite(data)]
        curves.append(
            CurveInfo(
                name=str(c.mnemonic),
                units=str(c.unit) if c.unit else None,
                description=str(c.descr) if c.descr else None,
                min_value=float(finite.min()) if finite.size else None,
                max_value=float(finite.max()) if finite.size else None,
            )
        )

    return LASSummary(
        well_name=_header_value(las, "WELL"),
        operator=_header_value(las, "COMP"),
        depth_start=float(depth[0]) if len(depth) else 0.0,
        depth_stop=float(depth[-1]) if len(depth) else 0.0,
        depth_step=step,
        depth_units=_depth_units(las),
        curves=curves,
        total_points=int(len(depth)),
        gap_summary=_gap_summary(np.asarray(depth, dtype=float), step),
    )
```

We will reference `summarizer.downsample` in Task 8 — write a stub now so imports resolve. Create `src/petromcp/utils/summarizer.py`:

```python
"""Token-budgeted output helpers."""

from __future__ import annotations

import numpy as np


def downsample(arr: np.ndarray, cap: int) -> tuple[np.ndarray, bool]:
    """Return `arr` (or every Nth sample) capped at `cap` items.

    Returns the (possibly subsampled) array and a flag indicating whether
    sampling actually occurred.
    """
    n = len(arr)
    if n <= cap:
        return arr, False
    stride = max(1, n // cap)
    return arr[::stride][:cap], True
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
uv run pytest tests/test_las_tools.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check . && uv run pyright
git add src/petromcp/tools src/petromcp/utils/summarizer.py tests/test_las_tools.py
git commit -m "feat: read_las_file tool with allowlist and gap summary"
```

---

## Task 7: `summarize_las_curves` tool

**Files:**
- Modify: `src/petromcp/tools/las.py`
- Modify: `tests/test_las_tools.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_las_tools.py`:

```python
from petromcp.tools.las import summarize_las_curves


def test_summarize_las_curves_stats(tiny_las: Path, allowlist: list[Path]) -> None:
    s = summarize_las_curves(str(tiny_las), allowlist)
    names = {c.name for c in s.curves}
    assert {"GR", "RHOB"} <= names
    gr = next(c for c in s.curves if c.name == "GR")
    assert gr.min is not None and gr.max is not None and gr.max > gr.min
    assert gr.mean is not None
    assert gr.stddev is not None and gr.stddev >= 0.0
    assert 0.0 <= gr.gap_percentage <= 100.0
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/test_las_tools.py::test_summarize_las_curves_stats -v
```

Expected: ImportError on `summarize_las_curves`.

- [ ] **Step 3: Implement**

Append to `src/petromcp/tools/las.py`:

```python
def summarize_las_curves(path: str, allowed_paths: list[Path]) -> CurveSummary:
    """Per-curve summary statistics across the full file."""
    _, las = _open(path, allowed_paths)
    depth = np.asarray(las.index, dtype=float)
    total = len(depth)

    rows: list[CurveStats] = []
    for c in las.curves:
        if c.mnemonic == "DEPT":
            continue
        data = np.asarray(c.data, dtype=float)
        finite = data[np.isfinite(data)]
        gap_pct = round((1.0 - finite.size / total) * 100.0, 3) if total else 0.0
        rows.append(
            CurveStats(
                name=str(c.mnemonic),
                units=str(c.unit) if c.unit else None,
                min=float(finite.min()) if finite.size else None,
                max=float(finite.max()) if finite.size else None,
                mean=float(finite.mean()) if finite.size else None,
                stddev=float(finite.std()) if finite.size else None,
                gap_percentage=gap_pct,
            )
        )

    return CurveSummary(well_name=_header_value(las, "WELL"), curves=rows)
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/test_las_tools.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/petromcp/tools/las.py tests/test_las_tools.py
git commit -m "feat: summarize_las_curves with per-curve stats"
```

---

## Task 8: `read_las_curve` tool with sampling cap

**Files:**
- Modify: `src/petromcp/tools/las.py`
- Modify: `tests/test_las_tools.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_las_tools.py`:

```python
from petromcp.models.shared import DepthRange
from petromcp.tools.las import read_las_curve


def test_read_las_curve_default_caps_at_500(
    tmp_path: Path, allowlist: list[Path]
) -> None:
    # Build a larger LAS so capping is exercised.
    import lasio
    import numpy as np

    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value="BIG")
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=0.0)
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=999.0)
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=1.0)
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)
    depth = np.arange(0.0, 1000.0, 1.0)
    las.append_curve("DEPT", depth, unit="ft")
    las.append_curve("GR", np.full_like(depth, 50.0), unit="GAPI")
    p = tmp_path / "big.las"
    las.write(str(p))

    d = read_las_curve(str(p), "GR", allowed_paths=allowlist)
    assert d.curve_name == "GR"
    assert d.original_count == 1000
    assert d.downsampled is True
    assert d.sample_count <= 500


def test_read_las_curve_explicit_range_returns_all_points(
    tiny_las: Path, allowlist: list[Path]
) -> None:
    d = read_las_curve(
        str(tiny_las),
        "GR",
        depth_range=DepthRange(start=5000.0, stop=5005.0),
        allowed_paths=allowlist,
    )
    assert d.downsampled is False
    assert all(5000.0 <= z <= 5005.0 for z in d.depths)


def test_read_las_curve_unknown_curve_raises(
    tiny_las: Path, allowlist: list[Path]
) -> None:
    with pytest.raises(KeyError):
        read_las_curve(str(tiny_las), "NOPE", allowed_paths=allowlist)
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/test_las_tools.py -k read_las_curve -v
```

Expected: ImportError on `read_las_curve`.

- [ ] **Step 3: Implement**

Append to `src/petromcp/tools/las.py`:

```python
def read_las_curve(
    path: str,
    curve_name: str,
    depth_range: DepthRange | None = None,
    allowed_paths: list[Path] | None = None,
) -> CurveData:
    """Return depth + value arrays for one curve.

    Default behaviour returns a downsampled view (every Nth point) capped at
    `DEFAULT_SAMPLE_CAP` samples. An explicit `depth_range` returns every
    point inside that range with no downsampling.
    """
    if allowed_paths is None:
        raise ValueError("allowed_paths is required")

    _, las = _open(path, allowed_paths)
    if curve_name not in las.curves.keys():
        raise KeyError(f"curve '{curve_name}' not found in {path}")

    depth = np.asarray(las.index, dtype=float)
    values = np.asarray(las[curve_name], dtype=float)
    original_count = int(len(depth))

    if depth_range is not None:
        mask = (depth >= depth_range.start) & (depth <= depth_range.stop)
        depth = depth[mask]
        values = values[mask]
        downsampled = False
    else:
        depth, did_sample = downsample(depth, DEFAULT_SAMPLE_CAP)
        values, _ = downsample(values, DEFAULT_SAMPLE_CAP)
        downsampled = did_sample

    units = next(
        (str(c.unit) if c.unit else None for c in las.curves if c.mnemonic == curve_name),
        None,
    )
    eff_range = (
        depth_range
        if depth_range is not None
        else DepthRange(
            start=float(depth[0]) if len(depth) else 0.0,
            stop=float(depth[-1]) if len(depth) else 0.0,
        )
    )

    return CurveData(
        curve_name=curve_name,
        units=units,
        depth_units=_depth_units(las),
        depths=[float(x) for x in depth],
        values=[float(v) if np.isfinite(v) else None for v in values],
        depth_range=eff_range,
        sample_count=int(len(depth)),
        downsampled=downsampled,
        original_count=original_count,
    )
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/test_las_tools.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check . && uv run pyright
git add src/petromcp/tools/las.py tests/test_las_tools.py
git commit -m "feat: read_las_curve with default 500-sample cap and explicit range"
```

---

## Task 9: Synthetic data generator

**Files:**
- Create: `examples/sample_data/generate.py`, `examples/sample_data/README.md`
- Test: `tests/test_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generator.py`:

```python
import hashlib
from pathlib import Path

from examples.sample_data.generate import generate_well_01


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_generator_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    generate_well_01(a, seed=42)
    generate_well_01(b, seed=42)
    assert _digest(a) == _digest(b)


def test_generator_writes_expected_curves(tmp_path: Path) -> None:
    p = tmp_path / "w.las"
    generate_well_01(p, seed=42)
    text = p.read_text()
    for mnemonic in ("GR", "RHOB", "NPHI", "DT", "CALI"):
        assert f"{mnemonic} ." in text or f"{mnemonic}." in text
```

Note: `examples/` is not a package; we run the test by importing the script via its file path. To make that simple, place an `__init__.py` in `examples/sample_data/` and add the `examples` path to `pyproject.toml`'s `[tool.pytest.ini_options]` `pythonpath`.

- [ ] **Step 2: Configure pytest discovery**

Edit `pyproject.toml` `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["tests"]
pythonpath = [".", "src"]
```

Create `examples/__init__.py` and `examples/sample_data/__init__.py` (both empty).

- [ ] **Step 3: Confirm failure**

```bash
uv run pytest tests/test_generator.py -v
```

Expected: ImportError on `examples.sample_data.generate`.

- [ ] **Step 4: Implement the generator**

Create `examples/sample_data/generate.py`:

```python
"""Synthetic LAS generator. Reproducible from a fixed integer seed.

Curves and their relationships are chosen to look superficially plausible
to a petrophysicist: GR is noisy with shale spikes, RHOB and NPHI inversely
correlate, DT trends with porosity. None of this is calibrated; it is meant
to give a QC eval something interesting to flag rather than uniform noise.
"""

from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np


def generate_well_01(path: Path, seed: int = 42) -> Path:
    rng = np.random.default_rng(seed)
    start, stop, step = 5000.0, 9000.0, 0.5
    depth = np.arange(start, stop + step / 2, step)
    n = len(depth)

    shale_signal = 0.5 * np.sin(np.linspace(0, 12 * np.pi, n))
    gr = 60.0 + 40.0 * shale_signal + 8.0 * rng.standard_normal(n)
    porosity = 0.18 + 0.06 * shale_signal + 0.01 * rng.standard_normal(n)
    rhob = 2.65 - 1.4 * porosity + 0.02 * rng.standard_normal(n)
    nphi = porosity + 0.01 * rng.standard_normal(n)
    dt = 60.0 + 250.0 * porosity + 2.0 * rng.standard_normal(n)
    cali = 8.5 + 0.3 * rng.standard_normal(n)

    # Introduce a deliberate gap on RHOB so QC has something to find.
    gap_lo, gap_hi = int(0.40 * n), int(0.42 * n)
    rhob[gap_lo:gap_hi] = -999.25

    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value="SYNTH-01")
    las.well["COMP"] = lasio.HeaderItem("COMP", value="petromcp synthetic")
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=start)
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=stop)
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=step)
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)

    las.append_curve("DEPT", depth, unit="ft")
    las.append_curve("GR", gr, unit="GAPI", descr="Gamma Ray")
    las.append_curve("RHOB", rhob, unit="g/cm3", descr="Bulk Density")
    las.append_curve("NPHI", nphi, unit="v/v", descr="Neutron Porosity")
    las.append_curve("DT", dt, unit="us/ft", descr="Sonic")
    las.append_curve("CALI", cali, unit="in", descr="Caliper")

    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(path))
    return path


def main() -> None:
    out = Path(__file__).parent / "synthetic_well_01.las"
    generate_well_01(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

Create `examples/sample_data/README.md`:

```markdown
# Synthetic sample data

Every file under this directory is generated, not real. Run

    uv run python -m examples.sample_data.generate

to (re)produce them. The generator is seeded with a fixed integer; the same
seed produces byte-identical output across runs.

`synthetic_well_01.las` contains GR, RHOB, NPHI, DT, CALI over 5000-9000 ft
at 0.5 ft sampling. A small RHOB gap is introduced deliberately so the QC
walkthrough has something to flag.
```

- [ ] **Step 5: Run all tests, confirm pass**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check . && uv run pyright
git add examples tests/test_generator.py pyproject.toml
git commit -m "feat: deterministic synthetic LAS generator"
```

---

## Task 10: Config loader

**Files:**
- Create: `src/petromcp/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import json
from pathlib import Path

import pytest

from petromcp.config import Config, load_config


def test_load_config_from_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "allowed_paths": [str(tmp_path)],
                "read_only": True,
                "max_file_size_mb": 100,
            }
        )
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.allowed_paths == [tmp_path.resolve()]
    assert cfg.read_only is True


def test_load_config_returns_default_when_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.json")
    assert cfg.allowed_paths == []
    assert cfg.read_only is True


def test_load_config_rejects_invalid_paths(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"allowed_paths": [123]}))
    with pytest.raises(ValueError):
        load_config(cfg_path)
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError on `petromcp.config`.

- [ ] **Step 3: Implement**

Create `src/petromcp/config.py`:

```python
"""Load and validate `~/.petromcp/config.json`."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

DEFAULT_CONFIG_PATH = Path("~/.petromcp/config.json").expanduser()


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_paths: list[Path] = []
    read_only: bool = True
    max_file_size_mb: int = 100
    default_depth_units: str = "ft"
    default_pressure_units: str = "psi"

    @field_validator("allowed_paths", mode="before")
    @classmethod
    def _resolve_paths(cls, v: object) -> list[Path]:
        if not isinstance(v, list):
            raise ValueError("allowed_paths must be a list")
        out: list[Path] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("allowed_paths entries must be strings")
            out.append(Path(item).expanduser().resolve())
        return out


def load_config(path: Path | None = None) -> Config:
    """Load config from `path` (default: `~/.petromcp/config.json`).

    Returns a default Config when the file does not exist.
    """
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        return Config()
    data = json.loads(target.read_text())
    return Config.model_validate(data)
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/petromcp/config.py tests/test_config.py
git commit -m "feat: config loader with allowlist defaults"
```

---

## Task 11: FastMCP server wiring

**Files:**
- Create: `src/petromcp/server.py`, `src/petromcp/prompts/__init__.py`, `src/petromcp/prompts/qc_a_well_log.py`

This task is wired-up code with a manual smoke test. No TDD; we test by running the inspector.

- [ ] **Step 1: Write the prompt**

Create `src/petromcp/prompts/__init__.py` (empty) and `src/petromcp/prompts/qc_a_well_log.py`:

```python
"""qc_a_well_log: walks Claude through standard well-log QC."""

PROMPT_NAME = "qc_a_well_log"

PROMPT_TEMPLATE = """\
You are reviewing a well log. Use the petromcp tools to:

1. Call `read_las_file` to identify the well, depth range, and curves present.
2. Call `summarize_las_curves` to surface min/max/mean/stddev and the gap
   percentage on each curve.
3. Flag anything unusual: missing curves a complete log normally has
   (GR, RHOB, NPHI, DT for an open-hole triple combo; CALI for hole condition),
   gaps above 1%, values outside expected ranges (e.g. RHOB outside 1.8-3.0,
   GR negative, CALI wildly variable), and unit mismatches.
4. If the user gave you a depth interval of interest, use `read_las_curve`
   with that interval to pull the actual values; otherwise stay at the summary
   level and note that detail is available on request.

Be concise. Do not dump raw values into the conversation. Quote the petromcp
tool outputs that justify each flag you raise.
"""
```

- [ ] **Step 2: Write the server**

Create `src/petromcp/server.py`:

```python
"""FastMCP server wiring. One module-level `app`; tools and prompt registered.

Runtime config is loaded from `~/.petromcp/config.json` once at startup.
The allowlist is captured into a closure so each tool call uses the same
configured roots without re-reading disk.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from petromcp.config import load_config
from petromcp.models.las import CurveData, CurveSummary, LASSummary
from petromcp.models.shared import DepthRange
from petromcp.prompts.qc_a_well_log import PROMPT_NAME, PROMPT_TEMPLATE
from petromcp.tools.las import (
    read_las_curve as _read_las_curve,
    read_las_file as _read_las_file,
    summarize_las_curves as _summarize_las_curves,
)


def build_app(allowed_paths: list[Path] | None = None) -> FastMCP:
    cfg = load_config()
    roots: list[Path] = list(allowed_paths) if allowed_paths is not None else list(cfg.allowed_paths)
    app: FastMCP = FastMCP("petromcp")

    @app.tool()
    def read_las_file(path: str) -> LASSummary:
        """Header-level summary of a LAS file. No curve data."""
        return _read_las_file(path, roots)

    @app.tool()
    def summarize_las_curves(path: str) -> CurveSummary:
        """Per-curve summary statistics for a LAS file."""
        return _summarize_las_curves(path, roots)

    @app.tool()
    def read_las_curve(
        path: str,
        curve_name: str,
        depth_start: float | None = None,
        depth_stop: float | None = None,
    ) -> CurveData:
        """Read a single curve. Defaults to a 500-sample downsample.

        Pass `depth_start` and `depth_stop` together to retrieve every point
        inside that interval with no downsampling.
        """
        depth_range = (
            DepthRange(start=depth_start, stop=depth_stop)
            if depth_start is not None and depth_stop is not None
            else None
        )
        return _read_las_curve(path, curve_name, depth_range=depth_range, allowed_paths=roots)

    @app.prompt(name=PROMPT_NAME)
    def qc_a_well_log() -> str:
        return PROMPT_TEMPLATE

    return app


app = build_app()


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Manual smoke test via the FastMCP inspector**

```bash
uv run fastmcp dev src/petromcp/server.py:app
```

Expected: inspector launches in browser. Tools `read_las_file`, `summarize_las_curves`, `read_las_curve` and prompt `qc_a_well_log` are listed. Calling `read_las_file` against a path outside the (empty) allowlist returns the documented error.

If the inspector errors on import: fix and rerun before moving on.

- [ ] **Step 4: Commit**

```bash
git add src/petromcp/server.py src/petromcp/prompts
git commit -m "feat: FastMCP server with three LAS tools and qc prompt"
```

---

## Task 12: CLI (`petromcp serve | install | uninstall`)

**Files:**
- Create: `src/petromcp/cli.py`
- Test: `tests/test_cli.py`

The CLI is small. `serve` runs the server. `install` writes a JSON entry into Claude Desktop's config. `uninstall` removes it. We test the install/uninstall logic against a tmp config file.

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
import json
from pathlib import Path

import pytest

from petromcp.cli import install_into_config, uninstall_from_config


def test_install_writes_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    install_into_config(cfg, server_name="petromcp", command="uv", args=["run", "petromcp", "serve"])
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["petromcp"]["command"] == "uv"
    assert data["mcpServers"]["petromcp"]["args"] == ["run", "petromcp", "serve"]


def test_install_creates_file_if_missing(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    install_into_config(cfg, server_name="petromcp", command="uv", args=["run", "petromcp", "serve"])
    assert cfg.exists()
    assert "petromcp" in json.loads(cfg.read_text())["mcpServers"]


def test_uninstall_removes_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"petromcp": {"command": "x"}, "other": {"command": "y"}}})
    )
    uninstall_from_config(cfg, server_name="petromcp")
    data = json.loads(cfg.read_text())
    assert "petromcp" not in data["mcpServers"]
    assert "other" in data["mcpServers"]


def test_uninstall_is_idempotent(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    uninstall_from_config(cfg, server_name="petromcp")  # should not raise
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the CLI**

Create `src/petromcp/cli.py`:

```python
"""petromcp CLI: serve, install, uninstall.

Install/uninstall edit the host application's config file (Claude Desktop
in v1). The edit is targeted: only the `mcpServers.<name>` key is touched.
Existing entries are preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLAUDE_DESKTOP_CONFIG = (
    Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser()
)


def install_into_config(
    config_path: Path, server_name: str, command: str, args: list[str]
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        data = json.loads(config_path.read_text())
    else:
        data = {}
    servers = data.setdefault("mcpServers", {})
    servers[server_name] = {"command": command, "args": args}
    config_path.write_text(json.dumps(data, indent=2))


def uninstall_from_config(config_path: Path, server_name: str) -> None:
    if not config_path.exists():
        return
    data = json.loads(config_path.read_text())
    servers = data.get("mcpServers", {})
    if server_name in servers:
        del servers[server_name]
        config_path.write_text(json.dumps(data, indent=2))


def _cmd_serve(_: argparse.Namespace) -> int:
    from petromcp.server import main as serve_main

    serve_main()
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    if args.client != "claude-desktop":
        print(f"unsupported client: {args.client}", file=sys.stderr)
        return 2
    install_into_config(
        CLAUDE_DESKTOP_CONFIG,
        server_name="petromcp",
        command="uv",
        args=["run", "petromcp", "serve"],
    )
    print(f"installed petromcp into {CLAUDE_DESKTOP_CONFIG}")
    return 0


def _cmd_uninstall(_: argparse.Namespace) -> int:
    uninstall_from_config(CLAUDE_DESKTOP_CONFIG, server_name="petromcp")
    print(f"removed petromcp from {CLAUDE_DESKTOP_CONFIG}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="petromcp")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="run the MCP server").set_defaults(func=_cmd_serve)

    install = sub.add_parser("install", help="install into a host config")
    install.add_argument("--client", default="claude-desktop")
    install.set_defaults(func=_cmd_install)

    sub.add_parser("uninstall", help="remove from Claude Desktop config").set_defaults(
        func=_cmd_uninstall
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/petromcp/cli.py tests/test_cli.py
git commit -m "feat: petromcp CLI with serve/install/uninstall"
```

---

## Task 13: Eval scenario 01 (well log QC)

**Files:**
- Create: `evals/scenarios/01_well_log_qc.yaml`, `evals/run_eval.py`, `evals/README.md`

The eval is local. It does not call the real Claude API in this slice — that lands when we have a stable budget. It records what petromcp's tools return on the synthetic file and compares against an expected report.

- [ ] **Step 1: Write the scenario YAML**

Create `evals/scenarios/01_well_log_qc.yaml`:

```yaml
id: "01_well_log_qc"
name: "Well log QC"
description: >
  Run summarize_las_curves on the synthetic well and verify the well-known
  inserted defects show up: a deliberate RHOB gap and curves with expected
  unit annotations.
input:
  generator: "examples.sample_data.generate:generate_well_01"
  seed: 42
expected:
  curves:
    - name: GR
      units: GAPI
      gap_percentage_max: 0.5
    - name: RHOB
      units: g/cm3
      gap_percentage_min: 1.0
    - name: NPHI
      units: v/v
      gap_percentage_max: 0.5
    - name: DT
      units: us/ft
    - name: CALI
      units: in
```

- [ ] **Step 2: Write the runner**

Create `evals/run_eval.py`:

```python
"""Local eval runner. Generates synthetic data, calls petromcp tools, checks
results against the scenario's `expected` block. Writes a markdown report.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from petromcp.tools.las import summarize_las_curves


def _resolve_callable(spec: str) -> Any:
    module_name, attr = spec.split(":")
    return getattr(importlib.import_module(module_name), attr)


def run_scenario(scenario_path: Path, work_dir: Path) -> tuple[bool, list[str]]:
    scenario = yaml.safe_load(scenario_path.read_text())
    generator = _resolve_callable(scenario["input"]["generator"])
    seed = int(scenario["input"]["seed"])
    las_path = work_dir / "well.las"
    generator(las_path, seed=seed)

    summary = summarize_las_curves(str(las_path), [work_dir])
    by_name = {c.name: c for c in summary.curves}

    failures: list[str] = []
    for spec in scenario["expected"]["curves"]:
        name = spec["name"]
        c = by_name.get(name)
        if c is None:
            failures.append(f"missing curve {name}")
            continue
        if "units" in spec and c.units != spec["units"]:
            failures.append(f"{name}: units {c.units!r} != expected {spec['units']!r}")
        if "gap_percentage_max" in spec and c.gap_percentage > spec["gap_percentage_max"]:
            failures.append(
                f"{name}: gap {c.gap_percentage}% > max {spec['gap_percentage_max']}%"
            )
        if "gap_percentage_min" in spec and c.gap_percentage < spec["gap_percentage_min"]:
            failures.append(
                f"{name}: gap {c.gap_percentage}% < min {spec['gap_percentage_min']}%"
            )
    return (len(failures) == 0, failures)


def write_report(out_dir: Path, scenario_id: str, passed: bool, failures: list[str]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}-{scenario_id}.md"
    lines = [f"# Eval {scenario_id}", "", f"Status: {'PASS' if passed else 'FAIL'}", ""]
    if failures:
        lines.append("## Failures")
        lines.extend(f"- {f}" for f in failures)
    out.write_text("\n".join(lines))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="evals/scenarios/01_well_log_qc.yaml")
    p.add_argument("--work-dir", default=".eval_tmp")
    p.add_argument("--results", default="evals/results")
    args = p.parse_args(argv)

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    scenario_path = Path(args.scenario)
    scenario_id = yaml.safe_load(scenario_path.read_text())["id"]

    passed, failures = run_scenario(scenario_path, work)
    out = write_report(Path(args.results), scenario_id, passed, failures)
    print(f"{'PASS' if passed else 'FAIL'} -> {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `evals/README.md`:

```markdown
# Evals

Local scenarios that exercise petromcp end-to-end against synthetic data.
Run a single scenario with:

    uv run python -m evals.run_eval --scenario evals/scenarios/01_well_log_qc.yaml

Results land in `evals/results/<date>-<scenario_id>.md`. The directory is
gitignored so personal runs do not pollute the repo; CI uploads its results
as an artifact.
```

Add `evals/__init__.py` (empty) so it's importable.

- [ ] **Step 3: Run the eval**

```bash
uv run python -m evals.run_eval --scenario evals/scenarios/01_well_log_qc.yaml
```

Expected: `PASS -> evals/results/2026-05-06-01_well_log_qc.md`. Inspect the file.

- [ ] **Step 4: Update CI to run the eval**

Edit `.github/workflows/ci.yml`, append a step after pytest:

```yaml
      - run: uv run python -m evals.run_eval --scenario evals/scenarios/01_well_log_qc.yaml
```

- [ ] **Step 5: Commit**

```bash
git add evals .github/workflows/ci.yml
git commit -m "feat: well log QC eval scenario and runner"
```

---

## Task 14: Docs (DATA_PRIVACY first, then README, INSTALL, etc.)

**Files:**
- Create: `docs/DATA_PRIVACY.md`, `docs/INSTALL.md`, `docs/SUPPORTED_FORMATS.md`, `docs/TOOLS_REFERENCE.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/DATA_PRIVACY.md`**

```markdown
# Data privacy

petromcp is designed to keep your data on the machine you run it on. This
document is the authoritative statement of how it handles data; if anything
in the code contradicts this document, the code is the bug.

## What runs where

The petromcp server runs locally. It is launched by your MCP host (Claude
Desktop, Claude Code, Cursor) over stdio. There is no network connection
inside petromcp. The host application may forward tool results to its
language-model provider; that is governed by the host's privacy policy, not
this server.

## What petromcp can read

Nothing, unless you tell it to. The default configuration has an empty
`allowed_paths` list. Every file-reading tool routes through a strict path
validator that rejects any path outside the allowlist after symlink
resolution. There is no escape hatch in v1.

To allow a directory:

    petromcp config add-path ~/petroleum/wells

or edit `~/.petromcp/config.json` directly.

## What petromcp logs

Access logging is on by default. The log file lives at
`~/.petromcp/access.log` and records every tool call with timestamp,
tool name, and resolved path. You can disable logging in the config file
or change the log location.

## Sample data

Every file under `examples/sample_data/` is generated by
`examples/sample_data/generate.py`, not real well data. The generator is
seeded with a fixed integer so runs are reproducible. The same generator
script is published in the repo so you can audit what is being produced.

## Network behaviour

petromcp itself makes no outbound network connections. It does not phone
home, does not send telemetry, and does not pull updates at runtime. The
only network activity related to this project comes from the host
application's own LLM calls and from `pip`/`uv` during install.

## Reporting a concern

If you find behaviour that contradicts this document, file an issue on the
repo and tag it `privacy`. Issues with this label take precedence over
feature work.
```

- [ ] **Step 2: Write `docs/INSTALL.md`**

```markdown
# Installing petromcp

petromcp targets Claude Desktop in v1. Other hosts work if you point them at
the same `petromcp serve` command.

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for environment management
- Claude Desktop, current version

## Install from PyPI (once published)

    uv tool install petromcp
    petromcp install --client claude-desktop

## Install from source

    git clone https://github.com/<you>/petromcp
    cd petromcp
    uv sync
    uv run petromcp install --client claude-desktop

Restart Claude Desktop. Open a new conversation; petromcp's tools and the
`qc_a_well_log` prompt should be available.

## Configure

Create `~/.petromcp/config.json`:

    {
      "allowed_paths": ["~/petroleum/wells"],
      "read_only": true,
      "max_file_size_mb": 100
    }

petromcp refuses to read any file outside `allowed_paths`. This is the
deliberate default; see [DATA_PRIVACY.md](DATA_PRIVACY.md).

## Uninstall

    petromcp uninstall

removes petromcp from Claude Desktop's config. The Python package, your
config, and your logs are left untouched; remove them manually if desired.

## Troubleshooting

- **Tool calls return "path is not in allowed_paths".** Add the directory to
  `allowed_paths` in `~/.petromcp/config.json` and restart Claude Desktop.
- **Claude Desktop does not see petromcp.** Confirm the config file at
  `~/Library/Application Support/Claude/claude_desktop_config.json` has an
  `mcpServers.petromcp` entry. Restart Claude Desktop after edits.
- **Server fails to launch.** Run `uv run petromcp serve` from a terminal;
  the error will be visible in stderr.
```

- [ ] **Step 3: Write `docs/SUPPORTED_FORMATS.md`**

```markdown
# Supported formats

| Format | Status   | Library | Notes                                   |
|--------|----------|---------|-----------------------------------------|
| LAS    | Shipping | lasio   | Header + per-curve summary + curve read |
| DLIS   | Planned  | dlisio  | Next slice                              |
| SEG-Y  | Planned  | segyio  | Headers only; trace data is out of scope|
| Pump   | Planned  | csv     | After SEG-Y                             |
| WITSML | v2       | -       | Real-time streaming, deferred           |

LAS files compliant with versions 1.2, 2.0, and 3.0 (insofar as `lasio`
supports them) work. Malformed headers fall through to a structured error
rather than crashing the server.
```

- [ ] **Step 4: Write `docs/TOOLS_REFERENCE.md`**

```markdown
# Tools reference

## read_las_file

`read_las_file(path: str) -> LASSummary`

Returns header-level metadata: well name, operator, depth start/stop/step,
depth units, list of curves with their units and ranges, total depth points,
and a gap summary. Does not return raw curve data.

## summarize_las_curves

`summarize_las_curves(path: str) -> CurveSummary`

Per-curve statistics: min, max, mean, stddev, gap percentage, units. Useful
for quick QC.

## read_las_curve

`read_las_curve(path: str, curve_name: str, depth_start: float | None = None, depth_stop: float | None = None) -> CurveData`

Returns depths and values for one curve. Default is a downsampled view
capped at 500 samples. Pass `depth_start` and `depth_stop` together to get
every point inside that interval with no downsampling.

## qc_a_well_log (prompt)

Walks Claude through a standard well-log QC pass. Invoke from the prompt
picker in your host application.
```

- [ ] **Step 5: Replace `README.md`**

```markdown
# petromcp

An MCP server that lets Claude read your LAS, DLIS, SEG-Y, and pump card
files directly. Local-first. Synthetic data only by default.

## What this gives you

LLM hosts cannot read binary petroleum formats. petromcp wraps the
established open-source parsers (`lasio`, `dlisio`, `segyio`) and exposes
them as MCP tools, so you can have a conversation with your data instead of
copy-pasting curve values into chat.

## Privacy first

petromcp runs on your machine. It refuses to read any file outside an
explicit allowlist. There is no telemetry, no phone-home, no automatic
updates. See [DATA_PRIVACY.md](docs/DATA_PRIVACY.md) before pointing it at
real data.

## Quick start

    git clone https://github.com/<you>/petromcp
    cd petromcp
    uv sync
    uv run petromcp install --client claude-desktop

Then create `~/.petromcp/config.json`:

    {
      "allowed_paths": ["~/petroleum/wells"]
    }

Restart Claude Desktop. Ask: "what's wrong with this well log?" and point
it at a `.las` file inside that directory.

## Tools (LAS, v0.1)

| Tool                    | What it does                                       |
|-------------------------|----------------------------------------------------|
| `read_las_file`         | Header-level summary of a LAS file                 |
| `summarize_las_curves`  | Per-curve min, max, mean, stddev, gap percentage   |
| `read_las_curve`        | Depths and values for one curve, with sampling cap |
| `qc_a_well_log` prompt  | Walks Claude through a standard QC pass            |

DLIS, SEG-Y, and pump card support land in subsequent releases.

## Status

v0.1 ships the LAS slice. The remaining formats are tracked in
[SPEC_petromcp.md](SPEC_petromcp.md). The non-goals list there is real;
read it before filing feature requests.

## License

MIT.
```

- [ ] **Step 6: Verify links and commit**

```bash
uv run ruff check . && uv run pyright && uv run pytest
git add docs README.md
git commit -m "docs: privacy doc, install, supported formats, tools reference"
```

---

## Task 15: End-to-end smoke against Claude Desktop

This task is manual. No commit unless something gets fixed.

- [ ] **Step 1: Generate the synthetic well**

```bash
uv run python -m examples.sample_data.generate
```

Confirm `examples/sample_data/synthetic_well_01.las` exists.

- [ ] **Step 2: Configure the allowlist**

```bash
mkdir -p ~/.petromcp
cat > ~/.petromcp/config.json <<'JSON'
{
  "allowed_paths": ["__REPO__/examples/sample_data"]
}
JSON
sed -i '' "s|__REPO__|$(pwd)|" ~/.petromcp/config.json
```

- [ ] **Step 3: Install into Claude Desktop**

```bash
uv run petromcp install --client claude-desktop
```

Restart Claude Desktop.

- [ ] **Step 4: Manual exercise**

In a new Claude Desktop conversation:

1. Open the `qc_a_well_log` prompt from the picker.
2. Provide the path to `synthetic_well_01.las`.
3. Confirm Claude calls `read_las_file`, then `summarize_las_curves`, and
   flags the deliberate RHOB gap.
4. Ask Claude to pull the GR curve between 5500 and 5600 ft. Confirm
   `read_las_curve` returns no more than 200 points and matches the depth
   range.
5. Ask Claude to read a path outside `allowed_paths`. Confirm the server
   returns the documented error and Claude reports it back.

If any of those fail, fix and recommit. If all pass, mark the
Definition-of-Done checklist in `.claude/PROJECT_CONTEXT.md` and append an
entry to `.claude/WORKLOG.md`.

- [ ] **Step 5: Final tag**

```bash
git tag 0.1.0
```

(No `v` prefix — per project convention.)

---

## Self-review notes (for the implementer)

The plan above covers every Definition-of-Done item from the design doc.
Type names line up across tasks: `LASSummary`, `CurveSummary`, `CurveData`,
`DepthRange`, `CurveStats`, `CurveInfo`, `GapSummary`. Method names are
consistent: `read_las_file`, `summarize_las_curves`, `read_las_curve`,
`validate_path`, `downsample`, `load_config`, `install_into_config`,
`uninstall_from_config`, `build_app`. The allowlist plumbs through every
file-reading entry point.

Two deliberate omissions, flagged for a later slice:

- The `--temp-allow` flag mentioned in the validator's error message is not
  implemented in v0.1. The error text still references it because it points
  the user at a future release; if it bothers you, soften the wording in
  Task 3 to drop the flag mention.
- The "weekly CI job that floats the FastMCP pin" is described in
  CLAUDE.md but not yet implemented. Add when DLIS lands; not worth the
  workflow complexity for a single dependency in v0.1.

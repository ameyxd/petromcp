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
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=start)  # type: ignore[arg-type]
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=stop)  # type: ignore[arg-type]
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=step)  # type: ignore[arg-type]
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)  # type: ignore[arg-type]

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

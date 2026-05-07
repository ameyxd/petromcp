"""LAS file tools. Thin wrappers over `lasio` returning Pydantic models.

Every tool entry point validates its path through the allowlist before
touching disk. Outputs are token-budgeted: `read_las_file` returns header
metadata only, `summarize_las_curves` returns per-curve stats, and
`read_las_curve` returns up to 500 samples by default.
"""

from __future__ import annotations

from collections.abc import Sequence
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
from petromcp.utils.access_log import log_access
from petromcp.utils.path_validator import validate_path
from petromcp.utils.summarizer import downsample

DEFAULT_SAMPLE_CAP = 500


def _open(
    path: str, allowed: Sequence[Path | str], tool: str
) -> tuple[Path, lasio.LASFile]:
    resolved = validate_path(path, allowed)
    log_access(tool, resolved)
    return resolved, lasio.read(str(resolved))


def _header_value(las: lasio.LASFile, key: str) -> str | None:
    item = las.well.get(key) if hasattr(las.well, "get") else None  # type: ignore[attr-defined]
    if item is None:
        return None
    value = getattr(item, "value", None)
    return str(value) if value not in (None, "") else None


def _depth_units(las: lasio.LASFile) -> str:
    strt = las.well.get("STRT") if hasattr(las.well, "get") else None  # type: ignore[attr-defined]
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


def read_las_file(path: str, allowed_paths: Sequence[Path | str]) -> LASSummary:
    """Return header-level metadata about a LAS file. No curve data."""
    _, las = _open(path, allowed_paths, "read_las_file")
    depth = las.index  # type: ignore[attr-defined]
    step = float(getattr(las.well.get("STEP"), "value", 0.0)) if hasattr(las.well, "get") else 0.0  # type: ignore[attr-defined]

    curves: list[CurveInfo] = []
    for c in las.curves:  # type: ignore[attr-defined]
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


def summarize_las_curves(path: str, allowed_paths: Sequence[Path | str]) -> CurveSummary:
    """Per-curve summary statistics across the full file."""
    _, las = _open(path, allowed_paths, "summarize_las_curves")
    depth = np.asarray(las.index, dtype=float)  # type: ignore[attr-defined]
    total = len(depth)

    rows: list[CurveStats] = []
    for c in las.curves:  # type: ignore[attr-defined]
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


def read_las_curve(
    path: str,
    curve_name: str,
    depth_range: DepthRange | None = None,
    allowed_paths: Sequence[Path | str] | None = None,
) -> CurveData:
    """Return depth + value arrays for one curve.

    Default behaviour returns a downsampled view (every Nth point) capped at
    `DEFAULT_SAMPLE_CAP` samples. An explicit `depth_range` returns every
    point inside that range with no downsampling.
    """
    if allowed_paths is None:
        raise ValueError("allowed_paths is required")

    _, las = _open(path, allowed_paths, "read_las_curve")
    if curve_name not in las.curves:
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

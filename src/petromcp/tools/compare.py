"""Pure LAS-on-LAS comparison tool.

Both paths route through `validate_path` before either file is opened.
Each file is opened with `lasio.read` and inspected for header fields,
curve list, and depth range. Comparison is strict: case-sensitive curve
mnemonics, exact-string units. False mismatches that surface in real-world
use can be addressed with a normalisation layer later.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import lasio

from petromcp.models.compare import ComparisonReport, CurveDiff
from petromcp.models.shared import DepthRange
from petromcp.utils.access_log import log_access
from petromcp.utils.lasio_open import read_lasio, safe_index
from petromcp.utils.path_validator import validate_path


def _open(path: str, allowed: Sequence[Path | str]) -> tuple[Path, lasio.LASFile]:
    resolved = validate_path(path, allowed)
    log_access("compare_well_logs", resolved)
    return resolved, read_lasio(resolved)


def _well_name(las: lasio.LASFile) -> str | None:
    item = las.well.get("WELL") if hasattr(las.well, "get") else None  # type: ignore[attr-defined]
    if item is None:
        return None
    value = getattr(item, "value", None)
    return str(value) if value not in (None, "") else None


def _operator(las: lasio.LASFile) -> str | None:
    item = las.well.get("COMP") if hasattr(las.well, "get") else None  # type: ignore[attr-defined]
    if item is None:
        return None
    value = getattr(item, "value", None)
    return str(value) if value not in (None, "") else None


def _curves(las: lasio.LASFile) -> dict[str, str | None]:
    """Return {mnemonic: units} for non-DEPT curves."""
    return {
        str(c.mnemonic): (str(c.unit) if c.unit else None)
        for c in las.curves  # type: ignore[attr-defined]
        if c.mnemonic != "DEPT"
    }


def _depth_range(las: lasio.LASFile) -> DepthRange | None:
    """Depth extent of the file, or None when it carries no curve data."""
    depth = safe_index(las)
    if len(depth) == 0:
        return None
    return DepthRange(start=float(depth[0]), stop=float(depth[-1]))


def _intersect(a: DepthRange | None, b: DepthRange | None) -> DepthRange | None:
    if a is None or b is None:
        return None
    lo = max(a.start, b.start)
    hi = min(a.stop, b.stop)
    if lo > hi:
        return None
    return DepthRange(start=lo, stop=hi)


def compare_well_logs(
    path_a: str,
    path_b: str,
    allowed_paths: Sequence[Path | str],
) -> ComparisonReport:
    """Compare two LAS files. See `ComparisonReport` for the output shape."""
    _, las_a = _open(path_a, allowed_paths)
    _, las_b = _open(path_b, allowed_paths)

    name_a = _well_name(las_a)
    name_b = _well_name(las_b)
    op_a = _operator(las_a)
    op_b = _operator(las_b)

    curves_a = _curves(las_a)
    curves_b = _curves(las_b)
    set_a = set(curves_a)
    set_b = set(curves_b)

    common = sorted(set_a & set_b)
    unique_a = sorted(set_a - set_b)
    unique_b = sorted(set_b - set_a)

    range_a = _depth_range(las_a)
    range_b = _depth_range(las_b)
    overlap = _intersect(range_a, range_b)

    unit_diffs: list[CurveDiff] = []
    for name in common:
        ua = curves_a[name]
        ub = curves_b[name]
        unit_diffs.append(
            CurveDiff(
                name=name,
                in_a=True,
                in_b=True,
                units_a=ua,
                units_b=ub,
                units_match=(ua == ub),
            )
        )

    flags: list[str] = []
    # Distinguish "the intervals don't touch" from "one file has no curve
    # data at all" — the second is a broken file, not a geological finding.
    for label, rng in (("A", range_a), ("B", range_b)):
        if rng is None:
            flags.append(f"{label} has no depth data (truncated or empty LAS)")
    if overlap is None and range_a is not None and range_b is not None:
        flags.append("no depth overlap")
    if op_a and op_b and op_a != op_b:
        flags.append(f"different operators ({op_a} vs {op_b})")
    for u in unit_diffs:
        if not u.units_match:
            flags.append(f"unit mismatch on {u.name} ({u.units_a} vs {u.units_b})")
    for n in unique_a:
        flags.append(f"curve {n} present in A only")
    for n in unique_b:
        flags.append(f"curve {n} present in B only")

    return ComparisonReport(
        well_a=name_a,
        well_b=name_b,
        common_curves=common,
        unique_to_a=unique_a,
        unique_to_b=unique_b,
        depth_overlap=overlap,
        unit_diffs=unit_diffs,
        flags=flags,
    )

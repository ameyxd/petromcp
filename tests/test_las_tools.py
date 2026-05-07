from pathlib import Path

import pytest

from petromcp.models.shared import DepthRange
from petromcp.tools.las import read_las_curve, read_las_file, summarize_las_curves
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


def test_summarize_las_curves_stats(tiny_las: Path, allowlist: list[Path]) -> None:
    s = summarize_las_curves(str(tiny_las), allowlist)
    names = {c.name for c in s.curves}
    assert {"GR", "RHOB"} <= names
    gr = next(c for c in s.curves if c.name == "GR")
    assert gr.min is not None and gr.max is not None and gr.max > gr.min
    assert gr.mean is not None
    assert gr.stddev is not None and gr.stddev >= 0.0
    assert 0.0 <= gr.gap_percentage <= 100.0


def test_read_las_curve_default_caps_at_500(
    tmp_path: Path, allowlist: list[Path]
) -> None:
    # Build a larger LAS so capping is exercised.
    import lasio
    import numpy as np

    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value="BIG")  # type: ignore[arg-type]
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=0.0)  # type: ignore[arg-type]
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=999.0)  # type: ignore[arg-type]
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=1.0)  # type: ignore[arg-type]
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)  # type: ignore[arg-type]
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

from pathlib import Path

import pytest

from petromcp.tools.las import read_las_file, summarize_las_curves
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

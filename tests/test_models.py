import pytest
from pydantic import ValidationError

from petromcp.models.compare import ComparisonReport, CurveDiff
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


def test_from_optional_returns_none_when_both_omitted() -> None:
    assert DepthRange.from_optional(None, None) is None


def test_from_optional_builds_range_when_both_given() -> None:
    r = DepthRange.from_optional(5000.0, 5100.0)
    assert r == DepthRange(start=5000.0, stop=5100.0)


@pytest.mark.parametrize(
    ("start", "stop"),
    [(5000.0, None), (None, 5100.0)],
)
def test_from_optional_rejects_half_specified_interval(
    start: float | None, stop: float | None
) -> None:
    """A half-given interval used to be silently dropped back to a 500-sample
    downsample, so the caller got a whole-well view believing it was their
    interval. Fail loudly instead."""
    with pytest.raises(ValueError, match="both"):
        DepthRange.from_optional(start, stop)


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


def test_curve_diff_is_frozen() -> None:
    d = CurveDiff(
        name="GR", in_a=True, in_b=True, units_a="GAPI", units_b="GAPI", units_match=True
    )
    with pytest.raises(ValidationError):
        d.name = "X"  # type: ignore[misc]


def test_comparison_report_minimal() -> None:
    r = ComparisonReport(
        well_a="A",
        well_b="B",
        common_curves=["GR"],
        unique_to_a=[],
        unique_to_b=["RHOB"],
        depth_overlap=None,
        unit_diffs=[],
        flags=["no depth overlap"],
    )
    assert r.flags == ["no depth overlap"]
    assert r.depth_overlap is None

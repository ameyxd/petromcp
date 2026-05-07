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

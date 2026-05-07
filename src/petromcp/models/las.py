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

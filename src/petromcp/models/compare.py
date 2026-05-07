"""Pydantic models for the well-log comparison tool. Frozen. No I/O."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from petromcp.models.shared import DepthRange


class CurveDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    in_a: bool
    in_b: bool
    units_a: str | None = None
    units_b: str | None = None
    units_match: bool


class ComparisonReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    well_a: str | None
    well_b: str | None
    common_curves: list[str]
    unique_to_a: list[str]
    unique_to_b: list[str]
    depth_overlap: DepthRange | None
    unit_diffs: list[CurveDiff]
    flags: list[str]

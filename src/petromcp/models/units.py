"""Pydantic models for unit-conversion tool outputs. Frozen. No I/O."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnitPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_unit: str
    to_unit: str
    quantity: str


class SupportedUnits(BaseModel):
    model_config = ConfigDict(frozen=True)

    pairs: list[UnitPair]

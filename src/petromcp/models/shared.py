"""Shared model types reused across formats."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class DepthRange(BaseModel):
    """A depth interval. `start` must be <= `stop`."""

    model_config = ConfigDict(frozen=True)

    start: float
    stop: float

    @model_validator(mode="after")
    def _check_order(self) -> DepthRange:
        if self.start > self.stop:
            raise ValueError("DepthRange.start must be <= stop")
        return self

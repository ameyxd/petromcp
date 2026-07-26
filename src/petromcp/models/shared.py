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

    @classmethod
    def from_optional(cls, start: float | None, stop: float | None) -> DepthRange | None:
        """Build a range from a pair of optional tool arguments.

        Returns None when neither endpoint is given (the caller wants the
        default whole-curve view). Raises when exactly one is given: a
        half-specified interval is a caller mistake, and silently falling
        back to the downsampled whole-curve view hands back a different
        answer than the one that was asked for.
        """
        if start is None and stop is None:
            return None
        if start is None or stop is None:
            raise ValueError(
                "depth_start and depth_stop must both be given, or both omitted. "
                f"Got depth_start={start!r}, depth_stop={stop!r}."
            )
        return cls(start=start, stop=stop)

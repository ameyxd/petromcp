"""Ground-truth manifest for a generated synthetic well.

The generator writes one of these beside every LAS it produces, recording the
bed sequence and every defect it injected. The eval asserts against this file
rather than carrying its own copy of the expectations, so the two cannot
drift apart.

The manifest is only as useful as it is honest. `tests/test_generator.py`
reads a generated LAS back and checks the file really does contain what the
manifest claims; that test is the reason anything here can be trusted.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

#: Defect kinds the generator can inject. `unit_mismatch` and `missing_curve`
#: act on the header and curve set rather than on sample values, but they are
#: recorded in the same shape so consumers handle one type.
DefectKind = Literal[
    "null_gap",
    "washout",
    "spike",
    "flatline",
    "unit_mismatch",
    "missing_curve",
]

#: Kinds that occupy a depth interval, and so must carry `top` and `base`.
_INTERVAL_KINDS: frozenset[str] = frozenset({"null_gap", "washout", "flatline"})

#: Kinds that name a single curve. `washout` is excluded: it is a hole
#: condition affecting CALI and RHOB together, not one curve's defect.
_CURVE_KINDS: frozenset[str] = frozenset(
    {"null_gap", "spike", "flatline", "unit_mismatch", "missing_curve"}
)


class DepthAxis(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: float
    stop: float
    step: float
    units: str

    @model_validator(mode="after")
    def _check(self) -> DepthAxis:
        if self.start > self.stop:
            raise ValueError("DepthAxis.start must be <= stop")
        if self.step <= 0:
            raise ValueError("DepthAxis.step must be positive")
        return self


class Bed(BaseModel):
    """One bed in the generated sequence. `base` is deeper than `top`."""

    model_config = ConfigDict(frozen=True)

    top: float
    base: float
    facies: str

    @model_validator(mode="after")
    def _check(self) -> Bed:
        if self.top > self.base:
            raise ValueError("Bed.top must be <= base")
        return self


class DefectRecord(BaseModel):
    """One injected defect, in enough detail for the eval to look for it."""

    model_config = ConfigDict(frozen=True)

    kind: DefectKind
    curve: str | None = None
    top: float | None = None
    base: float | None = None
    magnitude: float | None = None
    declared_unit: str | None = None

    @model_validator(mode="after")
    def _check_required_fields_for_kind(self) -> DefectRecord:
        if self.kind in _INTERVAL_KINDS and (self.top is None or self.base is None):
            raise ValueError(f"{self.kind} requires top and base")
        if self.top is not None and self.base is not None and self.top > self.base:
            raise ValueError("DefectRecord.top must be <= base")
        if self.kind in _CURVE_KINDS and not self.curve:
            raise ValueError(f"{self.kind} requires a curve")
        if self.kind == "spike" and self.top is None:
            raise ValueError("spike requires top (the depth of the spike)")
        if self.kind == "unit_mismatch" and not self.declared_unit:
            raise ValueError("unit_mismatch requires declared_unit")
        return self


class WellTruth(BaseModel):
    model_config = ConfigDict(frozen=True)

    well: str
    seed: int
    depth: DepthAxis
    curves: list[str]
    beds: list[Bed]
    defects: list[DefectRecord]
    #: Frame name -> channel names, for formats that group curves into frames.
    #: Empty for LAS, which has one flat curve set. DLIS uses it, and it is what
    #: lets the eval assert the structure and not just the values.
    frames: dict[str, list[str]] = {}
    #: Frame name -> that frame's index channel. RP66 forbids sharing a channel
    #: between frames, so each frame has its own and the names differ.
    frame_indexes: dict[str, str] = {}

    def defects_for(self, kind: DefectKind) -> list[DefectRecord]:
        return [d for d in self.defects if d.kind == kind]

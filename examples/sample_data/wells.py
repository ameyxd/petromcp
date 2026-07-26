"""Synthetic well definitions.

Two wells, specified so that cross-well comparison has real findings rather
than needing contrived assertions:

- **SYNTH-01** — the reference well. Full triple combo, three single-well
  defects for the QC eval to find.
- **SYNTH-02** — an offset well. Overlaps SYNTH-01 in depth but does not match
  it: no sonic, and a neutron curve whose header lies about its units.

`compare_well_logs` on the pair should therefore report a partial depth
overlap, DT present in one well only, and a NPHI unit mismatch. Each of those
is a finding because it was put here on purpose, and the emitted manifest says
so.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from examples.sample_data.defects import (
    flatline,
    missing_curve,
    null_gap,
    spike,
    unit_mismatch,
    washout,
)
from examples.sample_data.truth import DefectRecord

#: Canonical units for a triple-combo curve set. A `unit_mismatch` defect
#: record overrides an entry at write time, and is the only thing that does —
#: the declared unit lives in one place so the file and the manifest agree.
CURVE_UNITS: dict[str, str] = {
    "GR": "GAPI",
    "RHOB": "g/cm3",
    "NPHI": "v/v",
    "DT": "us/ft",
    "CALI": "in",
}

CURVE_DESCRIPTIONS: dict[str, str] = {
    "GR": "Gamma Ray",
    "RHOB": "Bulk Density",
    "NPHI": "Neutron Porosity",
    "DT": "Sonic Transit Time",
    "CALI": "Caliper",
}

#: Signature of a defect plan: mutate the curve dict, return what was done.
DefectPlan = Callable[[dict[str, np.ndarray], np.ndarray], list[DefectRecord]]


@dataclass(frozen=True)
class WellSpec:
    name: str
    operator: str
    start: float
    stop: float
    step: float
    seed: int
    apply_defects: DefectPlan
    depth_units: str = "ft"


def _synth_01_defects(
    curves: dict[str, np.ndarray], depth: np.ndarray
) -> list[DefectRecord]:
    """Three problems a petrophysicist would flag on a single log."""
    return [
        # Density tool dropped out over a 40 ft interval.
        null_gap(curves, depth, "RHOB", 6600.0, 6640.0),
        # Enlarged hole: caliper opens, density reads light.
        washout(curves, depth, 7210.0, 7255.0),
        # Single non-physical gamma ray sample.
        spike(curves, depth, "GR", 5820.0, magnitude=410.0),
    ]


def _synth_02_defects(
    curves: dict[str, np.ndarray], depth: np.ndarray
) -> list[DefectRecord]:
    """Problems that only surface when compared against the reference well."""
    return [
        # No sonic was run on this well.
        missing_curve(curves, "DT"),
        # Header claims percent; the values are fractional. Invisible in one
        # file, obvious when compared against SYNTH-01.
        unit_mismatch("NPHI", declared_unit="%"),
        # Caliper stopped responding for 30 ft.
        flatline(curves, depth, "CALI", 6000.0, 6030.0),
    ]


WELLS: dict[str, WellSpec] = {
    "SYNTH-01": WellSpec(
        name="SYNTH-01",
        operator="petromcp synthetic",
        start=5000.0,
        stop=9000.0,
        step=0.5,
        seed=42,
        apply_defects=_synth_01_defects,
    ),
    "SYNTH-02": WellSpec(
        name="SYNTH-02",
        operator="petromcp synthetic",
        start=5200.0,
        stop=8600.0,
        step=0.5,
        seed=43,
        apply_defects=_synth_02_defects,
    ),
}

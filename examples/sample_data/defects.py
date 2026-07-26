"""Defect injectors for synthetic wells.

Each function makes one recognisable, real-world log problem and returns a
`DefectRecord` describing precisely what it did. Those records become the
ground-truth manifest the eval asserts against, so an injector that does more
than its record claims would make the manifest a lie. Tests cover both halves:
the change happened, and nothing outside the interval moved.

Interval bounds are inclusive on both ends, matching how a petrophysicist
reads a depth range off a log.

The array-level injectors mutate the curve dict in place. That is deliberate —
several defects are applied in sequence to one well — but it means callers
should not share arrays between wells.
"""

from __future__ import annotations

import numpy as np

from examples.sample_data.truth import DefectRecord

#: The conventional LAS absent-value marker, declared in `~Well` as NULL.
NULL_VALUE = -999.25

#: How far a washed-out hole reads above bit size, inches.
_WASHOUT_ENLARGEMENT_IN = 1.8
#: Density deficit in a washout. Enough to be obvious, small enough to stay
#: above the 1.8 g/cm3 floor `qc_a_well_log` flags, so the injected defect
#: shows up as a hole-condition problem rather than as impossible data.
_WASHOUT_DENSITY_DEFICIT = 0.35


def _interval(depth: np.ndarray, top: float, base: float) -> np.ndarray:
    return (depth >= top) & (depth <= base)


def _require(curves: dict[str, np.ndarray], curve: str) -> None:
    if curve not in curves:
        raise KeyError(f"curve {curve!r} is not in the generated set: {sorted(curves)}")


def null_gap(
    curves: dict[str, np.ndarray],
    depth: np.ndarray,
    curve: str,
    top: float,
    base: float,
) -> DefectRecord:
    """Blank an interval of one curve, as a tool failure or an edited log would."""
    _require(curves, curve)
    curves[curve] = curves[curve].astype(float)
    curves[curve][_interval(depth, top, base)] = NULL_VALUE
    return DefectRecord(kind="null_gap", curve=curve, top=top, base=base)


def washout(
    curves: dict[str, np.ndarray],
    depth: np.ndarray,
    top: float,
    base: float,
) -> DefectRecord:
    """Enlarge the hole and degrade density over an interval.

    A washout is a hole condition, not one curve's defect: the caliper opens
    up and the density tool loses formation contact, so it reads light. Both
    curves move together, which is what makes it diagnosable.
    """
    for curve in ("CALI", "RHOB"):
        _require(curves, curve)
    mask = _interval(depth, top, base)
    curves["CALI"] = curves["CALI"].astype(float)
    curves["RHOB"] = curves["RHOB"].astype(float)
    curves["CALI"][mask] += _WASHOUT_ENLARGEMENT_IN
    curves["RHOB"][mask] -= _WASHOUT_DENSITY_DEFICIT
    return DefectRecord(kind="washout", top=top, base=base)


def spike(
    curves: dict[str, np.ndarray],
    depth: np.ndarray,
    curve: str,
    at_depth: float,
    magnitude: float,
) -> DefectRecord:
    """Set a single sample to a non-physical value.

    The spike lands on the sample nearest `at_depth`, and the record reports
    that sample's depth rather than the request, so the manifest names a depth
    that exists in the file.
    """
    _require(curves, curve)
    idx = int(np.argmin(np.abs(depth - at_depth)))
    curves[curve] = curves[curve].astype(float)
    curves[curve][idx] = magnitude
    return DefectRecord(
        kind="spike",
        curve=curve,
        top=float(depth[idx]),
        base=float(depth[idx]),
        magnitude=magnitude,
    )


def flatline(
    curves: dict[str, np.ndarray],
    depth: np.ndarray,
    curve: str,
    top: float,
    base: float,
) -> DefectRecord:
    """Hold a curve constant over an interval, as a stuck tool would.

    The held value is the reading at the top of the interval: a tool that
    stops responding repeats its last good sample.
    """
    _require(curves, curve)
    mask = _interval(depth, top, base)
    if mask.any():
        curves[curve] = curves[curve].astype(float)
        curves[curve][mask] = float(curves[curve][np.argmax(mask)])
    return DefectRecord(kind="flatline", curve=curve, top=top, base=base)


def missing_curve(curves: dict[str, np.ndarray], curve: str) -> DefectRecord:
    """Drop a curve a complete triple combo would carry."""
    _require(curves, curve)
    del curves[curve]
    return DefectRecord(kind="missing_curve", curve=curve)


def unit_mismatch(curve: str, declared_unit: str) -> DefectRecord:
    """Record that a curve should be *written* with the wrong unit.

    No values change: the numbers stay correct and only the header lies. That
    is why this defect is invisible inside one file and only surfaces when two
    wells are compared — which is exactly the case eval scenario 02 covers.
    Applying it is the writer's job, from this record.
    """
    return DefectRecord(kind="unit_mismatch", curve=curve, declared_unit=declared_unit)

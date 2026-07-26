"""Ground-truth manifest model.

The manifest is what the eval asserts against, so it is the one artefact that
must never overstate what the generator did. These tests cover the model;
`test_generator.py` covers the stronger claim that a written manifest matches
the LAS file beside it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from examples.sample_data.truth import Bed, DefectRecord, DepthAxis, WellTruth


def _axis() -> DepthAxis:
    return DepthAxis(start=5000.0, stop=9000.0, step=0.5, units="ft")


def test_depth_axis_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        DepthAxis(start=9000.0, stop=5000.0, step=0.5, units="ft")


def test_depth_axis_rejects_non_positive_step() -> None:
    with pytest.raises(ValidationError):
        DepthAxis(start=5000.0, stop=9000.0, step=0.0, units="ft")


def test_bed_rejects_inverted_interval() -> None:
    with pytest.raises(ValidationError):
        Bed(top=5100.0, base=5000.0, facies="shale")


def test_defect_record_requires_a_known_kind() -> None:
    with pytest.raises(ValidationError):
        DefectRecord(kind="not_a_real_defect")


def test_interval_defect_requires_its_interval() -> None:
    """A null_gap with no interval would let the eval assert nothing."""
    with pytest.raises(ValidationError, match="top and base"):
        DefectRecord(kind="null_gap", curve="RHOB")


def test_curve_scoped_defect_requires_a_curve() -> None:
    with pytest.raises(ValidationError, match="curve"):
        DefectRecord(kind="null_gap", top=6600.0, base=6640.0)


def test_washout_needs_no_curve() -> None:
    """Washout is a hole condition, not a curve defect: it affects CALI and
    RHOB together, so the record carries the interval only."""
    d = DefectRecord(kind="washout", top=7210.0, base=7255.0)
    assert d.curve is None


def test_unit_mismatch_requires_declared_unit() -> None:
    with pytest.raises(ValidationError, match="declared_unit"):
        DefectRecord(kind="unit_mismatch", curve="NPHI")


def test_missing_curve_needs_only_a_curve() -> None:
    d = DefectRecord(kind="missing_curve", curve="DT")
    assert d.top is None and d.base is None


def test_manifest_round_trips_through_json() -> None:
    truth = WellTruth(
        well="SYNTH-01",
        seed=42,
        depth=_axis(),
        curves=["GR", "RHOB"],
        beds=[Bed(top=5000.0, base=5032.5, facies="shale")],
        defects=[DefectRecord(kind="null_gap", curve="RHOB", top=6600.0, base=6640.0)],
    )
    assert WellTruth.model_validate_json(truth.model_dump_json()) == truth


def test_manifest_is_frozen() -> None:
    truth = WellTruth(well="W", seed=1, depth=_axis(), curves=[], beds=[], defects=[])
    with pytest.raises(ValidationError):
        truth.well = "X"  # type: ignore[misc]


def test_defects_for_selects_by_kind() -> None:
    """The eval asks 'what null gaps did you inject' constantly; make it a
    method rather than a comprehension repeated at every call site."""
    truth = WellTruth(
        well="W",
        seed=1,
        depth=_axis(),
        curves=["RHOB", "CALI"],
        beds=[],
        defects=[
            DefectRecord(kind="null_gap", curve="RHOB", top=6600.0, base=6640.0),
            DefectRecord(kind="washout", top=7210.0, base=7255.0),
        ],
    )
    assert [d.curve for d in truth.defects_for("null_gap")] == ["RHOB"]
    assert truth.defects_for("spike") == []

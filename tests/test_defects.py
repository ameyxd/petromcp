"""Defect injectors.

Each injector must do exactly what its record claims and nothing else. The
"nothing else" half matters as much as the first: a washout that quietly
altered GR outside its interval would make the eval assert against a file
that does not match its manifest.
"""

from __future__ import annotations

import numpy as np
import pytest

from examples.sample_data.defects import (
    NULL_VALUE,
    flatline,
    missing_curve,
    null_gap,
    spike,
    unit_mismatch,
    washout,
)
from examples.sample_data.facies import BIT_SIZE, depth_axis

START, STOP, STEP = 5000.0, 5100.0, 0.5


def _fixture() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    depth = depth_axis(START, STOP, STEP)
    n = len(depth)
    return depth, {
        "GR": np.full(n, 60.0),
        "RHOB": np.full(n, 2.45),
        "NPHI": np.full(n, 0.18),
        "DT": np.full(n, 80.0),
        "CALI": np.full(n, BIT_SIZE),
    }


def _outside(depth: np.ndarray, top: float, base: float) -> np.ndarray:
    return (depth < top) | (depth > base)


# --- null_gap -----------------------------------------------------------------


def test_null_gap_nulls_its_interval() -> None:
    """Absence is NaN in memory, not the LAS sentinel. Writing -999.25 here
    would be a real value of minus nine hundred in a DLIS channel."""
    depth, curves = _fixture()
    null_gap(curves, depth, "RHOB", 5020.0, 5030.0)
    inside = (depth >= 5020.0) & (depth <= 5030.0)
    assert np.all(np.isnan(curves["RHOB"][inside]))


def test_null_gap_does_not_write_the_las_sentinel_into_the_array() -> None:
    """The LAS encoding belongs to the LAS writer, not the defect injector."""
    depth, curves = _fixture()
    null_gap(curves, depth, "RHOB", 5020.0, 5030.0)
    assert not np.any(curves["RHOB"] == NULL_VALUE)


def test_null_gap_leaves_the_rest_of_the_curve_alone() -> None:
    depth, curves = _fixture()
    null_gap(curves, depth, "RHOB", 5020.0, 5030.0)
    assert np.all(curves["RHOB"][_outside(depth, 5020.0, 5030.0)] == 2.45)


def test_null_gap_leaves_other_curves_alone() -> None:
    depth, curves = _fixture()
    null_gap(curves, depth, "RHOB", 5020.0, 5030.0)
    assert np.all(curves["GR"] == 60.0)


def test_null_gap_record_describes_what_it_did() -> None:
    depth, curves = _fixture()
    rec = null_gap(curves, depth, "RHOB", 5020.0, 5030.0)
    assert (rec.kind, rec.curve, rec.top, rec.base) == ("null_gap", "RHOB", 5020.0, 5030.0)


def test_null_gap_rejects_an_unknown_curve() -> None:
    depth, curves = _fixture()
    with pytest.raises(KeyError):
        null_gap(curves, depth, "NOPE", 5020.0, 5030.0)


# --- washout ------------------------------------------------------------------


def test_washout_opens_the_hole_above_bit_size() -> None:
    depth, curves = _fixture()
    washout(curves, depth, 5040.0, 5055.0)
    inside = (depth >= 5040.0) & (depth <= 5055.0)
    assert np.all(curves["CALI"][inside] > BIT_SIZE)


def test_washout_degrades_density_in_the_enlarged_interval() -> None:
    """A washed-out hole reads too light on density because the tool loses
    contact with the formation."""
    depth, curves = _fixture()
    washout(curves, depth, 5040.0, 5055.0)
    inside = (depth >= 5040.0) & (depth <= 5055.0)
    assert np.all(curves["RHOB"][inside] < 2.45)


def test_washout_leaves_caliper_and_density_outside_untouched() -> None:
    depth, curves = _fixture()
    washout(curves, depth, 5040.0, 5055.0)
    out = _outside(depth, 5040.0, 5055.0)
    assert np.all(curves["CALI"][out] == BIT_SIZE)
    assert np.all(curves["RHOB"][out] == 2.45)


def test_washout_does_not_touch_gamma_ray() -> None:
    depth, curves = _fixture()
    washout(curves, depth, 5040.0, 5055.0)
    assert np.all(curves["GR"] == 60.0)


def test_washout_record_carries_no_curve() -> None:
    depth, curves = _fixture()
    rec = washout(curves, depth, 5040.0, 5055.0)
    assert rec.kind == "washout"
    assert rec.curve is None


def test_washout_keeps_density_physically_plausible() -> None:
    """Degraded, not absurd: the QC prompt flags RHOB below 1.8, and we do not
    want the washout to trip that as well as the caliper."""
    depth, curves = _fixture()
    washout(curves, depth, 5040.0, 5055.0)
    assert curves["RHOB"].min() >= 1.8


# --- spike --------------------------------------------------------------------


def test_spike_affects_exactly_one_sample() -> None:
    depth, curves = _fixture()
    spike(curves, depth, "GR", 5060.0, magnitude=400.0)
    assert int(np.count_nonzero(curves["GR"] != 60.0)) == 1


def test_spike_lands_at_the_nearest_sample_to_the_requested_depth() -> None:
    depth, curves = _fixture()
    spike(curves, depth, "GR", 5060.2, magnitude=400.0)
    idx = int(np.argmax(curves["GR"] != 60.0))
    assert depth[idx] == pytest.approx(5060.0)


def test_spike_record_reports_depth_and_magnitude() -> None:
    depth, curves = _fixture()
    rec = spike(curves, depth, "GR", 5060.0, magnitude=400.0)
    assert rec.kind == "spike"
    assert rec.top == pytest.approx(5060.0)
    assert rec.magnitude == pytest.approx(400.0)


# --- flatline -----------------------------------------------------------------


def test_flatline_makes_the_interval_constant() -> None:
    depth, curves = _fixture()
    curves["DT"] = np.linspace(70.0, 90.0, len(depth))
    flatline(curves, depth, "DT", 5020.0, 5040.0)
    inside = (depth >= 5020.0) & (depth <= 5040.0)
    assert len(np.unique(curves["DT"][inside])) == 1


def test_flatline_holds_the_value_from_the_top_of_the_interval() -> None:
    """A stuck tool repeats its last good reading."""
    depth, curves = _fixture()
    curves["DT"] = np.linspace(70.0, 90.0, len(depth))
    at_top = float(curves["DT"][np.argmax(depth >= 5020.0)])
    flatline(curves, depth, "DT", 5020.0, 5040.0)
    inside = (depth >= 5020.0) & (depth <= 5040.0)
    assert curves["DT"][inside][0] == pytest.approx(at_top)


def test_flatline_leaves_the_rest_varying() -> None:
    depth, curves = _fixture()
    curves["DT"] = np.linspace(70.0, 90.0, len(depth))
    flatline(curves, depth, "DT", 5020.0, 5040.0)
    assert len(np.unique(curves["DT"][_outside(depth, 5020.0, 5040.0)])) > 1


# --- header-level defects -----------------------------------------------------


def test_missing_curve_removes_it_from_the_set() -> None:
    _, curves = _fixture()
    rec = missing_curve(curves, "DT")
    assert "DT" not in curves
    assert (rec.kind, rec.curve) == ("missing_curve", "DT")


def test_missing_curve_rejects_a_curve_that_is_not_there() -> None:
    _, curves = _fixture()
    with pytest.raises(KeyError):
        missing_curve(curves, "NOPE")


def test_unit_mismatch_records_without_altering_values() -> None:
    """The values stay correct; only the declared unit lies. That is what makes
    it findable by cross-well comparison and invisible within one file."""
    _, curves = _fixture()
    before = curves["NPHI"].copy()
    rec = unit_mismatch("NPHI", declared_unit="%")
    assert (rec.kind, rec.curve, rec.declared_unit) == ("unit_mismatch", "NPHI", "%")
    np.testing.assert_array_equal(curves["NPHI"], before)

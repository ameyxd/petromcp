"""Facies-based curve synthesis.

Curves are derived from the standard petrophysical relations rather than
invented shapes, so these tests check the relations hold and that every
output stays physically plausible. The constants themselves are textbook
typical values and are not calibrated to any basin; see the module docstring
in `facies.py`.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from examples.sample_data.facies import (
    FACIES,
    FLUID_DENSITY,
    FLUID_DT,
    build_beds,
    depth_axis,
    dt_from_porosity,
    rhob_from_porosity,
    synthesize_curves,
)

START, STOP, STEP = 5000.0, 6000.0, 0.5


def _curves(seed: int = 42) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    depth = depth_axis(START, STOP, STEP)
    beds = build_beds(START, STOP, seed=seed)
    return depth, synthesize_curves(depth, beds, seed=seed)


# --- the underlying relations -------------------------------------------------


def test_rhob_at_zero_porosity_is_matrix_density() -> None:
    assert rhob_from_porosity(0.0, 2.65) == pytest.approx(2.65)


def test_rhob_at_unit_porosity_is_fluid_density() -> None:
    assert rhob_from_porosity(1.0, 2.65) == pytest.approx(FLUID_DENSITY)


def test_rhob_decreases_as_porosity_rises() -> None:
    assert rhob_from_porosity(0.30, 2.65) < rhob_from_porosity(0.10, 2.65)


def test_rhob_is_linear_in_porosity() -> None:
    """The density-porosity relation is a straight line; the midpoint of two
    porosities must give the midpoint density."""
    lo, hi = rhob_from_porosity(0.10, 2.71), rhob_from_porosity(0.30, 2.71)
    assert rhob_from_porosity(0.20, 2.71) == pytest.approx((lo + hi) / 2)


def test_dt_at_zero_porosity_is_matrix_transit_time() -> None:
    assert dt_from_porosity(0.0, 55.5) == pytest.approx(55.5)


def test_dt_at_unit_porosity_is_fluid_transit_time() -> None:
    assert dt_from_porosity(1.0, 55.5) == pytest.approx(FLUID_DT)


def test_dt_increases_with_porosity() -> None:
    """Sound travels slower through fluid than rock, so transit time rises."""
    assert dt_from_porosity(0.25, 55.5) > dt_from_porosity(0.05, 55.5)


# --- the facies table ---------------------------------------------------------


def test_expected_facies_are_defined() -> None:
    assert set(FACIES) == {"clean_sand", "shaly_sand", "shale", "limestone"}


def test_shale_reads_hotter_than_clean_sand_on_gamma_ray() -> None:
    assert FACIES["shale"].gr_mean > FACIES["clean_sand"].gr_mean


def test_shale_carries_bound_water_and_clean_facies_do_not() -> None:
    """Bound water is what separates the neutron and density curves in shale;
    without it the synthetic logs lose their most recognisable feature."""
    assert FACIES["shale"].bound_water > 0.0
    assert FACIES["clean_sand"].bound_water == 0.0
    assert FACIES["limestone"].bound_water == 0.0


def test_limestone_matrix_is_denser_than_sandstone_matrix() -> None:
    # Calcite 2.71 vs quartz 2.65 g/cm3.
    assert FACIES["limestone"].matrix_density > FACIES["clean_sand"].matrix_density


@pytest.mark.parametrize("name", ["clean_sand", "shaly_sand", "shale", "limestone"])
def test_every_facies_has_a_sane_porosity_window(name: str) -> None:
    f = FACIES[name]
    assert 0.0 <= f.porosity_min < f.porosity_max < 0.5


# --- bed construction ---------------------------------------------------------


def test_beds_tile_the_interval_without_gaps_or_overlaps() -> None:
    beds = build_beds(START, STOP, seed=7)
    assert beds[0].top == pytest.approx(START)
    assert beds[-1].base == pytest.approx(STOP)
    for earlier, later in pairwise(beds):
        assert later.top == pytest.approx(earlier.base)


def test_bed_facies_are_all_from_the_table() -> None:
    assert {b.facies for b in build_beds(START, STOP, seed=7)} <= set(FACIES)


def test_bed_sequence_alternates_rather_than_repeating_one_facies() -> None:
    """A transition matrix, not a coin flip: a 1000 ft section should not come
    back as a single bed or as one facies throughout."""
    beds = build_beds(START, STOP, seed=7)
    assert len(beds) > 3
    assert len({b.facies for b in beds}) > 1


def test_build_beds_is_deterministic_for_a_seed() -> None:
    a = build_beds(START, STOP, seed=11)
    b = build_beds(START, STOP, seed=11)
    assert a == b


def test_different_seeds_give_different_bed_sequences() -> None:
    assert build_beds(START, STOP, seed=1) != build_beds(START, STOP, seed=2)


# --- synthesized curves -------------------------------------------------------


def test_synthesizes_the_expected_triple_combo_curve_set() -> None:
    _, curves = _curves()
    assert set(curves) == {"GR", "RHOB", "NPHI", "DT", "CALI"}


def test_every_curve_matches_the_depth_axis_length() -> None:
    depth, curves = _curves()
    for name, values in curves.items():
        assert len(values) == len(depth), name


@pytest.mark.parametrize(
    ("curve", "low", "high"),
    [
        ("GR", 0.0, 300.0),
        ("RHOB", 1.8, 3.0),
        ("NPHI", 0.0, 1.0),
        ("DT", 30.0, 200.0),
        ("CALI", 4.0, 20.0),
    ],
)
def test_curve_values_stay_physically_plausible(curve: str, low: float, high: float) -> None:
    """These are the same bounds `qc_a_well_log` flags against. Synthetic data
    that violates them would make the QC prompt report defects we did not
    inject."""
    _, curves = _curves()
    values = curves[curve]
    assert np.all(np.isfinite(values)), curve
    assert values.min() >= low, f"{curve} min {values.min()}"
    assert values.max() <= high, f"{curve} max {values.max()}"


def test_gamma_ray_is_higher_in_shale_beds_than_in_clean_sand_beds() -> None:
    """The headline relationship. If this fails the logs are noise."""
    depth = depth_axis(START, STOP, STEP)
    beds = build_beds(START, STOP, seed=42)
    curves = synthesize_curves(depth, beds, seed=42)

    def mean_gr(facies: str) -> float:
        mask = np.zeros(len(depth), dtype=bool)
        for bed in (b for b in beds if b.facies == facies):
            mask |= (depth >= bed.top) & (depth < bed.base)
        return float(curves["GR"][mask].mean()) if mask.any() else float("nan")

    shale, sand = mean_gr("shale"), mean_gr("clean_sand")
    if np.isnan(shale) or np.isnan(sand):
        pytest.skip("seed produced no bed of one facies")
    assert shale > sand


def test_density_and_neutron_separate_in_shale() -> None:
    """Bound water pushes NPHI up while RHOB stays high. Comparing shale to
    clean sand, the neutron-density gap must widen."""
    depth = depth_axis(START, STOP, STEP)
    beds = build_beds(START, STOP, seed=42)
    curves = synthesize_curves(depth, beds, seed=42)

    def mean_nphi(facies: str) -> float:
        mask = np.zeros(len(depth), dtype=bool)
        for bed in (b for b in beds if b.facies == facies):
            mask |= (depth >= bed.top) & (depth < bed.base)
        return float(curves["NPHI"][mask].mean()) if mask.any() else float("nan")

    shale, sand = mean_nphi("shale"), mean_nphi("clean_sand")
    if np.isnan(shale) or np.isnan(sand):
        pytest.skip("seed produced no bed of one facies")
    assert shale > sand


def test_synthesis_is_deterministic_for_a_seed() -> None:
    _, first = _curves(seed=99)
    _, second = _curves(seed=99)
    for name in first:
        np.testing.assert_array_equal(first[name], second[name])


def test_curves_are_smoothed_rather_than_square() -> None:
    """A ~2 ft moving average models tool vertical resolution. Without it bed
    boundaries are vertical steps, which no real log has."""
    _, curves = _curves()
    gr = curves["GR"]
    # Largest single-sample jump should be well under the full shale-to-sand
    # contrast, which a square boundary would produce in one step.
    contrast = FACIES["shale"].gr_mean - FACIES["clean_sand"].gr_mean
    assert np.abs(np.diff(gr)).max() < contrast

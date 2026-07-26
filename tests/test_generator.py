"""Generator and ground-truth manifest agreement.

The eval asserts against the manifest instead of a hand-copied duplicate of
the expectations. That removes drift, but it moves the risk: if the manifest
claims a defect the file does not contain, the eval passes on a lie.

`TestManifestDoesNotLie` is the test that closes that hole. It reads the
written LAS back through the real parser and checks every recorded defect is
actually present. It covers every kind in the catalogue; adding a new defect
kind without extending it should fail `test_every_defect_kind_is_covered`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import lasio
import numpy as np
import pytest

from examples.sample_data.defects import NULL_VALUE
from examples.sample_data.facies import BIT_SIZE
from examples.sample_data.generate import (
    generate,
    generate_well_01,
    generate_well_02,
    truth_path_for,
)
from examples.sample_data.truth import WellTruth
from examples.sample_data.wells import CURVE_UNITS, WELLS


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def wells(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[lasio.LASFile, WellTruth]]:
    """Generate every defined well once and read each back from disk."""
    out = tmp_path_factory.mktemp("wells")
    built: dict[str, tuple[lasio.LASFile, WellTruth]] = {}
    for name, spec in WELLS.items():
        las_path, truth_path = generate(spec, out / f"{name}.las")
        built[name] = (
            lasio.read(str(las_path)),
            WellTruth.model_validate_json(truth_path.read_text()),
        )
    return built


# --- determinism and basic shape ----------------------------------------------


def test_generator_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a.las", tmp_path / "b.las"
    generate_well_01(a, seed=42)
    generate_well_01(b, seed=42)
    assert _digest(a) == _digest(b)


def test_manifest_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a.las", tmp_path / "b.las"
    generate_well_01(a, seed=42)
    generate_well_01(b, seed=42)
    assert _digest(truth_path_for(a)) == _digest(truth_path_for(b))


def test_different_seeds_produce_different_files(tmp_path: Path) -> None:
    a, b = tmp_path / "a.las", tmp_path / "b.las"
    generate_well_01(a, seed=42)
    generate_well_01(b, seed=7)
    assert _digest(a) != _digest(b)


def test_generate_writes_a_manifest_beside_the_las(tmp_path: Path) -> None:
    las = tmp_path / "w.las"
    generate_well_01(las)
    assert truth_path_for(las).exists()


def test_offset_well_generates(tmp_path: Path) -> None:
    las = tmp_path / "w2.las"
    generate_well_02(las)
    assert las.exists() and truth_path_for(las).exists()


class TestManifestDoesNotLie:
    """Every claim in the manifest, checked against the written file."""

    def test_every_defect_kind_is_covered_by_this_class(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        """A new defect kind must not slip in unverified."""
        injected = {d.kind for _, truth in wells.values() for d in truth.defects}
        verified = {
            "null_gap",
            "washout",
            "spike",
            "flatline",
            "unit_mismatch",
            "missing_curve",
        }
        assert injected <= verified, f"unverified defect kinds: {injected - verified}"
        assert injected == verified, f"catalogue kinds never injected: {verified - injected}"

    def test_declared_well_name_matches(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        for name, (las, truth) in wells.items():
            assert str(las.well["WELL"].value) == truth.well == name

    def test_depth_axis_matches(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        for name, (las, truth) in wells.items():
            depth = np.asarray(las.index, dtype=float)
            assert depth[0] == pytest.approx(truth.depth.start), name
            assert depth[-1] == pytest.approx(truth.depth.stop), name
            assert float(depth[1] - depth[0]) == pytest.approx(truth.depth.step), name

    def test_curve_list_matches(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        for name, (las, truth) in wells.items():
            in_file = {str(c.mnemonic) for c in las.curves if c.mnemonic != "DEPT"}
            assert in_file == set(truth.curves), name

    def test_beds_tile_the_declared_depth_range(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        for name, (_, truth) in wells.items():
            assert truth.beds, name
            assert truth.beds[0].top == pytest.approx(truth.depth.start), name
            assert truth.beds[-1].base == pytest.approx(truth.depth.stop), name

    def test_recorded_null_gaps_are_actually_null(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            depth = np.asarray(las.index, dtype=float)
            for d in truth.defects_for("null_gap"):
                assert d.curve and d.top is not None and d.base is not None
                values = np.asarray(las[d.curve], dtype=float)
                inside = (depth >= d.top) & (depth <= d.base)
                # lasio maps the declared NULL to NaN on read.
                assert np.all(
                    np.isnan(values[inside]) | (values[inside] == NULL_VALUE)
                ), f"{name} {d.curve} {d.top}-{d.base} is not null in the file"
                assert not np.all(np.isnan(values)), f"{name} {d.curve} is null everywhere"
                seen += 1
        assert seen, "no null_gap defects were verified"

    def test_recorded_washouts_show_an_enlarged_hole_and_light_density(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            depth = np.asarray(las.index, dtype=float)
            for d in truth.defects_for("washout"):
                assert d.top is not None and d.base is not None
                inside = (depth >= d.top) & (depth <= d.base)
                cali = np.asarray(las["CALI"], dtype=float)
                rhob = np.asarray(las["RHOB"], dtype=float)
                assert np.all(cali[inside] > BIT_SIZE), f"{name} caliper not enlarged"
                # Density inside must read lighter than the well's typical value.
                outside_median = float(np.nanmedian(rhob[~inside]))
                assert float(np.nanmax(rhob[inside])) < outside_median, name
                seen += 1
        assert seen, "no washout defects were verified"

    def test_recorded_spikes_are_present_at_the_recorded_depth(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            depth = np.asarray(las.index, dtype=float)
            for d in truth.defects_for("spike"):
                assert d.curve and d.top is not None and d.magnitude is not None
                values = np.asarray(las[d.curve], dtype=float)
                idx = int(np.argmin(np.abs(depth - d.top)))
                assert values[idx] == pytest.approx(d.magnitude, rel=1e-3), (
                    f"{name} {d.curve} spike missing at {d.top}"
                )
                seen += 1
        assert seen, "no spike defects were verified"

    def test_recorded_flatlines_are_constant_in_the_file(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            depth = np.asarray(las.index, dtype=float)
            for d in truth.defects_for("flatline"):
                assert d.curve and d.top is not None and d.base is not None
                values = np.asarray(las[d.curve], dtype=float)
                inside = values[(depth >= d.top) & (depth <= d.base)]
                assert inside.size > 1, name
                assert np.ptp(inside) == pytest.approx(0.0, abs=1e-9), (
                    f"{name} {d.curve} is not flat over {d.top}-{d.base}"
                )
                seen += 1
        assert seen, "no flatline defects were verified"

    def test_recorded_unit_mismatches_are_the_declared_unit_in_the_header(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            for d in truth.defects_for("unit_mismatch"):
                assert d.curve and d.declared_unit
                unit = next(
                    str(c.unit) for c in las.curves if str(c.mnemonic) == d.curve
                )
                assert unit == d.declared_unit, f"{name} {d.curve} unit {unit!r}"
                assert unit != CURVE_UNITS[d.curve], (
                    f"{name} {d.curve} mismatch is not actually a mismatch"
                )
                seen += 1
        assert seen, "no unit_mismatch defects were verified"

    def test_recorded_missing_curves_are_absent_from_the_file(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        seen = 0
        for name, (las, truth) in wells.items():
            present = {str(c.mnemonic) for c in las.curves}
            for d in truth.defects_for("missing_curve"):
                assert d.curve
                assert d.curve not in present, f"{name} still contains {d.curve}"
                assert d.curve not in truth.curves, f"{name} manifest still lists {d.curve}"
                seen += 1
        assert seen, "no missing_curve defects were verified"


class TestCrossWellSetup:
    """The two wells must actually differ in the ways scenario 02 asserts."""

    def test_depth_ranges_partially_overlap(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        a, b = wells["SYNTH-01"][1], wells["SYNTH-02"][1]
        assert b.depth.start > a.depth.start
        assert b.depth.stop < a.depth.stop

    def test_one_well_is_missing_a_curve_the_other_has(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        a, b = wells["SYNTH-01"][1], wells["SYNTH-02"][1]
        assert set(a.curves) - set(b.curves) == {"DT"}

    def test_the_wells_disagree_on_a_shared_curve_unit(
        self, wells: dict[str, tuple[lasio.LASFile, WellTruth]]
    ) -> None:
        def unit(las: lasio.LASFile, curve: str) -> str:
            return next(str(c.unit) for c in las.curves if str(c.mnemonic) == curve)

        assert unit(wells["SYNTH-01"][0], "NPHI") != unit(wells["SYNTH-02"][0], "NPHI")

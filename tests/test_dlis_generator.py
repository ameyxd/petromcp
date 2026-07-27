"""DLIS generator and manifest agreement.

Same contract as the LAS generator: the eval asserts against the manifest, so
the manifest must never claim more than the file contains. `TestManifestDoesNotLie`
reads each written DLIS back through the real parser and checks every recorded
claim, including the frame layout — which LAS has no equivalent of.

It also checks the reuse claim directly: a DLIS well and a LAS well built from
the same seed must carry the same geology, because both come from the same
facies model. If they diverge, one of the writers is wrong.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from examples.sample_data.dlis_generate import build_well, generate, truth_path_for
from examples.sample_data.dlis_wells import CHANNEL_UNITS, DLIS_WELLS
from examples.sample_data.truth import WellTruth
from petromcp.tools.dlis import list_dlis_channels, read_dlis_channel, read_dlis_file
from petromcp.utils.dlis_open import load_dlis


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def wells(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, tuple[Path, WellTruth]]]:
    """Generate every defined DLIS well once."""
    work = tmp_path_factory.mktemp("dlis_wells")
    built: dict[str, tuple[Path, WellTruth]] = {}
    for name, spec in DLIS_WELLS.items():
        path, manifest = generate(spec, work / f"{name}.dlis")
        built[name] = (path, WellTruth.model_validate_json(manifest.read_text()))
    return work, built


# --- determinism --------------------------------------------------------------


def test_generation_is_deterministic(tmp_path: Path) -> None:
    spec = DLIS_WELLS["DSYNTH-01"]
    a, _ = generate(spec, tmp_path / "a.dlis")
    b, _ = generate(spec, tmp_path / "b.dlis")
    assert _digest(a) == _digest(b)


def test_manifest_is_deterministic(tmp_path: Path) -> None:
    spec = DLIS_WELLS["DSYNTH-01"]
    a, _ = generate(spec, tmp_path / "a.dlis")
    b, _ = generate(spec, tmp_path / "b.dlis")
    assert _digest(truth_path_for(a)) == _digest(truth_path_for(b))


def test_staging_directory_is_cleaned_up(tmp_path: Path) -> None:
    """The multi-logical-file path writes parts then concatenates. Leaving them
    behind would put stray .dlis files next to the real one."""
    generate(DLIS_WELLS["DSYNTH-02"], tmp_path / "w.dlis")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".")]
    assert leftovers == [], f"staging not cleaned: {leftovers}"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["w.dlis", "w.truth.json"]


# --- the reuse claim ----------------------------------------------------------


def test_dlis_and_las_wells_share_the_same_geology() -> None:
    """`facies.py` knows nothing about either format, so the same seed must give
    the same curves. A divergence means one writer is transforming data it
    should be passing through."""
    from examples.sample_data.generate import build_well as build_las
    from examples.sample_data.wells import WELLS

    las_spec = WELLS["SYNTH-01"]
    dlis_spec = DLIS_WELLS["DSYNTH-01"]
    assert las_spec.seed == dlis_spec.seed, "fixture assumption: same seed"

    _, _, las_truth = build_las(las_spec)
    _, _, dlis_truth = build_well(dlis_spec)
    assert [(b.top, b.base, b.facies) for b in las_truth.beds] == [
        (b.top, b.base, b.facies) for b in dlis_truth.beds
    ]


# --- manifest honesty ---------------------------------------------------------


class TestManifestDoesNotLie:
    def test_declared_well_name_matches(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        _, built = wells
        for name, (path, truth) in built.items():
            with load_dlis(path) as batch:
                names = {
                    str(origin.well_name) for lf in batch for origin in lf.origins
                }
            assert truth.well == name
            assert name in names

    def test_logical_file_count_matches_the_spec(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        for name, (path, _) in built.items():
            expected = len(DLIS_WELLS[name].logical_files)
            summary = read_dlis_file(str(path), [work])
            assert len(summary.logical_files) == expected, name

    def test_recorded_frames_are_all_present(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        for name, (path, truth) in built.items():
            summary = read_dlis_file(str(path), [work])
            in_file = {f.name for lf in summary.logical_files for f in lf.frames}
            assert set(truth.frames) == in_file, name

    def test_each_frame_carries_exactly_the_recorded_channels(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        for name, (path, truth) in built.items():
            listing = list_dlis_channels(str(path), [work])
            for frame, channels in truth.frames.items():
                in_frame = {c.name for c in listing.channels if c.frame == frame}
                index = truth.frame_indexes[frame]
                assert in_frame == {*channels, index}, f"{name} {frame}"

    def test_units_match_what_was_declared(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        for name, (path, truth) in built.items():
            listing = list_dlis_channels(str(path), [work])
            for channel in listing.channels:
                if channel.name in CHANNEL_UNITS:
                    assert channel.units == CHANNEL_UNITS[channel.name], (
                        f"{name} {channel.name}"
                    )
                elif channel.name in truth.frame_indexes.values():
                    assert channel.units == truth.depth.units, f"{name} {channel.name}"

    def test_every_defect_kind_injected_is_verified_here(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        """A new defect kind must not slip in unchecked."""
        _, built = wells
        injected = {d.kind for _, truth in built.values() for d in truth.defects}
        verified = {"null_gap", "washout", "spike", "flatline"}
        assert injected == verified, f"unverified: {injected ^ verified}"

    def test_recorded_null_gaps_are_absent_in_the_file(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        seen = 0
        for name, (path, truth) in built.items():
            for defect in truth.defects_for("null_gap"):
                assert defect.curve and defect.top is not None and defect.base is not None
                data = read_dlis_channel(
                    str(path),
                    defect.curve,
                    depth_start=defect.top,
                    depth_stop=defect.base,
                    allowed_paths=[work],
                )
                assert data.values, f"{name} {defect.curve} returned nothing"
                assert all(v is None for v in data.values), (
                    f"{name} {defect.curve} {defect.top}-{defect.base} is not absent"
                )
                seen += 1
        assert seen, "no null_gap defects verified"

    def test_recorded_washouts_show_an_enlarged_hole(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        from examples.sample_data.facies import BIT_SIZE

        work, built = wells
        seen = 0
        for name, (path, truth) in built.items():
            for defect in truth.defects_for("washout"):
                assert defect.top is not None and defect.base is not None
                data = read_dlis_channel(
                    str(path), "CALI",
                    depth_start=defect.top, depth_stop=defect.base,
                    allowed_paths=[work],
                )
                values = [v for v in data.values if v is not None]
                assert values and min(values) > BIT_SIZE, f"{name} caliper not enlarged"
                seen += 1
        assert seen, "no washout defects verified"

    def test_recorded_spikes_are_present_at_the_recorded_depth(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        seen = 0
        for name, (path, truth) in built.items():
            for defect in truth.defects_for("spike"):
                assert defect.curve and defect.top is not None
                assert defect.magnitude is not None
                data = read_dlis_channel(
                    str(path), defect.curve,
                    depth_start=defect.top - 0.25, depth_stop=defect.top + 0.25,
                    allowed_paths=[work],
                )
                values = [v for v in data.values if v is not None]
                assert values, f"{name} spike interval empty"
                assert max(values) == pytest.approx(defect.magnitude, rel=1e-3), name
                seen += 1
        assert seen, "no spike defects verified"

    def test_recorded_flatlines_are_constant_in_the_file(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        seen = 0
        for name, (path, truth) in built.items():
            for defect in truth.defects_for("flatline"):
                assert defect.curve and defect.top is not None and defect.base is not None
                data = read_dlis_channel(
                    str(path), defect.curve,
                    depth_start=defect.top, depth_stop=defect.base,
                    allowed_paths=[work],
                )
                values = np.asarray(
                    [v for v in data.values if v is not None], dtype=float
                )
                assert values.size > 1, f"{name} too few samples to check"
                assert float(np.ptp(values)) == pytest.approx(0.0, abs=1e-9), name
                seen += 1
        assert seen, "no flatline defects verified"

    def test_depth_axis_matches(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        for name, (path, truth) in built.items():
            summary = read_dlis_file(str(path), [work])
            for logical in summary.logical_files:
                for frame in logical.frames:
                    assert frame.depth_range is not None, f"{name} {frame.name}"
                    assert frame.depth_range.start == pytest.approx(
                        truth.depth.start
                    ), f"{name} {frame.name}"


class TestMultiLogicalFileWell:
    """The structure LAS cannot express."""

    def test_has_two_logical_files(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        path, _ = built["DSYNTH-02"]
        assert len(read_dlis_file(str(path), [work]).logical_files) == 2

    def test_each_run_has_its_own_origin(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        path, _ = built["DSYNTH-02"]
        summary = read_dlis_file(str(path), [work])
        ids = [lf.file_id for lf in summary.logical_files]
        assert len(set(ids)) == 2, f"logging runs not distinguishable: {ids}"

    def test_a_channel_can_be_reached_in_the_second_run(
        self, wells: tuple[Path, dict[str, tuple[Path, WellTruth]]]
    ) -> None:
        work, built = wells
        path, _ = built["DSYNTH-02"]
        data = read_dlis_channel(str(path), "CALI", allowed_paths=[work])
        assert data.logical_file == 1
        assert data.frame == "CASED_HOLE"

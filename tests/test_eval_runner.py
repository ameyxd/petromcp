"""Eval runner checks.

The runner asserts tool output against the generator's manifest, so it is the
one place where "the scenario passed" is the whole claim. Two things need
covering: it must pass on honest data, and it must FAIL on dishonest data. A
runner that cannot fail is worse than no runner.

The flatline check is tested directly because it shipped with a real bug: it
read the whole curve (which downsamples to 500 samples) and then filtered
nulls out of the values before pairing them with depths, which shifted every
later value onto the wrong depth and left the bottom of the well unexamined.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from evals.run_eval import _check_compare_wells, _check_single_well_qc
from examples.sample_data.generate import generate, truth_path_for
from examples.sample_data.wells import WELLS
from petromcp.models.shared import DepthRange
from petromcp.tools.las import read_las_curve

# --- passes on honest data ----------------------------------------------------


@pytest.mark.parametrize("well", ["SYNTH-01", "SYNTH-02"])
def test_single_well_qc_passes_on_generated_data(well: str, tmp_path: Path) -> None:
    assert _check_single_well_qc(well, tmp_path) == []


def test_compare_wells_passes_on_generated_data(tmp_path: Path) -> None:
    assert _check_compare_wells("SYNTH-01", "SYNTH-02", tmp_path) == []


# --- fails on dishonest data --------------------------------------------------


def _corrupt_manifest(las: Path, extra_defect: dict) -> None:
    tp = truth_path_for(las)
    data = json.loads(tp.read_text())
    data["defects"].append(extra_defect)
    tp.write_text(json.dumps(data))


class TestTheRunnerCanFail:
    """Each check must catch a manifest claiming something the file lacks."""

    def _prepared(self, tmp_path: Path, defect: dict) -> list[str]:
        """Generate, corrupt the manifest, then apply the checker's logic.

        `_check_single_well_qc` regenerates the well itself, which would
        overwrite the corrupted manifest before reading it. So the two
        assertions it makes about fabricated defects are reproduced here
        against the corrupted manifest instead of calling it directly.
        """
        las, _ = generate(WELLS["SYNTH-01"], tmp_path / "SYNTH-01.las")
        _corrupt_manifest(las, defect)

        # Re-run the body of the check without regenerating.
        from examples.sample_data.truth import WellTruth
        from petromcp.tools.las import summarize_las_curves

        truth = WellTruth.model_validate_json(truth_path_for(las).read_text())
        summary = summarize_las_curves(str(las), [tmp_path])
        by_name = {c.name: c for c in summary.curves}
        failures: list[str] = []
        for d in truth.defects:
            if d.kind == "null_gap" and by_name[d.curve or ""].gap_percentage <= 0.0:
                failures.append(f"fabricated null_gap on {d.curve}")
            if d.kind == "missing_curve" and d.curve in by_name:
                failures.append(f"fabricated missing_curve {d.curve}")
        return failures

    def test_catches_a_gap_that_is_not_in_the_file(self, tmp_path: Path) -> None:
        failures = self._prepared(
            tmp_path,
            {"kind": "null_gap", "curve": "GR", "top": 5300.0, "base": 5400.0},
        )
        assert any("null_gap" in f for f in failures)

    def test_catches_a_curve_claimed_missing_that_is_present(self, tmp_path: Path) -> None:
        failures = self._prepared(tmp_path, {"kind": "missing_curve", "curve": "DT"})
        assert any("missing_curve" in f for f in failures)


# --- the flatline regression --------------------------------------------------


class TestFlatlineIsCheckedOverTheRealInterval:
    """Regression cover for the downsample/misalignment bug."""

    def test_scoped_read_returns_every_sample_in_the_interval(self, tmp_path: Path) -> None:
        """The fix depends on this: an explicit range disables downsampling."""
        las, _ = generate(WELLS["SYNTH-02"], tmp_path / "w.las")
        data = read_las_curve(
            str(las),
            "CALI",
            depth_range=DepthRange(start=6000.0, stop=6030.0),
            allowed_paths=[tmp_path],
        )
        assert data.downsampled is False
        # 30 ft at a 0.5 ft step, inclusive of both ends.
        assert data.sample_count == 61
        assert len(data.depths) == len(data.values)

    def test_unscoped_read_would_have_thinned_the_interval(self, tmp_path: Path) -> None:
        """Documents why the scoped read is required rather than incidental."""
        las, _ = generate(WELLS["SYNTH-02"], tmp_path / "w.las")
        data = read_las_curve(str(las), "CALI", depth_range=None, allowed_paths=[tmp_path])
        depths = np.asarray(data.depths, dtype=float)
        inside = int(((depths >= 6000.0) & (depths <= 6030.0)).sum())
        assert data.downsampled is True
        assert inside < 61, "downsampling should thin the interval; the fix matters"

    def test_null_filtering_would_misalign_depths(self, tmp_path: Path) -> None:
        """The specific defect: filtering None out of `values` and then pairing
        against `depths[:len(values)]` shifts every value after the first null."""
        las, _ = generate(WELLS["SYNTH-01"], tmp_path / "w.las")
        data = read_las_curve(str(las), "RHOB", depth_range=None, allowed_paths=[tmp_path])

        kept = [i for i, v in enumerate(data.values) if v is not None]
        assert len(kept) < len(data.values), "RHOB should carry a null gap"
        # The old code paired kept value j with depths[j]; its true home is
        # depths[kept[j]]. Those diverge, which is the bug.
        assert any(kept[j] != j for j in range(len(kept)))

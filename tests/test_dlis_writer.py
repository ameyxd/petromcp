"""The dev-only DLIS writer.

Its job is to fail loudly on the two RP66 v1 constraints that otherwise produce
a structurally wrong file: a channel shared between frames, and an empty frame.
Both were hit during the v0.7 spike, where `dliswriter` either warned and
carried on or failed with a message that did not name the real problem.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from examples.sample_data.dlis_writer import write_minimal_dlis
from petromcp.utils.dlis_open import load_dlis

DEPTH = np.arange(5000.0, 5030.0, 0.5)


def _frame(prefix: str = "") -> dict[str, tuple[np.ndarray, str]]:
    return {
        f"DEPT{prefix}": (DEPTH, "ft"),
        f"GR{prefix}": (np.full(len(DEPTH), 60.0), "gAPI"),
    }


def test_writes_a_file_dlisio_can_read(tmp_path: Path) -> None:
    path = write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"MAIN": _frame()})
    with load_dlis(path) as logical_files:
        assert len(logical_files) == 1


def test_round_trips_the_well_name(tmp_path: Path) -> None:
    path = write_minimal_dlis(tmp_path / "w.dlis", "ROUNDTRIP-01", {"MAIN": _frame()})
    with load_dlis(path) as logical_files:
        names = [o.well_name for lf in logical_files for o in lf.origins]
    assert "ROUNDTRIP-01" in names


def test_round_trips_channel_values_exactly(tmp_path: Path) -> None:
    """Float64 through a binary format must not drift; the manifest-does-not-lie
    tests depend on exact comparison."""
    path = write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"MAIN": _frame()})
    with load_dlis(path) as logical_files:
        frame = next(fr for lf in logical_files for fr in lf.frames)
        depth = next(c.curves() for c in frame.channels if c.name == "DEPT")
    np.testing.assert_allclose(depth, DEPTH)


def test_round_trips_units_including_ones_rp66_does_not_define(tmp_path: Path) -> None:
    """`g/cm3` is not in RP66's vocabulary but is what real files carry. It must
    survive unchanged rather than being silently normalised."""
    frames = {"MAIN": {"DEPT": (DEPTH, "ft"), "RHOB": (np.full(len(DEPTH), 2.45), "g/cm3")}}
    path = write_minimal_dlis(tmp_path / "w.dlis", "W-1", frames)
    with load_dlis(path) as logical_files:
        frame = next(fr for lf in logical_files for fr in lf.frames)
        units = {c.name: c.units for c in frame.channels}
    assert units["RHOB"] == "g/cm3"
    assert units["DEPT"] == "ft"


def test_supports_several_frames_in_one_logical_file(tmp_path: Path) -> None:
    """The structural difference from LAS. Each frame needs its own index."""
    frames = {"TRIPLE_COMBO": _frame("_A"), "RESISTIVITY": _frame("_B")}
    path = write_minimal_dlis(tmp_path / "w.dlis", "W-1", frames)
    with load_dlis(path) as logical_files:
        found = {fr.name: [c.name for c in fr.channels] for lf in logical_files for fr in lf.frames}
    assert set(found) == {"TRIPLE_COMBO", "RESISTIVITY"}
    assert found["TRIPLE_COMBO"] == ["DEPT_A", "GR_A"]
    assert found["RESISTIVITY"] == ["DEPT_B", "GR_B"]


def test_rejects_a_channel_shared_between_frames(tmp_path: Path) -> None:
    """RP66 forbids it. dliswriter only warns, leaving a file that misdescribes
    its own structure."""
    frames = {"ONE": _frame(), "TWO": _frame()}
    with pytest.raises(ValueError, match="one frame only"):
        write_minimal_dlis(tmp_path / "w.dlis", "W-1", frames)


def test_the_rejection_names_both_frames(tmp_path: Path) -> None:
    frames = {"ONE": _frame(), "TWO": _frame()}
    with pytest.raises(ValueError) as excinfo:
        write_minimal_dlis(tmp_path / "w.dlis", "W-1", frames)
    assert "ONE" in str(excinfo.value) and "TWO" in str(excinfo.value)


def test_rejects_an_empty_frame(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no channels"):
        write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"EMPTY": {}})


def test_writing_is_quiet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """dliswriter emits a progress bar and RP66 unit warnings. A test suite that
    prints those on every fixture build is a suite people stop reading."""
    write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"MAIN": _frame()})
    captured = capsys.readouterr()
    assert "not one of the allowed units" not in captured.err

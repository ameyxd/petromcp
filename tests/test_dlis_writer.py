"""The dev-only DLIS writer.

Its job is to fail loudly on the two RP66 v1 constraints that otherwise produce
a structurally wrong file: a channel shared between frames, and an empty frame.
Both were hit during the v0.7 spike, where `dliswriter` either warned and
carried on or failed with a message that did not name the real problem.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from examples.sample_data.dlis_writer import (
    STORAGE_UNIT_LABEL_BYTES,
    concatenate_logical_files,
    write_minimal_dlis,
)
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


def test_writing_is_quiet(tmp_path: Path) -> None:
    """Run the writer in a subprocess and capture its real file descriptors.

    `capsys` cannot cover this. dliswriter writes its progress bar past
    `sys.stderr` to fd 2, so a capsys-based version of this test passed while
    progress bars were being printed on every run — three times, through three
    different broken suppressions. Only capturing the actual descriptors of a
    child process proves silence.

    The three sources being checked: a log record emitted inside `add_channel`
    (not a warning, and not during `write`), the progress bar on the file
    descriptor, and anything via `warnings`.
    """
    script = textwrap.dedent(
        f"""
        import numpy as np
        from pathlib import Path
        from examples.sample_data.dlis_writer import write_minimal_dlis
        depth = np.arange(5000.0, 5030.0, 0.5)
        write_minimal_dlis(
            Path({str(tmp_path / "quiet.dlis")!r}),
            "QUIET-1",
            {{"MAIN": {{
                "DEPT": (depth, "ft"),
                # A unit RP66 does not define, which is what triggers the log
                # record. Using an allowed unit would make this test vacuous.
                "RHOB": (np.full(len(depth), 2.45), "g/cm3"),
            }}}},
        )
        """
    )
    env = {**os.environ, "PYTHONPATH": f"{Path.cwd()}{os.pathsep}{Path.cwd() / 'src'}"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"leaked to stdout: {result.stdout[:200]!r}"
    assert result.stderr == "", f"leaked to stderr: {result.stderr[:200]!r}"


def test_the_quiet_writer_restores_the_logger_level(tmp_path: Path) -> None:
    """Suppression must not leave a caller's logging configuration altered."""
    logger = logging.getLogger("dliswriter")
    logger.setLevel(logging.DEBUG)
    try:
        write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"MAIN": _frame()})
        assert logger.level == logging.DEBUG
    finally:
        logger.setLevel(logging.NOTSET)


def test_the_quiet_writer_restores_the_file_descriptors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A leaked dup2 would silence the rest of the process."""
    write_minimal_dlis(tmp_path / "w.dlis", "W-1", {"MAIN": _frame()})
    print("visible again")
    assert "visible again" in capsys.readouterr().out


class TestMultipleLogicalFiles:
    """A DLIS physical file is a sequence of logical files. dliswriter cannot
    emit more than one, so they are concatenated with the trailing Storage Unit
    Labels stripped."""

    def _part(self, tmp_path: Path, name: str, suffix: str, value: float) -> Path:
        return write_minimal_dlis(
            tmp_path / f"{name}.dlis",
            "MULTI-01",
            {f"FRAME{suffix}": {
                f"DEPT{suffix}": (DEPTH, "ft"),
                f"CH{suffix}": (np.full(len(DEPTH), value), "gAPI"),
            }},
            origin_id=f"RUN-{suffix}",
        )

    def test_concatenation_yields_several_logical_files(self, tmp_path: Path) -> None:
        parts = [
            self._part(tmp_path, "a", "_A", 60.0),
            self._part(tmp_path, "b", "_B", 70.0),
        ]
        combined = concatenate_logical_files(tmp_path / "combined.dlis", parts)
        with load_dlis(combined) as logical_files:
            frames = [[fr.name for fr in lf.frames] for lf in logical_files]
        assert frames == [["FRAME_A"], ["FRAME_B"]]

    def test_channel_values_survive_concatenation(self, tmp_path: Path) -> None:
        parts = [
            self._part(tmp_path, "a", "_A", 60.0),
            self._part(tmp_path, "b", "_B", 70.0),
        ]
        combined = concatenate_logical_files(tmp_path / "combined.dlis", parts)
        with load_dlis(combined) as logical_files:
            values = {
                c.name: float(c.curves()[0])
                for lf in logical_files
                for fr in lf.frames
                for c in fr.channels
            }
        assert values["CH_A"] == pytest.approx(60.0)
        assert values["CH_B"] == pytest.approx(70.0)

    def test_only_the_first_part_keeps_its_storage_unit_label(self, tmp_path: Path) -> None:
        """A second SUL mid-stream is exactly what dlisio rejects."""
        parts = [
            self._part(tmp_path, "a", "_A", 60.0),
            self._part(tmp_path, "b", "_B", 70.0),
        ]
        combined = concatenate_logical_files(tmp_path / "combined.dlis", parts)
        expected = len(parts[0].read_bytes()) + (
            len(parts[1].read_bytes()) - STORAGE_UNIT_LABEL_BYTES
        )
        assert combined.stat().st_size == expected

    def test_a_single_part_is_unchanged(self, tmp_path: Path) -> None:
        part = self._part(tmp_path, "a", "_A", 60.0)
        combined = concatenate_logical_files(tmp_path / "one.dlis", [part])
        assert combined.read_bytes() == part.read_bytes()

    def test_rejects_no_parts(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="at least one"):
            concatenate_logical_files(tmp_path / "x.dlis", [])

    def test_rejects_a_part_too_short_to_hold_a_label(self, tmp_path: Path) -> None:
        stub = tmp_path / "stub.dlis"
        stub.write_bytes(b"short")
        with pytest.raises(ValueError, match="too short"):
            concatenate_logical_files(tmp_path / "x.dlis", [stub, stub])

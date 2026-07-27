"""DLIS loading and error translation.

`dlisio` reports problems accurately and unhelpfully: its messages name RP66
internals like "Visible Record" and "Logical Record Segment". Those are the
right words for a format engineer and useless to a model deciding what to tell
the user, so they are translated into one exception carrying the path and a
plain statement of what is wrong.

The expected failure modes here are not guesses — each was observed by feeding
`dlisio` the corresponding input during the v0.7 feasibility spike:

    truncated                -> RuntimeError
    empty                    -> EOFError
    not a DLIS file          -> RuntimeError
    valid header, junk body  -> RuntimeError

Unlike LAS, nothing degrades: a DLIS that fails to load yields nothing at all,
so there is no partial answer to fall back to.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from petromcp.utils.dlis_open import DLISReadError, load_dlis


@pytest.fixture(scope="module")
def good_dlis(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A minimal valid DLIS, written with the dev-only writer."""
    from examples.sample_data.dlis_writer import write_minimal_dlis

    path = tmp_path_factory.mktemp("dlis") / "good.dlis"
    depth = np.arange(5000.0, 5050.0, 0.5)
    write_minimal_dlis(
        path,
        well_name="OPEN-01",
        frames={"MAIN": {"DEPT": (depth, "ft"), "GR": (np.full(len(depth), 60.0), "gAPI")}},
    )
    return path


def test_loads_a_valid_file(good_dlis: Path) -> None:
    with load_dlis(good_dlis) as logical_files:
        assert len(logical_files) == 1


def test_yields_logical_files_in_order(good_dlis: Path) -> None:
    with load_dlis(good_dlis) as logical_files:
        frames = [frame.name for lf in logical_files for frame in lf.frames]
    assert frames == ["MAIN"]


def test_closes_the_handle_on_exit(good_dlis: Path) -> None:
    """The context manager must release the file, or Windows callers cannot
    delete or rewrite it afterwards."""
    with load_dlis(good_dlis) as logical_files:
        assert logical_files
    # Reopening must work; a leaked handle would be the failure here.
    with load_dlis(good_dlis) as again:
        assert again


class TestErrorTranslation:
    """Every corrupt input becomes one exception type with a usable message."""

    def _write(self, tmp_path: Path, name: str, data: bytes) -> Path:
        path = tmp_path / name
        path.write_bytes(data)
        return path

    def test_truncated_file_raises_dlis_read_error(
        self, tmp_path: Path, good_dlis: Path
    ) -> None:
        raw = good_dlis.read_bytes()
        path = self._write(tmp_path, "truncated.dlis", raw[: len(raw) // 3])
        with pytest.raises(DLISReadError), load_dlis(path):
            pass

    def test_empty_file_raises_dlis_read_error(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "empty.dlis", b"")
        with pytest.raises(DLISReadError), load_dlis(path):
            pass

    def test_non_dlis_file_raises_dlis_read_error(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "not_dlis.dlis", b"this is not a DLIS file" * 20)
        with pytest.raises(DLISReadError), load_dlis(path):
            pass

    def test_junk_body_raises_dlis_read_error(
        self, tmp_path: Path, good_dlis: Path
    ) -> None:
        raw = good_dlis.read_bytes()
        path = self._write(tmp_path, "junk_body.dlis", raw[:200] + b"\x00" * 500)
        with pytest.raises(DLISReadError), load_dlis(path):
            pass

    def test_message_names_the_file(self, tmp_path: Path) -> None:
        """The model needs to know *which* file failed when several are in play."""
        path = self._write(tmp_path, "empty.dlis", b"")
        with pytest.raises(DLISReadError, match="empty.dlis"), load_dlis(path):
            pass

    def test_message_does_not_leak_rp66_jargon(self, tmp_path: Path) -> None:
        """`dlisio`'s own text mentions Visible Records and Logical Record
        Segments. Accurate, and not something to hand to a model."""
        path = self._write(tmp_path, "not_dlis.dlis", b"nope" * 100)
        with pytest.raises(DLISReadError) as excinfo, load_dlis(path):
            pass
        message = str(excinfo.value)
        for jargon in ("Visible Record", "Logical Record Segment", "tapemark"):
            assert jargon not in message, f"leaked {jargon!r}"

    def test_message_suggests_what_to_do(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "truncated.dlis", b"\x00" * 80)
        with pytest.raises(DLISReadError) as excinfo, load_dlis(path):
            pass
        assert "not a readable DLIS" in str(excinfo.value)

    def test_underlying_error_is_preserved_for_debugging(self, tmp_path: Path) -> None:
        """Translated for the model, but the original must remain chained so a
        maintainer can still see what dlisio said."""
        path = self._write(tmp_path, "empty.dlis", b"")
        with pytest.raises(DLISReadError) as excinfo, load_dlis(path):
            pass
        assert excinfo.value.__cause__ is not None


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """A path that does not exist is a caller mistake, not a corrupt file, and
    should not be dressed up as one."""
    with pytest.raises(FileNotFoundError), load_dlis(tmp_path / "nope.dlis"):
        pass

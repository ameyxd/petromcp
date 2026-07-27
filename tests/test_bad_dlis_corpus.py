"""Bad-DLIS fixture corpus.

Every file-reading tool runs against every fixture. That rule exists because
the LAS slice broke it: the v0.3 truncated-file fix patched `read_las_file`
only, the corpus tests called only that tool, and two other tools kept crashing
for two releases while the suite stayed green.

The fixtures are generated rather than committed, since each is a trivial
mutation of a valid file and a binary blob in git is harder to reason about
than the three lines that produce it.

Expected behaviour differs from LAS, and not uniformly. `dlisio` raises on most
corrupt input, so those tools must fail with one translated error rather than
degrade. But a file carrying only the 80-byte Storage Unit Label loads cleanly
and yields *zero logical files* — structurally valid and empty, typically a
transfer that wrote the label and stopped. That is reported honestly as an
empty file rather than refused, because "this DLIS holds nothing" is a more
useful answer than "unreadable".

That distinction was found by running the corpus, not by reasoning about it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from examples.sample_data.dlis_writer import write_minimal_dlis
from petromcp.tools.dlis import list_dlis_channels, read_dlis_channel, read_dlis_file
from petromcp.utils.dlis_open import DLISReadError

#: Every tool that opens a file, as a one-argument callable. Adding a tool
#: without adding it here fails `test_every_reading_tool_is_covered`.
TOOLS: dict[str, Callable[[str, list[Path]], object]] = {
    "read_dlis_file": lambda path, roots: read_dlis_file(path, roots),
    "list_dlis_channels": lambda path, roots: list_dlis_channels(path, roots),
    "read_dlis_channel": lambda path, roots: read_dlis_channel(
        path, "GR", allowed_paths=roots
    ),
}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Path]]:
    """A valid DLIS plus one fixture per known failure mode."""
    work = tmp_path_factory.mktemp("bad_dlis")
    depth = np.arange(5000.0, 5050.0, 0.5)
    good = write_minimal_dlis(
        work / "good.dlis",
        "CORPUS-01",
        {"MAIN": {"DEPT": (depth, "ft"), "GR": (np.full(len(depth), 60.0), "gAPI")}},
    )
    raw = good.read_bytes()

    fixtures = {
        "empty": b"",
        "truncated_early": raw[:120],
        "truncated_late": raw[: int(len(raw) * 0.9)],
        "not_dlis": b"this is plainly not a DLIS file\n" * 30,
        "junk_body": raw[:200] + b"\x00" * 600,
        # A LAS file handed to a DLIS tool. Users do this.
        "actually_las": b"~Version\n VERS. 2.0 : CWLS\n~Well\n WELL. W-1 : WELL\n",
        "header_only": raw[:80],
    }
    paths = {}
    for name, data in fixtures.items():
        path = work / f"{name}.dlis"
        path.write_bytes(data)
        paths[name] = path
    return work, {"good": good, **paths}


def test_every_reading_tool_is_covered(corpus: tuple[Path, dict[str, Path]]) -> None:
    """A new DLIS tool must be added to TOOLS, or it goes untested against the
    corpus — exactly how the LAS bug survived."""
    import petromcp.tools.dlis as module

    exported = {
        name
        for name in dir(module)
        if name.startswith(("read_dlis", "list_dlis", "summarize_dlis"))
        and callable(getattr(module, name))
    }
    assert exported == set(TOOLS), f"untested tools: {exported - set(TOOLS)}"


@pytest.mark.parametrize("tool_name", list(TOOLS))
def test_tool_works_on_the_valid_file(
    tool_name: str, corpus: tuple[Path, dict[str, Path]]
) -> None:
    """Guards against a tool that 'passes' the corpus by always raising."""
    work, files = corpus
    assert TOOLS[tool_name](str(files["good"]), [work]) is not None


#: Inputs dlisio refuses outright. Verified by running them.
UNREADABLE = [
    "empty",
    "truncated_early",
    "truncated_late",
    "not_dlis",
    "junk_body",
    "actually_las",
]


@pytest.mark.parametrize("tool_name", list(TOOLS))
@pytest.mark.parametrize("fixture", UNREADABLE)
def test_every_tool_fails_cleanly_on_every_unreadable_fixture(
    tool_name: str, fixture: str, corpus: tuple[Path, dict[str, Path]]
) -> None:
    """One translated error type, never an unhandled dlisio exception and never
    a silent wrong answer."""
    work, files = corpus
    with pytest.raises(DLISReadError):
        TOOLS[tool_name](str(files[fixture]), [work])


class TestAnEmptyButValidFile:
    """A Storage Unit Label with nothing after it. Valid, and holds nothing."""

    def test_structure_reports_no_logical_files(
        self, corpus: tuple[Path, dict[str, Path]]
    ) -> None:
        work, files = corpus
        summary = read_dlis_file(str(files["header_only"]), [work])
        assert summary.logical_files == []
        assert summary.total_frames == 0
        assert summary.total_channels == 0

    def test_listing_is_empty_rather_than_an_error(
        self, corpus: tuple[Path, dict[str, Path]]
    ) -> None:
        work, files = corpus
        assert list_dlis_channels(str(files["header_only"]), [work]).channels == []

    def test_reading_a_channel_says_the_file_is_empty(
        self, corpus: tuple[Path, dict[str, Path]]
    ) -> None:
        """Not "channel not found", which would send the caller hunting for a
        name problem that does not exist."""
        work, files = corpus
        with pytest.raises(KeyError, match="no logical files"):
            read_dlis_channel(str(files["header_only"]), "GR", allowed_paths=[work])


@pytest.mark.parametrize(
    "fixture",
    ["empty", "truncated_early", "not_dlis", "junk_body", "actually_las"],
)
def test_the_error_names_the_file(
    fixture: str, corpus: tuple[Path, dict[str, Path]]
) -> None:
    work, files = corpus
    with pytest.raises(DLISReadError, match=fixture):
        read_dlis_file(str(files[fixture]), [work])


def test_a_las_file_is_rejected_rather_than_misread(
    corpus: tuple[Path, dict[str, Path]]
) -> None:
    """Handing a LAS file to a DLIS tool is a plausible user mistake. It must
    fail, not return an empty structure that looks like a valid answer."""
    work, files = corpus
    with pytest.raises(DLISReadError):
        read_dlis_file(str(files["actually_las"]), [work])

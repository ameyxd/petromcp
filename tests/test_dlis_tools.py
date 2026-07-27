"""DLIS tools.

The structural difference from LAS drives most of these tests: a DLIS holds N
logical files, each with M frames, and a channel name is unique only within a
frame. So the tools need addressing, and the failure mode that matters is a
tool that resolves an ambiguous name by silently picking one — a confidently
wrong answer is worse than an error, especially for a tool a model drives.

Every fixture is generated, so what the tools should return is known rather
than asserted from their own output.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from examples.sample_data.dlis_writer import concatenate_logical_files, write_minimal_dlis
from petromcp.tools.dlis import (
    AmbiguousChannelError,
    list_dlis_channels,
    read_dlis_channel,
    read_dlis_file,
)
from petromcp.utils.path_validator import PathNotAllowedError

DEPTH = np.arange(5000.0, 5100.0, 0.5)
N = len(DEPTH)


@pytest.fixture(scope="module")
def multi(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Path]]:
    """Two logical files. The first has two frames; `GR` appears in both, which
    is legal in DLIS and the ambiguity the tools must handle."""
    work = tmp_path_factory.mktemp("dlis_tools")

    first = write_minimal_dlis(
        work / "part_a.dlis",
        "DLIS-01",
        {
            "TRIPLE_COMBO": {
                "DEPT": (DEPTH, "ft"),
                "GR": (np.full(N, 60.0), "gAPI"),
                "RHOB": (np.full(N, 2.45), "g/cm3"),
            },
            # Same channel name in a second frame, different values.
            "REPEAT_PASS": {
                "DEPT_R": (DEPTH, "ft"),
                "GR_REPEAT": (np.full(N, 65.0), "gAPI"),
            },
        },
        origin_id="RUN-1",
    )
    second = write_minimal_dlis(
        work / "part_b.dlis",
        "DLIS-01",
        {"SONIC": {"DEPT_S": (DEPTH, "ft"), "DT": (np.full(N, 80.0), "us")}},
        origin_id="RUN-2",
    )
    combined = concatenate_logical_files(work / "multi.dlis", [first, second])
    return combined, [work]


@pytest.fixture(scope="module")
def ambiguous(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Path]]:
    """One logical file where `GR` genuinely appears in two frames.

    RP66 forbids sharing a channel *object* between frames, but two frames may
    each define a channel of the same name — which is what makes an unqualified
    lookup ambiguous.
    """
    work = tmp_path_factory.mktemp("dlis_ambiguous")
    # dliswriter enforces unique names within a file, so the two same-named
    # channels are built as separate logical files and concatenated.
    a = write_minimal_dlis(
        work / "a.dlis", "AMB-01",
        {"PASS_ONE": {"DEPT": (DEPTH, "ft"), "GR": (np.full(N, 60.0), "gAPI")}},
        origin_id="RUN-1",
    )
    b = write_minimal_dlis(
        work / "b.dlis", "AMB-01",
        {"PASS_TWO": {"DEPT_2": (DEPTH, "ft"), "GR": (np.full(N, 90.0), "gAPI")}},
        origin_id="RUN-2",
    )
    return concatenate_logical_files(work / "ambiguous.dlis", [a, b]), [work]


# --- read_dlis_file -----------------------------------------------------------


class TestReadDlisFile:
    def test_reports_every_logical_file(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        assert len(summary.logical_files) == 2

    def test_logical_files_are_indexed_in_file_order(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        assert [lf.index for lf in summary.logical_files] == [0, 1]

    def test_reports_frames_per_logical_file(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        names = [[f.name for f in lf.frames] for lf in summary.logical_files]
        assert names == [["TRIPLE_COMBO", "REPEAT_PASS"], ["SONIC"]]

    def test_reports_the_well_name(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        assert summary.logical_files[0].well_name == "DLIS-01"

    def test_totals_match_the_per_frame_detail(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        frames = [f for lf in summary.logical_files for f in lf.frames]
        assert summary.total_frames == len(frames)
        assert summary.total_channels == sum(f.channel_count for f in frames)

    def test_reports_index_type_so_callers_know_if_depth_slicing_applies(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        """A time-indexed frame cannot be depth-sliced; the caller has to see
        which it is."""
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        frame = summary.logical_files[0].frames[0]
        assert frame.index_type == "BOREHOLE-DEPTH"

    def test_reports_the_depth_range_of_each_frame(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        depth_range = summary.logical_files[0].frames[0].depth_range
        assert depth_range is not None
        assert depth_range.start == pytest.approx(DEPTH[0])
        assert depth_range.stop == pytest.approx(DEPTH[-1])

    def test_returns_no_channel_values(self, multi: tuple[Path, list[Path]]) -> None:
        """The whole point of this tool: structure without paying for data."""
        path, roots = multi
        summary = read_dlis_file(str(path), roots)
        dumped = summary.model_dump_json()
        assert "2.45" not in dumped, "channel values leaked into the summary"

    def test_refuses_a_path_outside_the_allowlist(
        self, multi: tuple[Path, list[Path]], tmp_path: Path
    ) -> None:
        path, _ = multi
        with pytest.raises(PathNotAllowedError):
            read_dlis_file(str(path), [tmp_path])


# --- list_dlis_channels -------------------------------------------------------


class TestListDlisChannels:
    def test_lists_every_channel_across_logical_files(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        listing = list_dlis_channels(str(path), roots)
        names = {c.name for c in listing.channels}
        assert {"GR", "RHOB", "GR_REPEAT", "DT"} <= names

    def test_every_channel_names_its_frame_and_logical_file(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        """Without these a listing looks addressable but is not."""
        path, roots = multi
        listing = list_dlis_channels(str(path), roots)
        for channel in listing.channels:
            assert channel.frame
            assert channel.logical_file >= 0

    def test_reports_units(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        listing = list_dlis_channels(str(path), roots)
        units = {c.name: c.units for c in listing.channels}
        assert units["GR"] == "gAPI"
        assert units["RHOB"] == "g/cm3"

    def test_reports_sample_counts(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        listing = list_dlis_channels(str(path), roots)
        gr = next(c for c in listing.channels if c.name == "GR")
        assert gr.sample_count == N

    def test_frame_filter_narrows_the_listing(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        listing = list_dlis_channels(str(path), roots, frame="SONIC")
        assert {c.frame for c in listing.channels} == {"SONIC"}
        assert listing.frame_filter == "SONIC"

    def test_unfiltered_listing_records_no_filter(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        assert list_dlis_channels(str(path), roots).frame_filter is None

    def test_unknown_frame_raises_and_names_the_available_frames(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        with pytest.raises(KeyError) as excinfo:
            list_dlis_channels(str(path), roots, frame="NOPE")
        assert "SONIC" in str(excinfo.value)


# --- read_dlis_channel --------------------------------------------------------


class TestReadDlisChannel:
    def test_reads_an_unambiguous_channel_without_naming_the_frame(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        data = read_dlis_channel(str(path), "RHOB", allowed_paths=roots)
        assert data.channel_name == "RHOB"
        assert data.frame == "TRIPLE_COMBO"
        assert data.values[0] == pytest.approx(2.45)

    def test_finds_a_channel_in_a_later_logical_file(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        """A channel only present in logical file 1 must still be found without
        the caller having to know which file it is in."""
        path, roots = multi
        data = read_dlis_channel(str(path), "DT", allowed_paths=roots)
        assert data.logical_file == 1
        assert data.frame == "SONIC"

    def test_reports_the_index_alongside_the_values(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        data = read_dlis_channel(str(path), "RHOB", allowed_paths=roots)
        assert len(data.index) == len(data.values)
        assert data.index_units == "ft"

    def test_caps_output_and_says_so(self, tmp_path: Path) -> None:
        big_depth = np.arange(0.0, 2000.0, 0.5)
        path = write_minimal_dlis(
            tmp_path / "big.dlis",
            "BIG-01",
            {"MAIN": {"DEPT": (big_depth, "ft"),
                      "GR": (np.full(len(big_depth), 60.0), "gAPI")}},
        )
        data = read_dlis_channel(str(path), "GR", allowed_paths=[tmp_path])
        assert data.original_count == len(big_depth)
        assert data.downsampled is True
        assert data.sample_count <= 500

    def test_explicit_range_disables_downsampling(self, multi: tuple[Path, list[Path]]) -> None:
        path, roots = multi
        data = read_dlis_channel(
            str(path), "RHOB", depth_start=5010.0, depth_stop=5020.0, allowed_paths=roots
        )
        assert data.downsampled is False
        assert all(5010.0 <= d <= 5020.0 for d in data.index)

    def test_half_specified_range_is_rejected(self, multi: tuple[Path, list[Path]]) -> None:
        """Same contract as the LAS tool: a partial interval is an error, not a
        silent fallback to the whole channel."""
        path, roots = multi
        with pytest.raises(ValueError, match="both"):
            read_dlis_channel(str(path), "RHOB", depth_start=5010.0, allowed_paths=roots)

    def test_unknown_channel_raises_and_suggests_the_listing_tool(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        with pytest.raises(KeyError) as excinfo:
            read_dlis_channel(str(path), "NOPE", allowed_paths=roots)
        assert "list_dlis_channels" in str(excinfo.value)

    def test_ambiguous_channel_raises_rather_than_guessing(
        self, ambiguous: tuple[Path, list[Path]]
    ) -> None:
        """The important one. Picking a frame silently would produce a
        plausible, wrong answer."""
        path, roots = ambiguous
        with pytest.raises(AmbiguousChannelError):
            read_dlis_channel(str(path), "GR", allowed_paths=roots)

    def test_the_ambiguity_error_names_every_candidate(
        self, ambiguous: tuple[Path, list[Path]]
    ) -> None:
        """So the model's next call is correct rather than another guess."""
        path, roots = ambiguous
        with pytest.raises(AmbiguousChannelError) as excinfo:
            read_dlis_channel(str(path), "GR", allowed_paths=roots)
        message = str(excinfo.value)
        assert "PASS_ONE" in message and "PASS_TWO" in message

    def test_naming_the_frame_resolves_the_ambiguity(
        self, ambiguous: tuple[Path, list[Path]]
    ) -> None:
        path, roots = ambiguous
        one = read_dlis_channel(str(path), "GR", frame="PASS_ONE", allowed_paths=roots)
        two = read_dlis_channel(str(path), "GR", frame="PASS_TWO", allowed_paths=roots)
        assert one.values[0] == pytest.approx(60.0)
        assert two.values[0] == pytest.approx(90.0)

    def test_logical_file_argument_scopes_the_search(
        self, ambiguous: tuple[Path, list[Path]]
    ) -> None:
        path, roots = ambiguous
        data = read_dlis_channel(str(path), "GR", logical_file=1, allowed_paths=roots)
        assert data.logical_file == 1
        assert data.values[0] == pytest.approx(90.0)

    def test_out_of_range_logical_file_raises(
        self, multi: tuple[Path, list[Path]]
    ) -> None:
        path, roots = multi
        with pytest.raises(IndexError):
            read_dlis_channel(str(path), "GR", logical_file=99, allowed_paths=roots)

    def test_refuses_a_path_outside_the_allowlist(
        self, multi: tuple[Path, list[Path]], tmp_path: Path
    ) -> None:
        path, _ = multi
        with pytest.raises(PathNotAllowedError):
            read_dlis_channel(str(path), "GR", allowed_paths=[tmp_path])

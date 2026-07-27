"""DLIS tools. Thin wrappers over `dlisio` returning Pydantic models.

Every entry point validates its path through the allowlist before touching
disk, and every load goes through `utils.dlis_open` so `dlisio`'s RP66-flavoured
errors never reach a caller.

The structural difference from LAS shapes this module. A DLIS physical file
holds N logical files, each holding M frames, each holding K channels, and a
channel name is unique only within a frame. So:

- `read_dlis_file` reports structure and never values, because a real file can
  carry hundreds of channels.
- `list_dlis_channels` reports one row per channel with its frame and logical
  file, so the result is actually addressable.
- `read_dlis_channel` resolves a channel name, and **refuses** when the name is
  ambiguous rather than picking one. A silently-chosen frame produces a
  plausible wrong answer, which is the worst outcome for a tool an LLM drives.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from petromcp.models.dlis import (
    ChannelInfo,
    ChannelListing,
    DLISChannelData,
    DLISSummary,
    FrameInfo,
    LogicalFileInfo,
)
from petromcp.models.shared import DepthRange
from petromcp.utils.access_log import log_access
from petromcp.utils.dlis_open import load_dlis
from petromcp.utils.path_validator import validate_path
from petromcp.utils.summarizer import downsample

DEFAULT_SAMPLE_CAP = 500


class AmbiguousChannelError(Exception):
    """Raised when a channel name occurs in more than one frame.

    Carries every candidate so the caller's next attempt is correct rather than
    another guess.
    """


@dataclass(frozen=True)
class _Located:
    """A resolved channel and everything needed to describe where it came from."""

    logical_file: int
    frame_name: str
    channel: Any
    frame: Any


def _open(path: str, allowed: Sequence[Path | str], tool: str) -> Path:
    resolved = validate_path(path, allowed)
    log_access(tool, resolved)
    return resolved


def _text(value: object) -> str | None:
    """DLIS string fields arrive as str, bytes, or empty. Normalise to str|None."""
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text or None


def _index_channel(frame: Any) -> Any | None:
    """The frame's index is its first channel.

    RP66 permits an explicit index channel reference, but `dlisio` exposes the
    channel list in frame order and the index is first in every file the spike
    produced. Returning None rather than guessing keeps a malformed frame from
    silently reporting the wrong axis.
    """
    channels = list(frame.channels)
    return channels[0] if channels else None


def _frame_depth_range(frame: Any) -> DepthRange | None:
    index = _index_channel(frame)
    if index is None:
        return None
    try:
        values = np.asarray(index.curves(), dtype=float)
    except Exception:
        # A frame whose index cannot be read is reported without a range
        # rather than failing the whole summary.
        return None
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    return DepthRange(start=float(finite.min()), stop=float(finite.max()))


def _frame_info(index: int, frame: Any) -> FrameInfo:
    channels = list(frame.channels)
    index_channel = _index_channel(frame)
    return FrameInfo(
        name=_text(frame.name) or "",
        logical_file=index,
        index_type=_text(getattr(frame, "index_type", None)),
        index_units=_text(getattr(index_channel, "units", None)) if index_channel else None,
        depth_range=_frame_depth_range(frame),
        channel_count=len(channels),
        channel_names=[_text(c.name) or "" for c in channels],
    )


def read_dlis_file(path: str, allowed_paths: Sequence[Path | str]) -> DLISSummary:
    """Structure and metadata of a DLIS file. No channel values.

    Reports every logical file, its frames, each frame's index type and depth
    range, and channel counts. Deliberately cheap: a real DLIS can carry
    hundreds of channels, and reading them to summarise would defeat the point.
    """
    resolved = _open(path, allowed_paths, "read_dlis_file")

    logical_files: list[LogicalFileInfo] = []
    with load_dlis(resolved) as batch:
        for index, logical in enumerate(batch):
            origins = list(logical.origins)
            first = origins[0] if origins else None
            logical_files.append(
                LogicalFileInfo(
                    index=index,
                    file_id=_text(getattr(first, "file_id", None)) if first else None,
                    well_name=_text(getattr(first, "well_name", None)) if first else None,
                    operator=_text(getattr(first, "company", None)) if first else None,
                    frames=[_frame_info(index, frame) for frame in logical.frames],
                )
            )

    frames = [frame for lf in logical_files for frame in lf.frames]
    return DLISSummary(
        logical_files=logical_files,
        total_frames=len(frames),
        total_channels=sum(frame.channel_count for frame in frames),
    )


def list_dlis_channels(
    path: str,
    allowed_paths: Sequence[Path | str],
    frame: str | None = None,
) -> ChannelListing:
    """Every channel, with the frame and logical file needed to address it.

    Reports sample counts but no statistics: computing statistics means reading
    every curve, which is exactly the cost this tool exists to avoid.

    Raises:
        KeyError: if `frame` names no frame in the file. The message lists the
            frames that do exist.
    """
    resolved = _open(path, allowed_paths, "list_dlis_channels")

    channels: list[ChannelInfo] = []
    available: list[str] = []
    with load_dlis(resolved) as batch:
        for index, logical in enumerate(batch):
            for dlis_frame in logical.frames:
                frame_name = _text(dlis_frame.name) or ""
                available.append(frame_name)
                if frame is not None and frame_name != frame:
                    continue
                for channel in dlis_frame.channels:
                    channels.append(
                        ChannelInfo(
                            name=_text(channel.name) or "",
                            frame=frame_name,
                            logical_file=index,
                            units=_text(getattr(channel, "units", None)),
                            long_name=_text(getattr(channel, "long_name", None)),
                            sample_count=_sample_count(channel),
                        )
                    )

    if frame is not None and frame not in available:
        raise KeyError(
            f"frame {frame!r} is not in {resolved.name}. "
            f"Available frames: {', '.join(sorted(set(available))) or 'none'}."
        )
    return ChannelListing(channels=channels, frame_filter=frame)


def _sample_count(channel: Any) -> int:
    try:
        return int(len(channel.curves()))
    except Exception:
        # A channel whose data cannot be read is still worth listing; its
        # absence from the listing would be a worse answer than a zero count.
        return 0


def _locate(batch: Any, channel: str, frame: str | None, logical_file: int | None) -> _Located:
    """Find one channel, or explain why the name does not identify one."""
    logicals = list(batch)
    if logical_file is not None:
        if not 0 <= logical_file < len(logicals):
            raise IndexError(
                f"logical file {logical_file} does not exist; the file has "
                f"{len(logicals)}. They are numbered from 0."
            )
        candidates_source = [(logical_file, logicals[logical_file])]
    else:
        candidates_source = list(enumerate(logicals))

    matches: list[_Located] = []
    for index, logical in candidates_source:
        for dlis_frame in logical.frames:
            frame_name = _text(dlis_frame.name) or ""
            if frame is not None and frame_name != frame:
                continue
            for candidate in dlis_frame.channels:
                if (_text(candidate.name) or "") == channel:
                    matches.append(
                        _Located(
                            logical_file=index,
                            frame_name=frame_name,
                            channel=candidate,
                            frame=dlis_frame,
                        )
                    )

    if not matches:
        # A file carrying only a Storage Unit Label loads cleanly and yields no
        # logical files — an empty DLIS rather than a corrupt one, typically a
        # transfer that wrote the label and stopped. Saying "channel not found"
        # there sends the caller looking for a channel name problem.
        if not logicals:
            raise KeyError(
                "this DLIS file contains no logical files, so it holds no "
                "channels at all. It is structurally valid but empty, which "
                "usually means the transfer was truncated."
            )
        scope = f" in frame {frame!r}" if frame else ""
        raise KeyError(
            f"channel {channel!r} not found{scope}. "
            "Call list_dlis_channels to see what this file contains."
        )
    if len(matches) > 1:
        where = ", ".join(
            f"logical file {m.logical_file} frame {m.frame_name!r}" for m in matches
        )
        raise AmbiguousChannelError(
            f"channel {channel!r} occurs in {len(matches)} places: {where}. "
            "Pass `frame` (and `logical_file` if needed) to choose one — "
            "petromcp will not pick for you, because the values differ."
        )
    return matches[0]


def read_dlis_channel(
    path: str,
    channel: str,
    frame: str | None = None,
    logical_file: int | None = None,
    depth_start: float | None = None,
    depth_stop: float | None = None,
    allowed_paths: Sequence[Path | str] | None = None,
) -> DLISChannelData:
    """Values for one channel, with its index.

    Defaults to a 500-sample downsample. Pass `depth_start` and `depth_stop`
    together to get every sample in that interval instead; passing one without
    the other is an error rather than a silent fallback, matching the LAS tool.

    Raises:
        KeyError: if no channel matches.
        AmbiguousChannelError: if the name matches several. Never resolved by
            guessing — the values differ, so a guess is a wrong answer.
        IndexError: if `logical_file` is out of range.
    """
    if allowed_paths is None:
        raise ValueError("allowed_paths is required")
    depth_range = DepthRange.from_optional(depth_start, depth_stop)
    resolved = _open(path, allowed_paths, "read_dlis_channel")

    with load_dlis(resolved) as batch:
        located = _locate(batch, channel, frame, logical_file)
        values = np.asarray(located.channel.curves(), dtype=float)
        index_channel = _index_channel(located.frame)
        index_values = (
            np.asarray(index_channel.curves(), dtype=float)
            if index_channel is not None
            else np.arange(len(values), dtype=float)
        )
        index_name = _text(index_channel.name) if index_channel is not None else None
        index_units = (
            _text(getattr(index_channel, "units", None))
            if index_channel is not None
            else None
        )
        units = _text(getattr(located.channel, "units", None))
        frame_name = located.frame_name
        found_in = located.logical_file

    original_count = int(len(values))
    # The index and the channel come from the same frame, so they are the same
    # length; guard anyway rather than let a malformed file raise on a slice.
    usable = min(len(index_values), len(values))
    index_values, values = index_values[:usable], values[:usable]

    if depth_range is not None:
        mask = (index_values >= depth_range.start) & (index_values <= depth_range.stop)
        index_values, values = index_values[mask], values[mask]
        downsampled = False
    else:
        index_values, did_sample = downsample(index_values, DEFAULT_SAMPLE_CAP)
        values, _ = downsample(values, DEFAULT_SAMPLE_CAP)
        downsampled = did_sample

    effective_range = depth_range
    if effective_range is None and len(index_values):
        finite = index_values[np.isfinite(index_values)]
        if finite.size:
            effective_range = DepthRange(start=float(finite.min()), stop=float(finite.max()))

    return DLISChannelData(
        channel_name=channel,
        frame=frame_name,
        logical_file=found_in,
        units=units,
        index_name=index_name,
        index_units=index_units,
        index=[float(x) for x in index_values],
        values=[float(v) if np.isfinite(v) else None for v in values],
        depth_range=effective_range,
        sample_count=int(len(values)),
        downsampled=downsampled,
        original_count=original_count,
    )

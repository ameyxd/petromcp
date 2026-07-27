"""Pydantic models for DLIS tool outputs. Frozen. No I/O.

DLIS is structurally richer than LAS: a physical file holds N logical files,
each holding M frames, each holding K channels. Channel names are unique within
a frame but **not** across frames, which is why every model here carries the
frame a channel came from. Dropping that would make an output that looks
addressable but is not.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from petromcp.models.shared import DepthRange


class ChannelInfo(BaseModel):
    """One channel, with enough context to fetch it unambiguously."""

    model_config = ConfigDict(frozen=True)

    name: str
    frame: str
    logical_file: int
    units: str | None = None
    long_name: str | None = None
    #: Sample count. Reported instead of statistics because computing
    #: statistics means reading every curve, which a file with hundreds of
    #: channels cannot afford.
    sample_count: int = 0


class FrameInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    logical_file: int
    #: RP66 index type, e.g. `BOREHOLE-DEPTH` or `TIME`. A frame indexed on
    #: time cannot be depth-sliced, so callers need to see this.
    index_type: str | None = None
    index_units: str | None = None
    depth_range: DepthRange | None = None
    channel_count: int = 0
    channel_names: list[str] = []


class LogicalFileInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: Position in the physical file. This is the addressing handle, so it is
    #: an index rather than a name — RP66 does not require names to be unique.
    index: int
    file_id: str | None = None
    well_name: str | None = None
    operator: str | None = None
    frames: list[FrameInfo] = []


class DLISSummary(BaseModel):
    """Structure of a DLIS file. Never contains channel values."""

    model_config = ConfigDict(frozen=True)

    logical_files: list[LogicalFileInfo]
    total_frames: int
    total_channels: int


class ChannelListing(BaseModel):
    model_config = ConfigDict(frozen=True)

    channels: list[ChannelInfo]
    #: Set when the listing was narrowed, so a caller can tell "this file has
    #: three channels" from "you asked for one frame".
    frame_filter: str | None = None


class DLISChannelData(BaseModel):
    """Values for one channel, token-budgeted like the LAS equivalent."""

    model_config = ConfigDict(frozen=True)

    channel_name: str
    frame: str
    logical_file: int
    units: str | None
    index_name: str | None
    index_units: str | None
    index: list[float]
    values: list[float | None]
    depth_range: DepthRange | None
    sample_count: int
    downsampled: bool
    original_count: int

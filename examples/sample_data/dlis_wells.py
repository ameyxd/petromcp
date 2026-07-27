"""Synthetic DLIS well definitions.

The same facies model and defect catalogue the LAS generator uses, arranged the
way a DLIS file arranges things: curves split across frames, each frame with its
own index channel, and — for the multi-logical-file well — separate logging runs.

That reuse is the point. `facies.py` and `defects.py` produce arrays and know
nothing about either format, so a DLIS well built from the same seed carries the
same geology as its LAS counterpart. Only the container differs.

Two RP66 constraints shape the layout:

- **A channel belongs to one frame.** So each frame needs its own index channel
  under a distinct name. `DEPT` for the first, `DEPT_<FRAME>` after that.
- **Channel names are unique within a file.** Which is why the two-logical-file
  well is assembled from separately written parts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from examples.sample_data.defects import flatline, null_gap, spike, washout
from examples.sample_data.truth import DefectRecord

#: Units per channel. `g/cm3` is not in RP66's vocabulary but round-trips
#: unchanged and is what real service-company files carry; see the v0.7 design
#: doc for why we keep it rather than diverging from the LAS generator.
CHANNEL_UNITS: dict[str, str] = {
    "GR": "gAPI",
    "RHOB": "g/cm3",
    "NPHI": "v/v",
    "DT": "us",
    "CALI": "in",
}

#: RP66 index type for a depth-indexed frame.
INDEX_TYPE = "BOREHOLE-DEPTH"

DefectPlan = Callable[[dict[str, np.ndarray], np.ndarray], list[DefectRecord]]


@dataclass(frozen=True)
class DlisFrameSpec:
    """One frame: which synthesized curves it carries, and its index name."""

    name: str
    channels: tuple[str, ...]
    index_channel: str


@dataclass(frozen=True)
class DlisLogicalFileSpec:
    """One logging run. Becomes one logical file in the written DLIS.

    `origin_id` does not survive a round trip through `dliswriter` — no field
    `dlisio` exposes carries it — so `file_header_id` is what makes runs
    distinguishable to a reader. It defaults to `origin_id`.
    """

    origin_id: str
    frames: tuple[DlisFrameSpec, ...]
    file_header_id: str | None = None

    @property
    def header_id(self) -> str:
        return self.file_header_id or self.origin_id


@dataclass(frozen=True)
class DlisWellSpec:
    name: str
    operator: str
    start: float
    stop: float
    step: float
    seed: int
    logical_files: tuple[DlisLogicalFileSpec, ...]
    apply_defects: DefectPlan | None = None
    depth_units: str = "ft"
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def channel_names(self) -> tuple[str, ...]:
        """Every non-index channel across every frame, in file order."""
        return tuple(
            channel
            for logical in self.logical_files
            for frame in logical.frames
            for channel in frame.channels
        )


def _single_run_defects(
    curves: dict[str, np.ndarray], depth: np.ndarray
) -> list[DefectRecord]:
    """The same three problems the LAS reference well carries, so a reader can
    compare the two formats on identical ground."""
    return [
        null_gap(curves, depth, "RHOB", 6600.0, 6640.0),
        washout(curves, depth, 7210.0, 7255.0),
        spike(curves, depth, "GR", 5820.0, magnitude=410.0),
    ]


def _multi_run_defects(
    curves: dict[str, np.ndarray], depth: np.ndarray
) -> list[DefectRecord]:
    """A defect in each logging run, so a per-logical-file read is exercised."""
    return [
        null_gap(curves, depth, "NPHI", 5400.0, 5430.0),
        flatline(curves, depth, "CALI", 6000.0, 6030.0),
    ]


#: One logical file, three frames. The common case: a triple combo, a sonic
#: pass, and a caliper on separate frames because they were recorded at
#: different sample rates.
DLIS_SINGLE = DlisWellSpec(
    name="DSYNTH-01",
    operator="petromcp synthetic",
    start=5000.0,
    stop=9000.0,
    step=0.5,
    seed=42,
    logical_files=(
        DlisLogicalFileSpec(
            origin_id="RUN-1",
            frames=(
                DlisFrameSpec("TRIPLE_COMBO", ("GR", "RHOB", "NPHI"), "DEPT"),
                DlisFrameSpec("SONIC", ("DT",), "DEPT_SONIC"),
                DlisFrameSpec("CALIPER", ("CALI",), "DEPT_CALIPER"),
            ),
        ),
    ),
    apply_defects=_single_run_defects,
)

#: Two logical files: two logging runs in one physical file. This is the shape
#: LAS cannot express at all, and the reason `read_dlis_file` reports an
#: indexed list rather than a single curve set.
DLIS_MULTI = DlisWellSpec(
    name="DSYNTH-02",
    operator="petromcp synthetic",
    start=5200.0,
    stop=8600.0,
    step=0.5,
    seed=43,
    logical_files=(
        DlisLogicalFileSpec(
            origin_id="RUN-1",
            frames=(DlisFrameSpec("OPEN_HOLE", ("GR", "NPHI"), "DEPT"),),
        ),
        DlisLogicalFileSpec(
            origin_id="RUN-2",
            frames=(DlisFrameSpec("CASED_HOLE", ("CALI",), "DEPT_CASED"),),
        ),
    ),
    apply_defects=_multi_run_defects,
)

DLIS_WELLS: dict[str, DlisWellSpec] = {
    DLIS_SINGLE.name: DLIS_SINGLE,
    DLIS_MULTI.name: DLIS_MULTI,
}

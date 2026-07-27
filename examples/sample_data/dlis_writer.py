"""Write DLIS files for testing. Development only.

petromcp never writes DLIS — it is a reader. This module exists so the test
suite and the synthetic-data generator can produce DLIS input, and it depends
on `dliswriter`, which is in the dev dependency group only.

Two RP66 v1 constraints are enforced here rather than left to fail deep inside
`dliswriter`, because both were hit during the v0.7 spike:

- **A channel belongs to exactly one frame.** Sharing an index channel between
  two frames warns and produces a file that misrepresents its own structure, so
  each frame must carry its own index channel under a distinct name.
- **Units come from a controlled vocabulary.** RP66 has no compound density
  unit, so `g/cm3` is not in the list. It round-trips correctly but warns, and
  real service-company files use it anyway, so the warning is suppressed rather
  than the unit changed.

`dliswriter` 1.2.0 also cannot write more than one logical file: it fails with
`ValueError: No dataset '<name>' found in the source data` because its data
resolution is not scoped per logical file. Multi-logical-file coverage
therefore needs a committed fixture; see the v0.7 design doc.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

#: One frame: channel name -> (values, unit). Insertion order is preserved, and
#: the first entry is treated as the frame's index channel.
FrameSpec = dict[str, tuple[np.ndarray, str]]


def write_minimal_dlis(
    path: Path,
    well_name: str,
    frames: dict[str, FrameSpec],
    company: str = "petromcp synthetic",
    origin_id: str = "PETROMCP",
    index_type: str = "BOREHOLE-DEPTH",
) -> Path:
    """Write one logical file containing `frames`.

    The first channel of each frame is its index. Channel names must be unique
    across the whole file, not just within a frame, because RP66 forbids
    sharing a channel between frames — pass `DEPT_A`/`DEPT_B` rather than
    `DEPT` twice.

    Raises:
        ValueError: if a channel name is reused across frames, or a frame is
            empty. Both produce a structurally wrong file rather than an error
            if left to `dliswriter`.
    """
    from dliswriter import DLISFile  # noqa: PLC0415  dev-only dependency

    seen: dict[str, str] = {}
    for frame_name, spec in frames.items():
        if not spec:
            raise ValueError(f"frame {frame_name!r} has no channels")
        for channel in spec:
            if channel in seen:
                raise ValueError(
                    f"channel {channel!r} appears in both {seen[channel]!r} and "
                    f"{frame_name!r}; RP66 v1 allows a channel in one frame only, "
                    "so give each frame its own index channel name"
                )
            seen[channel] = frame_name

    dlis_file = DLISFile()
    logical = dlis_file.add_logical_file()
    logical.add_origin(origin_id, well_name=well_name, company=company)

    for frame_name, spec in frames.items():
        channels = [
            logical.add_channel(name, data=np.asarray(values, dtype=np.float64), units=unit)
            for name, (values, unit) in spec.items()
        ]
        logical.add_frame(frame_name, channels=tuple(channels), index_type=index_type)

    path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        # Suppresses the RP66 unit-vocabulary warning for units like g/cm3,
        # which round-trip correctly and match what real files carry. Also
        # silences dliswriter's progress bar chatter.
        warnings.simplefilter("ignore")
        dlis_file.write(path)
    return path

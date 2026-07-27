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

`dliswriter` 1.2.0 cannot write more than one logical file directly: it fails
with `ValueError: No dataset '<name>' found in the source data` because its data
resolution is not scoped per logical file. `concatenate_logical_files` works
around that — see its docstring.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import warnings
from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np

#: Length of the RP66 v1 Storage Unit Label, which opens a *physical* file. A
#: second one mid-stream is what makes naive concatenation fail.
STORAGE_UNIT_LABEL_BYTES = 80

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

    path.parent.mkdir(parents=True, exist_ok=True)

    # The suppression has to span channel construction, not just the write:
    # dliswriter validates units inside `add_channel`, so wrapping only
    # `write()` still let the RP66 vocabulary complaint through. Validation of
    # *our* arguments happens above, outside the silence, so a real mistake is
    # never hidden.
    with _quiet_dliswriter():
        dlis_file = DLISFile()
        logical = dlis_file.add_logical_file()
        logical.add_origin(origin_id, well_name=well_name, company=company)

        for frame_name, spec in frames.items():
            channels = [
                logical.add_channel(
                    name, data=np.asarray(values, dtype=np.float64), units=unit
                )
                for name, (values, unit) in spec.items()
            ]
            logical.add_frame(frame_name, channels=tuple(channels), index_type=index_type)

        dlis_file.write(path)
    return path


@contextlib.contextmanager
def _silenced_fds() -> Iterator[None]:
    """Redirect the process's stdout and stderr file descriptors to /dev/null.

    `contextlib.redirect_stderr` is not enough here, and finding that out cost
    a false-passing test: it rebinds `sys.stderr`, while `dliswriter`'s progress
    bar writes past it to the underlying descriptor. Only an `os.dup2` swap
    catches every emission mechanism.

    Python-level buffers are flushed on both sides so nothing already queued
    escapes into /dev/null, and nothing written here surfaces later.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    try:
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            yield
            sys.stdout.flush()
            sys.stderr.flush()
    finally:
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])


@contextlib.contextmanager
def _quiet_dliswriter() -> Iterator[None]:
    """Suppress everything dliswriter prints, from three separate sources.

    Suppressing any one of them is not enough, and each cost a debugging round:

    - The RP66 unit-vocabulary complaint is a **log record**, not a warning, and
      it fires inside `add_channel` rather than `write`. It triggers for
      `g/cm3`, which round-trips correctly and is what real files carry, so it
      is noise.
    - The progress bar writes to the **file descriptor**, past `sys.stderr`, so
      `contextlib.redirect_stderr` does not touch it.
    - `warnings`, for completeness.

    The logger level is restored afterwards, so this never leaves a caller's
    logging configuration altered.
    """
    logger = logging.getLogger("dliswriter")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        with warnings.catch_warnings(), _silenced_fds():
            warnings.simplefilter("ignore")
            yield
    finally:
        logger.setLevel(previous_level)


def concatenate_logical_files(path: Path, parts: Sequence[Path]) -> Path:
    """Combine single-logical-file DLIS files into one multi-logical-file DLIS.

    RP66 v1 defines a physical file as a Storage Unit Label followed by a
    sequence of logical files. `dliswriter` cannot emit more than one logical
    file itself, but concatenating its output works provided every part after
    the first has its Storage Unit Label removed — a second SUL mid-stream is
    what a naive concatenation gets rejected for.

    Verified against `dlisio` 1.0.4: the result reads back as N logical files
    with their frames and channels intact.

    Raises:
        ValueError: if `parts` is empty, or a part is too short to carry a SUL.
    """
    if not parts:
        raise ValueError("concatenate_logical_files needs at least one part")

    chunks: list[bytes] = []
    for index, part in enumerate(parts):
        raw = part.read_bytes()
        if len(raw) <= STORAGE_UNIT_LABEL_BYTES:
            raise ValueError(f"{part.name} is too short to be a DLIS file")
        # The first part keeps its label; it opens the physical file.
        chunks.append(raw if index == 0 else raw[STORAGE_UNIT_LABEL_BYTES:])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(chunks))
    return path

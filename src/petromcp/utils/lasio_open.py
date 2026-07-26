"""lasio quirk shims: encoding detection and a non-throwing depth index.

`lasio.read()` defaults to latin-1, which silently produces mojibake on
UTF-8 LAS files (a real-world hazard for Spanish, French, Norwegian wells).
`read_lasio` tries UTF-8 first and falls back to latin-1 when the file is
not valid UTF-8.

`safe_index` covers the other quirk: a LAS file with header sections but no
`~ASCII` block — a truncated log, typically a transfer that died mid-write —
makes `LASFile.index` raise IndexError. Every tool wants the same answer
there ("no depth data"), so the guard lives here rather than in each tool.
"""

from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np


def read_lasio(path: Path) -> lasio.LASFile:
    try:
        return lasio.read(str(path), encoding="utf-8")
    except UnicodeDecodeError:
        return lasio.read(str(path), encoding="latin-1")


def safe_index(las: lasio.LASFile) -> np.ndarray:
    """Return the depth index as a float array, or an empty array.

    Never raises. An empty result means the file carries no curve data and
    the caller should degrade rather than fail.
    """
    try:
        index = las.index  # type: ignore[attr-defined]
    except IndexError:
        return np.empty(0, dtype=float)
    return np.asarray(index, dtype=float)

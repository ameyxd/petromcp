"""LAS file opener with UTF-8 preference and latin-1 fallback.

`lasio.read()` defaults to latin-1, which silently produces mojibake on
UTF-8 LAS files (a real-world hazard for Spanish, French, Norwegian wells).
This helper tries UTF-8 first and falls back to latin-1 when the file is
not valid UTF-8.
"""

from __future__ import annotations

from pathlib import Path

import lasio


def read_lasio(path: Path) -> lasio.LASFile:
    try:
        return lasio.read(str(path), encoding="utf-8")
    except UnicodeDecodeError:
        return lasio.read(str(path), encoding="latin-1")

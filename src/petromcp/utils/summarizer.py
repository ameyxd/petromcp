"""Token-budgeted output helpers."""

from __future__ import annotations

import numpy as np


def downsample(arr: np.ndarray, cap: int) -> tuple[np.ndarray, bool]:
    """Return `arr` (or every Nth sample) capped at `cap` items.

    Returns the (possibly subsampled) array and a flag indicating whether
    sampling actually occurred.
    """
    n = len(arr)
    if n <= cap:
        return arr, False
    stride = max(1, n // cap)
    return arr[::stride][:cap], True

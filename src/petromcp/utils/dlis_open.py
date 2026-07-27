"""DLIS loading with error messages a model can act on.

`dlisio` reports failures accurately and in the vocabulary of RP66 v1:
"Visible Record", "Logical Record Segment", "tapemark". Correct for a format
engineer, useless to a language model deciding what to tell the user, and
mostly noise in a tool result. Everything raised out of a load is translated
into `DLISReadError` with the file named and one plain sentence about what is
wrong. The original is chained so a maintainer can still see it.

This is the opposite posture from `lasio_open.safe_index`. A truncated LAS
still parses far enough to yield a useful partial summary, so the LAS tools
degrade. A DLIS that fails to load yields nothing at all, so there is nothing
to degrade to and a clear error is the honest answer.

Failure modes below were each observed against `dlisio` 1.0.4, not inferred.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import dlisio


class DLISReadError(Exception):
    """Raised when a file cannot be read as DLIS.

    Covers truncation, an empty file, a non-DLIS file, and structural
    corruption. The distinction rarely changes what the caller should do, so
    they share one type rather than making a model choose between them.
    """


#: `dlisio` raises `RuntimeError` for truncation, non-DLIS input, and
#: structural corruption, and `EOFError` for an empty file. `OSError` covers
#: anything the platform reports while reading.
_LOAD_FAILURES = (RuntimeError, EOFError, OSError)


@contextmanager
def load_dlis(path: Path | str) -> Iterator[Any]:
    """Open a DLIS file, yielding its logical files.

    Raises:
        FileNotFoundError: if `path` does not exist. A missing file is a caller
            mistake and should not be reported as corruption.
        DLISReadError: if the file exists but cannot be parsed as DLIS.
    """
    target = Path(path)
    # Checked before handing to dlisio, whose own message for a missing file is
    # the same opaque read error it gives for a corrupt one.
    if not target.exists():
        raise FileNotFoundError(target)

    try:
        batch = dlisio.dlis.load(str(target))
    except _LOAD_FAILURES as exc:
        raise DLISReadError(
            f"petromcp: {target.name} is not a readable DLIS file. "
            "It may be truncated, empty, or in another format. "
            "Check the file opens in your usual log viewer before retrying."
        ) from exc

    try:
        yield batch
    finally:
        # dlisio holds an mmap of the file; leaving it open blocks rewrites and
        # deletes on Windows.
        batch.close()

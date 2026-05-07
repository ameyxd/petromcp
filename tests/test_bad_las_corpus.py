"""Bad-LAS fixture corpus.

Each fixture is a malformed or unusual LAS file. These tests lock in current
parsing behaviour: do we raise, do we return a degraded summary, or do we
silently parse to nothing? If a fixture's outcome surprises us, that is a
follow-up issue, not a v0.2 blocker.
"""

from pathlib import Path

import pytest

from petromcp.tools.las import read_las_file

FIXTURES = Path(__file__).parent / "fixtures" / "bad_las"


def _allowlist() -> list[Path]:
    return [FIXTURES]


def test_empty_file_raises() -> None:
    # lasio raises KeyError on a zero-byte file (no ~ sections found).
    with pytest.raises(KeyError):
        read_las_file(str(FIXTURES / "empty.las"), _allowlist())


def test_truncated_file_raises() -> None:
    # Spec expected a degraded summary with zero curves, but lasio raises
    # IndexError on a file that has header sections but no ~Curves or ~ASCII.
    # Surprise: follow-up issue to decide whether petromcp should catch this.
    with pytest.raises(IndexError):
        read_las_file(str(FIXTURES / "truncated.las"), _allowlist())


def test_crlf_file_parses_normally() -> None:
    s = read_las_file(str(FIXTURES / "crlf.las"), _allowlist())
    assert s.well_name == "CRLF"
    names = [c.name for c in s.curves]
    assert "GR" in names
    assert s.total_points == 3


def test_unicode_well_name_parses() -> None:
    s = read_las_file(str(FIXTURES / "unicode_well_name.las"), _allowlist())
    assert s.well_name is not None
    # lasio reads the UTF-8 file as latin-1, producing mojibake: "Pozo-\xc3\x91o\xc3\xb1o".
    # Characters above 127 are still present, so the check holds — but the
    # well name is garbled. Follow-up: pass encoding="utf-8" to lasio.read().
    assert any(ord(c) > 127 for c in s.well_name)

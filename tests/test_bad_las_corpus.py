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


def test_truncated_file_returns_summary_with_zero_curves() -> None:
    s = read_las_file(str(FIXTURES / "truncated.las"), _allowlist())
    assert s.well_name == "TRUNCATED"
    assert [c.name for c in s.curves] == []
    assert s.total_points == 0


def test_crlf_file_parses_normally() -> None:
    s = read_las_file(str(FIXTURES / "crlf.las"), _allowlist())
    assert s.well_name == "CRLF"
    names = [c.name for c in s.curves]
    assert "GR" in names
    assert s.total_points == 3


def test_unicode_well_name_parses() -> None:
    s = read_las_file(str(FIXTURES / "unicode_well_name.las"), _allowlist())
    # Correctly decoded UTF-8, not latin-1 mojibake.
    assert s.well_name == "Pozo-Ñoño"

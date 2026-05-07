from pathlib import Path

import pytest

from petromcp.tools.las import read_las_file
from petromcp.utils import access_log


@pytest.fixture
def isolated_log(tmp_path: Path):
    log_file = tmp_path / "access.log"
    access_log.configure(log_file=log_file, enabled=True)
    yield log_file
    access_log.configure(log_file=None, enabled=None)


def test_log_access_writes_line(isolated_log: Path) -> None:
    access_log.log_access("read_las_file", Path("/data/wells/A.las"))
    text = isolated_log.read_text()
    assert "tool=read_las_file" in text
    assert "path=/data/wells/A.las" in text


def test_log_access_disabled_writes_nothing(tmp_path: Path) -> None:
    log_file = tmp_path / "no.log"
    access_log.configure(log_file=log_file, enabled=False)
    try:
        access_log.log_access("x", Path("/y"))
        assert not log_file.exists()
    finally:
        access_log.configure(log_file=None, enabled=None)


def test_tool_call_emits_log_entry(
    isolated_log: Path, tiny_las: Path, allowlist: list[Path]
) -> None:
    read_las_file(str(tiny_las), allowlist)
    text = isolated_log.read_text()
    assert "tool=read_las_file" in text
    assert str(tiny_las.resolve()) in text

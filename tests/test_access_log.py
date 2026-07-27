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


class TestRotation:
    """The access log is the audit trail for a tool whose privacy claim is "you
    can see everything it read". An unbounded file nobody can open is not an
    audit trail, so it rotates."""

    def test_rotates_once_the_size_limit_is_passed(self, tmp_path: Path) -> None:
        log = tmp_path / "access.log"
        access_log.configure(log_file=log, max_bytes=200, backup_count=3)
        try:
            for i in range(200):
                access_log.log_access("read_las_file", Path(f"/wells/{i:04d}.las"))
        finally:
            access_log.configure()
        rotated = sorted(p.name for p in tmp_path.glob("access.log*"))
        assert len(rotated) > 1, f"never rotated: {rotated}"

    def test_keeps_no_more_than_backup_count_rotations(self, tmp_path: Path) -> None:
        log = tmp_path / "access.log"
        access_log.configure(log_file=log, max_bytes=200, backup_count=2)
        try:
            for i in range(400):
                access_log.log_access("read_las_file", Path(f"/wells/{i:04d}.las"))
        finally:
            access_log.configure()
        files = sorted(p.name for p in tmp_path.glob("access.log*"))
        # The live file plus at most `backup_count` rotations.
        assert len(files) <= 3, f"retention exceeded: {files}"

    def test_the_most_recent_entry_is_in_the_live_file(self, tmp_path: Path) -> None:
        """Rotation must not send new writes to an archived file."""
        log = tmp_path / "access.log"
        access_log.configure(log_file=log, max_bytes=200, backup_count=2)
        try:
            for i in range(200):
                access_log.log_access("read_las_file", Path(f"/wells/{i:04d}.las"))
            access_log.log_access("read_las_file", Path("/wells/LAST.las"))
        finally:
            access_log.configure()
        assert "LAST.las" in log.read_text()

    def test_rotation_is_disabled_when_max_bytes_is_zero(self, tmp_path: Path) -> None:
        """An operator who wants one unbroken file can have one, deliberately."""
        log = tmp_path / "access.log"
        access_log.configure(log_file=log, max_bytes=0, backup_count=0)
        try:
            for i in range(300):
                access_log.log_access("read_las_file", Path(f"/wells/{i:04d}.las"))
        finally:
            access_log.configure()
        assert sorted(p.name for p in tmp_path.glob("access.log*")) == ["access.log"]

    def test_defaults_come_from_config_and_are_bounded(self) -> None:
        from petromcp.config import LoggingConfig

        cfg = LoggingConfig()
        assert cfg.max_bytes > 0, "default must rotate; unbounded was the bug"
        assert cfg.backup_count > 0, "keeping zero rotations discards the trail"

    def test_negative_sizes_are_rejected(self) -> None:
        from pydantic import ValidationError

        from petromcp.config import LoggingConfig

        with pytest.raises(ValidationError):
            LoggingConfig(max_bytes=-1)
        with pytest.raises(ValidationError):
            LoggingConfig(backup_count=-1)

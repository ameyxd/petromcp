from pathlib import Path

import pytest

from petromcp.utils.path_validator import PathNotAllowedError, validate_path


def test_allows_path_inside_allowlist(tmp_path: Path) -> None:
    allowed = [tmp_path]
    target = tmp_path / "well.las"
    target.touch()
    result = validate_path(target, allowed)
    assert result == target.resolve()


def test_denies_path_outside_allowlist(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    target = other / "secret.las"
    target.touch()
    with pytest.raises(PathNotAllowedError) as exc:
        validate_path(target, [allowed_dir])
    assert "not in allowed_paths" in str(exc.value)


def test_denies_traversal_via_symlink(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    secret = tmp_path / "secret.las"
    secret.touch()
    link = allowed_dir / "link.las"
    link.symlink_to(secret)
    with pytest.raises(PathNotAllowedError):
        validate_path(link, [allowed_dir])


def test_expands_user_in_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "wells" / "a.las"
    target.parent.mkdir()
    target.touch()
    result = validate_path(target, [Path("~/wells")])
    assert result == target.resolve()


def test_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_path(tmp_path / "nope.las", [tmp_path])

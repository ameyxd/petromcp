import json
from pathlib import Path

import pytest

from petromcp.config import Config, LoggingConfig, load_config, resolve_allowed_paths


def test_load_config_from_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "allowed_paths": [str(tmp_path)],
            }
        )
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.allowed_paths == [tmp_path.resolve()]


def test_load_config_returns_default_when_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.json")
    assert cfg.allowed_paths == []
    assert cfg.logging.enabled is True


def test_load_config_rejects_invalid_paths(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"allowed_paths": [123]}))
    with pytest.raises(ValueError):
        load_config(cfg_path)


def test_logging_config_overrides(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    target_log = str(tmp_path / "custom.log")
    cfg_path.write_text(
        json.dumps(
            {
                "allowed_paths": [str(tmp_path)],
                "logging": {"enabled": False, "log_file": target_log},
            }
        )
    )
    cfg = load_config(cfg_path)
    assert cfg.logging.enabled is False
    assert cfg.logging.log_file == Path(target_log)


def test_logging_config_defaults() -> None:
    lc = LoggingConfig()
    assert lc.enabled is True
    assert str(lc.log_file).endswith(".petromcp/access.log")


class TestResolveAllowedPaths:
    """`serve --allow-path` unions with the config file rather than replacing
    it. The union is what the MCPB bundle relies on: the host passes the
    directories the user picked at install time, while a config file written
    later still applies."""

    def test_returns_config_paths_when_no_cli_paths(self, tmp_path: Path) -> None:
        assert resolve_allowed_paths([tmp_path], []) == [tmp_path]

    def test_returns_cli_paths_when_no_config(self, tmp_path: Path) -> None:
        assert resolve_allowed_paths([], [str(tmp_path)]) == [tmp_path]

    def test_unions_both_sources(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        assert set(resolve_allowed_paths([a], [str(b)])) == {a, b}

    def test_deduplicates_across_sources(self, tmp_path: Path) -> None:
        assert resolve_allowed_paths([tmp_path], [str(tmp_path)]) == [tmp_path]

    def test_expands_and_resolves_cli_paths(self, tmp_path: Path) -> None:
        nested = tmp_path / "wells"
        nested.mkdir()
        got = resolve_allowed_paths([], [str(tmp_path / "wells" / "." )])
        assert got == [nested]

    def test_empty_everywhere_stays_default_deny(self) -> None:
        """The whole privacy posture rests on this: no config and no flag
        means the server can read nothing."""
        assert resolve_allowed_paths([], []) == []

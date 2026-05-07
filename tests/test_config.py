import json
from pathlib import Path

import pytest

from petromcp.config import Config, LoggingConfig, load_config


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

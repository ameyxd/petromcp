import json
from pathlib import Path

import pytest

from petromcp.config import Config, load_config


def test_load_config_from_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "allowed_paths": [str(tmp_path)],
                "read_only": True,
                "max_file_size_mb": 100,
            }
        )
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.allowed_paths == [tmp_path.resolve()]
    assert cfg.read_only is True


def test_load_config_returns_default_when_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.json")
    assert cfg.allowed_paths == []
    assert cfg.read_only is True


def test_load_config_rejects_invalid_paths(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"allowed_paths": [123]}))
    with pytest.raises(ValueError):
        load_config(cfg_path)

import json
from pathlib import Path

from petromcp.cli import install_into_config, uninstall_from_config


def test_install_writes_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    install_into_config(
        cfg, server_name="petromcp", command="uv", args=["run", "petromcp", "serve"]
    )
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["petromcp"]["command"] == "uv"
    assert data["mcpServers"]["petromcp"]["args"] == ["run", "petromcp", "serve"]


def test_install_creates_file_if_missing(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    install_into_config(
        cfg, server_name="petromcp", command="uv", args=["run", "petromcp", "serve"]
    )
    assert cfg.exists()
    assert "petromcp" in json.loads(cfg.read_text())["mcpServers"]


def test_uninstall_removes_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"petromcp": {"command": "x"}, "other": {"command": "y"}}})
    )
    uninstall_from_config(cfg, server_name="petromcp")
    data = json.loads(cfg.read_text())
    assert "petromcp" not in data["mcpServers"]
    assert "other" in data["mcpServers"]


def test_uninstall_is_idempotent(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    uninstall_from_config(cfg, server_name="petromcp")  # should not raise

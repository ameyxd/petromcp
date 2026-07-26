import json
from pathlib import Path

import pytest

from petromcp import cli
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


def test_install_command_pins_project_and_skips_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    monkeypatch.setattr(cli, "CLAUDE_DESKTOP_CONFIG", cfg)

    rc = cli.main(["install", "--client", "claude-desktop"])
    assert rc == 0

    args = json.loads(cfg.read_text())["mcpServers"]["petromcp"]["args"]
    assert "--no-sync" in args
    assert "--project" in args
    project_idx = args.index("--project")
    assert args[project_idx + 1] == str(cli.PROJECT_ROOT)
    assert args[-2:] == ["petromcp", "serve"]


class TestServeAllowPath:
    """MCPB expands a `multiple: true` directory config into separate argv
    entries, so `--allow-path` has to swallow a run of them, not just one."""

    def test_accepts_several_directories_after_one_flag(self) -> None:
        args = cli.build_parser().parse_args(
            ["serve", "--allow-path", "/wells/a", "/wells/b"]
        )
        assert args.allow_path == ["/wells/a", "/wells/b"]

    def test_accepts_the_flag_repeated(self) -> None:
        args = cli.build_parser().parse_args(
            ["serve", "--allow-path", "/wells/a", "--allow-path", "/wells/b"]
        )
        assert args.allow_path == ["/wells/a", "/wells/b"]

    def test_defaults_to_no_extra_paths(self) -> None:
        args = cli.build_parser().parse_args(["serve"])
        assert args.allow_path == []

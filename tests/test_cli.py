import json
from dataclasses import replace
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


def _point_host_at(monkeypatch: pytest.MonkeyPatch, client: str, path: Path) -> None:
    """Redirect one host's config file, so no test touches a real one."""
    from petromcp import hosts

    original = hosts.HOSTS[client]
    monkeypatch.setitem(
        hosts.HOSTS, client, replace(original, config_path=lambda: path)
    )


class TestInstall:
    """`petromcp install` writes one entry into a host's config.

    Hosts nest that entry under different keys — `mcpServers` for Claude Desktop
    and Cursor, `mcp.servers` for VS Code. Writing the wrong key produces a valid
    file the host silently ignores, which is why every host is covered here.
    """

    def test_defaults_to_the_published_package(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Most users have no checkout, so the default must not assume one."""
        cfg = tmp_path / "claude_desktop_config.json"
        _point_host_at(monkeypatch, "claude-desktop", cfg)

        assert cli.main(["install"]) == 0
        entry = json.loads(cfg.read_text())["mcpServers"]["petromcp"]
        assert entry["command"] == "uvx"
        assert entry["args"] == ["petroleum-mcp", "serve"]

    def test_from_source_pins_the_checkout_and_skips_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--no-sync` matters on macOS: the implicit sync re-hides the .pth
        files and breaks the entry point."""
        cfg = tmp_path / "claude_desktop_config.json"
        _point_host_at(monkeypatch, "claude-desktop", cfg)

        assert cli.main(["install", "--from-source"]) == 0
        args = json.loads(cfg.read_text())["mcpServers"]["petromcp"]["args"]
        assert "--no-sync" in args
        assert args[args.index("--project") + 1] == str(cli.PROJECT_ROOT)
        assert args[-2:] == ["petromcp", "serve"]

    @pytest.mark.parametrize(
        "client", ["claude-desktop", "claude-code", "cursor", "codex", "vscode"]
    )
    def test_every_host_installs(
        self, client: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from petromcp import hosts

        cfg = tmp_path / f"{client}.json"
        _point_host_at(monkeypatch, client, cfg)
        assert cli.main(["install", "--client", client]) == 0

        data = json.loads(cfg.read_text())
        node = data
        for key in hosts.HOSTS[client].server_key:
            assert key in node, f"{client}: missing key {key!r}"
            node = node[key]
        assert "petromcp" in node

    def test_vscode_uses_its_own_nesting_and_transport(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VS Code reads `mcp.servers`, not `mcpServers`, and wants the
        transport named. The wrong shape is silently ignored."""
        cfg = tmp_path / "vscode.json"
        _point_host_at(monkeypatch, "vscode", cfg)
        assert cli.main(["install", "--client", "vscode"]) == 0

        data = json.loads(cfg.read_text())
        assert "mcpServers" not in data
        assert data["mcp"]["servers"]["petromcp"]["type"] == "stdio"

    def test_allow_path_is_written_into_the_host_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "claude_desktop_config.json"
        _point_host_at(monkeypatch, "claude-desktop", cfg)
        wells = tmp_path / "wells"
        wells.mkdir()

        assert cli.main(["install", "--allow-path", str(wells)]) == 0
        args = json.loads(cfg.read_text())["mcpServers"]["petromcp"]["args"]
        assert args[-2:] == ["--allow-path", str(wells)]

    def test_existing_servers_are_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The file is the user's, and usually holds their other servers."""
        cfg = tmp_path / "claude_desktop_config.json"
        cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}},
                                   "unrelated": {"keep": True}}))
        _point_host_at(monkeypatch, "claude-desktop", cfg)

        assert cli.main(["install"]) == 0
        data = json.loads(cfg.read_text())
        assert data["mcpServers"]["other"] == {"command": "x"}
        assert data["unrelated"] == {"keep": True}

    def test_reinstalling_replaces_rather_than_duplicates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "claude_desktop_config.json"
        _point_host_at(monkeypatch, "claude-desktop", cfg)
        cli.main(["install", "--from-source"])
        cli.main(["install"])
        entry = json.loads(cfg.read_text())["mcpServers"]["petromcp"]
        assert entry["command"] == "uvx"

    def test_refuses_to_overwrite_a_corrupt_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Overwriting would destroy the user's other servers."""
        cfg = tmp_path / "claude_desktop_config.json"
        cfg.write_text("{ this is not json")
        _point_host_at(monkeypatch, "claude-desktop", cfg)
        with pytest.raises(SystemExit, match="not valid JSON"):
            cli.main(["install"])

    def test_an_unknown_client_is_rejected_by_the_parser(self) -> None:
        with pytest.raises(SystemExit):
            cli.main(["install", "--client", "emacs"])


class TestUninstall:
    def test_removes_only_petromcp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "claude_desktop_config.json"
        _point_host_at(monkeypatch, "claude-desktop", cfg)
        cli.main(["install"])
        cfg.write_text(json.dumps({**json.loads(cfg.read_text()),
                                   "mcpServers": {**json.loads(cfg.read_text())["mcpServers"],
                                                  "other": {"command": "x"}}}))

        assert cli.main(["uninstall"]) == 0
        servers = json.loads(cfg.read_text())["mcpServers"]
        assert "petromcp" not in servers
        assert "other" in servers

    def test_uninstalling_when_absent_is_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _point_host_at(monkeypatch, "cursor", tmp_path / "nothing.json")
        assert cli.main(["uninstall", "--client", "cursor"]) == 0

    def test_uninstalls_from_the_host_it_was_told_to(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vscode = tmp_path / "vscode.json"
        _point_host_at(monkeypatch, "vscode", vscode)
        cli.main(["install", "--client", "vscode"])
        assert cli.main(["uninstall", "--client", "vscode"]) == 0
        assert "petromcp" not in json.loads(vscode.read_text())["mcp"]["servers"]


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


class TestConsoleScripts:
    """`uvx <package>` runs the executable whose name matches the package.

    The distribution is `petroleum-mcp` while the historical script is
    `petromcp`, so without an alias every documented install command fails
    with "executable not found". These tests fail if the alias is dropped.
    """

    def test_both_console_scripts_are_installed(self) -> None:
        from importlib.metadata import entry_points

        names = {
            ep.name
            for ep in entry_points(group="console_scripts")
            if ep.value.startswith("petromcp.cli")
        }
        assert {"petromcp", "petroleum-mcp"} <= names, f"got {names}"

    def test_the_alias_matching_the_distribution_name_exists(self) -> None:
        """This is the one uvx needs; the other is for PATH installs."""
        from importlib.metadata import entry_points

        from petromcp import DISTRIBUTION_NAME

        names = {ep.name for ep in entry_points(group="console_scripts")}
        assert DISTRIBUTION_NAME in names

    def test_both_scripts_point_at_the_same_entry_point(self) -> None:
        from importlib.metadata import entry_points

        targets = {
            ep.value
            for ep in entry_points(group="console_scripts")
            if ep.name in {"petromcp", "petroleum-mcp"}
        }
        assert len(targets) == 1, f"aliases diverged: {targets}"

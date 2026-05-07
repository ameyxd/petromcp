"""petromcp CLI: serve, install, uninstall.

Install/uninstall edit the host application's config file (Claude Desktop
in v1). The edit is targeted: only the `mcpServers.<name>` key is touched.
Existing entries are preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLAUDE_DESKTOP_CONFIG = (
    Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser()
)

# Project root: src/petromcp/cli.py -> src/petromcp -> src -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]

USER_CONFIG_PATH = Path("~/.petromcp/config.json").expanduser()

DEFAULT_USER_CONFIG: dict[str, object] = {
    "allowed_paths": [],
    "logging": {
        "enabled": True,
        "log_file": "~/.petromcp/access.log",
    },
}


def install_into_config(
    config_path: Path, server_name: str, command: str, args: list[str]
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(config_path.read_text()) if config_path.exists() else {}
    servers = data.setdefault("mcpServers", {})
    servers[server_name] = {"command": command, "args": args}
    config_path.write_text(json.dumps(data, indent=2))


def uninstall_from_config(config_path: Path, server_name: str) -> None:
    if not config_path.exists():
        return
    data = json.loads(config_path.read_text())
    servers = data.get("mcpServers", {})
    if server_name in servers:
        del servers[server_name]
        config_path.write_text(json.dumps(data, indent=2))


def _read_user_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return dict(DEFAULT_USER_CONFIG)
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _write_user_config(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _resolve_user_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _cmd_serve(_: argparse.Namespace) -> int:
    from petromcp.server import main as serve_main

    serve_main()
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    if args.client != "claude-desktop":
        print(f"unsupported client: {args.client}", file=sys.stderr)
        return 2
    # `--project` pins uv to the petromcp checkout regardless of where Claude
    # Desktop spawns the process from. `--no-sync` prevents the implicit sync
    # that re-applies UF_HIDDEN to .pth files on macOS.
    install_into_config(
        CLAUDE_DESKTOP_CONFIG,
        server_name="petromcp",
        command="uv",
        args=[
            "run",
            "--no-sync",
            "--project",
            str(PROJECT_ROOT),
            "petromcp",
            "serve",
        ],
    )
    print(f"installed petromcp into {CLAUDE_DESKTOP_CONFIG}")
    return 0


def _cmd_uninstall(_: argparse.Namespace) -> int:
    uninstall_from_config(CLAUDE_DESKTOP_CONFIG, server_name="petromcp")
    print(f"removed petromcp from {CLAUDE_DESKTOP_CONFIG}")
    return 0


def _cmd_config_show(_: argparse.Namespace) -> int:
    if not USER_CONFIG_PATH.exists():
        print(
            f"# (default — no config file at {USER_CONFIG_PATH})",
            file=sys.stderr,
        )
        print(json.dumps(DEFAULT_USER_CONFIG, indent=2))
        return 0
    print(USER_CONFIG_PATH.read_text())
    return 0


def _cmd_config_init(_: argparse.Namespace) -> int:
    if USER_CONFIG_PATH.exists():
        print(
            f"config already exists at {USER_CONFIG_PATH}; "
            "remove it manually to re-init",
            file=sys.stderr,
        )
        return 2
    _write_user_config(USER_CONFIG_PATH, dict(DEFAULT_USER_CONFIG))
    print(f"wrote default config to {USER_CONFIG_PATH}")
    return 0


def _cmd_config_add_path(args: argparse.Namespace) -> int:
    target = _resolve_user_path(args.path)
    data = _read_user_config(USER_CONFIG_PATH)
    raw = data.setdefault("allowed_paths", [])
    paths: list[str] = raw if isinstance(raw, list) else []
    data["allowed_paths"] = paths
    if target in paths:
        print(f"already in allowlist: {target}")
        return 0
    paths.append(target)
    _write_user_config(USER_CONFIG_PATH, data)
    print(f"added {target}")
    return 0


def _cmd_config_remove_path(args: argparse.Namespace) -> int:
    target = _resolve_user_path(args.path)
    data = _read_user_config(USER_CONFIG_PATH)
    raw = data.get("allowed_paths", [])
    paths: list[str] = raw if isinstance(raw, list) else []
    if target not in paths:
        print(f"not in allowlist: {target}", file=sys.stderr)
        return 0
    data["allowed_paths"] = [p for p in paths if p != target]
    _write_user_config(USER_CONFIG_PATH, data)
    print(f"removed {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="petromcp")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="run the MCP server").set_defaults(func=_cmd_serve)

    install = sub.add_parser("install", help="install into a host config")
    install.add_argument("--client", default="claude-desktop")
    install.set_defaults(func=_cmd_install)

    sub.add_parser("uninstall", help="remove from Claude Desktop config").set_defaults(
        func=_cmd_uninstall
    )

    config = sub.add_parser("config", help="manage ~/.petromcp/config.json")
    config_sub = config.add_subparsers(dest="config_cmd", required=True)
    config_sub.add_parser("show", help="print the current config").set_defaults(
        func=_cmd_config_show
    )
    config_sub.add_parser("init", help="write a default config if missing").set_defaults(
        func=_cmd_config_init
    )
    add_path = config_sub.add_parser("add-path", help="add a directory to allowed_paths")
    add_path.add_argument("path")
    add_path.set_defaults(func=_cmd_config_add_path)
    remove_path = config_sub.add_parser(
        "remove-path", help="remove a directory from allowed_paths"
    )
    remove_path.add_argument("path")
    remove_path.set_defaults(func=_cmd_config_remove_path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

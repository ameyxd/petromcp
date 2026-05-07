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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

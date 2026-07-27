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

from pydantic import ValidationError

from petromcp import DISTRIBUTION_NAME, hosts
from petromcp.config import Config

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


def _server_map(data: dict, keys: tuple[str, ...], *, create: bool) -> dict | None:
    """Walk to the nested map a host keeps its servers in.

    Hosts differ: `mcpServers` for Claude Desktop and Cursor, `mcp.servers` for
    VS Code. Writing to the wrong key produces a valid file the host silently
    ignores, which is why the key comes from the host definition rather than
    being assumed.
    """
    node: dict = data
    for key in keys[:-1]:
        if key not in node:
            if not create:
                return None
            node[key] = {}
        node = node[key]
        if not isinstance(node, dict):
            raise SystemExit(f"petromcp: config key {key!r} is not an object")
    last = keys[-1]
    if last not in node:
        if not create:
            return None
        node[last] = {}
    target = node[last]
    if not isinstance(target, dict):
        raise SystemExit(f"petromcp: config key {last!r} is not an object")
    return target


def install_into_config(
    config_path: Path,
    server_name: str,
    command: str,
    args: list[str],
    server_key: tuple[str, ...] = ("mcpServers",),
    extra_fields: tuple[tuple[str, str], ...] = (),
) -> None:
    """Add or replace one server entry, preserving everything else in the file.

    The file belongs to the host and usually contains the user's other servers,
    so the edit is targeted: only `<server_key>.<server_name>` is touched.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text() or "{}")
        except json.JSONDecodeError as exc:
            # Overwriting would destroy the user's other servers.
            raise SystemExit(
                f"petromcp: {config_path} is not valid JSON ({exc}). "
                "Fix or move it; refusing to overwrite a config that may hold "
                "your other servers."
            ) from exc
    else:
        data = {}
    if not isinstance(data, dict):
        raise SystemExit(f"petromcp: {config_path} must contain a JSON object.")

    servers = _server_map(data, server_key, create=True)
    assert servers is not None
    entry: dict[str, object] = {"command": command, "args": args}
    entry.update(dict(extra_fields))
    servers[server_name] = entry
    config_path.write_text(json.dumps(data, indent=2) + "\n")


def uninstall_from_config(
    config_path: Path,
    server_name: str,
    server_key: tuple[str, ...] = ("mcpServers",),
) -> bool:
    """Remove the entry. Returns whether anything was removed."""
    if not config_path.exists():
        return False
    try:
        data = json.loads(config_path.read_text() or "{}")
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    servers = _server_map(data, server_key, create=False)
    if not servers or server_name not in servers:
        return False
    del servers[server_name]
    config_path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def _read_user_config(path: Path) -> dict[str, object]:
    """Read the config, validating it through the same model the server uses.

    There used to be two readers: this one, raw `json.loads`, and
    `config.load_config`, which validates. A malformed config written or edited
    here therefore surfaced at server start rather than at the moment it was
    written — the worst place to learn, since the host swallows the traceback and
    reports only that the server would not launch.

    Returns the raw mapping (so `config` subcommands can round-trip unknown keys
    rather than silently dropping them) but raises here if it would not load.
    """
    if not path.exists():
        return dict(DEFAULT_USER_CONFIG)

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"petromcp: {path} is not valid JSON ({exc}). "
            "Fix it, or remove it and run `petromcp config init`."
        ) from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"petromcp: {path} must contain a JSON object, not {type(raw).__name__}.")

    # Same validation the server performs, so a bad value fails here.
    try:
        Config.model_validate(raw)
    except ValidationError as exc:
        raise SystemExit(
            f"petromcp: {path} is not a usable config.\n{exc}"
        ) from exc
    return raw


def _write_user_config(path: Path, data: dict[str, object]) -> None:
    """Write the config, refusing to leave an unusable one on disk.

    Validating before writing means a bad `add-path` cannot produce a file that
    breaks the next server start.
    """
    try:
        Config.model_validate(data)
    except ValidationError as exc:
        raise SystemExit(
            f"petromcp: refusing to write an invalid config.\n{exc}"
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _resolve_user_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _cmd_serve(args: argparse.Namespace) -> int:
    from petromcp.config import load_config, resolve_allowed_paths
    from petromcp.server import build_app

    roots = resolve_allowed_paths(load_config().allowed_paths, args.allow_path)
    build_app(allowed_paths=roots).run()
    return 0


def _launch_command(from_source: bool) -> tuple[str, list[str]]:
    """How the host should start petromcp.

    Published by default: `uvx petroleum-mcp serve` needs no checkout and
    always resolves the current release. `--from-source` pins uv to this
    checkout instead, for working on petromcp rather than using it — `--no-sync`
    there prevents the implicit sync that re-applies UF_HIDDEN to .pth files on
    macOS.
    """
    if from_source:
        return "uv", ["run", "--no-sync", "--project", str(PROJECT_ROOT), "petromcp", "serve"]
    return "uvx", [DISTRIBUTION_NAME, "serve"]


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        host = hosts.get(args.client)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command, launch_args = _launch_command(args.from_source)
    launch_args = [*launch_args, *(a for path in args.allow_path for a in ("--allow-path", path))]
    config_path = host.config_path()

    install_into_config(
        config_path,
        server_name="petromcp",
        command=command,
        args=launch_args,
        server_key=host.server_key,
        extra_fields=host.extra_fields,
    )
    print(f"installed petromcp into {host.label} at {config_path}")
    if host.note:
        print(host.note)
    print(f"  {command} {' '.join(launch_args)}")
    print(f"Restart {host.label} for it to appear.")
    if not args.allow_path:
        print(
            "petromcp can read nothing until you allow a directory:\n"
            "  petromcp config add-path ~/petroleum/wells"
        )
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        host = hosts.get(args.client)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    config_path = host.config_path()
    if uninstall_from_config(config_path, "petromcp", server_key=host.server_key):
        print(f"removed petromcp from {host.label} at {config_path}")
    else:
        print(f"petromcp was not installed in {host.label} ({config_path})")
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

    serve = sub.add_parser("serve", help="run the MCP server")
    # `nargs="+"` with `action="extend"` covers both shapes: the flag repeated
    # once per directory, and a single flag followed by a run of them. MCPB
    # produces the second when it expands a `multiple: true` directory config.
    serve.add_argument(
        "--allow-path",
        action="extend",
        nargs="+",
        default=[],
        metavar="DIR",
        help=(
            "additional directory the server may read, on top of "
            "allowed_paths in ~/.petromcp/config.json. Repeatable."
        ),
    )
    serve.set_defaults(func=_cmd_serve)

    clients = ", ".join(sorted(hosts.HOSTS))
    install = sub.add_parser("install", help="install into an MCP host's config")
    install.add_argument(
        "--client",
        default=hosts.DEFAULT_HOST,
        choices=sorted(hosts.HOSTS),
        metavar="CLIENT",
        help=f"which host to configure. One of: {clients} (default: %(default)s)",
    )
    install.add_argument(
        "--from-source",
        action="store_true",
        help="launch from this checkout instead of the published package",
    )
    install.add_argument(
        "--allow-path",
        action="extend",
        nargs="+",
        default=[],
        metavar="DIR",
        help="grant a directory in the host entry itself. Repeatable.",
    )
    install.set_defaults(func=_cmd_install)

    uninstall = sub.add_parser("uninstall", help="remove from an MCP host's config")
    uninstall.add_argument(
        "--client",
        default=hosts.DEFAULT_HOST,
        choices=sorted(hosts.HOSTS),
        metavar="CLIENT",
        help=f"which host to clean up. One of: {clients} (default: %(default)s)",
    )
    uninstall.set_defaults(func=_cmd_uninstall)

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

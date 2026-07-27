"""Where each MCP host keeps its server configuration.

`petromcp install` writes one entry into a host's config file. Each host puts
that file somewhere different and, more importantly, nests the server list under
a different key — Claude Desktop and Cursor use `mcpServers`, VS Code uses
`servers` inside an `mcp` block. Getting the key wrong writes a valid JSON file
the host silently ignores, which is a bad failure to debug.

Adding a host means adding a `Host` here. Nothing else changes.

Paths are resolved lazily rather than at import, so a test can point `HOME`
somewhere harmless and so importing this module never depends on the machine it
runs on.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Host:
    """One MCP host's configuration layout."""

    name: str
    #: Human-readable, used in messages.
    label: str
    #: Where the config lives, per platform. Called rather than stored so tests
    #: can move HOME.
    config_path: Callable[[], Path]
    #: The keys to walk to reach the server map. Claude Desktop and Cursor use
    #: ("mcpServers",); VS Code uses ("mcp", "servers").
    server_key: tuple[str, ...] = ("mcpServers",)
    #: Some hosts want an explicit transport marker on each entry.
    extra_fields: tuple[tuple[str, str], ...] = ()
    #: Set when the host reads a per-project file rather than a global one, so
    #: the CLI can say where it wrote and why.
    note: str = ""


def _claude_desktop_config() -> Path:
    if sys.platform == "darwin":
        return Path(
            "~/Library/Application Support/Claude/claude_desktop_config.json"
        ).expanduser()
    if sys.platform == "win32":
        return Path("~/AppData/Roaming/Claude/claude_desktop_config.json").expanduser()
    return Path("~/.config/Claude/claude_desktop_config.json").expanduser()


def _cursor_config() -> Path:
    # Cursor reads a global file from the home directory on every platform.
    return Path("~/.cursor/mcp.json").expanduser()


def _codex_config() -> Path:
    return Path("~/.codex/mcp.json").expanduser()


def _vscode_config() -> Path:
    if sys.platform == "darwin":
        return Path("~/Library/Application Support/Code/User/mcp.json").expanduser()
    if sys.platform == "win32":
        return Path("~/AppData/Roaming/Code/User/mcp.json").expanduser()
    return Path("~/.config/Code/User/mcp.json").expanduser()


def _claude_code_config() -> Path:
    return Path("~/.claude.json").expanduser()


HOSTS: dict[str, Host] = {
    "claude-desktop": Host(
        name="claude-desktop",
        label="Claude Desktop",
        config_path=_claude_desktop_config,
    ),
    "claude-code": Host(
        name="claude-code",
        label="Claude Code",
        config_path=_claude_code_config,
    ),
    "cursor": Host(
        name="cursor",
        label="Cursor",
        config_path=_cursor_config,
    ),
    "codex": Host(
        name="codex",
        label="Codex CLI",
        config_path=_codex_config,
    ),
    "vscode": Host(
        name="vscode",
        label="VS Code",
        config_path=_vscode_config,
        # VS Code nests servers under `mcp.servers` and wants the transport
        # named. Writing `mcpServers` here produces a file it ignores without
        # complaint.
        server_key=("mcp", "servers"),
        extra_fields=(("type", "stdio"),),
    ),
}

#: Kept as the default so existing instructions and scripts do not change.
DEFAULT_HOST = "claude-desktop"


def get(name: str) -> Host:
    """Look up a host, listing the alternatives when the name is unknown."""
    try:
        return HOSTS[name]
    except KeyError:
        raise KeyError(
            f"unknown client {name!r}. Supported: {', '.join(sorted(HOSTS))}."
        ) from None

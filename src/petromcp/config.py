"""Load and validate `~/.petromcp/config.json`."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_PATH = Path("~/.petromcp/config.json").expanduser()


class LoggingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    log_file: Path = Path("~/.petromcp/access.log").expanduser()
    #: Rotate once the log passes this size. The access log grows by a line per
    #: tool call forever otherwise, which on a machine that reads logs daily
    #: becomes a file nobody can open. 5 MB is roughly 50,000 calls.
    max_bytes: int = 5 * 1024 * 1024
    #: How many rotated files to keep. Five at 5 MB caps the audit trail at
    #: ~30 MB, which is enough history to answer "what did it read last week"
    #: without unbounded growth.
    backup_count: int = 5

    @field_validator("max_bytes", "backup_count")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_bytes and backup_count must not be negative")
        return v

    @field_validator("log_file", mode="before")
    @classmethod
    def _expand(cls, v: object) -> Path:
        if isinstance(v, str):
            return Path(v).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        raise ValueError("log_file must be a string or Path")


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_paths: list[Path] = Field(default_factory=list)
    default_depth_units: str = "ft"
    default_pressure_units: str = "psi"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("allowed_paths", mode="before")
    @classmethod
    def _resolve_paths(cls, v: object) -> list[Path]:
        if not isinstance(v, list):
            raise ValueError("allowed_paths must be a list")
        out: list[Path] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("allowed_paths entries must be strings")
            out.append(Path(item).expanduser().resolve())
        return out


def resolve_allowed_paths(
    config_paths: Sequence[Path], cli_paths: Sequence[str]
) -> list[Path]:
    """Union the config-file allowlist with directories passed on the CLI.

    Both sources are explicit grants from the user: one written to
    `~/.petromcp/config.json`, one chosen in the host's install dialog and
    forwarded as `serve --allow-path`. Neither is a bypass — with both empty
    the server can still read nothing, which is the default.

    Order is preserved (config first, then CLI) and duplicates are dropped.
    """
    out: list[Path] = []
    for p in [*config_paths, *(Path(c) for c in cli_paths)]:
        resolved = Path(p).expanduser().resolve()
        if resolved not in out:
            out.append(resolved)
    return out


def load_config(path: Path | None = None) -> Config:
    """Load config from `path` (default: `~/.petromcp/config.json`).

    Returns a default Config when the file does not exist.
    """
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        return Config()
    data = json.loads(target.read_text())
    return Config.model_validate(data)


class Allowlist:
    """The set of directories the server may read, re-read when it changes.

    The allowlist used to be resolved once at startup, so `petromcp config
    add-path` did nothing until the host was restarted — and hosts do not make
    restarting obvious. This watches the config file's identity (mtime and size)
    and re-reads when it moves.

    This is not a widening of what can grant access. The two sources are the
    same as before: the config file and the `--allow-path` arguments this process
    was started with. Anyone able to edit the config file could already have
    granted themselves the same access on the next restart; the only change is
    that they no longer have to wait for one, and every resulting read still goes
    through the validator and the access log.

    CLI grants are fixed for the process lifetime, because process arguments are.
    """

    def __init__(
        self,
        cli_paths: Sequence[str] | None = None,
        config_path: Path | None = None,
    ) -> None:
        self._cli_paths = list(cli_paths or [])
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._stamp: tuple[float, int] | None = None
        self._resolved: list[Path] = []
        self._loaded = False

    def _config_stamp(self) -> tuple[float, int] | None:
        """Cheap identity for the config file. None when it does not exist."""
        try:
            stat = self._config_path.stat()
        except OSError:
            return None
        return (stat.st_mtime, stat.st_size)

    def current(self) -> list[Path]:
        """The allowlist as of now, re-reading the config only if it changed."""
        stamp = self._config_stamp()
        if self._loaded and stamp == self._stamp:
            return self._resolved

        config = load_config(self._config_path)
        resolved = resolve_allowed_paths(config.allowed_paths, self._cli_paths)

        if self._loaded and resolved != self._resolved:
            # The audit trail should show a permission change, not just the reads
            # that follow from it.
            logging.getLogger("petromcp.access").info(
                "allowlist changed: %d -> %d directories",
                len(self._resolved),
                len(resolved),
            )

        self._stamp = stamp
        self._resolved = resolved
        self._loaded = True
        return resolved

"""Load and validate `~/.petromcp/config.json`."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_PATH = Path("~/.petromcp/config.json").expanduser()


class LoggingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    log_file: Path = Path("~/.petromcp/access.log").expanduser()

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

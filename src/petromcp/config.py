"""Load and validate `~/.petromcp/config.json`."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_PATH = Path("~/.petromcp/config.json").expanduser()


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_paths: list[Path] = Field(default_factory=list)
    read_only: bool = True
    max_file_size_mb: int = 100
    default_depth_units: str = "ft"
    default_pressure_units: str = "psi"

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


def load_config(path: Path | None = None) -> Config:
    """Load config from `path` (default: `~/.petromcp/config.json`).

    Returns a default Config when the file does not exist.
    """
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        return Config()
    data = json.loads(target.read_text())
    return Config.model_validate(data)

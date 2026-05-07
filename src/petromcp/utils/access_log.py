"""File-based access log.

One line per tool call: `<timestamp> tool=<name> path=<resolved>`. Controlled
by the `logging` block in `~/.petromcp/config.json`; defaults to
`~/.petromcp/access.log` with logging on.

Tests use `configure(...)` to override the destination so they never write
to the real user log.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from petromcp.config import load_config

_LOGGER_NAME = "petromcp.access"
_initialised = False
_override_log_file: Path | None = None
_override_enabled: bool | None = None


def configure(log_file: Path | None = None, enabled: bool | None = None) -> None:
    """Override the config-driven log location. Tests call this; production code does not.

    Pass `log_file=None, enabled=None` to revert to config-driven behaviour.
    """
    global _initialised, _override_log_file, _override_enabled
    _override_log_file = log_file
    _override_enabled = enabled
    _initialised = False
    logger = logging.getLogger(_LOGGER_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        with contextlib.suppress(Exception):
            h.close()


def _ensure_logger() -> logging.Logger | None:
    global _initialised
    if _initialised:
        logger = logging.getLogger(_LOGGER_NAME)
        return logger if logger.handlers else None

    if _override_log_file is not None:
        enabled = True if _override_enabled is None else _override_enabled
        log_file = _override_log_file
    else:
        cfg = load_config()
        enabled = cfg.logging.enabled
        log_file = Path(cfg.logging.log_file).expanduser()

    _initialised = True

    if not enabled:
        return None

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def log_access(tool: str, path: Path) -> None:
    logger = _ensure_logger()
    if logger is None:
        return
    logger.info(f"tool={tool} path={path}")

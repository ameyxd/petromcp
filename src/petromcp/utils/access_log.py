"""File-based access log.

One line per tool call: `<timestamp> tool=<name> path=<resolved>`. Controlled
by the `logging` block in `~/.petromcp/config.json`; defaults to
`~/.petromcp/access.log` with logging on.

The log rotates. It is the audit trail for a tool whose entire privacy claim is
"you can see everything it read", so it has to stay readable — an unbounded file
that nobody can open is not an audit trail. Size and retention come from the
config so an operator with a retention policy can match it.

Tests use `configure(...)` to override the destination so they never write
to the real user log.
"""

from __future__ import annotations

import contextlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from petromcp.config import load_config

_LOGGER_NAME = "petromcp.access"
_initialised = False
_override_log_file: Path | None = None
_override_enabled: bool | None = None
_override_max_bytes: int | None = None
_override_backup_count: int | None = None


def configure(
    log_file: Path | None = None,
    enabled: bool | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> None:
    """Override the config-driven log settings. Tests call this; production does not.

    Pass every argument as None to revert to config-driven behaviour.
    """
    global _initialised, _override_log_file, _override_enabled
    global _override_max_bytes, _override_backup_count
    _override_log_file = log_file
    _override_enabled = enabled
    _override_max_bytes = max_bytes
    _override_backup_count = backup_count
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
        max_bytes = 0 if _override_max_bytes is None else _override_max_bytes
        backup_count = 0 if _override_backup_count is None else _override_backup_count
    else:
        cfg = load_config()
        enabled = cfg.logging.enabled
        log_file = Path(cfg.logging.log_file).expanduser()
        max_bytes = cfg.logging.max_bytes
        backup_count = cfg.logging.backup_count

    _initialised = True

    if not enabled:
        return None

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # maxBytes=0 disables rotation, which is what tests want and what an
    # operator gets by setting max_bytes to 0 deliberately.
    handler: logging.Handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def log_access(tool: str, path: Path) -> None:
    logger = _ensure_logger()
    if logger is None:
        return
    logger.info(f"tool={tool} path={path}")

"""Path allowlist enforcement. Default deny.

Every file-reading tool routes through `validate_path`. The allowlist is
checked against the *resolved* path so that symlinks cannot escape it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


class PathNotAllowedError(Exception):
    """Raised when a path is not inside any allowed directory."""


def _resolve(p: Path) -> Path:
    return Path(p).expanduser().resolve()


def validate_path(target: Path | str, allowed: Sequence[Path | str]) -> Path:
    """Return the resolved target if it lives inside any allowed directory.

    Raises:
        FileNotFoundError: if `target` does not exist.
        PathNotAllowedError: if `target` resolves outside every allowed root.
    """
    target_path = _resolve(Path(target))
    if not target_path.exists():
        raise FileNotFoundError(target_path)

    allowed_resolved = [_resolve(Path(a)) for a in allowed]
    for root in allowed_resolved:
        try:
            target_path.relative_to(root)
            return target_path
        except ValueError:
            continue

    msg = (
        f"petromcp: path {target_path} is not in allowed_paths "
        "(symlinks are resolved before this check, so the displayed path "
        "may differ from the literal one you passed). "
        "Add the directory to ~/.petromcp/config.json and restart the host."
    )
    raise PathNotAllowedError(msg)

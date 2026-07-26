"""petromcp — a local-first MCP server for petroleum data formats."""

from importlib.metadata import PackageNotFoundError, version

try:
    # pyproject's `version` is the single source of truth. Reading it back
    # from installed metadata keeps this constant from drifting, which it
    # previously did (0.3.0 here against 0.4.0 there).
    __version__ = version("petromcp")
except PackageNotFoundError:  # pragma: no cover - source tree, not installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]

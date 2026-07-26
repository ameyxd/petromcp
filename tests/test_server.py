"""Server wiring tests.

These assert the shape the MCP host and the public directories actually see:
the tool set, the read-only annotations, and the registered prompt.

FastMCP's introspection API is async, but these are the only async calls in
the suite — `asyncio.run` keeps them sync rather than pulling in
`pytest-asyncio` for three tests.
"""

from __future__ import annotations

import asyncio
from typing import Any

from petromcp.server import build_app

EXPECTED_TOOLS = {
    "read_las_file",
    "summarize_las_curves",
    "read_las_curve",
    "compare_well_logs",
    "convert_units",
}


def _tools() -> dict[str, Any]:
    return asyncio.run(build_app(allowed_paths=[]).get_tools())


def test_server_module_imports() -> None:
    from petromcp.server import app

    assert app is not None
    assert build_app(allowed_paths=[]) is not None


def test_registers_the_expected_tool_set() -> None:
    assert set(_tools()) == EXPECTED_TOOLS


def test_every_tool_is_annotated_read_only_and_closed_world() -> None:
    """petromcp only ever reads. Hosts use these hints to skip write-approval
    prompts, and directories use them to label the server."""
    for name, tool in _tools().items():
        assert tool.annotations is not None, f"{name} has no annotations"
        assert tool.annotations.readOnlyHint is True, name
        assert tool.annotations.destructiveHint is False, name
        assert tool.annotations.openWorldHint is False, name
        assert tool.title, f"{name} has no display title"


def test_registers_the_qc_prompt() -> None:
    prompts = asyncio.run(build_app(allowed_paths=[]).get_prompts())
    assert "qc_a_well_log" in prompts

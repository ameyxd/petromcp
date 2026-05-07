"""FastMCP server wiring. One module-level `app`; tools and prompt registered.

Runtime config is loaded from `~/.petromcp/config.json` once at startup.
The allowlist is captured into a closure so each tool call uses the same
configured roots without re-reading disk.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from petromcp.config import load_config
from petromcp.models.compare import ComparisonReport
from petromcp.models.las import CurveData, CurveSummary, LASSummary
from petromcp.models.shared import DepthRange
from petromcp.prompts.qc_a_well_log import PROMPT_NAME, PROMPT_TEMPLATE
from petromcp.tools.compare import compare_well_logs as _compare_well_logs
from petromcp.tools.las import (
    read_las_curve as _read_las_curve,
)
from petromcp.tools.las import (
    read_las_file as _read_las_file,
)
from petromcp.tools.las import (
    summarize_las_curves as _summarize_las_curves,
)
from petromcp.utils.units import convert_units as _convert_units


def build_app(allowed_paths: list[Path] | None = None) -> FastMCP:
    cfg = load_config()
    roots: list[Path] = (
        list(allowed_paths) if allowed_paths is not None else list(cfg.allowed_paths)
    )
    app: FastMCP = FastMCP("petromcp")

    @app.tool()
    def read_las_file(path: str) -> LASSummary:
        """Header-level summary of a LAS file. No curve data."""
        return _read_las_file(path, roots)

    @app.tool()
    def summarize_las_curves(path: str) -> CurveSummary:
        """Per-curve summary statistics for a LAS file."""
        return _summarize_las_curves(path, roots)

    @app.tool()
    def read_las_curve(
        path: str,
        curve_name: str,
        depth_start: float | None = None,
        depth_stop: float | None = None,
    ) -> CurveData:
        """Read a single curve. Defaults to a 500-sample downsample.

        Pass `depth_start` and `depth_stop` together to retrieve every point
        inside that interval with no downsampling.
        """
        depth_range = (
            DepthRange(start=depth_start, stop=depth_stop)
            if depth_start is not None and depth_stop is not None
            else None
        )
        return _read_las_curve(path, curve_name, depth_range=depth_range, allowed_paths=roots)

    @app.tool()
    def compare_well_logs(path_a: str, path_b: str) -> ComparisonReport:
        """Compare two LAS files. Reports common curves, depth overlap,
        unit consistency, and human-readable issue flags."""
        return _compare_well_logs(path_a, path_b, roots)

    @app.tool()
    def convert_units(value: float, from_unit: str, to_unit: str) -> float:
        """Convert a value between supported petroleum units. Strict
        case-sensitive matching. Supported pairs: ft<->m, psi<->kPa,
        psi<->bar, bbl<->m3, degF<->degC, mD<->m2."""
        return _convert_units(value, from_unit, to_unit)

    @app.prompt(name=PROMPT_NAME)
    def qc_a_well_log() -> str:
        return PROMPT_TEMPLATE

    return app


app = build_app()


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()

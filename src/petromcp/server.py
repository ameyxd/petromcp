"""FastMCP server wiring. One module-level `app`; tools and prompt registered.

Runtime config is loaded from `~/.petromcp/config.json` once at startup.
The allowlist is captured into a closure so each tool call uses the same
configured roots without re-reading disk.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from petromcp import __version__
from petromcp.config import Allowlist
from petromcp.models.compare import ComparisonReport
from petromcp.models.dlis import ChannelListing, DLISChannelData, DLISSummary
from petromcp.models.las import CurveData, CurveSummary, LASSummary
from petromcp.models.shared import DepthRange
from petromcp.models.units import SupportedUnits
from petromcp.prompts.qc_a_well_log import PROMPT_NAME, PROMPT_TEMPLATE
from petromcp.tools.compare import compare_well_logs as _compare_well_logs
from petromcp.tools.dlis import (
    list_dlis_channels as _list_dlis_channels,
)
from petromcp.tools.dlis import (
    read_dlis_channel as _read_dlis_channel,
)
from petromcp.tools.dlis import (
    read_dlis_file as _read_dlis_file,
)
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
from petromcp.utils.units import supported_units as _supported_units

# Shown to the model when the server is connected. It exists to prevent the
# most common wasted turn: guessing at a path that is not on the allowlist.
INSTRUCTIONS = """\
petromcp reads petroleum data files from the local disk. It supports LAS well
logs and DLIS files.

It can only read files inside the user's configured allowlist; every other
path is refused. If a read is refused, tell the user to run
`petromcp config add-path <directory>` and restart this host — the
allowlist is read once at startup. Do not try neighbouring paths.

For LAS, prefer `read_las_file` and `summarize_las_curves` first. Reach for
`read_las_curve` only when specific values are needed, and pass
`depth_start` and `depth_stop` together to scope it.

For DLIS, always call `read_dlis_file` first: these files hold several frames
and often hundreds of channels, so reading blindly is expensive. Then
`list_dlis_channels` to find what you want, then `read_dlis_channel`. A
channel name can occur in more than one frame; if that happens the read fails
and lists the candidates, so pass `frame` on the retry.
"""

# Every petromcp tool is a reader. Declaring that lets hosts skip the
# write-confirmation prompt and lets directories label the server correctly.
# `openWorldHint=False` is the important one: nothing here touches a network.
READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def build_app(
    allowed_paths: list[Path] | None = None,
    allowlist: Allowlist | None = None,
) -> FastMCP:
    """Build the server.

    `allowed_paths` pins a fixed list, which tests use. Otherwise an `Allowlist`
    re-reads `~/.petromcp/config.json` when it changes, so
    `petromcp config add-path` takes effect without restarting the host.
    """
    if allowed_paths is not None:
        pinned = list(allowed_paths)

        def roots() -> list[Path]:
            return pinned
    else:
        resolver = allowlist or Allowlist()

        def roots() -> list[Path]:
            return resolver.current()
    # `version` matters beyond cosmetics: without it FastMCP reports its own
    # version in serverInfo, which is what hosts and public directories show.
    app: FastMCP = FastMCP(
        "petromcp",
        version=__version__,
        website_url="https://github.com/ameyxd/petromcp",
        instructions=INSTRUCTIONS,
    )

    @app.tool(title="Read LAS header", annotations=READ_ONLY)
    def read_las_file(path: str) -> LASSummary:
        """Header-level summary of a LAS file. No curve data."""
        return _read_las_file(path, roots())

    @app.tool(title="Summarize LAS curves", annotations=READ_ONLY)
    def summarize_las_curves(path: str) -> CurveSummary:
        """Per-curve summary statistics for a LAS file."""
        return _summarize_las_curves(path, roots())

    @app.tool(title="Read one LAS curve", annotations=READ_ONLY)
    def read_las_curve(
        path: str,
        curve_name: str,
        depth_start: float | None = None,
        depth_stop: float | None = None,
    ) -> CurveData:
        """Read a single curve. Defaults to a 500-sample downsample.

        Pass `depth_start` and `depth_stop` together to retrieve every point
        inside that interval with no downsampling. Passing only one of the
        two is an error, not a partial interval.
        """
        depth_range = DepthRange.from_optional(depth_start, depth_stop)
        return _read_las_curve(path, curve_name, depth_range=depth_range, allowed_paths=roots())

    @app.tool(title="Compare two well logs", annotations=READ_ONLY)
    def compare_well_logs(path_a: str, path_b: str) -> ComparisonReport:
        """Compare two LAS files. Reports common curves, depth overlap,
        unit consistency, and human-readable issue flags."""
        return _compare_well_logs(path_a, path_b, roots())

    @app.tool(title="Convert units", annotations=READ_ONLY)
    def convert_units(value: float, from_unit: str, to_unit: str) -> float:
        """Convert a value between supported petroleum units. Strict
        case-sensitive matching. Supported pairs: ft<->m, psi<->kPa,
        psi<->bar, bbl<->m3, degF<->degC, mD<->m2."""
        return _convert_units(value, from_unit, to_unit)

    @app.tool(title="Read DLIS structure", annotations=READ_ONLY)
    def read_dlis_file(path: str) -> DLISSummary:
        """Structure of a DLIS file: logical files, frames, index types, depth
        ranges, and channel counts. No channel values.

        Start here. A DLIS can hold hundreds of channels across several frames,
        so this is the cheap call that tells you what to ask for next."""
        return _read_dlis_file(path, roots())

    @app.tool(title="List DLIS channels", annotations=READ_ONLY)
    def list_dlis_channels(path: str, frame: str | None = None) -> ChannelListing:
        """Every channel with its frame, logical file, units, and length.

        Channel names are unique only within a frame, so the frame and logical
        file in each row are what make a channel addressable. Pass `frame` to
        narrow a large file."""
        return _list_dlis_channels(path, roots(), frame=frame)

    @app.tool(title="Read one DLIS channel", annotations=READ_ONLY)
    def read_dlis_channel(
        path: str,
        channel: str,
        frame: str | None = None,
        logical_file: int | None = None,
        depth_start: float | None = None,
        depth_stop: float | None = None,
    ) -> DLISChannelData:
        """Read one channel's values and its index.

        Defaults to a 500-sample downsample; pass `depth_start` and
        `depth_stop` together for every sample in an interval.

        If the channel name occurs in more than one frame this fails and lists
        the candidates rather than choosing one, because their values differ.
        Pass `frame` to disambiguate."""
        return _read_dlis_channel(
            path,
            channel,
            frame=frame,
            logical_file=logical_file,
            depth_start=depth_start,
            depth_stop=depth_stop,
            allowed_paths=roots(),
        )

    @app.tool(title="List supported units", annotations=READ_ONLY)
    def list_supported_units() -> SupportedUnits:
        """Every unit pair `convert_units` accepts, with its physical quantity.

        Call this instead of guessing at unit names — matching is strict and
        case-sensitive."""
        return _supported_units()

    @app.prompt(name=PROMPT_NAME)
    def qc_a_well_log() -> str:
        return PROMPT_TEMPLATE

    return app


app = build_app()


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()

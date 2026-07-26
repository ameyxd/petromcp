"""Build the MCPB bundle (`dist/petromcp-<version>.mcpb`) for Smithery.

An MCPB bundle is a zip archive that a host unpacks and runs locally. This
one carries a manifest and nothing else: it launches `uvx petromcp==<version>
serve`, so uv fetches the package and a matching interpreter on first run.

The obvious alternative — vendoring dependencies into `server/lib` — does
not work here. petromcp depends on numpy and pydantic, whose wheels ship
CPython extension modules tagged for one exact minor version
(`_pydantic_core.cpython-310-darwin.so`). A bundle built against 3.10
therefore fails to import on 3.12, so it could never honestly declare
`runtimes.python: ">=3.10"`. Delegating to uv moves interpreter and
dependency resolution to the machine that will actually run the server.

The tradeoff is that uv must be on the user's PATH. That is already
petromcp's documented prerequisite, and the manifest says so.

Run via `make bundle`.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIST = ROOT / "dist"

DISTRIBUTION_NAME = "petroleum-mcp"


def project_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("could not find `version` in pyproject.toml")


def check_distribution_name() -> None:
    """The manifest pin is worthless if it names a distribution pyproject
    does not publish under."""
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        if line.startswith("name = "):
            declared = line.split("=", 1)[1].strip().strip('"')
            if declared != DISTRIBUTION_NAME:
                raise SystemExit(
                    f"pyproject publishes as {declared!r} but "
                    f"petromcp.DISTRIBUTION_NAME is {DISTRIBUTION_NAME!r}. "
                    "`uvx` in the bundle would fetch the wrong package."
                )
            return
    raise SystemExit("could not find `name` in pyproject.toml")


def load_manifest(version: str) -> dict:
    """Read the manifest and check every version claim it makes."""
    manifest = json.loads((HERE / "manifest.json").read_text())
    if manifest["version"] != version:
        raise SystemExit(
            f"manifest.json says {manifest['version']} but pyproject says "
            f"{version}. Update packaging/mcpb/manifest.json."
        )
    # The bundle launches `uvx <distribution>@<version>`.
    #
    # The `@` form is required, not cosmetic. `uvx <name>==<version>` is a
    # parse error, and `uvx <name>` only works because the package declares a
    # console script matching the distribution name — see the alias in
    # pyproject's [project.scripts]. Both were verified against a real uvx
    # before this shape was chosen.
    pin = f"{DISTRIBUTION_NAME}@{version}"
    args = manifest["server"]["mcp_config"]["args"]
    if pin not in args:
        raise SystemExit(
            f"manifest args must pin {pin} so the bundle and the published "
            f"package cannot drift. Got: {args}"
        )
    if any("==" in a for a in args):
        raise SystemExit(
            f"manifest args use `==`, which uvx rejects as a package name. "
            f"Use {pin}. Got: {args}"
        )
    return manifest


def introspect_tools_and_prompts() -> tuple[list[dict], list[dict]]:
    """Read the tool and prompt metadata off a live server instance.

    Hand-maintained copies in the manifest go stale the moment a signature
    changes, and nothing catches it — the bundle is metadata, so a wrong
    entry produces a wrong directory listing rather than a failing test.
    Generating from the real server removes the possibility.

    Smithery's ServerCard requires `inputSchema` on every tool. Omitting it
    is a 400 at publish time, one error per tool, so this is not optional
    detail.
    """
    import asyncio

    from petromcp.server import build_app

    app = build_app(allowed_paths=[])

    async def collect() -> tuple[list[dict], list[dict]]:
        tools = []
        for name, tool in (await app.get_tools()).items():
            entry: dict = {"name": name, "inputSchema": tool.parameters}
            if tool.title:
                entry["title"] = tool.title
            if tool.description:
                entry["description"] = tool.description.strip().split("\n\n")[0]
            tools.append(entry)
        prompts = [
            {"name": name, "description": (p.description or "").strip()}
            for name, p in (await app.get_prompts()).items()
        ]
        return tools, prompts

    return asyncio.run(collect())


def build() -> Path:
    check_distribution_name()
    version = project_version()
    manifest = load_manifest(version)

    tools, prompts = introspect_tools_and_prompts()
    manifest["tools"] = tools
    manifest["prompts"] = [
        # MCPB wants prompt `text`; keep whatever the manifest declares and
        # only refresh name/description from the server.
        {**declared, **found}
        for declared, found in zip(manifest.get("prompts", []), prompts, strict=True)
    ]
    print(f"introspected {len(tools)} tools, {len(prompts)} prompt(s) from the server")

    DIST.mkdir(exist_ok=True)
    out = DIST / f"petromcp-{version}.mcpb"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        zf.write(ROOT / "README.md", "README.md")
        zf.write(ROOT / "LICENSE", "LICENSE")

    print(f"built {out.name} ({out.stat().st_size / 1024:.1f} KB)")
    return out


if __name__ == "__main__":
    build()

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


def project_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("could not find `version` in pyproject.toml")


def load_manifest(version: str) -> dict:
    """Read the manifest and check every version claim it makes."""
    manifest = json.loads((HERE / "manifest.json").read_text())
    if manifest["version"] != version:
        raise SystemExit(
            f"manifest.json says {manifest['version']} but pyproject says "
            f"{version}. Update packaging/mcpb/manifest.json."
        )
    pin = f"petromcp=={version}"
    args = manifest["server"]["mcp_config"]["args"]
    if pin not in args:
        raise SystemExit(
            f"manifest args must pin {pin} so the bundle and the published "
            f"package cannot drift. Got: {args}"
        )
    return manifest


def build() -> Path:
    version = project_version()
    manifest = load_manifest(version)

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

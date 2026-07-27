"""Pre-release consistency checks.

The version appears in five places and the launch command appears in several
more. Every release failure this project has had was one of them disagreeing
with another:

- a bundle pinned a version that was never uploaded to PyPI
- the console script did not match the distribution name, so the documented
  `uvx <package>` command could not work
- the bundle used `uvx name==version`, which uvx rejects as a package name

None of those are interesting bugs. They are all mechanical, and this script
catches them before a tag is pushed rather than after users hit them.

Run `python -m scripts.check_release` locally, or let the release workflow do
it. Exit code 0 means the tree is internally consistent; it says nothing about
what is actually on PyPI (see `--verify-published` for that).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# `tomllib` is stdlib only from 3.11. This project supports 3.10, and a dev
# script that crashes on the declared floor is a dev script that stops being
# run. Surfaced by pointing ruff at requires-python's floor instead of 3.12.
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 in CI
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Problem:
    where: str
    detail: str

    def __str__(self) -> str:
        return f"{self.where}: {self.detail}"


def load_pyproject(root: Path | None = None) -> dict:
    """Parsed pyproject. Exposed so tests read it the same way this does."""
    return tomllib.loads(((root or ROOT) / "pyproject.toml").read_text())


def _pyproject() -> dict:
    return load_pyproject()


def _json_file(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def check_versions_agree() -> list[Problem]:
    """Every file that states a version must state the same one."""
    proj = _pyproject()["project"]
    version = proj["version"]
    problems: list[Problem] = []

    server = _json_file("server.json")
    if server["version"] != version:
        problems.append(Problem("server.json", f"version {server['version']} != {version}"))
    pkg = server["packages"][0]
    if pkg["version"] != version:
        problems.append(
            Problem("server.json", f"packages[0].version {pkg['version']} != {version}")
        )

    manifest = _json_file("packaging/mcpb/manifest.json")
    if manifest["version"] != version:
        problems.append(
            Problem("mcpb manifest", f"version {manifest['version']} != {version}")
        )

    changelog = (ROOT / "CHANGELOG.md").read_text()
    if f"## {version}" not in changelog:
        problems.append(Problem("CHANGELOG.md", f"no '## {version}' section"))

    return problems


def check_distribution_name() -> list[Problem]:
    """The name PyPI publishes under must be the name every consumer uses."""
    declared = _pyproject()["project"]["name"]
    problems: list[Problem] = []

    sys.path.insert(0, str(ROOT / "src"))
    from petromcp import DISTRIBUTION_NAME  # noqa: PLC0415

    if declared != DISTRIBUTION_NAME:
        problems.append(
            Problem(
                "petromcp.DISTRIBUTION_NAME",
                f"{DISTRIBUTION_NAME!r} != pyproject name {declared!r}",
            )
        )

    identifier = _json_file("server.json")["packages"][0]["identifier"]
    if identifier != declared:
        problems.append(
            Problem("server.json", f"packages[0].identifier {identifier!r} != {declared!r}")
        )
    return problems


def check_console_scripts() -> list[Problem]:
    """`uvx <package>` runs the executable named after the package.

    Without a script matching the distribution name, every documented install
    command fails with "executable not found" — after a successful install,
    which makes it read like a packaging bug rather than a usage one.
    """
    proj = _pyproject()["project"]
    scripts = proj.get("scripts", {})
    name = proj["name"]
    problems: list[Problem] = []

    if name not in scripts:
        problems.append(
            Problem(
                "pyproject [project.scripts]",
                f"no console script named {name!r}; `uvx {name}` will fail",
            )
        )
    if len(set(scripts.values())) > 1:
        problems.append(
            Problem("pyproject [project.scripts]", f"aliases diverged: {scripts}")
        )
    return problems


#: The official MCP registry rejects a description longer than this.
REGISTRY_DESCRIPTION_LIMIT = 100


def check_registry_metadata() -> list[Problem]:
    """server.json must satisfy the registry's own constraints.

    The limit below is not guesswork: `mcp-publisher validate` rejected a
    200-character description with a 422. Checking it here means the failure
    lands while editing rather than midway through a release.
    """
    server = _json_file("server.json")
    problems: list[Problem] = []
    description = server.get("description", "")
    if len(description) > REGISTRY_DESCRIPTION_LIMIT:
        problems.append(
            Problem(
                "server.json",
                f"description is {len(description)} characters; the MCP registry "
                f"rejects anything over {REGISTRY_DESCRIPTION_LIMIT}",
            )
        )
    if not description:
        problems.append(Problem("server.json", "description is empty"))
    return problems


def check_bundle_launch_command() -> list[Problem]:
    """The bundle's command must be one uvx actually accepts."""
    proj = _pyproject()["project"]
    name, version = proj["name"], proj["version"]
    args = _json_file("packaging/mcpb/manifest.json")["server"]["mcp_config"]["args"]
    problems: list[Problem] = []

    if any("==" in a for a in args):
        problems.append(
            Problem(
                "mcpb manifest",
                f"args use '==', which uvx rejects as a package name: {args}. "
                f"Use {name}@{version}",
            )
        )
    pin = f"{name}@{version}"
    if pin not in args:
        problems.append(Problem("mcpb manifest", f"args do not pin {pin}: {args}"))
    return problems


#: Files whose commands a reader is meant to copy and run. CHANGELOG.md is
#: deliberately excluded: an entry describing a fix quotes the broken form on
#: purpose, and flagging that would train people to ignore this check.
INSTRUCTIONAL_DOCS = ("README.md", "docs/INSTALL.md", "docs/PUBLISHING.md")


def check_docs_use_a_working_command() -> list[Problem]:
    """Catch the `uvx <name>==<version>` form anywhere a reader could copy it."""
    problems: list[Problem] = []
    name = _pyproject()["project"]["name"]
    pattern = re.compile(rf"uvx\s+{re.escape(name)}==")
    for rel in INSTRUCTIONAL_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                problems.append(
                    Problem(f"{rel}:{lineno}", f"`uvx {name}==...` is a uvx parse error")
                )
    return problems


def check_tag_matches(tag: str) -> list[Problem]:
    """Assert the tag equals the declared version, exactly.

    This project's tags carry no `v` prefix, so `v0.6.0` is a convention
    violation rather than an alternate spelling — normalising it away here
    would let an inconsistent tag reach the registry. Normalisation is
    deliberately not done in the caller either: one contract, one place.
    """
    version = _pyproject()["project"]["version"]
    if tag.startswith("v") and tag[1:] == version:
        return [
            Problem(
                "git tag",
                f"tag {tag!r} has a 'v' prefix; this project tags as {version!r}",
            )
        ]
    if tag != version:
        return [Problem("git tag", f"tag {tag!r} != pyproject version {version!r}")]
    return []


def verify_published(version: str) -> list[Problem]:
    """Confirm the documented command works against the real index.

    Deliberately runs the exact invocation the docs give rather than an
    equivalent one. A similar command succeeding is what let two broken
    releases through.
    """
    name = _pyproject()["project"]["name"]
    command = ["uvx", "--no-cache", f"{name}@{version}", "--help"]
    print(f"  $ {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
        return [Problem("published package", "  ".join(tail) or "non-zero exit")]
    return []


CHECKS = (
    ("versions agree", check_versions_agree),
    ("distribution name", check_distribution_name),
    ("registry metadata", check_registry_metadata),
    ("console scripts", check_console_scripts),
    ("bundle launch command", check_bundle_launch_command),
    ("docs use a working command", check_docs_use_a_working_command),
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="pre-release consistency checks")
    p.add_argument("--tag", help="assert this git tag matches the declared version")
    p.add_argument(
        "--verify-published",
        action="store_true",
        help="additionally run the documented uvx command against the real index",
    )
    args = p.parse_args(argv)

    problems: list[Problem] = []
    for label, check in CHECKS:
        found = check()
        status = "FAIL" if found else "ok"
        print(f"  [{status:>4}] {label}")
        problems.extend(found)

    if args.tag:
        found = check_tag_matches(args.tag)
        print(f"  [{'FAIL' if found else '  ok'}] tag matches version")
        problems.extend(found)

    if args.verify_published:
        version = _pyproject()["project"]["version"]
        found = verify_published(version)
        print(f"  [{'FAIL' if found else '  ok'}] published package launches")
        problems.extend(found)

    if problems:
        print("\nrelease checks failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nall release checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

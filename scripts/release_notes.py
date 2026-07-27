"""Extract one version's section from CHANGELOG.md.

Used as the body of the GitHub release, so the release notes and the changelog
cannot say different things. Writing them twice is how they diverge.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(changelog: str, version: str) -> str:
    """Return the body of the `## <version>` section, without its heading.

    Raises:
        KeyError: if the version has no section. A release with no changelog
            entry is a mistake worth stopping for, not something to paper over
            with empty notes.
    """
    lines = changelog.splitlines()
    heading = f"## {version}"
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        raise KeyError(f"no '{heading}' section in CHANGELOG.md") from None

    body: list[str] = []
    for line in lines[start + 1 :]:
        # The next release heading ends this section. Deeper headings (###)
        # belong to it.
        if line.startswith("## "):
            break
        body.append(line)

    return "\n".join(body).strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="print one version's changelog section")
    p.add_argument("version")
    args = p.parse_args(argv)

    try:
        print(extract((ROOT / "CHANGELOG.md").read_text(), args.version))
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

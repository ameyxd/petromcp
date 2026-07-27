"""Pre-release consistency checks.

Each check exists because a real release broke on exactly the thing it looks
for. A check that cannot fail is worse than no check, so every one is tested
against a deliberately corrupted tree as well as the real one.

The corruption is applied to a *copy*: `ROOT` is monkeypatched at a temporary
directory. Mutating the real repo and restoring it afterwards would leave the
project broken if a test crashed partway.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import scripts.check_release as cr

#: Everything the checks read.
_FILES = (
    "pyproject.toml",
    "server.json",
    "packaging/mcpb/manifest.json",
    "CHANGELOG.md",
    "README.md",
    "docs/INSTALL.md",
    "docs/PUBLISHING.md",
)


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway copy of the files the checks inspect."""
    for rel in _FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cr.ROOT / rel, dest)
    monkeypatch.setattr(cr, "ROOT", tmp_path)
    return tmp_path


def _edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data, indent=2) + "\n")


# --- the real tree is consistent ----------------------------------------------


@pytest.mark.parametrize("label,check", cr.CHECKS, ids=[c[0] for c in cr.CHECKS])
def test_real_tree_passes_every_check(label: str, check) -> None:
    assert check() == [], f"{label} failed on the committed tree"


def test_main_passes_on_the_real_tree() -> None:
    assert cr.main([]) == 0


def _declared_version() -> str:
    return cr.load_pyproject()["project"]["version"]


def test_tag_matching_the_declared_version_passes() -> None:
    version = _declared_version()
    assert cr.check_tag_matches(version) == []


def test_rejects_a_v_prefixed_tag() -> None:
    """The project tags without a `v`. A v-prefixed tag is a convention
    violation, not an alternate spelling, so it must fail rather than be
    silently normalised."""
    version = _declared_version()
    problems = cr.check_tag_matches(f"v{version}")
    assert problems
    assert "prefix" in str(problems[0])


# --- each check catches its own violation -------------------------------------


def test_catches_version_drift_in_server_json(tree: Path) -> None:
    _edit_json(tree / "server.json", lambda d: d.update(version="9.9.9"))
    assert cr.check_versions_agree()


def test_catches_version_drift_in_the_bundle_manifest(tree: Path) -> None:
    _edit_json(tree / "packaging/mcpb/manifest.json", lambda d: d.update(version="9.9.9"))
    assert cr.check_versions_agree()


def test_catches_a_missing_changelog_section(tree: Path) -> None:
    (tree / "CHANGELOG.md").write_text("# Changelog\n\nnothing here\n")
    assert cr.check_versions_agree()


def test_catches_an_identifier_that_is_not_the_distribution_name(tree: Path) -> None:
    _edit_json(
        tree / "server.json",
        lambda d: d["packages"][0].update(identifier="something-else"),
    )
    assert cr.check_distribution_name()


def test_catches_a_missing_console_script_for_uvx(tree: Path) -> None:
    """The bug that broke every install instruction in 0.5.0."""
    p = tree / "pyproject.toml"
    p.write_text(p.read_text().replace('petroleum-mcp = "petromcp.cli:main"\n', ""))
    problems = cr.check_console_scripts()
    assert problems
    assert "uvx" in str(problems[0])


def test_catches_diverged_script_aliases(tree: Path) -> None:
    p = tree / "pyproject.toml"
    p.write_text(
        p.read_text().replace(
            'petroleum-mcp = "petromcp.cli:main"',
            'petroleum-mcp = "petromcp.other:main"',
        )
    )
    assert cr.check_console_scripts()


def test_catches_double_equals_in_the_bundle_args(tree: Path) -> None:
    """The bug that made the 0.5.0 bundle unlaunchable."""
    _edit_json(
        tree / "packaging/mcpb/manifest.json",
        lambda d: d["server"]["mcp_config"].update(
            args=["petroleum-mcp==0.6.0", "serve"]
        ),
    )
    problems = cr.check_bundle_launch_command()
    assert problems
    assert "==" in str(problems[0])


def test_catches_an_unpinned_bundle(tree: Path) -> None:
    _edit_json(
        tree / "packaging/mcpb/manifest.json",
        lambda d: d["server"]["mcp_config"].update(args=["petroleum-mcp", "serve"]),
    )
    assert cr.check_bundle_launch_command()


def test_catches_a_broken_command_in_an_instructional_doc(tree: Path) -> None:
    p = tree / "README.md"
    p.write_text(p.read_text() + "\n    uvx petroleum-mcp==0.6.0 serve\n")
    problems = cr.check_docs_use_a_working_command()
    assert problems
    assert "README.md" in str(problems[0])


def test_tolerates_the_broken_form_in_the_changelog(tree: Path) -> None:
    """A changelog entry describing a fix quotes the broken command on purpose.
    Flagging that would teach people to ignore this check."""
    p = tree / "CHANGELOG.md"
    p.write_text(p.read_text() + "\n- was `uvx petroleum-mcp==1.0.0`, now fixed\n")
    assert cr.check_docs_use_a_working_command() == []


def test_catches_a_tag_that_does_not_match(tree: Path) -> None:
    assert cr.check_tag_matches("0.0.1")


def test_main_reports_failure_when_a_check_fails(tree: Path) -> None:
    _edit_json(tree / "server.json", lambda d: d.update(version="9.9.9"))
    assert cr.main([]) == 1


class TestReleaseNotes:
    """The GitHub release body comes from the changelog, so the two cannot
    diverge. A release with no changelog section must stop the workflow."""

    def test_extracts_the_named_section_only(self) -> None:
        from scripts.release_notes import extract

        changelog = (
            "# Changelog\n\n"
            "## 2.0.0\n\n### Added\n\n- the new thing\n\n"
            "## 1.0.0\n\n- the old thing\n"
        )
        body = extract(changelog, "2.0.0")
        assert "the new thing" in body
        assert "the old thing" not in body
        assert "## 2.0.0" not in body, "heading should not be repeated in the body"

    def test_keeps_subsections(self) -> None:
        from scripts.release_notes import extract

        changelog = "## 1.0.0\n\n### Fixed\n\n- a bug\n\n### Added\n\n- a feature\n"
        body = extract(changelog, "1.0.0")
        assert "### Fixed" in body and "### Added" in body

    def test_raises_for_a_version_with_no_section(self) -> None:
        from scripts.release_notes import extract

        with pytest.raises(KeyError, match="9.9.9"):
            extract("# Changelog\n\n## 1.0.0\n\n- thing\n", "9.9.9")

    def test_current_version_has_release_notes(self) -> None:
        """The version about to ship must have something to say for itself."""
        from scripts.release_notes import extract

        version = _declared_version()
        body = extract((cr.ROOT / "CHANGELOG.md").read_text(), version)
        assert len(body) > 50, f"changelog section for {version} is nearly empty"

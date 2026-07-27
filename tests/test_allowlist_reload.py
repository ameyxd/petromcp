"""Allowlist re-reading.

The allowlist used to resolve once at startup, so `petromcp config add-path`
did nothing until the host restarted — and hosts do not make restarting
obvious. `Allowlist` re-reads the config when the file changes.

The property that must survive is default-deny: with no config and no
`--allow-path`, the server can still read nothing. These tests assert the
convenience did not cost the guarantee.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from petromcp.config import Allowlist


def _write(path: Path, paths: list[str]) -> None:
    path.write_text(json.dumps({"allowed_paths": paths}))
    # Some filesystems have coarse mtime granularity; nudge it so the change is
    # detectable in a fast test rather than relying on timing.
    stamp = time.time() + 1
    os.utime(path, (stamp, stamp))


def test_no_config_and_no_flags_grants_nothing(tmp_path: Path) -> None:
    """Default deny. The whole privacy posture rests on this line."""
    assert Allowlist(config_path=tmp_path / "absent.json").current() == []


def test_reads_the_config_on_first_use(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    wells = tmp_path / "wells"
    wells.mkdir()
    _write(cfg, [str(wells)])
    assert Allowlist(config_path=cfg).current() == [wells]


def test_picks_up_a_directory_added_after_startup(tmp_path: Path) -> None:
    """The bug this fixes: add-path used to require a host restart."""
    cfg = tmp_path / "config.json"
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write(cfg, [str(first)])

    allowlist = Allowlist(config_path=cfg)
    assert allowlist.current() == [first]

    _write(cfg, [str(first), str(second)])
    assert allowlist.current() == [first, second]


def test_picks_up_a_directory_removed_after_startup(tmp_path: Path) -> None:
    """Revocation has to work too, or the feature is only a widening."""
    cfg = tmp_path / "config.json"
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write(cfg, [str(first), str(second)])

    allowlist = Allowlist(config_path=cfg)
    assert len(allowlist.current()) == 2

    _write(cfg, [str(first)])
    assert allowlist.current() == [first]


def test_an_unchanged_config_is_not_re_read(tmp_path: Path) -> None:
    """Re-parsing on every tool call would put a file read in the hot path."""
    cfg = tmp_path / "config.json"
    wells = tmp_path / "wells"
    wells.mkdir()
    _write(cfg, [str(wells)])

    allowlist = Allowlist(config_path=cfg)
    first = allowlist.current()
    second = allowlist.current()
    assert first is second, "unchanged config should return the cached list"


def test_cli_grants_survive_a_config_change(tmp_path: Path) -> None:
    """Process arguments are fixed for the process; a config edit must not drop
    a directory the host passed at launch."""
    cfg = tmp_path / "config.json"
    from_cli = tmp_path / "cli"
    from_config = tmp_path / "cfg"
    from_cli.mkdir()
    from_config.mkdir()
    _write(cfg, [str(from_config)])

    allowlist = Allowlist(cli_paths=[str(from_cli)], config_path=cfg)
    assert set(allowlist.current()) == {from_cli, from_config}

    _write(cfg, [])
    assert allowlist.current() == [from_cli]


def test_deleting_the_config_falls_back_to_cli_grants_only(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    from_cli = tmp_path / "cli"
    other = tmp_path / "other"
    from_cli.mkdir()
    other.mkdir()
    _write(cfg, [str(other)])

    allowlist = Allowlist(cli_paths=[str(from_cli)], config_path=cfg)
    assert len(allowlist.current()) == 2

    cfg.unlink()
    assert allowlist.current() == [from_cli]


def test_deleting_the_config_with_no_cli_grants_denies_everything(tmp_path: Path) -> None:
    """Removing the config must not leave the previous allowlist in force."""
    cfg = tmp_path / "config.json"
    wells = tmp_path / "wells"
    wells.mkdir()
    _write(cfg, [str(wells)])

    allowlist = Allowlist(config_path=cfg)
    assert allowlist.current() == [wells]

    cfg.unlink()
    assert allowlist.current() == []


def test_the_server_enforces_the_updated_allowlist(tmp_path: Path) -> None:
    """End to end: a tool call refused before the edit succeeds after it."""
    import pytest

    from petromcp.tools.las import read_las_file
    from petromcp.utils.path_validator import PathNotAllowedError

    cfg = tmp_path / "config.json"
    wells = tmp_path / "wells"
    wells.mkdir()

    # A real LAS file to read.
    import lasio
    import numpy as np

    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value="RELOAD-01")
    depth = np.arange(5000.0, 5010.0, 0.5)
    las.append_curve("DEPT", depth, unit="ft")
    las.append_curve("GR", np.full(len(depth), 60.0), unit="GAPI")
    target = wells / "w.las"
    las.write(str(target))

    _write(cfg, [])
    allowlist = Allowlist(config_path=cfg)
    with pytest.raises(PathNotAllowedError):
        read_las_file(str(target), allowlist.current())

    _write(cfg, [str(wells)])
    assert read_las_file(str(target), allowlist.current()).well_name == "RELOAD-01"

from pathlib import Path

import lasio
import numpy as np
import pytest

from petromcp.tools.compare import compare_well_logs
from petromcp.utils.path_validator import PathNotAllowedError


def _write_las(
    path: Path,
    well_name: str,
    operator: str,
    start: float,
    stop: float,
    step: float,
    curves: dict[str, str],  # mnemonic -> unit
    seed: int = 42,
) -> None:
    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value=well_name)  # type: ignore[arg-type]
    las.well["COMP"] = lasio.HeaderItem("COMP", value=operator)  # type: ignore[arg-type]
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=start)  # type: ignore[arg-type]
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=stop)  # type: ignore[arg-type]
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=step)  # type: ignore[arg-type]
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)  # type: ignore[arg-type]
    depth = np.arange(start, stop + step / 2, step)
    rng = np.random.default_rng(seed)
    las.append_curve("DEPT", depth, unit="ft")
    for mnem, unit in curves.items():
        las.append_curve(mnem, rng.standard_normal(len(depth)), unit=unit)
    las.write(str(path))


def test_identical_wells_have_no_flags(tmp_path: Path, allowlist: list[Path]) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    spec = dict(
        well_name="W", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI", "RHOB": "g/cm3"},
    )
    _write_las(a, **spec)  # type: ignore[arg-type]
    _write_las(b, **spec)  # type: ignore[arg-type]

    r = compare_well_logs(str(a), str(b), allowlist)
    assert set(r.common_curves) == {"GR", "RHOB"}
    assert r.unique_to_a == []
    assert r.unique_to_b == []
    assert r.depth_overlap is not None
    assert r.depth_overlap.start == pytest.approx(5000.0)
    assert r.depth_overlap.stop == pytest.approx(5010.0)
    assert all(d.units_match for d in r.unit_diffs)
    assert r.flags == []


def test_missing_curve_flagged(tmp_path: Path, allowlist: list[Path]) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    _write_las(
        a, well_name="A", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI", "RHOB": "g/cm3"},
    )
    _write_las(
        b, well_name="B", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )

    r = compare_well_logs(str(a), str(b), allowlist)
    assert r.unique_to_a == ["RHOB"]
    assert r.unique_to_b == []
    assert any("RHOB" in f for f in r.flags)


def test_disjoint_depths_no_overlap(tmp_path: Path, allowlist: list[Path]) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    _write_las(
        a, well_name="A", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )
    _write_las(
        b, well_name="B", operator="op", start=6000.0, stop=6010.0, step=0.5,
        curves={"GR": "GAPI"},
    )

    r = compare_well_logs(str(a), str(b), allowlist)
    assert r.depth_overlap is None
    assert any("overlap" in f.lower() for f in r.flags)


def test_unit_mismatch_flagged(tmp_path: Path, allowlist: list[Path]) -> None:
    a = tmp_path / "a.las"
    b = tmp_path / "b.las"
    _write_las(
        a, well_name="A", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"RHOB": "g/cm3"},
    )
    _write_las(
        b, well_name="B", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"RHOB": "kg/m3"},
    )

    r = compare_well_logs(str(a), str(b), allowlist)
    rhob = next(d for d in r.unit_diffs if d.name == "RHOB")
    assert rhob.units_match is False
    assert rhob.units_a == "g/cm3"
    assert rhob.units_b == "kg/m3"
    assert any("RHOB" in f for f in r.flags)


def test_path_a_outside_allowlist_denies(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other")
    a = other / "a.las"
    b = tmp_path / "b.las"
    _write_las(
        a, well_name="A", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )
    _write_las(
        b, well_name="B", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )
    with pytest.raises(PathNotAllowedError):
        compare_well_logs(str(a), str(b), [tmp_path])


def test_path_b_outside_allowlist_denies(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other")
    a = tmp_path / "a.las"
    b = other / "b.las"
    _write_las(
        a, well_name="A", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )
    _write_las(
        b, well_name="B", operator="op", start=5000.0, stop=5010.0, step=0.5,
        curves={"GR": "GAPI"},
    )
    with pytest.raises(PathNotAllowedError):
        compare_well_logs(str(a), str(b), [tmp_path])

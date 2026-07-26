"""Synthetic LAS generator. Deterministic from a fixed integer seed.

This is the only module in the package that touches disk. It composes the
facies model and the defect catalogue, writes a LAS file, and writes a
ground-truth manifest beside it recording the bed sequence and every injected
defect.

The manifest is what the eval asserts against, which is why
`tests/test_generator.py` reads the written LAS back and checks it really does
contain what the manifest claims. Nothing here is trustworthy without that.

Both outputs are gitignored; regenerate with `make generate`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lasio
import numpy as np

from examples.sample_data.defects import NULL_VALUE
from examples.sample_data.facies import build_beds, depth_axis, synthesize_curves
from examples.sample_data.truth import DepthAxis, WellTruth
from examples.sample_data.wells import (
    CURVE_DESCRIPTIONS,
    CURVE_UNITS,
    WELLS,
    WellSpec,
)


def truth_path_for(las_path: Path) -> Path:
    """Manifest location for a LAS path. One rule, used by writer and reader."""
    return las_path.with_suffix(".truth.json")


def build_well(
    spec: WellSpec, seed: int | None = None
) -> tuple[np.ndarray, dict[str, np.ndarray], WellTruth]:
    """Build curves and the matching manifest in memory. No I/O.

    Defects are applied after synthesis, so the manifest's bed sequence
    describes the clean geology and its defect list describes what was then
    done to it.
    """
    effective_seed = spec.seed if seed is None else seed
    depth = depth_axis(spec.start, spec.stop, spec.step)
    beds = build_beds(spec.start, spec.stop, seed=effective_seed)
    curves = synthesize_curves(depth, beds, seed=effective_seed)

    defects = spec.apply_defects(curves, depth)

    truth = WellTruth(
        well=spec.name,
        seed=effective_seed,
        depth=DepthAxis(
            start=spec.start, stop=spec.stop, step=spec.step, units=spec.depth_units
        ),
        curves=sorted(curves),
        beds=beds,
        defects=defects,
    )
    return depth, curves, truth


def declared_units(truth: WellTruth) -> dict[str, str]:
    """Units to write into the LAS header.

    Canonical units, with any `unit_mismatch` record applied on top. The record
    is the single source for the lie, so the header and the manifest cannot
    disagree about which curve is mislabelled.
    """
    units = dict(CURVE_UNITS)
    for defect in truth.defects_for("unit_mismatch"):
        if defect.curve and defect.declared_unit:
            units[defect.curve] = defect.declared_unit
    return units


def write_las(
    path: Path,
    spec: WellSpec,
    depth: np.ndarray,
    curves: dict[str, np.ndarray],
    truth: WellTruth,
) -> Path:
    units = declared_units(truth)
    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value=spec.name)
    las.well["COMP"] = lasio.HeaderItem("COMP", value=spec.operator)
    las.well["STRT"] = lasio.HeaderItem("STRT", unit=spec.depth_units, value=spec.start)  # type: ignore[arg-type]
    las.well["STOP"] = lasio.HeaderItem("STOP", unit=spec.depth_units, value=spec.stop)  # type: ignore[arg-type]
    las.well["STEP"] = lasio.HeaderItem("STEP", unit=spec.depth_units, value=spec.step)  # type: ignore[arg-type]
    las.well["NULL"] = lasio.HeaderItem("NULL", value=NULL_VALUE)  # type: ignore[arg-type]

    las.append_curve("DEPT", depth, unit=spec.depth_units, descr="Depth")
    # Sorted so curve order is stable across runs, which the determinism test
    # depends on.
    for name in sorted(curves):
        las.append_curve(
            name,
            curves[name],
            unit=units.get(name, ""),
            descr=CURVE_DESCRIPTIONS.get(name, ""),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(path))
    return path


def generate(spec: WellSpec, las_path: Path, seed: int | None = None) -> tuple[Path, Path]:
    """Write a well and its manifest. Returns both paths."""
    depth, curves, truth = build_well(spec, seed=seed)
    write_las(las_path, spec, depth, curves, truth)
    truth_file = truth_path_for(las_path)
    truth_file.write_text(truth.model_dump_json(indent=2) + "\n")
    return las_path, truth_file


def generate_well_01(path: Path, seed: int = 42) -> Path:
    """SYNTH-01, the reference well. Signature kept for the eval runner."""
    return generate(WELLS["SYNTH-01"], Path(path), seed=seed)[0]


def generate_well_02(path: Path, seed: int = 43) -> Path:
    """SYNTH-02, the offset well used by the comparison scenario."""
    return generate(WELLS["SYNTH-02"], Path(path), seed=seed)[0]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="generate petromcp synthetic wells")
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).parent),
        help="directory to write into (default: alongside this module)",
    )
    args = p.parse_args(argv)
    out_dir = Path(args.out_dir)

    for index, name in enumerate(sorted(WELLS), start=1):
        las_path = out_dir / f"synthetic_well_{index:02d}.las"
        las, truth = generate(WELLS[name], las_path)
        print(f"wrote {las} and {truth.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

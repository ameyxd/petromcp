"""Generate synthetic DLIS wells and their ground-truth manifests.

Reuses the facies model and defect catalogue unchanged — a DLIS well built from
a given seed carries the same geology as the LAS well from that seed. What
differs is the container: curves are split across frames, each frame carries its
own index channel, and a well may span several logical files.

Writes `<name>.dlis` plus `<name>.truth.json` beside it. The manifest records
the bed sequence, every injected defect, and the frame layout, so the eval can
assert structure as well as values.

`tests/test_dlis_generator.py` reads each written file back through `dlisio` and
checks the manifest against it. Without that the manifest is a claim rather
than a fact.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from examples.sample_data.dlis_wells import (
    CHANNEL_UNITS,
    DLIS_WELLS,
    INDEX_TYPE,
    DlisWellSpec,
)
from examples.sample_data.dlis_writer import concatenate_logical_files, write_minimal_dlis
from examples.sample_data.facies import build_beds, depth_axis, synthesize_curves
from examples.sample_data.truth import DepthAxis, WellTruth


def truth_path_for(dlis_path: Path) -> Path:
    """Manifest location. One rule, used by writer and reader alike."""
    return dlis_path.with_suffix(".truth.json")


def build_well(
    spec: DlisWellSpec, seed: int | None = None
) -> tuple[np.ndarray, dict[str, np.ndarray], WellTruth]:
    """Build curves and the matching manifest in memory. No I/O.

    Defects are applied after synthesis, so the manifest's beds describe the
    clean geology and its defect list describes what was then done to it.
    """
    effective_seed = spec.seed if seed is None else seed
    depth = depth_axis(spec.start, spec.stop, spec.step)
    beds = build_beds(spec.start, spec.stop, seed=effective_seed)
    synthesized = synthesize_curves(depth, beds, seed=effective_seed)

    # Only the channels this well actually declares. The facies model always
    # produces the full triple combo; a well that omits DT should not carry it.
    curves = {name: synthesized[name] for name in spec.channel_names}

    defects = spec.apply_defects(curves, depth) if spec.apply_defects else []

    frames = {
        frame.name: list(frame.channels)
        for logical in spec.logical_files
        for frame in logical.frames
    }
    frame_indexes = {
        frame.name: frame.index_channel
        for logical in spec.logical_files
        for frame in logical.frames
    }

    truth = WellTruth(
        well=spec.name,
        seed=effective_seed,
        depth=DepthAxis(
            start=spec.start, stop=spec.stop, step=spec.step, units=spec.depth_units
        ),
        curves=sorted(curves),
        beds=beds,
        defects=defects,
        frames=frames,
        frame_indexes=frame_indexes,
    )
    return depth, curves, truth


def write_well(
    path: Path,
    spec: DlisWellSpec,
    depth: np.ndarray,
    curves: dict[str, np.ndarray],
) -> Path:
    """Write the DLIS. One logical file is written directly; several are written
    separately and concatenated, because `dliswriter` cannot emit more than one.
    """
    parts: list[Path] = []
    staging = path.parent / f".{path.stem}_parts"
    staging.mkdir(parents=True, exist_ok=True)

    for index, logical in enumerate(spec.logical_files):
        frames = {
            frame.name: {
                # The index channel comes first; the writer treats position 0 as
                # the frame index.
                frame.index_channel: (depth, spec.depth_units),
                **{
                    channel: (curves[channel], CHANNEL_UNITS.get(channel, ""))
                    for channel in frame.channels
                },
            }
            for frame in logical.frames
        }
        parts.append(
            write_minimal_dlis(
                staging / f"part_{index:02d}.dlis",
                well_name=spec.name,
                frames=frames,
                company=spec.operator,
                origin_id=logical.origin_id,
                index_type=INDEX_TYPE,
                file_header_id=logical.header_id,
            )
        )

    if len(parts) == 1:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(parts[0].read_bytes())
    else:
        concatenate_logical_files(path, parts)

    for part in parts:
        part.unlink()
    staging.rmdir()
    return path


def generate(spec: DlisWellSpec, path: Path, seed: int | None = None) -> tuple[Path, Path]:
    """Write a DLIS well and its manifest. Returns both paths."""
    depth, curves, truth = build_well(spec, seed=seed)
    write_well(path, spec, depth, curves)
    manifest = truth_path_for(path)
    manifest.write_text(truth.model_dump_json(indent=2) + "\n")
    return path, manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="generate petromcp synthetic DLIS wells")
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).parent),
        help="directory to write into (default: alongside this module)",
    )
    args = p.parse_args(argv)
    out_dir = Path(args.out_dir)

    for index, name in enumerate(sorted(DLIS_WELLS), start=1):
        dlis_path = out_dir / f"synthetic_dlis_{index:02d}.dlis"
        written, manifest = generate(DLIS_WELLS[name], dlis_path)
        print(f"wrote {written.name} and {manifest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

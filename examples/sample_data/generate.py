"""Synthetic LAS generator. Reproducible from a fixed integer seed.

Curves and their relationships are chosen to look superficially plausible
to a petrophysicist: GR is noisy with shale spikes, RHOB and NPHI inversely
correlate, DT trends with porosity. None of this is calibrated; it is meant
to give a QC eval something interesting to flag rather than uniform noise.
"""

from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np


def generate_well_01(path: Path, seed: int = 42) -> Path:
    rng = np.random.default_rng(seed)
    start, stop, step = 5000.0, 9000.0, 0.5
    depth = np.arange(start, stop + step / 2, step)
    n = len(depth)

    shale_signal = 0.5 * np.sin(np.linspace(0, 12 * np.pi, n))
    gr = 60.0 + 40.0 * shale_signal + 8.0 * rng.standard_normal(n)
    porosity = 0.18 + 0.06 * shale_signal + 0.01 * rng.standard_normal(n)
    rhob = 2.65 - 1.4 * porosity + 0.02 * rng.standard_normal(n)
    nphi = porosity + 0.01 * rng.standard_normal(n)
    dt = 60.0 + 250.0 * porosity + 2.0 * rng.standard_normal(n)
    cali = 8.5 + 0.3 * rng.standard_normal(n)

    # Introduce a deliberate gap on RHOB so QC has something to find.
    gap_lo, gap_hi = int(0.40 * n), int(0.42 * n)
    rhob[gap_lo:gap_hi] = -999.25

    las = lasio.LASFile()
    las.well["WELL"] = lasio.HeaderItem("WELL", value="SYNTH-01")
    las.well["COMP"] = lasio.HeaderItem("COMP", value="petromcp synthetic")
    las.well["STRT"] = lasio.HeaderItem("STRT", unit="ft", value=start)  # type: ignore[arg-type]
    las.well["STOP"] = lasio.HeaderItem("STOP", unit="ft", value=stop)  # type: ignore[arg-type]
    las.well["STEP"] = lasio.HeaderItem("STEP", unit="ft", value=step)  # type: ignore[arg-type]
    las.well["NULL"] = lasio.HeaderItem("NULL", value=-999.25)  # type: ignore[arg-type]

    las.append_curve("DEPT", depth, unit="ft")
    las.append_curve("GR", gr, unit="GAPI", descr="Gamma Ray")
    las.append_curve("RHOB", rhob, unit="g/cm3", descr="Bulk Density")
    las.append_curve("NPHI", nphi, unit="v/v", descr="Neutron Porosity")
    las.append_curve("DT", dt, unit="us/ft", descr="Sonic")
    las.append_curve("CALI", cali, unit="in", descr="Caliper")

    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(path))
    return path


def main() -> None:
    out = Path(__file__).parent / "synthetic_well_01.las"
    generate_well_01(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

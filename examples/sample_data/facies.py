"""Facies-based synthetic log curves.

Curve values are derived from the standard petrophysical relations rather than
drawn as arbitrary shapes, so a petrophysicist reading a plot sees the
relationships they expect: gamma ray hot in shale, density and neutron
separating where there is bound water, transit time tracking porosity.

    RHOB = rho_matrix * (1 - phi) + rho_fluid * phi      density-porosity
    DT   = phi * DT_fluid + (1 - phi) * DT_matrix        Wyllie time-average
    NPHI = phi + bound_water                             apparent porosity

**These constants are textbook typical values, not calibrated to any basin.**
They are here so the QC eval has plausible signal to work against, not to
support any petrophysical conclusion. Sources are named per constant below.
An SME review of this table is an open item; see the v0.5 design doc.

Everything in this module is pure and deterministic given a seed. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from examples.sample_data.truth import Bed

# Wyllie (1956) matrix transit times, us/ft: sandstone 55.5, limestone 47.6,
# dolomite 43.5. Fluid (fresh mud filtrate) 189.
FLUID_DT = 189.0
#: Fresh mud filtrate density, g/cm3.
FLUID_DENSITY = 1.0
#: Nominal bit size, inches. CALI reads near this in competent hole.
BIT_SIZE = 8.5
#: Tool vertical resolution used for boundary smoothing, feet. Real logging
#: tools average over roughly this interval, which is why beds read as ramps
#: rather than steps.
SMOOTHING_WINDOW_FT = 2.0


@dataclass(frozen=True)
class Facies:
    """Log response of one rock type.

    `porosity_min`/`porosity_max` bound effective porosity, from which RHOB
    and DT are computed. `bound_water` is added to NPHI only: clay-bound
    water raises apparent neutron porosity without lowering bulk density,
    which is exactly what produces neutron-density separation in shale.
    """

    name: str
    gr_mean: float  # gAPI
    gr_sd: float
    porosity_min: float  # v/v
    porosity_max: float
    matrix_density: float  # g/cm3
    matrix_dt: float  # us/ft
    bound_water: float  # v/v, added to NPHI only
    rugosity_sd: float  # inches of CALI variability


#: Matrix densities: quartz 2.65, calcite 2.71 g/cm3 (standard log-analysis
#: values). Gamma ray: clean quartz sand and clean limestone read 10-30 gAPI,
#: shale 100-140 gAPI. Shale apparent neutron porosity of 0.25-0.35 v/v is
#: dominated by clay-bound water rather than effective porosity.
FACIES: dict[str, Facies] = {
    "clean_sand": Facies(
        name="clean_sand",
        gr_mean=25.0,
        gr_sd=6.0,
        porosity_min=0.15,
        porosity_max=0.28,
        matrix_density=2.65,
        matrix_dt=55.5,
        bound_water=0.0,
        rugosity_sd=0.10,
    ),
    "shaly_sand": Facies(
        name="shaly_sand",
        gr_mean=65.0,
        gr_sd=10.0,
        porosity_min=0.10,
        porosity_max=0.20,
        matrix_density=2.67,
        matrix_dt=62.0,
        bound_water=0.06,
        rugosity_sd=0.18,
    ),
    "shale": Facies(
        name="shale",
        gr_mean=120.0,
        gr_sd=14.0,
        porosity_min=0.02,
        porosity_max=0.07,
        matrix_density=2.70,
        matrix_dt=95.0,
        bound_water=0.26,
        rugosity_sd=0.35,
    ),
    "limestone": Facies(
        name="limestone",
        gr_mean=14.0,
        gr_sd=4.0,
        porosity_min=0.03,
        porosity_max=0.12,
        matrix_density=2.71,
        matrix_dt=47.6,
        bound_water=0.0,
        rugosity_sd=0.08,
    ),
}

#: Facies transition probabilities. Shale is the background lithology and
#: everything tends to return to it, which produces the sand-shale alternation
#: real sections show instead of a random walk through four rock types.
_ORDER = ("clean_sand", "shaly_sand", "shale", "limestone")
_TRANSITIONS: dict[str, tuple[float, ...]] = {
    #                 clean  shaly  shale  lime
    "clean_sand": (0.10, 0.35, 0.50, 0.05),
    "shaly_sand": (0.30, 0.10, 0.55, 0.05),
    "shale": (0.35, 0.30, 0.10, 0.25),
    "limestone": (0.15, 0.15, 0.60, 0.10),
}

_BED_THICKNESS_MEAN_FT = 22.0
_BED_THICKNESS_SIGMA = 0.55
_BED_THICKNESS_MIN_FT = 5.0
_BED_THICKNESS_MAX_FT = 50.0


def depth_axis(start: float, stop: float, step: float) -> np.ndarray:
    """Inclusive depth axis. `step / 2` guards float accumulation at the end."""
    return np.arange(start, stop + step / 2, step)


def rhob_from_porosity(porosity: float | np.ndarray, matrix_density: float) -> np.ndarray:
    """Bulk density from the density-porosity relation."""
    return np.asarray(matrix_density * (1.0 - porosity) + FLUID_DENSITY * porosity)


def dt_from_porosity(porosity: float | np.ndarray, matrix_dt: float) -> np.ndarray:
    """Transit time from the Wyllie time-average equation."""
    return np.asarray(porosity * FLUID_DT + (1.0 - porosity) * matrix_dt)


def build_beds(start: float, stop: float, seed: int) -> list[Bed]:
    """Build a bed sequence tiling [start, stop] with no gaps or overlaps.

    Thicknesses are lognormal, clipped to a plausible range. Facies follow
    `_TRANSITIONS` so the sequence alternates the way a real section does.
    """
    rng = np.random.default_rng(seed)
    beds: list[Bed] = []
    current = "shale"
    top = start

    while top < stop:
        thickness = float(
            np.clip(
                rng.lognormal(mean=np.log(_BED_THICKNESS_MEAN_FT), sigma=_BED_THICKNESS_SIGMA),
                _BED_THICKNESS_MIN_FT,
                _BED_THICKNESS_MAX_FT,
            )
        )
        base = min(top + thickness, stop)
        beds.append(Bed(top=top, base=base, facies=current))
        top = base
        current = str(rng.choice(_ORDER, p=_TRANSITIONS[current]))

    return beds


def _smooth(values: np.ndarray, step: float) -> np.ndarray:
    """Moving average approximating tool vertical resolution.

    `mode="same"` on a normalised boxcar keeps the array length. Edges are
    biased toward zero by the convolution, so they are restored from the
    unsmoothed values rather than left as artificial lows.
    """
    width = max(1, int(round(SMOOTHING_WINDOW_FT / step)))
    if width < 2 or len(values) < width:
        return values
    kernel = np.ones(width) / width
    smoothed = np.convolve(values, kernel, mode="same")
    half = width // 2
    if half:
        smoothed[:half] = values[:half]
        smoothed[-half:] = values[-half:]
    return smoothed


def synthesize_curves(
    depth: np.ndarray, beds: list[Bed], seed: int
) -> dict[str, np.ndarray]:
    """Build a triple-combo curve set over `depth` from the bed sequence.

    Porosity varies smoothly inside each bed rather than being constant, so
    the logs have character without the bed boundaries disappearing.
    """
    rng = np.random.default_rng(seed + 1)
    n = len(depth)
    step = float(depth[1] - depth[0]) if n > 1 else 1.0

    gr = np.empty(n)
    rhob = np.empty(n)
    nphi = np.empty(n)
    dt = np.empty(n)
    cali = np.empty(n)

    for bed in beds:
        f = FACIES[bed.facies]
        mask = (depth >= bed.top) & (depth < bed.base)
        # The final bed's base is the axis end; include it.
        if bed.base >= depth[-1]:
            mask |= depth >= bed.top
        count = int(mask.sum())
        if not count:
            continue

        porosity = rng.uniform(f.porosity_min, f.porosity_max, count)
        gr[mask] = f.gr_mean + f.gr_sd * rng.standard_normal(count)
        rhob[mask] = rhob_from_porosity(porosity, f.matrix_density)
        nphi[mask] = porosity + f.bound_water
        dt[mask] = dt_from_porosity(porosity, f.matrix_dt)
        cali[mask] = BIT_SIZE + np.abs(f.rugosity_sd * rng.standard_normal(count))

    curves = {
        "GR": np.clip(_smooth(gr, step), 0.0, None),
        "RHOB": _smooth(rhob, step),
        "NPHI": np.clip(_smooth(nphi, step), 0.0, 1.0),
        "DT": _smooth(dt, step),
        "CALI": _smooth(cali, step),
    }
    return curves

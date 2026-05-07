"""Hand-coded unit conversion table.

Pure utility — no I/O, no allowlist. Strict case matching: `Ft` is not `ft`.
Symmetry is derived where possible: register `ft -> m` and `m -> ft` is
computed as the reciprocal automatically.

Why hand-coded over Pint: v0.2 supports five small domains. Pint adds 5MB
plus a transitive C library for what fits in a 30-line table. Reassess if
the table reaches double-digit pairs.
"""

from __future__ import annotations

import math
from collections.abc import Callable

Conversion = float | Callable[[float], float]


class UnitConversionError(ValueError):
    """Raised when (from_unit, to_unit) is not a supported pair."""


_FORWARD: dict[tuple[str, str], Conversion] = {
    ("ft", "m"): 0.3048,
    ("psi", "kPa"): 6.894757,
    ("psi", "bar"): 0.0689476,
    ("bbl", "m3"): 0.158987,
    ("mD", "m2"): 9.869233e-16,
    ("degF", "degC"): lambda f: (f - 32.0) * 5.0 / 9.0,
    ("degC", "degF"): lambda c: c * 9.0 / 5.0 + 32.0,
}


def _supported_pairs() -> list[str]:
    seen: set[tuple[str, str]] = set()
    out: list[str] = []
    for a, b in _FORWARD:
        if (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        out.append(f"{a}<->{b}")
    return out


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convert `value` from `from_unit` to `to_unit`.

    Raises:
        ValueError: if `value` is non-finite.
        UnitConversionError: if the pair is not supported.
    """
    if not math.isfinite(value):
        raise ValueError(f"convert_units: non-finite value {value!r}")
    if from_unit == to_unit:
        return value

    forward = _FORWARD.get((from_unit, to_unit))
    if forward is not None:
        return forward(value) if callable(forward) else value * forward

    reverse = _FORWARD.get((to_unit, from_unit))
    if reverse is not None and not callable(reverse):
        return value / float(reverse)

    raise UnitConversionError(
        f"convert_units: {from_unit} -> {to_unit} is not supported. "
        f"Supported pairs: {', '.join(_supported_pairs())}."
    )

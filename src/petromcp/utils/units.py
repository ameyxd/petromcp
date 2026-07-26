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
from typing import NamedTuple

from petromcp.models.units import SupportedUnits, UnitPair

Conversion = float | Callable[[float], float]


class UnitConversionError(ValueError):
    """Raised when (from_unit, to_unit) is not a supported pair."""


class _Entry(NamedTuple):
    """One conversion and the physical quantity it belongs to.

    The quantity lives here rather than in a parallel lookup so that
    `list_supported_units` cannot advertise a label for a pair that has been
    removed, or miss one that has been added.
    """

    apply: Conversion
    quantity: str


_FORWARD: dict[tuple[str, str], _Entry] = {
    ("ft", "m"): _Entry(0.3048, "length"),
    ("psi", "kPa"): _Entry(6.894757, "pressure"),
    ("psi", "bar"): _Entry(0.0689476, "pressure"),
    ("bbl", "m3"): _Entry(0.158987, "volume"),
    ("mD", "m2"): _Entry(9.869233e-16, "permeability"),
    ("degF", "degC"): _Entry(lambda f: (f - 32.0) * 5.0 / 9.0, "temperature"),
    ("degC", "degF"): _Entry(lambda c: c * 9.0 / 5.0 + 32.0, "temperature"),
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
        op = forward.apply
        return op(value) if callable(op) else value * op

    reverse = _FORWARD.get((to_unit, from_unit))
    if reverse is not None and not callable(reverse.apply):
        return value / float(reverse.apply)

    raise UnitConversionError(
        f"convert_units: {from_unit} -> {to_unit} is not supported. "
        f"Supported pairs: {', '.join(_supported_pairs())}. "
        "Call list_supported_units for the full table."
    )


def supported_units() -> SupportedUnits:
    """Every convertible pair, both directions, with its physical quantity.

    Derived from `_FORWARD` so it cannot advertise a pair `convert_units`
    would reject. Reverse directions are included because callers convert both
    ways and a factor pair only stores one. Sorted for stable output.
    """
    pairs: dict[tuple[str, str], str] = {}
    for (a, b), entry in _FORWARD.items():
        pairs[(a, b)] = entry.quantity
        pairs[(b, a)] = entry.quantity

    return SupportedUnits(
        pairs=[
            UnitPair(from_unit=a, to_unit=b, quantity=quantity)
            for (a, b), quantity in sorted(
                pairs.items(), key=lambda kv: (kv[1], kv[0][0], kv[0][1])
            )
        ]
    )

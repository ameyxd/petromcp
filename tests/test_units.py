import math

import pytest
from pydantic import ValidationError

from petromcp.utils.units import (
    _FORWARD,
    UnitConversionError,
    convert_units,
    supported_units,
)


def test_identity_returns_value() -> None:
    assert convert_units(7.0, "ft", "ft") == 7.0


def test_ft_to_m_golden() -> None:
    assert convert_units(1.0, "ft", "m") == pytest.approx(0.3048, rel=1e-9)


def test_m_to_ft_round_trip() -> None:
    out = convert_units(convert_units(1.0, "ft", "m"), "m", "ft")
    assert out == pytest.approx(1.0, rel=1e-9)


def test_psi_to_kpa_golden() -> None:
    assert convert_units(1.0, "psi", "kPa") == pytest.approx(6.894757, rel=1e-6)


def test_psi_to_bar_round_trip() -> None:
    out = convert_units(convert_units(100.0, "psi", "bar"), "bar", "psi")
    assert out == pytest.approx(100.0, rel=1e-9)


def test_bbl_to_m3_golden() -> None:
    assert convert_units(1.0, "bbl", "m3") == pytest.approx(0.158987, rel=1e-5)


def test_degF_degC_zero_celsius() -> None:  # noqa: N802
    assert convert_units(0.0, "degC", "degF") == pytest.approx(32.0, rel=1e-9)


def test_degF_degC_round_trip() -> None:  # noqa: N802
    out = convert_units(convert_units(72.0, "degF", "degC"), "degC", "degF")
    assert out == pytest.approx(72.0, rel=1e-9)


def test_mD_to_m2_golden() -> None:  # noqa: N802
    assert convert_units(1.0, "mD", "m2") == pytest.approx(9.869233e-16, rel=1e-5)


def test_mD_round_trip() -> None:  # noqa: N802
    out = convert_units(convert_units(50.0, "mD", "m2"), "m2", "mD")
    assert out == pytest.approx(50.0, rel=1e-6)


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnitConversionError) as exc:
        convert_units(1.0, "ft", "kg")
    assert "ft" in str(exc.value) and "kg" in str(exc.value)


def test_case_sensitive_strict() -> None:
    with pytest.raises(UnitConversionError):
        convert_units(1.0, "Ft", "m")


def test_non_finite_input_raises() -> None:
    with pytest.raises(ValueError):
        convert_units(math.inf, "ft", "m")
    with pytest.raises(ValueError):
        convert_units(math.nan, "ft", "m")


class TestListSupportedUnits:
    """The tool and the conversion table must not diverge. Assert in both
    directions: everything reported is convertible, and everything convertible
    is reported."""

    def test_reports_every_pair_in_the_conversion_table(self) -> None:
        reported = {(p.from_unit, p.to_unit) for p in supported_units().pairs}
        for a, b in _FORWARD:
            assert (a, b) in reported or (b, a) in reported, f"{a}->{b} not reported"

    def test_every_reported_pair_actually_converts(self) -> None:
        for pair in supported_units().pairs:
            # Would raise UnitConversionError if the tool advertised a pair the
            # converter does not accept.
            convert_units(1.0, pair.from_unit, pair.to_unit)

    def test_every_reported_pair_converts_in_reverse_too(self) -> None:
        for pair in supported_units().pairs:
            convert_units(1.0, pair.to_unit, pair.from_unit)

    def test_reports_both_directions_for_each_pair(self) -> None:
        reported = {(p.from_unit, p.to_unit) for p in supported_units().pairs}
        for a, b in list(reported):
            assert (b, a) in reported, f"{b}->{a} missing"

    def test_every_pair_carries_a_quantity_label(self) -> None:
        for pair in supported_units().pairs:
            assert pair.quantity, f"{pair.from_unit}->{pair.to_unit} has no quantity"

    def test_quantities_are_from_the_known_set(self) -> None:
        known = {"length", "pressure", "volume", "temperature", "permeability"}
        assert {p.quantity for p in supported_units().pairs} <= known

    def test_result_is_frozen(self) -> None:
        result = supported_units()
        with pytest.raises(ValidationError):
            result.pairs = []  # type: ignore[misc]

    def test_pairs_are_sorted_for_stable_output(self) -> None:
        """Token-budgeted output should be deterministic across calls so it
        caches and diffs cleanly."""
        pairs = [(p.quantity, p.from_unit, p.to_unit) for p in supported_units().pairs]
        assert pairs == sorted(pairs)

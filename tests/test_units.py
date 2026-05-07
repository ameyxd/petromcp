import math

import pytest

from petromcp.utils.units import UnitConversionError, convert_units


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

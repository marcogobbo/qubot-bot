import pytest

from qubot.core.units import format_value


@pytest.mark.parametrize(
    "raw,quantity,kwargs,expected",
    [
        # Temperature: K vs mK only.
        (0.9, "temperature", {}, "900.000 mK"),
        (1.2, "temperature", {}, "1.200 K"),
        (1.234, "temperature", {"precision": 2}, "1.23 K"),
        # Pressure: kPa / Pa only.
        (1500, "pressure", {}, "1.500 kPa"),
        (12.0, "pressure", {}, "12.000 Pa"),
        # 500 Pa keeps mantissa >= 1 in Pa, so it does not promote to kPa.
        (500, "pressure", {"precision": 1}, "500.0 Pa"),
        # Power: full SI range.
        (1.2e-9, "power", {}, "1.200 nW"),
        (3.4e-13, "power", {}, "0.340 pW"),
        (2.5e-3, "power", {}, "2.500 mW"),
        # Flow: fixed display μmol/s with from_base_scale=1e6.
        (5e-3, "flow", {"from_base_scale": 1e6, "precision": 2}, "5000.00 μmol/s"),
        # None (sensor read failed).
        (None, "temperature", {}, "N/A"),
        (None, "pressure", {}, "N/A"),
        # Zero (out of range).
        (0, "temperature", {}, "Out of range"),
        (0, "power", {}, "Out of range"),
        (0.0, "pressure", {}, "Out of range"),
        # Magnetic field: T vs mT.
        (1.5, "magnetic_field", {}, "1.500 T"),
        (0.02, "magnetic_field", {}, "20.000 mT"),
        # Negative values keep their sign and scale by magnitude.
        (-0.5, "temperature", {}, "-500.000 mK"),
        (-2.0, "magnetic_field", {}, "-2.000 T"),
        # Below the smallest prefix (pW) — still rendered with it (mantissa < 1).
        (1e-14, "power", {}, "0.010 pW"),
        (1e-14, "power", {"precision": 6}, "0.010000 pW"),
    ],
)
def test_format_value(raw, quantity, kwargs, expected):
    assert format_value(raw, quantity, **kwargs) == expected


def test_unknown_quantity_raises():
    with pytest.raises(ValueError):
        format_value(1.0, "bogus")


def test_none_and_zero_short_circuit_before_unknown_quantity():
    # None / 0 are handled before the quantity table is consulted, so an unknown
    # quantity does not raise in those cases.
    assert format_value(None, "bogus") == "N/A"
    assert format_value(0, "bogus") == "Out of range"

import pytest

from qubot.core.units import format_value


@pytest.mark.parametrize(
    "raw,quantity,kwargs,expected",
    [
        # Temperature: K vs mK only.
        (0.9,    "temperature", {}, "900.000 mK"),
        (1.2,    "temperature", {}, "1.200 K"),
        (1.234,  "temperature", {"precision": 2}, "1.23 K"),
        # Pressure: kPa / Pa only.
        (1500,   "pressure", {}, "1.500 kPa"),
        (12.0,   "pressure", {}, "12.000 Pa"),
        (500,    "pressure", {"precision": 1}, "0.5 kPa"),
        # Power: full SI range.
        (1.2e-9, "power", {}, "1.200 nW"),
        (3.4e-13,"power", {}, "0.340 pW"),
        (2.5e-3, "power", {}, "2.500 mW"),
        # Flow: fixed display μmol/s with from_base_scale=1e6.
        (5e-3,   "flow", {"from_base_scale": 1e6, "precision": 2}, "5000.00 μmol/s"),
        # None (sensor read failed).
        (None,   "temperature", {}, "N/A"),
        (None,   "pressure", {}, "N/A"),
        # Zero (out of range).
        (0,      "temperature", {}, "Out of range"),
        (0,      "power", {}, "Out of range"),
        (0.0,    "pressure", {}, "Out of range"),
    ],
)
def test_format_value(raw, quantity, kwargs, expected):
    assert format_value(raw, quantity, **kwargs) == expected


def test_unknown_quantity_raises():
    with pytest.raises(ValueError):
        format_value(1.0, "bogus")

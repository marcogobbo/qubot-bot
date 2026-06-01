"""Tests for the pure dataclasses in ``qubot.services.proteox``.

Only ``Snapshot`` and ``SensorReading`` are exercised — never the WAMP client.
Importing this module pulls in ``qtics`` (a dependency of ``proteox``); that is
installed by ``poetry install`` and in CI.
"""

from __future__ import annotations

import pytest

from qubot.core.fridge_config import SensorSpec
from qubot.services.proteox import SensorReading, Snapshot


def _reading(uri_key: str, value, quantity: str = "temperature", **kw) -> SensorReading:
    return SensorReading(
        spec=SensorSpec(uri_key=uri_key, label=uri_key, quantity=quantity, **kw),
        value=value,
    )


# --- Snapshot.status / is_idle ----------------------------------------------


def test_status_is_first_state():
    assert Snapshot(fridge_name="elsa", states=["Running", "Idle"]).status == "Running"


def test_status_unknown_when_no_states():
    assert Snapshot(fridge_name="elsa", states=[]).status == "Unknown"


@pytest.mark.parametrize(
    "states,expected",
    [
        (["IDLE"], True),
        (["Idle (precool)"], True),
        (["idle"], True),
        (["Running"], False),
        ([], False),
        (["Cooldown", "Idle complete"], True),
    ],
)
def test_is_idle(states, expected):
    assert Snapshot(fridge_name="elsa", states=states).is_idle is expected


# --- Snapshot.temperature_value ---------------------------------------------


def test_temperature_value_hit_and_miss():
    snap = Snapshot(
        fridge_name="elsa",
        states=["Running"],
        temperatures=[_reading("PT2_T1", 3.2), _reading("MC_T", 0.012)],
    )
    assert snap.temperature_value("PT2_T1") == 3.2
    assert snap.temperature_value("MC_T") == 0.012
    assert snap.temperature_value("DOES_NOT_EXIST") is None


# --- SensorReading.formatted ------------------------------------------------


def test_heater_zero_renders_off():
    assert _reading("MC_H", 0, quantity="power").formatted() == "OFF"


def test_non_heater_zero_is_out_of_range():
    assert _reading("MC_T", 0, quantity="temperature").formatted() == "Out of range"


def test_none_value_is_na():
    assert _reading("MC_T", None).formatted() == "N/A"


def test_normal_value_delegates_to_format_value():
    # 0.9 K → 900 mK via the temperature prefix table.
    assert _reading("MC_T", 0.9, precision=3).formatted() == "900.000 mK"


def test_heater_nonzero_still_formats_power():
    assert _reading("MC_H", 2.5e-3, quantity="power").formatted() == "2.500 mW"

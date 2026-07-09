"""Tests for the UTA CGI HTML parser (``qubot.services.uta``).

``parse_uta_html`` is pure: HTML in, ``UtaSnapshot`` out. No network involved.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from qubot.services.uta import UtaSnapshot, _grab, _strip_html, parse_uta_html

TZ = ZoneInfo("Europe/Rome")


# --- helpers ----------------------------------------------------------------


def test_strip_html_removes_tags_and_unescapes_entities():
    out = _strip_html("<p>T&nbsp;lab: 21.4 &amp; rising</p>")
    assert "<p>" not in out
    assert "&amp;" not in out
    assert "21.4" in out


def test_grab_returns_none_when_pattern_absent():
    assert _grab(r"T laboratorio:\s*(-?\d+(?:\.\d+)?)", "nothing here") is None


def test_grab_parses_first_match():
    assert _grab(r"x:\s*(-?\d+(?:\.\d+)?)", "x: -3.5 y: 9") == -3.5


# --- full parse: running plant, summer --------------------------------------


def test_parse_running_summer(uta_html_running):
    snap = parse_uta_html(uta_html_running, TZ)

    # Timestamp parsed from the embedded date/time.
    assert (snap.timestamp.year, snap.timestamp.month, snap.timestamp.day) == (2026, 5, 14)
    assert snap.timestamp.hour == 12
    assert snap.timestamp.tzinfo == TZ

    # Season + setpoint routing (summer → sp_summer set, sp_winter None).
    assert snap.stagione == 0
    assert snap.sp_summer == 24.0
    assert snap.sp_winter is None

    # Analog grabs.
    assert snap.t_lab == 21.4
    assert snap.t_pumps_room == 19.2
    assert snap.t_external == 27.8
    assert snap.t_water_cold == 7.1
    assert snap.t_water_hot == 41.0
    assert (snap.t_preheat, snap.sp_preheat, snap.valve_preheat) == (22.0, 23.0, 10.0)
    assert (snap.t_cool, snap.valve_cool) == (18.5, 40.0)
    assert (snap.t_supply, snap.sp_supply, snap.valve_supply) == (20.1, 21.0, 55.0)
    assert (snap.flow_supply, snap.flow_return) == (1200.0, 1100.0)
    assert snap.dp_pocket == 120.0
    assert snap.dp_absolute == 80.0
    assert snap.humidity == 45.0
    assert snap.co2 == 480.0
    assert snap.t_water_chiller == 6.5

    # Digital state.
    assert snap.marcia == 1
    assert snap.inverterin == 1
    assert snap.inverterout == 1
    assert snap.fancoil == 1
    assert (snap.iauto, snap.ausiliari) == (1, 0)
    assert snap.frigoon == 1

    # Derived properties.
    assert snap.any_alarm is False
    assert snap.any_alarm_chiller is False
    assert snap.is_running is True
    assert snap.chiller_running is True


# --- full parse: stopped plant with alarms, winter --------------------------


def test_parse_alarm_winter(uta_html_alarm_winter):
    snap = parse_uta_html(uta_html_alarm_winter, TZ)

    assert snap.stagione == 1
    assert snap.sp_winter == 20.0
    assert snap.sp_summer is None

    assert snap.marcia == 0
    assert snap.inverterin == 0
    assert snap.inverterout == 0
    assert snap.termalarm == 1
    assert snap.notifier == 1
    assert (snap.alinverterin, snap.alinverterout) == (1, 0)

    # Chiller alarm discrimination: "termico gruppo frigo" must NOT also set the
    # plain "gruppo frigo" alarm.
    assert snap.frigotermico == 1
    assert snap.frigoalarm == 0
    assert snap.frigoon == 0

    assert snap.any_alarm is True
    assert snap.any_alarm_chiller is True
    assert snap.is_running is False
    assert snap.chiller_running is False


# --- sparse / fallback behaviour --------------------------------------------


def test_parse_sparse_uses_fallbacks(uta_html_sparse):
    snap = parse_uta_html(uta_html_sparse, TZ)

    # No timestamp in the HTML → falls back to "now" in the given tz.
    assert snap.timestamp.tzinfo == TZ
    # Missing analog fields stay None.
    assert snap.t_lab is None
    assert snap.flow_supply is None
    # Defaults: no stop-phrases means inverters/chiller read "on", plant "off".
    assert snap.marcia == 0
    assert snap.inverterin == 1
    assert snap.inverterout == 1
    assert snap.frigoon == 1
    assert snap.is_running is False


# --- property truth tables (constructed directly) ---------------------------


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, False),
        ({"termalarm": 1}, True),
        ({"notifier": 1}, True),
        ({"incendio": 1}, True),
        ({"alinverterin": 1}, True),
        ({"generalarm": 1}, True),
    ],
)
def test_any_alarm(kwargs, expected):
    from datetime import datetime

    snap = UtaSnapshot(timestamp=datetime.now(tz=TZ), **kwargs)
    assert snap.any_alarm is expected


def test_is_running_requires_all_three_and_no_alarm():
    from datetime import datetime

    base = dict(marcia=1, inverterin=1, inverterout=1)
    assert UtaSnapshot(timestamp=datetime.now(tz=TZ), **base).is_running is True
    # Any alarm disqualifies.
    assert UtaSnapshot(timestamp=datetime.now(tz=TZ), notifier=1, **base).is_running is False
    # Missing any component disqualifies.
    assert (
        UtaSnapshot(timestamp=datetime.now(tz=TZ), marcia=0, inverterin=1, inverterout=1).is_running
        is False
    )

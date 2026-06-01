"""Light cog tests with mocked Discord / Proteox objects.

These import the cog modules (and therefore ``discord`` and ``qtics``), both of
which are installed by ``poetry install`` and in CI.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from qubot.cogs import reports, scheduler

# --- helpers ----------------------------------------------------------------


def _conn(dest_id: int):
    return SimpleNamespace(destination_id=dest_id)


def _fake_bot(fridges=None, profiles=None):
    settings = SimpleNamespace(
        fridges=fridges or {},
        profiles=profiles or {},
        daily_report_tz="Europe/Rome",
        daily_report_hour=9,
        daily_report_minute=30,
    )
    return SimpleNamespace(settings=settings, profiles=profiles or {})


class _FakeSnap:
    def __init__(self, *, status="Running", is_idle=False, pt2=2.0):
        self.status = status
        self.is_idle = is_idle
        self._pt2 = pt2

    def temperature_value(self, _key):
        return self._pt2


def _proteox_cls_returning(snap):
    class _FakeProteox:
        def __init__(self, conn, profile):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def snapshot(self):
            return snap

    return _FakeProteox


# --- ReportsCog -------------------------------------------------------------


def test_reports_builds_channel_map():
    bot = _fake_bot(fridges={"elsa": _conn(111), "anna": _conn(222)})
    cog = reports.ReportsCog(bot)
    assert cog._fridge_by_channel == {111: "elsa", 222: "anna"}


@pytest.mark.asyncio
async def test_report_in_unbound_channel_defers_ephemerally():
    bot = _fake_bot(fridges={"elsa": _conn(111)})
    cog = reports.ReportsCog(bot)

    interaction = SimpleNamespace(
        channel_id=999,  # not bound to any fridge
        user="tester",
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    await reports.ReportsCog.report.callback(cog, interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.followup.send.assert_not_called()


# --- SchedulerCog._maybe_post_for -------------------------------------------


@pytest.fixture
def scheduler_cog():
    profile = SimpleNamespace(pt2_key="PT2_T1", display_name="Elsa")
    bot = _fake_bot(fridges={"elsa": _conn(111)}, profiles={"elsa": profile})
    return scheduler.SchedulerCog(bot)


async def _run_maybe_post(monkeypatch, cog, snap):
    send_mock = AsyncMock()
    monkeypatch.setattr(scheduler, "ProteoxService", _proteox_cls_returning(snap))
    monkeypatch.setattr(scheduler.destinations, "send_embed", send_mock)
    monkeypatch.setattr(scheduler, "build_report_embed", lambda profile, snap: "EMBED")
    await cog._maybe_post_for("elsa")
    return send_mock


@pytest.mark.asyncio
async def test_skip_when_idle_and_warm(monkeypatch, scheduler_cog):
    snap = _FakeSnap(status="Idle", is_idle=True, pt2=300.0)
    send = await _run_maybe_post(monkeypatch, scheduler_cog, snap)
    send.assert_not_called()


@pytest.mark.asyncio
async def test_post_when_running(monkeypatch, scheduler_cog):
    snap = _FakeSnap(status="Running", is_idle=False, pt2=2.0)
    send = await _run_maybe_post(monkeypatch, scheduler_cog, snap)
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_when_idle_but_cold(monkeypatch, scheduler_cog):
    snap = _FakeSnap(status="Idle", is_idle=True, pt2=2.0)
    send = await _run_maybe_post(monkeypatch, scheduler_cog, snap)
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_when_local_mode(monkeypatch, scheduler_cog):
    snap = _FakeSnap(status="Unknown (None)", is_idle=False, pt2=2.0)
    send = await _run_maybe_post(monkeypatch, scheduler_cog, snap)
    send.assert_not_called()

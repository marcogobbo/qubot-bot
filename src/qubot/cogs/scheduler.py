"""Daily 9:30 report scheduler.

For each fridge, takes a snapshot and posts to its configured destination
unless:
  * the cryostat is in LOCAL mode, or
  * the fridge is warm: status is Idle AND Pulse-tube 2 reads above 273 K.
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from qubot.core.logging_setup import get_logger
from qubot.services import destinations
from qubot.services.proteox import ProteoxService
from qubot.services.report import build_report_embed

if TYPE_CHECKING:
    from qubot.main import QuBot


class SchedulerCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.scheduler")

        tz = ZoneInfo(bot.settings.daily_report_tz)
        run_at = time(
            hour=bot.settings.daily_report_hour,
            minute=bot.settings.daily_report_minute,
            tzinfo=tz,
        )
        # tasks.loop accepts `time=` for fixed daily fire times (timezone-aware).
        self.daily_report = tasks.loop(time=run_at)(self._daily_report_impl)

    async def cog_load(self) -> None:
        self.daily_report.start()
        self.log.info(
            "daily report scheduled for %02d:%02d %s",
            self.bot.settings.daily_report_hour,
            self.bot.settings.daily_report_minute,
            self.bot.settings.daily_report_tz,
        )

    async def cog_unload(self) -> None:
        self.daily_report.cancel()

    async def _daily_report_impl(self) -> None:
        self.log.info("daily report tick — checking %d fridges", len(self.bot.profiles))
        for name, profile in self.bot.profiles.items():
            await self._maybe_post_for(name)

    async def _maybe_post_for(self, name: str) -> None:
        profile = self.bot.profiles[name]
        conn = self.bot.settings.fridges[name]
        try:
            async with ProteoxService(conn, profile) as svc:
                snap = await svc.snapshot()
        except RuntimeError as exc:
            # Timeout / connection error — give users the same feedback as /report.
            self.log.error("service error for %s: %s — posting network warning", name, exc)
            try:
                await destinations.send_text(
                    self.bot, conn, f":warning: **{profile.display_name}** {exc}"
                )
            except Exception:  # noqa: BLE001
                self.log.exception("failed to send network warning for %s", name)
            return
        except Exception:  # noqa: BLE001
            self.log.exception("snapshot failed for %s — skipping post", name)
            return

        # Check if cryostat is in LOCAL mode (not REMOTE).
        if snap.status is None or "None" in snap.status:
            self.log.info("%s is in LOCAL mode — skipping daily report", name)
            return

        pt2 = snap.temperature_value(profile.pt2_key)
        if snap.is_idle and pt2 is not None and pt2 > 273:
            self.log.info(
                "skip %s: warm (idle and PT2=%.2f K > 273 K)",
                name, pt2,
            )
            return

        embed = build_report_embed(profile, snap)
        try:
            await destinations.send_embed(self.bot, conn, embed)
        except Exception:  # noqa: BLE001
            self.log.exception("failed to send report for %s", name)


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(SchedulerCog(bot))

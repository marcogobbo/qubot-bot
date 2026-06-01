"""Monday Meeting reminder — scheduled embed sent at 09:15 every Monday."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from qubot.core.logging_setup import get_logger

if TYPE_CHECKING:
    from qubot.main import QuBot


class MondayCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.monday")

        tz = ZoneInfo(bot.settings.daily_report_tz)
        run_at = time(
            hour=bot.settings.monday_meeting_hour,
            minute=bot.settings.monday_meeting_minute,
            tzinfo=tz,
        )
        # tasks.loop with time= fires once per day at that time, every day.
        # We skip non-Monday days in _impl().
        self.monday_reminder = tasks.loop(time=run_at)(self._impl)

    async def cog_load(self) -> None:
        self.monday_reminder.start()
        self.log.info(
            "monday meeting reminder scheduled for %02d:%02d %s",
            self.bot.settings.monday_meeting_hour,
            self.bot.settings.monday_meeting_minute,
            self.bot.settings.daily_report_tz,
        )

    async def cog_unload(self) -> None:
        self.monday_reminder.cancel()

    async def _impl(self) -> None:
        # Check if today is Monday (weekday() returns 0 for Monday).
        tz = ZoneInfo(self.bot.settings.daily_report_tz)
        if datetime.now(tz).weekday() != 0:
            return

        # Check if destination is configured.
        dest_id = self.bot.settings.monday_meeting_destination_id
        if dest_id == 0:
            self.log.warning("MONDAY_MEETING_DESTINATION_ID not set, skipping send")
            return

        zoom_url = self.bot.settings.monday_meeting_zoom_url
        minutes_url = self.bot.settings.monday_meeting_minutes_url

        if not zoom_url or not minutes_url:
            self.log.warning(
                "MONDAY_MEETING_ZOOM_URL or MONDAY_MEETING_MINUTES_URL not set, skipping"
            )
            return

        # Build the embed.
        embed = discord.Embed(
            title="📢 **Monday Meeting**",
            description=(
                f"Good morning everyone! ☀️ The **Monday Meeting** starts in 15 minutes! ☕\n"
                f"Can't make it in person? Join on [**Zoom**]({zoom_url})! "
                f"And don't forget to take the [**minutes**]({minutes_url})! 📝"
            ),
            color=0x3498DB,
        )

        # Resolve the destination (channel or thread).
        try:
            dest_type = self.bot.settings.monday_meeting_destination_type
            if dest_type == "channel":
                target = self.bot.get_channel(dest_id)
                if target is None:
                    target = await self.bot.fetch_channel(dest_id)
                if not isinstance(target, (discord.TextChannel, discord.Thread)):
                    self.log.error("destination %s is not a text channel", dest_id)
                    return
            else:  # thread
                target = self.bot.get_channel(dest_id)
                if target is None:
                    target = await self.bot.fetch_channel(dest_id)
                if not isinstance(target, discord.Thread):
                    self.log.error("destination %s is not a thread", dest_id)
                    return

            await target.send(embed=embed)
            self.log.info("sent Monday Meeting reminder to %s id=%s", dest_type, dest_id)
        except Exception:  # noqa: BLE001
            self.log.exception("failed to send Monday Meeting reminder")


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(MondayCog(bot))

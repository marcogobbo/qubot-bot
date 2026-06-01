"""`/report` slash command — on-demand fridge report.

The fridge is inferred from the channel or thread where /report is invoked:
each fridge has a `<FRIDGE>_DESTINATION_ID` in `.env`, and the cog builds a
reverse map at load time. Invocations in unbound channels are silently
absorbed (logged for audit) so the bot doesn't spam unrelated rooms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from qubot.core.logging_setup import get_logger
from qubot.services.proteox import ProteoxService
from qubot.services.report import build_report_embed

if TYPE_CHECKING:
    from qubot.main import QuBot


class ReportsCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.reports")
        # Reverse-lookup: which fridge owns a given channel/thread ID?
        self._fridge_by_channel: dict[int, str] = {
            conn.destination_id: name for name, conn in bot.settings.fridges.items()
        }
        self.log.info(
            "channel→fridge map: %s",
            {cid: n for cid, n in self._fridge_by_channel.items()},
        )

    @app_commands.command(name="report", description="Generate a fridge report for this channel.")
    async def report(self, interaction: discord.Interaction) -> None:
        channel_id = interaction.channel_id
        # channel_id is None in DMs; .get tolerates it and the None branch below
        # handles unbound/DM channels identically.
        name = self._fridge_by_channel.get(channel_id)  # type: ignore[arg-type]
        if name is None:
            self.log.info(
                "/report ignored: channel %s not bound to a fridge (user=%s)",
                channel_id,
                interaction.user,
            )
            # Silently absorb the click — ephemeral defer clears the loading state
            # without producing a message visible to anyone else.
            await interaction.response.defer(ephemeral=True)
            return

        self.log.info("/report invoked by %s for fridge=%s", interaction.user, name)
        await interaction.response.defer(thinking=True)

        conn = self.bot.settings.fridges[name]
        profile = self.bot.profiles[name]
        try:
            async with ProteoxService(conn, profile) as svc:
                snap = await svc.snapshot()
        except RuntimeError as exc:
            # Timeout or connection error from ProteoxService
            self.log.error("service error for %s: %s", name, exc)
            await interaction.followup.send(f":warning: **{profile.display_name}** {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.log.exception("snapshot failed for %s", name)
            await interaction.followup.send(
                f":x: Failed to query **{profile.display_name}**: `{exc}`"
            )
            return

        # Check if cryostat is in LOCAL mode (not REMOTE).
        if snap.status is None or "None" in snap.status:
            self.log.info("%s is in LOCAL mode", name)
            await interaction.followup.send(
                f":warning: **{profile.display_name}** is in **LOCAL** mode. "
                "Please set it to **REMOTE** mode."
            )
            return

        embed = build_report_embed(profile, snap)
        await interaction.followup.send(embed=embed)


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(ReportsCog(bot))

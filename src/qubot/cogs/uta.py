"""`/uta` slash command — HVAC plant (UTA) status report.

Unlike `/report`, this command is available in **every** channel/thread: there
is no destination map and no channel gating. Each invocation downloads the
two controller SQLite databases via FTP, reads the latest row, and renders a
Discord embed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from qubot.core.logging_setup import get_logger
from qubot.services.uta import fetch_uta_snapshot
from qubot.services.uta_report import build_uta_embed

if TYPE_CHECKING:
    from qubot.main import QuBot


class UtaCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.uta")

    @app_commands.command(name="uta", description="Show UTA (HVAC) status report.")
    async def uta(self, interaction: discord.Interaction) -> None:
        self.log.info("/uta invoked by %s in channel=%s", interaction.user, interaction.channel_id)
        await interaction.response.defer(thinking=True)
        try:
            snap = await fetch_uta_snapshot(self.bot.settings)
        except RuntimeError as exc:
            self.log.error("UTA fetch failed: %s", exc)
            await interaction.followup.send(f":warning: **UTA** {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.log.exception("UTA fetch failed unexpectedly")
            await interaction.followup.send(f":x: UTA report failed: `{exc}`")
            return
        await interaction.followup.send(
            embed=build_uta_embed(snap, cgi_url=self.bot.settings.uta_cgi_url)
        )


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(UtaCog(bot))

"""Global `/help` command — lists every QuBot slash command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from qubot.core.logging_setup import get_logger

if TYPE_CHECKING:
    from qubot.main import QuBot


def _build_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🤖 **QuBot — Commands**",
        description="Available slash commands.",
        color=0x3498DB,
    )
    embed.add_field(
        name="**In a fridge channel/thread.**",
        value=(
            "`/report` — full cryostat snapshot (temperatures, pressures, heaters, flow).\n"
            "`/recognized` — whether the cryostat is currently in a recognized state.\n"
            "`/recognizedstates` — list every recognized state from the Proteox table.\n"
            "`/howto [target_state]` — suggest actions to reach a recognized state "
            "(closest one if no argument)."
        ),
        inline=False,
    )
    embed.add_field(
        name="**Everywhere**",
        value=("`/uta` — HVAC plant (UTA) status report.\n" "`/help` — this message."),
        inline=False,
    )
    embed.add_field(
        name="**Notes**",
        value=(
            "- Fridge-channel commands are silently ignored elsewhere.\n"
            "- `/howto` autocompletes recognized-state names as you type."
        ),
        inline=False,
    )
    return embed


class HelpCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.help")

    @app_commands.command(name="help", description="Show available QuBot commands.")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        self.log.info("/help invoked by %s in channel=%s", interaction.user, interaction.channel_id)
        await interaction.response.defer(thinking=True)
        await interaction.followup.send(embed=_build_help_embed())


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(HelpCog(bot))

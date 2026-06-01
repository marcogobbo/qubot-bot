"""Channel-gated recognized-state commands: `/recognizedstates`, `/recognized`, `/howto`.

Each command is bound to the same channel→fridge map as `/report`. Invocations
in a non-fridge channel are silently absorbed via an ephemeral defer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from qtics.instruments.network.proteox.recognized_states import RECOGNIZED_STATES

from qubot.core.logging_setup import get_logger
from qubot.services.proteox import ProteoxService
from qubot.services.recognized_report import (
    build_recognized_embed,
    build_recognized_states_embed,
    build_transition_plan_embed,
)

if TYPE_CHECKING:
    from qubot.main import QuBot


class StatesCog(commands.Cog):
    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.states")
        self._fridge_by_channel: dict[int, str] = {
            conn.destination_id: name for name, conn in bot.settings.fridges.items()
        }

    async def _silently_ignore(self, interaction: discord.Interaction, cmd: str) -> None:
        self.log.info(
            "/%s ignored: channel %s not bound to a fridge (user=%s)",
            cmd,
            interaction.channel_id,
            interaction.user,
        )
        await interaction.response.defer(ephemeral=True)

    @app_commands.command(
        name="recognizedstates",
        description="List recognized cryostat states for this channel's fridge.",
    )
    async def recognizedstates(self, interaction: discord.Interaction) -> None:
        # channel_id is None in DMs; .get tolerates it and the None branch below
        # handles unbound/DM channels identically.
        name = self._fridge_by_channel.get(interaction.channel_id)  # type: ignore[arg-type]
        if name is None:
            await self._silently_ignore(interaction, "recognizedstates")
            return
        await interaction.response.defer(thinking=True)
        profile = self.bot.profiles[name]
        names = sorted(RECOGNIZED_STATES.keys())
        await interaction.followup.send(embed=build_recognized_states_embed(profile, names))

    @app_commands.command(
        name="recognized",
        description="Check whether the cryostat is in a recognized state.",
    )
    async def recognized(self, interaction: discord.Interaction) -> None:
        # channel_id is None in DMs; .get tolerates it and the None branch below
        # handles unbound/DM channels identically.
        name = self._fridge_by_channel.get(interaction.channel_id)  # type: ignore[arg-type]
        if name is None:
            await self._silently_ignore(interaction, "recognized")
            return

        self.log.info("/recognized invoked by %s for fridge=%s", interaction.user, name)
        await interaction.response.defer(thinking=True)

        conn = self.bot.settings.fridges[name]
        profile = self.bot.profiles[name]
        try:
            async with ProteoxService(conn, profile) as svc:
                result = await svc.recognized_status()
        except RuntimeError as exc:
            self.log.error("service error for %s: %s", name, exc)
            await interaction.followup.send(f":warning: **{profile.display_name}** {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.log.exception("recognized check failed for %s", name)
            await interaction.followup.send(
                f":x: Failed to query **{profile.display_name}**: `{exc}`"
            )
            return

        if result is None:
            self.log.info("%s is in LOCAL mode", name)
            await interaction.followup.send(
                f":warning: **{profile.display_name}** is in **LOCAL** mode. "
                "Please set it to **REMOTE** mode."
            )
            return

        is_recognized, states = result
        await interaction.followup.send(
            embed=build_recognized_embed(profile, is_recognized, states)
        )

    @app_commands.command(
        name="howto",
        description="Suggest how to reach a recognized state.",
    )
    @app_commands.describe(
        target_state="Recognized state to reach. Leave empty for the closest match."
    )
    async def howto(
        self,
        interaction: discord.Interaction,
        target_state: str | None = None,
    ) -> None:
        # channel_id is None in DMs; .get tolerates it and the None branch below
        # handles unbound/DM channels identically.
        name = self._fridge_by_channel.get(interaction.channel_id)  # type: ignore[arg-type]
        if name is None:
            await self._silently_ignore(interaction, "howto")
            return

        self.log.info(
            "/howto invoked by %s for fridge=%s target=%r",
            interaction.user,
            name,
            target_state,
        )
        await interaction.response.defer(thinking=True)

        conn = self.bot.settings.fridges[name]
        profile = self.bot.profiles[name]
        try:
            async with ProteoxService(conn, profile) as svc:
                plan = await svc.transition_plan(target_state)
        except RuntimeError as exc:
            self.log.error("service error for %s: %s", name, exc)
            await interaction.followup.send(f":warning: **{profile.display_name}** {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.log.exception("transition plan failed for %s", name)
            await interaction.followup.send(
                f":x: Failed to query **{profile.display_name}**: `{exc}`"
            )
            return

        if plan is None:
            self.log.info("%s is in LOCAL mode", name)
            await interaction.followup.send(
                f":warning: **{profile.display_name}** is in **LOCAL** mode. "
                "Please set it to **REMOTE** mode."
            )
            return

        await interaction.followup.send(
            embed=build_transition_plan_embed(profile, plan, target_state)
        )

    @howto.autocomplete("target_state")
    async def _howto_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.lower()
        return [
            app_commands.Choice(name=s, value=s)
            for s in sorted(RECOGNIZED_STATES.keys())
            if needle in s.lower()
        ][:25]


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(StatesCog(bot))

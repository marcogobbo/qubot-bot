"""`/uta` slash command group — HVAC plant (UTA) status report + hourly monitor.

Unlike `/report`, `/uta report` is available in **every** channel/thread: there
is no destination map and no channel gating. Each invocation downloads the
controller report via the legacy CGI, parses it, and renders a Discord embed.

`/uta monitor on` / `/uta monitor off` toggle an hourly watchdog that checks the
chiller water temperature and the absolute-filter ΔP. Each time a value is out of
range (or the report can't be reached) it posts a warning into the thread where
Elsa's daily report is sent. The monitor keeps running until `/uta monitor off`;
its on/off state is in memory only, so it starts off after a bot restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from qubot.core.logging_setup import get_logger
from qubot.services import destinations
from qubot.services.uta import fetch_uta_snapshot
from qubot.services.uta_report import build_uta_embed

if TYPE_CHECKING:
    from qubot.main import QuBot

# Fridge whose daily-report destination receives the monitor warnings.
MONITOR_FRIDGE = "elsa"

NETWORK_WARNING = (
    ":warning: **UTA** report is not reachable. Please check the network."
)


class UtaCog(commands.Cog):
    uta = app_commands.Group(name="uta", description="UTA (HVAC) plant.")
    monitor = app_commands.Group(
        name="monitor", parent=uta, description="Hourly UTA health monitor."
    )

    def __init__(self, bot: "QuBot") -> None:
        self.bot = bot
        self.log = get_logger("cog.uta")
        self._monitor_enabled = False
        self._monitor_loop = tasks.loop(hours=1)(self._check)

    async def cog_unload(self) -> None:
        if self._monitor_loop.is_running():
            self._monitor_loop.cancel()

    @uta.command(name="report", description="Show UTA (HVAC) status report.")
    async def report(self, interaction: discord.Interaction) -> None:
        self.log.info(
            "/uta report invoked by %s in channel=%s",
            interaction.user,
            interaction.channel_id,
        )
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

    @monitor.command(name="on", description="Enable the hourly UTA monitor.")
    async def monitor_on(self, interaction: discord.Interaction) -> None:
        self.log.info("/uta monitor on invoked by %s", interaction.user)
        if self.bot.settings.fridges.get(MONITOR_FRIDGE) is None:
            await interaction.response.send_message(
                f":x: **{MONITOR_FRIDGE.capitalize()}** has no configured "
                "destination — cannot enable the UTA monitor.",
                ephemeral=True,
            )
            return
        if self._monitor_enabled:
            await interaction.response.send_message(
                ":information_source: UTA monitor is already running.",
                ephemeral=True,
            )
            return
        self._monitor_enabled = True
        self._monitor_loop.start()
        await interaction.response.send_message(
            ":white_check_mark: UTA monitor **enabled** — checking hourly until "
            "`/uta monitor off`.",
            ephemeral=True,
        )

    @monitor.command(name="off", description="Disable the hourly UTA monitor.")
    async def monitor_off(self, interaction: discord.Interaction) -> None:
        self.log.info("/uta monitor off invoked by %s", interaction.user)
        if not self._monitor_enabled:
            await interaction.response.send_message(
                ":information_source: UTA monitor is not running.",
                ephemeral=True,
            )
            return
        self._monitor_enabled = False
        self._monitor_loop.cancel()
        await interaction.response.send_message(
            ":white_check_mark: UTA monitor **disabled**.",
            ephemeral=True,
        )

    async def _check(self) -> None:
        """One hourly monitor iteration. Keeps running regardless of result."""
        settings = self.bot.settings
        conn = settings.fridges.get(MONITOR_FRIDGE)
        if conn is None:
            self.log.warning(
                "UTA monitor: %s not configured — skipping check", MONITOR_FRIDGE
            )
            return

        try:
            snap = await fetch_uta_snapshot(settings)
        except Exception as exc:  # noqa: BLE001
            self.log.error("UTA monitor: fetch failed: %s", exc)
            await self._safe_send(conn, NETWORK_WARNING)
            return

        temp = snap.t_water_chiller
        dp = snap.dp_absolute
        if temp is None or dp is None:
            self.log.error(
                "UTA monitor: missing values (chiller=%s, abs_filter=%s)", temp, dp
            )
            await self._safe_send(conn, NETWORK_WARNING)
            return

        temp_max = settings.uta_monitor_chiller_temp_max
        dp_min = settings.uta_monitor_abs_filter_min
        faults: list[str] = []
        if temp >= temp_max:
            faults.append(
                f"Chiller water temperature is {temp:.1f} °C "
                f"(must be below {temp_max:.0f} °C)"
            )
        if dp <= dp_min:
            faults.append(
                f"Absolute filter ΔP is {dp:.1f} Pa "
                f"(must be above {dp_min:.0f} Pa)"
            )

        if not faults:
            self.log.info(
                "UTA monitor ok (chiller=%.1f °C, abs_filter=%.1f Pa)", temp, dp
            )
            return

        message = ":warning: **UTA** anomaly detected:\n" + "\n".join(
            f"- {f}" for f in faults
        )
        await self._safe_send(conn, message)

    async def _safe_send(self, conn, content: str) -> None:
        try:
            await destinations.send_text(self.bot, conn, content)
        except Exception:  # noqa: BLE001
            self.log.exception("UTA monitor: failed to send warning")


async def setup(bot: "QuBot") -> None:
    await bot.add_cog(UtaCog(bot))

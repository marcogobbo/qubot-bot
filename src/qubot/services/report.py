"""Build a Discord Embed from a fridge Snapshot + FridgeProfile."""

from __future__ import annotations

import discord

from qubot.core.fridge_config import FridgeProfile
from qubot.services.proteox import SensorReading, Snapshot


def _format_readings(readings: list[SensorReading]) -> str:
    """Format readings as a bullet list."""
    if not readings:
        return "_(none)_"
    lines = [f"- **{r.spec.label}**: {r.formatted()}" for r in readings]
    return "\n".join(lines)


def build_report_embed(profile: FridgeProfile, snap: Snapshot) -> discord.Embed:
    """Render the snapshot as a Discord embed personalized for the fridge."""
    embed = discord.Embed(
        title=f"📋 **Report - {profile.display_name}**",
        color=profile.color,
    )
    embed.add_field(name="**STATE**", value=f"{snap.status.title()}", inline=False)
    for label, readings in snap.sections():
        if not readings:
            continue
        embed.add_field(name=f"**{label.upper()}**", value=_format_readings(readings), inline=False)

    # Add resources if configured
    if profile.has_resources():
        resources_text = "\n".join(f"- **[{link.label}]({link.url})**" for link in profile.resources)
        embed.add_field(name="**RESOURCES**", value=resources_text, inline=False)

    return embed

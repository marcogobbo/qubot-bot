"""Embed builders for the recognized-state commands."""

from __future__ import annotations

from typing import Any

import discord

from qubot.core.fridge_config import FridgeProfile

COLOR_OK = 0x2ECC71
COLOR_WARN = 0xF1C40F
COLOR_FAIL = 0xE74C3C


def build_recognized_states_embed(profile: FridgeProfile, names: list[str]) -> discord.Embed:
    """Static list of every recognized state in the Proteox truth table."""
    embed = discord.Embed(
        title=f"📚 **Recognized states — {profile.display_name}**",
        color=profile.color,
    )
    embed.add_field(
        name=f"**{len(names)} states**",
        value="\n".join(f"- {n}" for n in names) or "_(none configured)_",
        inline=False,
    )
    return embed


def build_recognized_embed(
    profile: FridgeProfile, is_recognized: bool, states: list[str]
) -> discord.Embed:
    """Current recognized-state status."""
    if is_recognized and len(states) == 1:
        return discord.Embed(
            title=f"✅ **{profile.display_name}** is in recognized state",
            description=f"**{states[0]}**",
            color=COLOR_OK,
        )
    if is_recognized and len(states) > 1:
        embed = discord.Embed(
            title=f"⚠️ **{profile.display_name}** matches multiple recognized states",
            color=COLOR_WARN,
        )
        embed.add_field(
            name="**Matches**",
            value="\n".join(f"- {s}" for s in states),
            inline=False,
        )
        return embed
    return discord.Embed(
        title=f"❌ **{profile.display_name}** is **not** in a recognized state",
        color=COLOR_FAIL,
    )


def build_transition_plan_embed(
    profile: FridgeProfile,
    plan: dict[str, Any],
    requested_target: str | None,
) -> discord.Embed:
    """Suggested actions to reach a recognized state."""
    target_state = plan.get("target_state")
    matched = plan.get("matched", False)
    mismatch_count = plan.get("mismatch_count")
    actions = plan.get("actions", [])

    if target_state is None:
        return discord.Embed(
            title=f"❌ **{profile.display_name}** — No target state",
            description=(
                "Could not determine a target recognized state."
                if requested_target is None
                else f"Unknown recognized state: `{requested_target}`."
            ),
            color=COLOR_FAIL,
        )

    if matched:
        return discord.Embed(
            title=f"✅ **{profile.display_name}** is already in: {target_state}",
            color=COLOR_OK,
        )

    embed = discord.Embed(
        title=f"🛠️ **{profile.display_name}** — Transition suggestion",
        color=profile.color,
    )
    header = "**Closest target state**" if requested_target is None else "**Target state**"
    embed.add_field(name=header, value=target_state, inline=True)
    if mismatch_count is not None:
        embed.add_field(name="**Mismatches**", value=str(mismatch_count), inline=True)

    if actions:
        lines = []
        for action in actions:
            label = action.get("label") or action.get("condition", "Unknown")
            suggestion = action.get("suggestion", "No suggestion available.")
            prefix = "🟢" if action.get("target_value") is True else "🔴"
            lines.append(f"{prefix} **{label}** → {suggestion}")
        embed.add_field(name="**Suggested actions**", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="**Suggested actions**", value="_(none)_", inline=False)

    return embed

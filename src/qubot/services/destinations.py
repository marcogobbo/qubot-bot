"""Resolve a fridge's configured destination ID to a sendable Discord object."""

from __future__ import annotations

import discord

from qubot.core.logging_setup import get_logger
from qubot.core.settings import FridgeConnection

_log = get_logger("destinations")


async def resolve(bot: discord.Client, conn: FridgeConnection) -> discord.abc.Messageable:
    """Return the Channel or Thread for `conn`. Raises if not found."""
    target_id = conn.destination_id
    if conn.destination_type == "channel":
        channel = bot.get_channel(target_id) or await bot.fetch_channel(target_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise RuntimeError(f"destination {target_id} is not a text channel")
        return channel

    # thread
    thread = bot.get_channel(target_id)
    if thread is None:
        thread = await bot.fetch_channel(target_id)
    if not isinstance(thread, discord.Thread):
        raise RuntimeError(f"destination {target_id} is not a thread")
    return thread


async def send_embed(
    bot: discord.Client, conn: FridgeConnection, embed: discord.Embed
) -> None:
    """Send an embed to the configured destination."""
    target = await resolve(bot, conn)
    await target.send(embed=embed)
    _log.info("sent embed to %s id=%s", conn.destination_type, conn.destination_id)

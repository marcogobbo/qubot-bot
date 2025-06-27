"""Announcements ABC class cog for QuBot."""

from abc import ABC, ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from discord import Embed, TextChannel
from discord.ext.commands import Bot, Cog
from discord.ext.commands.cog import CogMeta
from discord.ext.tasks import Loop, loop
from discord.ui import View

from utils import load_json

ZONE_INFO: ZoneInfo = ZoneInfo("Europe/Rome")
COLOR_BLUE: int = 0x4285F4


class CombinedMeta(CogMeta, ABCMeta):
    """Combined metaclass for abstract cogs."""


class Announcements(Cog, ABC, metaclass=CombinedMeta):
    """Abstract base class for announcement-related Discord cogs."""

    def __init__(self, bot: Bot, channel_id: int, messages_path: str) -> None:
        self.bot: Bot = bot
        self.channel_id: int = channel_id
        self.messages: dict[str, Any] = load_json(messages_path)
        self.message_key: str = self.__class__.__name__

        self.announcement: Loop = loop(minutes=1)(self._announce)
        self.announcement.before_loop(self._before_loop)

        if not self.announcement.is_running():
            self.announcement.start()

    async def send_announcement(
        self,
        channel_id: int,
        title: str,
        description: str,
        color: int = COLOR_BLUE,
        add_field: Optional[dict[str, str]] = None,
        view: Optional[View] = None,
    ) -> None:
        """Send an embedded announcement message to a text channel."""
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, TextChannel):
            embed = Embed(title=title, description=description, color=color)

            if (
                isinstance(add_field, dict)
                and "name" in add_field
                and "value" in add_field
            ):
                embed.add_field(
                    name=add_field["name"],
                    value=add_field["value"],
                    inline=add_field.get("inline", False),
                )

            await channel.send(embed=embed, view=view)

    @abstractmethod
    def prepare_announcement(
        self, content: dict[str, Any]
    ) -> tuple[dict[str, int], dict[str, str], Optional[View]]:
        """Prepare announcement data and optional view."""

    async def _announce(self) -> None:
        """Task loop function that checks current time and sends announcements."""
        now: datetime = datetime.now(ZONE_INFO)

        for content in self.messages[self.message_key]["content"]:
            time, content_formatted, view = self.prepare_announcement(content)

            if (
                now.weekday() == time["day"]
                and now.hour == time["hour"]
                and now.minute == time["minute"]
            ):
                await self.send_announcement(
                    channel_id=self.channel_id,
                    title=content_formatted["title"],
                    description=content_formatted["description"],
                    add_field=content_formatted.get("add_field"),
                    view=view,
                )

    async def _before_loop(self) -> None:
        """Wait until the bot is ready before starting the announcement loop."""
        await self.bot.wait_until_ready()

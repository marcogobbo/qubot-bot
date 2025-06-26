"""General class cog for QuBot."""

from os import getenv
from typing import Any, Dict, Optional, Tuple

from discord.ext.commands import Bot
from discord.ui import View
from dotenv import load_dotenv

from .announcements import Announcements


class General(Announcements):
    """Cog for scheduling and sending general announcements."""

    def __init__(
        self,
        bot: Bot,
        channel_id: int,
        messages_path: str,
        data: Dict[str, str],
    ) -> None:
        """Initialize the General cog."""
        self.data: Dict[str, str] = data
        super().__init__(bot, channel_id, messages_path)

    def prepare_announcement(
        self, content: Dict[str, Any]
    ) -> Tuple[Dict[str, int], Dict[str, str], Optional[View]]:
        """Format message content by filling placeholders with data."""
        return (
            content["time"],
            {
                "title": content["title"],
                "description": content["description"].format(**self.data),
            },
            None,
        )


async def setup(bot: Bot) -> None:
    """Load environment variables and add the General cog to the bot."""
    load_dotenv()

    channel_id: int = int(getenv("GENERAL_CHANNEL"))
    messages_path: str = getenv("MESSAGES_JSON")
    data: Dict[str, str] = {
        "link": getenv("MONDAY_MEETING_ZOOM_URL"),
        "minutes": getenv("MONDAY_MEETING_MINUTES_URL"),
    }
    await bot.add_cog(
        General(bot=bot, channel_id=channel_id, messages_path=messages_path, data=data)
    )

"""JournalClub class cog for QuBot."""

from os import getenv
from typing import Any, Dict, Optional, Tuple

from discord.ext.commands import Bot
from discord.ui import View
from dotenv import load_dotenv

from utils import load_data, parse_data

from .announcements import Announcements


class JournalClub(Announcements):
    """Cog for scheduling and sending journal club announcements."""

    def __init__(
        self,
        bot: Bot,
        channel_id: int,
        messages_path: str,
        service_account_path: str,
        spreadsheet_url: str,
    ) -> None:
        """Initialize the JournalClub cog."""
        self.service_account_path: str = service_account_path
        self.spreadsheet_url: str = spreadsheet_url
        super().__init__(bot, channel_id, messages_path)

    def prepare_announcement(
        self, content: Dict[str, Any]
    ) -> Tuple[Dict[str, int], Dict[str, str], Optional[View]]:
        """Format message content by filling placeholders with data."""
        data: Dict[str, str] = parse_data(
            load_data(self.service_account_path, self.spreadsheet_url)
        )
        return (
            content["time"],
            {
                "title": content["title"],
                "description": content["description"].format(**data),
                "add_field": {
                    "name": content["add_field"]["name"],
                    "value": content["add_field"]["value"].format(**data),
                },
            },
            None,
        )


async def setup(bot: Bot) -> None:
    """Load environment variables and add the JournalClub cog to the bot."""
    load_dotenv()

    journal_club_channel_id: int = int(getenv("JOURNAL_CLUB_CHANNEL"))
    messages_path: str = getenv("MESSAGES_JSON")
    service_account_path: str = getenv("SERVICE_ACCOUNT_JSON")
    spreadsheet_url: str = getenv("JOURNAL_CLUB_SPREADSHEET_URL")

    await bot.add_cog(
        JournalClub(
            bot=bot,
            channel_id=journal_club_channel_id,
            messages_path=messages_path,
            service_account_path=service_account_path,
            spreadsheet_url=spreadsheet_url,
        )
    )

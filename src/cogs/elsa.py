"""Elsa class cog for QuBot."""

from os import getenv
from typing import Any, Dict, Optional, Tuple

from discord import ButtonStyle, Interaction
from discord.ext.commands import Bot
from discord.ui import Button, View
from dotenv import load_dotenv

from .announcements import Announcements


class Elsa(Announcements):
    """Cog for scheduling and sending announcements about Elsa."""

    def prepare_announcement(
        self, content: Dict[str, Any]
    ) -> Tuple[Dict[str, int], Dict[str, str], Optional[View]]:
        """Format message content by filling placeholders with data and adding buttons."""
        return (
            content["time"],
            {
                "title": content["title"],
                "description": content["description"],
            },
            RefillButton(content["button"]) if "button" in content else None,
        )


class RefillButton(View):
    """Custom Discord UI View for the refill button."""

    def __init__(self, button_info: Dict[str, Any]) -> None:
        """Initialize the refill button view."""
        super().__init__()
        self.button_clicked: bool = False
        self.button_info: Dict[str, Any] = button_info

        button = Button(
            label=button_info["label"],
            style=ButtonStyle.green,
        )
        button.callback = self.refill_button
        self.add_item(button)

    async def refill_button(self, interaction: Interaction) -> None:
        """Callback for the refill button."""
        self.button_clicked = True
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            self.button_info["response"].format(user=interaction.user.mention)
        )


async def setup(bot: Bot) -> None:
    """Load environment variables and add Elsa cog to the bot."""
    load_dotenv()
    channel_id: int = int(getenv("ELSA_CHANNEL"))
    messages_path: str = getenv("MESSAGES_JSON")
    await bot.add_cog(Elsa(bot=bot, channel_id=channel_id, messages_path=messages_path))

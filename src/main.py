"""QuBot setup: loads cogs and runs the bot."""

from os import getenv

from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN: str = getenv("BOT_TOKEN")
intents: Intents = Intents.all()


class QuBot(commands.Bot):
    """QuBot main class."""

    async def setup_hook(self) -> None:
        """Load cogs on startup."""
        await self.load_extension("cogs.elsa")
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.journal_club")


qubot: QuBot = QuBot(command_prefix="/", intents=intents)


@qubot.event
async def on_ready() -> None:
    """Triggered when the bot connects."""
    print(f"QuBot connected as {qubot.user}")


if TOKEN:
    qubot.run(TOKEN)
else:
    raise EnvironmentError("BOT_TOKEN not found in the .env file.")

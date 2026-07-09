"""QuBot entrypoint."""

from __future__ import annotations

# Load .env into os.environ FIRST, so the qtics module (which reads
# WAMP_USER / WAMP_USER_SECRET / WAMP_REALM / WAMP_ROUTER_URL at import time
# via os.getenv) sees them before any cog imports it transitively.
from dotenv import load_dotenv

load_dotenv()

import asyncio  # noqa: E402
import ssl  # noqa: E402
from pathlib import Path  # noqa: E402

import aiohttp  # noqa: E402
import certifi  # noqa: E402
import discord  # noqa: E402
from discord.ext import commands  # noqa: E402

from qubot.core.fridge_config import FridgeProfile, load_all_profiles  # noqa: E402
from qubot.core.logging_setup import get_logger, setup_logging  # noqa: E402
from qubot.core.settings import FRIDGE_NAMES, Settings  # noqa: E402

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
COGS = [
    "qubot.cogs.reports",
    "qubot.cogs.scheduler",
    "qubot.cogs.monday",
    "qubot.cogs.uta",
    "qubot.cogs.states",
    "qubot.cogs.help",
]


class QuBot(commands.Bot):
    def __init__(
        self,
        settings: Settings,
        profiles: dict[str, FridgeProfile],
        connector: aiohttp.BaseConnector | None = None,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents, connector=connector)
        self.settings = settings
        self.profiles = profiles
        self.log = get_logger("bot")
        self._globals_cleared = False

    async def setup_hook(self) -> None:
        for cog in COGS:
            await self.load_extension(cog)
            self.log.info("loaded cog %s", cog)
        # No global sync: commands are registered per-guild in on_ready /
        # on_guild_join for instant availability. A global sync here would
        # duplicate every command (once globally, once per-guild) in the
        # slash picker.

    async def on_ready(self) -> None:
        self.log.info("logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")
        self.log.info("connected to %d guild(s)", len(self.guilds))
        # Push commands to every currently connected guild for instant availability.
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.log.info("synced commands to guild %s (%s)", guild.name, guild.id)

        # One-time cleanup: deregister any leftover global registrations from
        # the previous "global + per-guild" sync model so users don't see each
        # command twice. Uses the raw HTTP API so the in-memory global tree
        # stays populated (on_guild_join still needs it for copy_global_to).
        if not self._globals_cleared and self.application_id is not None:
            await self.http.bulk_upsert_global_commands(self.application_id, [])
            self._globals_cleared = True
            self.log.info("cleared stale global command registrations")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        # Sync immediately when the bot is added to a new server.
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.log.info("joined new guild %s (%s) — commands synced", guild.name, guild.id)


async def _main() -> None:
    settings = Settings.load()
    setup_logging(settings.log_level)
    log = get_logger("startup")
    log.info("starting QuBot")

    profiles = load_all_profiles(list(FRIDGE_NAMES), CONFIG_DIR)
    log.info("loaded profiles for: %s", ", ".join(profiles.keys()))

    # Use certifi's CA bundle so the bot works on macOS without running
    # "Install Certificates.command" and in other environments with missing
    # system CA stores (corporate proxies, minimal Docker images, etc.).
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    bot = QuBot(settings, profiles, connector=connector)
    async with bot:
        await bot.start(settings.discord_token)


def run() -> None:
    """Console-script entrypoint (see pyproject.toml [tool.poetry.scripts])."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()

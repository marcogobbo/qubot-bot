"""QuBot General Cog Module.

This module implements the General cog for the QuBot Discord bot, providing
core functionality including scheduled meeting reminders and general purpose
commands. The cog integrates with APScheduler to handle automated notifications
and uses Discord embeds.

Example:
    Load the General cog in the main bot:

        await bot.load_extension("cogs.general")

    The cog will automatically:
    - Start the scheduler for recurring tasks
    - Send Monday meeting reminders at configured times
    - Handle proper cleanup when unloaded

Note:
    - Requires GENERAL_CHANNEL_ID to send messages in the #general channel
    - Requires MONDAY_MEETING_ZOOM_URL and MONDAY_MEETING_MINUTES_URL
    - Configuration timing is loaded from config.json file
    - Uses bot's default timezone (Europe/Rome)
"""

import logging
from dataclasses import dataclass
from os import getenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import Embed
from discord.ext.commands import Bot, Cog
from dotenv import load_dotenv

from utils.constants import COLOR_BLUE, ZONE_INFO
from utils.scheduler import ScheduledTime
from utils.utils import load_json

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

# Load environment variables from .env file
load_dotenv()

# Discord channel ID where general announcements are sent
GENERAL_CHANNEL_ID: int = int(getenv("GENERAL_CHANNEL_ID"))
"""int: #general channel ID for general announcements and meeting reminders.

This channel is used for automated notifications such as Monday meeting
reminders. Must be set in the .env file.

Raises:
    ValueError: If GENERAL_CHANNEL_ID is not set or invalid.
"""

# Meeting URLs from the .env file for security
MONDAY_MEETING_ZOOM_URL: str = getenv("MONDAY_MEETING_ZOOM_URL")
"""str: Zoom URL for Monday meetings.

Used in meeting reminder embeds to provide direct access to virtual meetings.
Should be set in the .env file to avoid hardcoding sensitive URLs.
"""

MONDAY_MEETING_MINUTES_URL: str = getenv("MONDAY_MEETING_MINUTES_URL")
"""str: URL for Monday meeting minutes documentation.

Provides a link to the shared document where meeting minutes are recorded.
Should be set in the .env file for easy configuration updates.
"""

# Load bot configuration from JSON file
config: dict[str, dict[str, dict[str, int]]] = load_json("config.json")
"""dict: Scheduling loaded from config.json file.

Contains scheduling information.
"""

# =============================================================================
# CONFIGURATION DATACLASSES
# =============================================================================


@dataclass
class GeneralConfig:
    """Configuration dataclass for the General cog.

    Holds all scheduled task timing for the General cog functionality.

    Attributes:
        monday_meeting (ScheduledTime): Configuration for Monday meeting reminders.

    Example:
        Create configuration from loaded JSON:

            config_data = load_json("config.json")
            general_config = GeneralConfig(
                monday_meeting=ScheduledTime(
                    day=config_data["general"]["monday_meeting"].get("day"),
                    hour=config_data["general"]["monday_meeting"]["hour"],
                    minute=config_data["general"]["monday_meeting"]["minute"]
                )
            )
    """

    monday_meeting: ScheduledTime


# Create global configuration instance from loaded JSON
general_config = GeneralConfig(
    monday_meeting=ScheduledTime(
        day=config["general"]["monday_meeting"].get("day"),
        hour=config["general"]["monday_meeting"]["hour"],
        minute=config["general"]["monday_meeting"]["minute"],
    )
)
"""GeneralConfig: Global configuration instance for the General cog.

Pre-configured with values from config.json, ready to use throughout the cog.
"""

# =============================================================================
# GENERAL COG CLASS
# =============================================================================


class General(Cog):
    """General cog for QuBot.

    This cog provides core bot functionality including automated meeting reminders,
    general utility commands, and scheduled task management. It uses APScheduler
    for reliable task execution and integrates with Discord's embed system.

    Attributes:
        bot (Bot): Reference to the main bot instance.
        scheduler (AsyncIOScheduler): APScheduler instance for managing scheduled tasks.

    Example:
        The cog is typically loaded automatically by the bot:

            # In main bot setup
            await bot.load_extension("cogs.general")
    """

    def __init__(self, bot: Bot) -> None:
        """Initialize the General cog with bot reference and scheduler.

        Sets up the cog with a reference to the main bot instance and creates
        an APScheduler instance configured with the bot's timezone. Automatically
        configures and starts the scheduler for recurring tasks.

        Args:
            bot (Bot): The main Discord bot instance.

        Note:
            - Scheduler is configured with bot's default timezone
            - Automatic setup of scheduled tasks occurs during initialization
            - Scheduler starts immediately after setup
        """
        self.bot: Bot = bot
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone=ZONE_INFO)
        self._setup_scheduler()

    async def cog_load(self) -> None:
        """Handle cog loading lifecycle event.

        Called automatically when the cog is loaded by the bot. Provides
        logging confirmation that the cog has been successfully initialized.

        Note:
            - Logs cog loading for debugging and monitoring
            - Uses the cog's name from Discord.py's internal naming
        """
        logging.info("> %s cog loaded", self.__cog_name__)

    async def cog_unload(self) -> None:
        """Handle cog unloading lifecycle event.

        Called automatically when the cog is unloaded or the bot shuts down.
        Provides logging confirmation and opportunity for cleanup operations.

        Note:
            - Logs cog unloading for debugging and monitoring
            - Scheduler cleanup is handled automatically by APScheduler
        """
        logging.info("> %s cog unloaded", self.__cog_name__)

    def _setup_scheduler(self) -> None:
        """Configure and start the APScheduler with all scheduled tasks.

        Sets up all recurring tasks that the General cog needs to execute,
        including meeting reminders and other automated notifications.
        Starts the scheduler after configuration is complete.

        Note:
            - Private method called during cog initialization
            - Adds all scheduled jobs before starting scheduler
            - Uses configuration from general_config for task timing
        """
        self.scheduler.add_job(
            self.monday_meeting_reminder,
            general_config.monday_meeting.to_cron_trigger(),
            id="monday_meeting_reminder",
        )
        self.scheduler.start()

    # =============================================================================
    # SCHEDULED TASKS
    # =============================================================================

    async def monday_meeting_reminder(self) -> None:
        """Send automated Monday meeting reminder to the general channel.

        Scheduled task that sends a formatted embed reminder about the upcoming
        Monday meeting. Includes links to Zoom meeting and minutes document.
        Handles channel lookup failures gracefully with appropriate logging.

        Raises:
            discord.HTTPException: If sending the message fails.
            discord.Forbidden: If bot lacks permissions to send messages.

        Note:
            - Waits for bot to be ready before attempting to send messages
            - Logs successful reminder sending for monitoring
            - Handles missing channel gracefully with warning log
        """
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if channel is None:
            logging.warning("General channel not found.")
            return

        embed = self.build_embed()
        await channel.send(embed=embed)
        logging.info("Sent scheduled Monday meeting reminder.")

    @staticmethod
    def build_embed() -> Embed:
        """Build a formatted Discord embed for Monday meeting reminders.

        Creates an embed message with meeting information, including
        Zoom link and minutes document link. Uses consistent branding
        colors and emoji for visual appeal.

        Returns:
            Embed: A formatted Discord embed ready to send.

        Example:
            Use in custom commands or scheduled tasks:

                embed = General.build_embed()
                await channel.send(embed=embed)

        Note:
            - Static method can be used without class instance
            - Uses global environment variables for URLs
        """
        embed = Embed(
            title="📢 **Monday Meeting**",
            description=(
                f"Good morning everyone! ☀️ The **Monday Meeting** starts in 15 minutes! ☕\n"
                f"Can't make it in person? Join on [**Zoom**]({MONDAY_MEETING_ZOOM_URL})! "
                f"And don't forget to take the [**minutes**]({MONDAY_MEETING_MINUTES_URL})! 📝"
            ),
            color=COLOR_BLUE,
        )
        return embed


# =============================================================================
# COG SETUP FUNCTION
# =============================================================================


async def setup(bot: Bot) -> None:
    """Set up the General cog for the bot.

    Entry point function called by Discord.py when loading this cog extension.
    Creates and adds the General cog instance to the bot.

    Args:
        bot (Bot): The Discord bot instance to add the cog to.

    Example:
        Load this cog in the main bot setup:

            await bot.load_extension("cogs.general")

    Note:
        - Required function name and signature for Discord.py cog loading
        - Automatically called when the extension is loaded
        - Creates new General instance with bot reference
    """
    await bot.add_cog(General(bot=bot))

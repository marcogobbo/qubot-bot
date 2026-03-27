"""QuBot Discord Bot.

This file initializes and configures the QuBot Discord bot with comprehensive logging,
loads the necessary cogs and establishes the bot connection.
The bot uses slash commands and requires all Discord intents for full functionality.

Example:
    Run the bot by ensuring DISCORD_TOKEN is set in your .env file:

        $ python main.py

Note:
    - Requires logs/ directory to exist for file logging
    - Requires .env file with DISCORD_TOKEN variable
    - Bot needs all intents enabled in Discord Developer Portal
"""

import logging
from logging.handlers import RotatingFileHandler
from os import getenv, listdir

from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Date format for log messages (DD-MM-YYYY HH:MM:SS format)
DT_FMT = "%d-%m-%Y %H:%M:%S"

# Create a consistent formatter for both file and console logging
# Uses bracket notation for structured log format
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", DT_FMT, style="{"
)

# Configure rotating file handler to prevent log files from growing indefinitely
# Logs are stored in logs/qubot.log with automatic rotation at 32MB
# Keeps 5 backup files (total ~160MB max disk usage for logs)
file_handler = RotatingFileHandler(
    filename="logs/qubot.log",
    encoding="utf-8",
    maxBytes=32 * 1024 * 1024,  # 32MB per file
    backupCount=5,  # Keep 5 backup files
)
file_handler.setFormatter(formatter)

# Configure console handler for real-time log monitoring during development
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configure root logger to capture all log messages at INFO level and above
# This ensures we get comprehensive logging from both our bot and discord.py
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Reduce discord.py HTTP request logging verbosity to avoid spam
# Only log INFO and above for Discord HTTP requests
logging.getLogger("discord.http").setLevel(logging.INFO)

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

# Load environment variables from .env file for secure token storage
load_dotenv()

# Retrieve Discord bot token from environment variables
# This token should never be hardcoded or committed to version control
TOKEN: str = getenv("DISCORD_TOKEN")

# Configure bot intents to enable all Discord features
# Note: Some intents require approval from Discord for verified bots
intents: Intents = Intents.all()

# =============================================================================
# BOT CLASS DEFINITION
# =============================================================================


class QuBot(commands.Bot):
    """The main QuBot class extending discord.py's Bot class.

    This bot uses slash commands (/) as the command prefix and has access to all
    Discord intents for comprehensive server interaction capabilities.

    """

    async def setup_hook(self) -> None:
        """Load and initialize all bot cogs during startup.

        This method is called automatically when the bot starts up, before
        the bot connects to Discord. It loads all necessary cogs for bot functionality.

        Raises:
            commands.ExtensionError: If any cog fails to load properly.
            commands.ExtensionNotFound: If a cog file cannot be found.
            commands.ExtensionFailed: If a cog fails during initialization.

        Note:
            Cogs loaded:
            - general: generic announcements for the #General channel
            - elsa: notifications about the dilution refrigerator Elsa
            - journal_club: reminders about the journal club sessions
        """
        for filename in listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")


# =============================================================================
# BOT INITIALIZATION
# =============================================================================

# Create the main bot instance with slash command support
qubot: QuBot = QuBot(command_prefix="/", intents=intents)

# =============================================================================
# EVENT HANDLERS
# =============================================================================


@qubot.event
async def on_ready() -> None:
    """Event handler triggered when the bot successfully connects to Discord.

    This function is called once the bot has established a connection with
    Discord and is ready to receive events and commands. It provides
    confirmation that the bot is online and operational.

    Note:
        Prints the bot's username and discriminator for identification purposes.
        This output appears in both console and log files.
    """
    print(f"QuBot connected as {qubot.user}")


# =============================================================================
# BOT STARTUP
# =============================================================================

# Start the bot if a valid token is provided
if TOKEN:
    # Run the bot with the Discord token
    # This call blocks until the bot is shut down
    qubot.run(TOKEN)
else:
    # Raise an error if the Discord token is missing or invalid
    # This prevents the bot from starting without proper authentication
    raise EnvironmentError(
        "DISCORD_TOKEN not found in the .env file. "
        "Please ensure your .env file contains a valid DISCORD_TOKEN."
    )

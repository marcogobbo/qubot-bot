"""QuBot Journal Club Cog Module.

This module implements the Journal Club cog for the QuBot Discord bot, providing
functionality for announcing journal club meetings. The cog integrates with Google
Sheets to dynamically load meeting information and uses APScheduler to send automated
reminders at specific times.

The module handles both today and weekly reminders for journal club sessions,
parsing meeting data from Google Sheets including date, speaker, paper title and DOI,
meeting room, and Zoom link.

Example:
    Load the Journal Club cog in the main bot:

        await bot.load_extension("cogs.journal_club")

    The cog will automatically:
    - Schedule daily and weekly reminders based on configuration
    - Parse upcoming meetings from Google Sheets
    - Send formatted embed notifications to the journal club channel
    - Provide manual reminder commands for immediate notifications

Note:
    - Requires JOURNAL_CLUB_CHANNEL_ID to send messages in the #journal-club channel
    - Requires JOURNAL_CLUB_SPREADSHEET_URL for Google Sheets integration
    - Requires SERVICE_ACCOUNT_JSON for Google Sheets authentication
    - Configuration timing is loaded from config.json file
    - Uses pandas for efficient data processing and datetime handling (tmp)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from os import getenv
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import Embed
from discord.ext.commands import Bot, Cog, Context, command
from dotenv import load_dotenv
from gspread import Client, Spreadsheet, Worksheet, service_account
from pandas import DataFrame, to_datetime

from utils.constants import COLOR_BLUE, ZONE_INFO
from utils.scheduler import ScheduledTime
from utils.utils import load_json

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

# Load environment variables from .env file
load_dotenv()

# Discord channel ID for journal club announcements
JOURNAL_CLUB_CHANNEL_ID: int = int(getenv("JOURNAL_CLUB_CHANNEL_ID"))
"""int: #journal-club channel ID for announcements and reminders.

This channel is used for automated notifications about upcoming journal club
meetings. Must be set in the .env file.

Raises:
    ValueError: If JOURNAL_CLUB_CHANNEL_ID is not set or invalid.
"""

# Google Sheets URL containing journal club data
JOURNAL_CLUB_SPREADSHEET_URL: str = getenv("JOURNAL_CLUB_SPREADSHEET_URL")
"""str: URL of the Google Sheets file containing journal club data.

The spreadsheet should contain columns for date, time, speaker, paper title and
DOI, room, and Zoom link information. Must be accessible by the service account.
"""

# Path to Google Sheets service account JSON file
SERVICE_ACCOUNT_JSON: str = getenv("SERVICE_ACCOUNT_JSON")
"""str: Path to the Google Sheets service account JSON credentials file.

Used for authenticating with Google Sheets API to read journal club data.
The service account must have read access to the target spreadsheet.
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
class JournalClubConfig:
    """Configuration dataclass for the Journal Club cog.

    Holds timing configuration for different journal club reminders, allowing
    flexible scheduling of notifications.

    Attributes:
        today_reminder (ScheduledTime): Configuration for same-day reminders.
        weekly_reminder (ScheduledTime): Configuration for weekly advance reminders.

    Example:
        Create configuration from loaded JSON:

            config_data = load_json("config.json")
            journal_config = JournalClubConfig(
                today_reminder=ScheduledTime(day=1, hour=14, minute=30),
                weekly_reminder=ScheduledTime(day=4, hour=10, minute=0)
            )
    """

    today_reminder: ScheduledTime
    weekly_reminder: ScheduledTime


# Create global configuration instance from loaded JSON
journal_club_config = JournalClubConfig(
    today_reminder=ScheduledTime(
        day=config["journal_club"]["today_reminder"].get("day"),
        hour=config["journal_club"]["today_reminder"]["hour"],
        minute=config["journal_club"]["today_reminder"]["minute"],
    ),
    weekly_reminder=ScheduledTime(
        day=config["journal_club"]["weekly_reminder"].get("day"),
        hour=config["journal_club"]["weekly_reminder"]["hour"],
        minute=config["journal_club"]["weekly_reminder"]["minute"],
    ),
)
"""JournalClubConfig: Global configuration instance for the Journal Club cog.

Pre-configured with values from config.json, ready to use throughout the cog.
"""

# =============================================================================
# JOURNAL CLUB COG CLASS
# =============================================================================


class JournalClub(Cog):
    """Journal Club cog for managing paper discussion sessions.

    This cog provides manual and automated reminders for journal club meetings by
    integrating with Google Sheets to fetch meeting information and using APScheduler
    for reliable notification delivery. It supports both same-day and weekly reminders
    with different messaging contexts.

    Attributes:
        bot (Bot): Reference to the main bot instance.
        scheduler (AsyncIOScheduler): APScheduler instance for managing scheduled tasks.

    Example:
        The cog is typically loaded automatically by the bot:

            # In main bot setup
            await bot.load_extension("cogs.journal_club")
    """

    def __init__(self, bot: Bot) -> None:
        """Initialize the Journal Club cog with bot reference and scheduler.

        Sets up the cog with a reference to the main bot instance and creates
        an APScheduler instance configured with the bot's timezone. Automatically
        configures and starts the scheduler for recurring reminder tasks.

        Args:
            bot (Bot): The main Discord bot instance.

        Note:
            - Scheduler is configured with bot's default timezone
            - Automatic setup of scheduled tasks occurs during initialization
            - Both today and weekly reminders are scheduled automatically
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

        Sets up both today and weekly reminder tasks that the Journal Club cog
        needs to execute. Configures job IDs for proper task management and
        starts the scheduler after all jobs are added.

        Note:
            - Private method called during cog initialization
            - Adds all scheduled jobs before starting scheduler
            - Uses configuration from journal_club_config for task timing
        """
        self.scheduler.add_job(
            self.today_reminder,
            journal_club_config.today_reminder.to_cron_trigger(),
            id="today_reminder",
        )
        self.scheduler.add_job(
            self.weekly_reminder,
            journal_club_config.weekly_reminder.to_cron_trigger(),
            id="weekly_reminder",
        )
        self.scheduler.start()

    # =============================================================================
    # COMMANDS
    # =============================================================================

    @command(name="reminder")
    async def reminder(self, ctx: Context) -> None:
        """Command to trigger a journal club reminder.

        Allows users to manually request a journal club reminder in the channel.
        This provides flexibility for immediate notifications outside of the scheduled
        reminder times.

        Usage:
            /reminder

        Args:
            ctx (Context): Discord command context containing message and channel info.

        Note:
            - Only works when called from the #journal-club channel
            - Triggers the weekly reminder format
            - No response if called from wrong channel (silent fail)
        """
        if ctx.channel.id == JOURNAL_CLUB_CHANNEL_ID:
            await self.weekly_reminder()

    # =============================================================================
    # SCHEDULED TASKS
    # =============================================================================

    async def today_reminder(self) -> None:
        """Send automated same-day journal club reminder (30 minutes before).

        Scheduled task that sends a formatted embed reminder about the journal club
        meeting happening today.

        Note:
            - Waits for bot to be ready before attempting to send messages
            - Loads data from Google Sheets for each reminder
            - Logs successful reminder sending for monitoring
        """
        await self.bot.wait_until_ready()
        channel: int
        data: dict
        channel, data = self.reminder_template()
        if channel is None or data is None:
            return

        data["time"]: str = "In 30 minutes"
        data["footer"]: str = "Make sure to at least check out the abstract! 👀"
        embed: Embed = self.build_embed(data)
        await channel.send(embed=embed)
        logging.info("Sent scheduled today reminder.")

    async def weekly_reminder(self) -> None:
        """Send automated weekly journal club reminder (advance notice).

        Scheduled task that sends a formatted embed reminder about the upcoming
        journal club meeting.

        Note:
            - Waits for bot to be ready before attempting to send messages
            - Loads data from Google Sheets for each reminder
            - Logs successful reminder sending for monitoring
        """
        await self.bot.wait_until_ready()
        channel: int
        data: dict
        channel, data = self.reminder_template()
        if channel is None or data is None:
            return

        data["time"]: str = "Next Tuesday"
        data["footer"]: str = "Don't forget to read the paper beforehand! 🤓"
        embed = self.build_embed(data)
        await channel.send(embed=embed)
        logging.info("Sent scheduled weekly reminder.")

    def reminder_template(self) -> tuple[Any, dict[str, str]] | tuple[None, None]:
        """Generate reminder template with channel reference and meeting data.

        Common method used by both reminder types to fetch the Discord channel
        and load/parse the latest meeting information from Google Sheets.

        Returns:
            tuple: A tuple containing (channel, data) where channel is the Discord
                  channel object and data is a dictionary with meeting information,
                  or (None, None) if channel is not found.

        Note:
            - Handles channel lookup failures gracefully
            - Loads data from Google Sheets on each call
            - Parses data to find the next upcoming meeting
        """
        channel: int = self.bot.get_channel(JOURNAL_CLUB_CHANNEL_ID)
        if channel is None:
            logging.warning("Journal Club channel not found.")
            return None, None

        data: dict[str, str] = self.parse_data(
            self.load_data(SERVICE_ACCOUNT_JSON, JOURNAL_CLUB_SPREADSHEET_URL)
        )
        return channel, data

    @staticmethod
    def build_embed(data: dict[str, str]) -> Embed:
        """Build a formatted Discord embed for journal club reminders.

        Creates an embed message with meeting information including speaker,
        paper title and DOI, meeting location, Zoom link, and spreadsheet URL.

        Args:
            data (dict[str, str]): Dictionary containing meeting information with keys:
                - time: When the meeting occurs (e.g., "In 30 minutes", "Next Tuesday")
                - speaker: Name of the person presenting
                - spreadsheet: URL to the full schedule spreadsheet
                - room: Physical meeting room location
                - link: Zoom meeting URL
                - paper: Title of the paper being discussed
                - doi: DOI link to the paper
                - footer: Additional message for the embed

        Returns:
            Embed: A formatted Discord embed ready to send.

        Example:
            Create embed from parsed meeting data:

                meeting_data = self.parse_data(df)
                meeting_data["time"] = "Next Tuesday"
                meeting_data["footer"] = "Don't forget to read!"
                embed = self.build_embed(meeting_data)
                await channel.send(embed=embed)

        Note:
            - Static method can be used without class instance
            - Includes clickable links for paper and meeting access
            - Formatted for optimal readability on mobile and desktop
        """
        embed = Embed(
            title="📢 **Quantum Journal Club**",
            description=(
                f"{data['time']}, **{data['speaker']}** will host the "
                f"[**QJC**]({data['spreadsheet']}) in room **{data['room']}** "
                f"and on [**Zoom**]({data['link']})."
            ),
            color=COLOR_BLUE,
        )
        embed.add_field(
            name="**Paper**",
            value=f"[{data['paper']}]({data['doi']})\n\n{data['footer']}",
        )
        return embed

    @staticmethod
    def load_data(
        service_account_path: str, spreadsheet_url: str, sheet: int | str = 0
    ) -> DataFrame:
        """Load data from a Google Sheet into a pandas DataFrame.

        Authenticates with Google Sheets API using a service account and loads
        the specified worksheet data into a DataFrame for processing. Adds
        the spreadsheet URL as a column for reference in embed links.

        Args:
            service_account_path (str): Path to the Google service account JSON file.
            spreadsheet_url (str): URL of the Google Sheets document to load.
            sheet (int | str, optional): Worksheet to load, either by index (0-based)
                                       or by name. Defaults to 0 (first sheet).

        Returns:
            DataFrame: Pandas DataFrame containing all worksheet data with an
                      additional 'spreadsheet' column containing the source URL.

        Raises:
            gspread.exceptions.APIError: If Google Sheets API request fails.
            gspread.exceptions.SpreadsheetNotFound: If spreadsheet URL is invalid.
            gspread.exceptions.WorksheetNotFound: If specified sheet doesn't exist.
            FileNotFoundError: If service account JSON file is not found.

        Example:
            Load journal club schedule data:

                df = JournalClub.load_data(
                    "service_account.json",
                    "https://docs.google.com/spreadsheets/d/...",
                    "Sheet1"  # Load by sheet name
                )

        Note:
            - Requires service account with read access to the spreadsheet
            - Adds spreadsheet URL to DataFrame for use in Discord embeds
            - Supports both numeric and string sheet identifiers
        """
        gc: Client = service_account(filename=service_account_path)
        sh: Spreadsheet = gc.open_by_url(spreadsheet_url)

        if isinstance(sheet, int):
            worksheet: Worksheet = sh.get_worksheet(sheet)
        else:
            worksheet: Worksheet = sh.worksheet(sheet)

        data: list[dict[str, Any]] = worksheet.get_all_records()
        df: DataFrame = DataFrame(data)
        df["spreadsheet"] = spreadsheet_url
        return df

    @staticmethod
    def parse_data(df: DataFrame) -> dict[str, Any]:
        """Parse DataFrame to find and return the next upcoming meeting information.

        Processes the journal club schedule DataFrame to identify the next
        chronological meeting based on current date/time. Combines date and
        time columns into datetime objects for accurate comparison.

        Args:
            df (DataFrame): DataFrame containing journal club schedule with columns:
                          - date: Meeting date in day-first format
                          - time: Meeting time
                          - Other meeting details (speaker, paper, room, etc.)

        Returns:
            dict[str, Any]: Dictionary containing all information for the next
                           upcoming meeting, including the Zoom link from the
                           first row (assumed to be constant).

        Raises:
            ValueError: If no future meetings are found in the DataFrame.
            KeyError: If required columns are missing from the DataFrame.
            pandas.errors.ParserError: If date/time parsing fails.

        Example:
            Find next meeting from loaded data:

                df = load_data("service_account.json",
                    "https://docs.google.com/spreadsheets/d/...")
                meeting = parse_data(df)
                print(f"Speaker: {meeting['speaker']}")
                print(f"Paper: {meeting['paper']}")

        Note:
            - Uses dayfirst=True for European date format compatibility
            - Assumes Zoom link in first row applies to all meetings
            - Filters out past meetings automatically
            - Returns the chronologically next meeting
        """
        df["datetime"] = to_datetime(df["date"] + " " + df["time"], dayfirst=True)
        df_next = df[df["datetime"] > datetime.now()]

        if df_next.empty:
            raise ValueError("No future meetings found in the schedule.")

        row = df_next.loc[df_next["datetime"].idxmin()].copy()
        row["link"] = df["link"][0]  # Assume first row contains the Zoom link
        return dict(row)


# =============================================================================
# COG SETUP FUNCTION
# =============================================================================


async def setup(bot: Bot) -> None:
    """Set up the Journal Club cog for the bot.

    Entry point function called by Discord.py when loading this cog extension.
    Creates and adds the Journal Club cog instance to the bot.

    Args:
        bot (Bot): The Discord bot instance to add the cog to.

    Example:
        Load this cog in the main bot setup:

            await bot.load_extension("cogs.journal_club")

    Note:
        - Required function name and signature for Discord.py cog loading
        - Automatically called when the extension is loaded
        - Creates new JournalClub instance with bot reference
    """
    await bot.add_cog(JournalClub(bot=bot))

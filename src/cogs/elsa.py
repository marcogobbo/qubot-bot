"""QuBot Elsa Cog Module.

This module implements the Elsa cog for the QuBot Discord bot, providing
automated monitoring and reporting functionality for the dilution
refrigerator Elsa. The cog integrates with the Proteox instrument control system and
APScheduler for automated notifications.

The module manages scheduled tasks such as temperature reports and LN cold trap
refill reminders, with scheduling loaded from external JSON files.

Example:
    Load the Elsa cog in the main bot:

        await bot.load_extension("cogs.elsa")

    The cog will automatically:
    - Start the scheduler for recurring tasks
    - Send temperature reports at configured times
    - Send LN refill reminders with interactive buttons

Note:
    - Requires ELSA_CHANNEL_ID to send messages in the #elsa channel
    - Requires ELSA_CONTROL_PANEL_URL and ELSA_GRAFANA_URL
    - Configuration timing is loaded from config.json file
    - Uses bot's default timezone (Europe/Rome)
    - Requires qtics.Proteox library for instrument communication
"""

import logging
from dataclasses import dataclass
from os import getenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import ButtonStyle, Embed, Interaction, Thread
from discord.ext.commands import Bot, Cog, command
from discord.ui import Button, View
from dotenv import load_dotenv
from qtics import Proteox

from utils.constants import COLOR_BLUE, ZONE_INFO
from utils.scheduler import ScheduledTime
from utils.utils import load_json

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

# Load environment from the .env file
load_dotenv()

# Discord thread ID where Elsa reports and notifications are sent
ELSA_STATUS_THREAD_ID = int(getenv("ELSA_STATUS_THREAD_ID"))
"""int: #elsa Status thread ID for Elsa reports and notifications.

This thread is used for automated temperature reports, system status updates,
and LN cold trap refill reminders. Must be set in the .env file.

Raises:
    ValueError: If ELSA_STATUS_THREAD_ID is not set or invalid.
"""
# Elsa system URLs from the .env file for security
ELSA_CONTROL_PANEL_URL = getenv("ELSA_CONTROL_PANEL_URL")
"""str: URL for Elsa control panel.

Used in report embeds to provide direct access to the instrument control
interface. Should be set in the .env file to avoid hardcoding URLs.
"""

ELSA_GRAFANA_URL = getenv("ELSA_GRAFANA_URL")
"""str: URL for ELSA Grafana dashboard.

Provides a link to the monitoring dashboard Grafana.
Should be set in in the .env file for easy configuration updates.
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
class ElsaConfig:
    """Configuration dataclass for the Elsa cog.

    Holds all scheduled task timing for Elsa functionality.

    Attributes:
        report (ScheduledTime): Configuration for automated temperature reports.
        ln_refill (ScheduledTime): Configuration for LN cold trap refill reminders.

    Example:
        Create configuration from loaded JSON:

            config_data = load_json("config.json")
            elsa_config = ElsaConfig(
                report=ScheduledTime(
                    day=config_data["elsa"]["report"].get("day"),
                    hour=config_data["elsa"]["report"]["hour"],
                    minute=config_data["elsa"]["report"]["minute"]
                ),
                ln_refill=ScheduledTime(
                    day=config_data["elsa"]["ln_refill"].get("day"),
                    hour=config_data["elsa"]["ln_refill"]["hour"],
                    minute=config_data["elsa"]["ln_refill"]["minute"]
                )
            )
    """

    report: ScheduledTime
    ln_refill: ScheduledTime


# Create global configuration instance from loaded JSON
elsa_config = ElsaConfig(
    report=ScheduledTime(
        day=config["elsa"]["report"].get("day"),
        hour=config["elsa"]["report"]["hour"],
        minute=config["elsa"]["report"]["minute"],
    ),
    ln_refill=ScheduledTime(
        day=config["elsa"]["ln_refill"].get("day"),
        hour=config["elsa"]["ln_refill"]["hour"],
        minute=config["elsa"]["ln_refill"]["minute"],
    ),
)
"""ElsaConfig: Global configuration instance for the Elsa cog.

Pre-configured with values from config.json, ready to use throughout the cog.
"""

# =============================================================================
# ELSA COG CLASS
# =============================================================================


class Elsa(Cog):
    """Elsa cog for QuBot.

    This cog provides automated monitoring and reporting functionality for the
    dilution refrigerator Elsa. It communicates with the Proteox control system
    to gather temperature data and system status, then formats and sends reports
    via Discord embeds. Also manages LN cold trap refill reminders with
    interactive buttons.

    Attributes:
        bot (Bot): Reference to the main bot instance.
        scheduler (AsyncIOScheduler): APScheduler instance for managing scheduled tasks.

    Example:
        The cog is typically loaded automatically by the bot:

            # In main bot setup
            await bot.load_extension("cogs.elsa")
    """

    def __init__(self, bot: Bot) -> None:
        """Initialize the Elsa cog with bot reference and scheduler.

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

    async def cog_load(self):
        """Handle cog loading lifecycle event.

        Called automatically when the cog is loaded by the bot. Provides
        logging confirmation that the cog has been successfully initialized.

        Note:
            - Logs cog loading for debugging and monitoring
            - Uses the cog's name from Discord.py's internal naming
        """
        logging.info("> %s cog loaded", self.__cog_name__)

    async def cog_unload(self):
        """Handle cog unloading lifecycle event.

        Called automatically when the cog is unloaded or the bot shuts down.
        Provides logging confirmation and opportunity for cleanup operations.

        Note:
            - Logs cog unloading for debugging and monitoring
            - Scheduler cleanup is handled automatically by APScheduler
        """
        logging.info("> %s cog unloaded", self.__cog_name__)

    def _setup_scheduler(self):
        """Configure and start the APScheduler with all scheduled tasks.

        Sets up all recurring tasks that the Elsa cog needs to execute,
        including temperature reports and LN refill reminders.
        Starts the scheduler after configuration is complete.

        Note:
            - Private method called during cog initialization
            - Adds all scheduled jobs before starting scheduler
            - Uses configuration from elsa_config for task timing
        """
        # Schedule automated temperature and status reports
        self.scheduler.add_job(
            self.send_report,
            elsa_config.report.to_cron_trigger(),
            id="send_report",
        )

        # Schedule LN cold trap refill reminders
        self.scheduler.add_job(
            self.send_ln_refill,
            elsa_config.ln_refill.to_cron_trigger(),
            id="send_ln_refill",
        )

        # Start the scheduler to begin executing tasks
        self.scheduler.start()

    # =============================================================================
    # DISCORD COMMANDS
    # =============================================================================

    @command(name="report")
    async def report(self, ctx):
        """Discord command to get an immediate Elsa status report.

        Provides manual access to the dilution refrigerator Elsa data including current
        state and all temperature readings. Only works in the #elsa channel.

        Usage:
            /report

        Args:
            ctx: Discord command context containing message and channel information.

        Note:
            - Command is restricted to the #elsa channel
            - Connects to Proteox instrument to gather real-time data
            - Formats data into a Discord embed
            - Logs successful report generation
        """
        await self.bot.wait_until_ready()

        if ctx.channel.id != ELSA_STATUS_THREAD_ID:
            logging.warning("Report command was executed in the wrong channel.")
            return

        thread = await self.fetch_thread(ELSA_STATUS_THREAD_ID)

        state, temps = await self.get_data()
        embed = self.build_embed(state, temps)

        await thread.send(embed=embed)
        logging.info("Sent requested report.")

    # =============================================================================
    # SCHEDULED TASKS
    # =============================================================================

    async def send_report(self):
        """Send automated Elsa status report to the #elsa Status thread.

        Scheduled task that gathers current instrument data and sends a formatted
        report to the #elsa Status thread. Includes system state and all temperature
        readings with proper error handling.

        Raises:
            discord.HTTPException: If sending the message fails.
            discord.Forbidden: If bot lacks permissions to send messages.

        Note:
            - Waits for bot to be ready before attempting to send messages
            - Logs successful report sending for monitoring
            - Handles missing channel gracefully with warning log
        """
        await self.bot.wait_until_ready()

        thread = await self.fetch_thread(ELSA_STATUS_THREAD_ID)

        state, temps = await self.get_data()
        if state == "IDLE":
            logging.info("Refrigerator is in the Idle state.")
            return

        embed = self.build_embed(state, temps)

        await thread.send(embed=embed)
        logging.info("Sent scheduled report.")

    async def send_ln_refill(self):
        """Send automated LN cold trap refill reminder with interactive button.

        Scheduled task that sends a reminder message about refilling Elsa's
        cold trap. Includes an interactive button that users can click to confirm
        the refill has been completed.

        Raises:
            discord.HTTPException: If sending the message fails.
            discord.Forbidden: If bot lacks permissions to send messages.

        Note:
            - Waits for bot to be ready before attempting to send messages
            - Uses RefillButton view for interactive confirmation
            - Logs successful reminder sending for monitoring
            - Handles missing channel gracefully with warning log
        """
        thread = await self.fetch_thread(ELSA_STATUS_THREAD_ID)

        embed = Embed(
            title="📢 **LN cold trap refill**",
            description="Refill **Elsa**'s cold trap with LN! ⚠️",
            color=COLOR_BLUE,
        )
        await thread.send(
            embed=embed,
            view=RefillButton(),
        )
        logging.info("Sent scheduled LN refill reminder.")

    # =============================================================================
    # INSTRUMENT COMMUNICATION
    # =============================================================================

    async def get_data(self):
        """Communicate with the dilution refrigerator Elsa to gather current data.

        Establishes connection with the Proteox instrument control system,
        queries current system state and all temperature sensors, then
        properly closes the connection.

        Returns:
            tuple: A tuple containing:
                - state (str): Current system state
                - temps (dict): Dictionary of temperature readings with keys:
                    - 'pt1': Pulse-tube 1 temperature
                    - 'pt2': Pulse-tube 2 temperature
                    - 'still': Still temperature
                    - 'cp': Cold plate temperature
                    - 'mc': Mixing chamber temperature

        Raises:
            ConnectionError: If unable to connect to the instrument.

        Note:
            - Handles connection errors gracefully with Discord notification
            - Ensures proper connection cleanup via instrument.close()
            - Logs connection errors for debugging
        """
        instrument = Proteox()

        try:
            # Establish connection to the instrument
            await instrument.connect()
        except ConnectionError as e:
            # Notify #elsa channel of connection failure
            thread = await self.fetch_thread(ELSA_STATUS_THREAD_ID)
            msg = f"Failed to query Elsa: {type(e).__name__}: {e}"
            await thread.send(msg)
            logging.error(msg)

        # Query system state
        state = await instrument.get_state()

        # Query all temperature sensors
        temps = {
            "pt1": await instrument.get_PT1_T1(),  # Pulse-tube 1
            "pt2": await instrument.get_PT2_T1(),  # Pulse-tube 2
            "still": await instrument.get_STILL_T(),  # Still
            "cp": await instrument.get_CP_T(),  # Cold plate
            "mc": await instrument.get_MC_T(),  # Mixing chamber
        }

        # Properly close the instrument connection
        await instrument.close()

        return state, temps

    # =============================================================================
    # DATA FORMATTING AND DISPLAY
    # =============================================================================

    @staticmethod
    def format_temp(value: float) -> str:
        """Format temperature values for display with appropriate units.

        Converts temperature values to appropriate units (Kelvin or millikelvin)
        based on the magnitude of the value, with proper precision formatting.

        Args:
            value (float): Temperature value in Kelvin.

        Returns:
            str: Formatted temperature string with units.

        Example:
            >>> Elsa.format_temp(0.015)
            "15.00 mK"
            >>> Elsa.format_temp(4.2)
            "4.20 K"

        Note:
            - Values < 1.0 K are displayed in millikelvin (mK)
            - Values >= 1.0 K are displayed in Kelvin (K)
            - Both formats use 2 decimal places for consistency
        """
        if value < 1.0:
            # Convert to millikelvin for small values
            return f"{value * 1000:.2f} mK"
        # Display in Kelvin for larger values
        return f"{value:.2f} K"

    def build_embed(self, state: str, temps: dict) -> Embed:
        """Build a formatted Discord embed for Elsa status reports.

        Creates a comprehensive status report embed containing system state,
        all temperature readings, and links to external resources.

        Args:
            state (str): Current system state from the instrument.
            temps (dict): Dictionary of temperature readings from all sensors.

        Returns:
            Embed: A formatted Discord embed ready to send.

        Example:
            Use in commands or scheduled tasks:

                state, temps = await self.get_data()
                embed = self.build_embed(state, temps)
                await channel.send(embed=embed)

        Note:
            - Formats all temperatures using format_temp() method
            - Includes links to control panel and Grafana dashboard
        """
        # Format all temperature values with appropriate units
        temps = {key: self.format_temp(value) for key, value in temps.items()}

        # Create the main embed structure
        embed = Embed(
            title="📋 **Report - ELSA**",
            description="",
            color=COLOR_BLUE,
        )

        # Add system state section
        embed.add_field(name="**STATE**", value=state.title(), inline=False)

        # Add temperature readings section
        embed.add_field(
            name="**TEMPERATURES**",
            value=(
                f"- **Pulse-tube 1**: {temps['pt1']}\n"
                f"- **Pulse-tube 2**: {temps['pt2']}\n"
                f"- **Still**: {temps['still']}\n"
                f"- **Cold plate**: {temps['cp']}\n"
                f"- **Mixing chamber**: {temps['mc']}"
            ),
            inline=False,
        )

        # Add external resources section
        embed.add_field(
            name="**RESOURCES**",
            value=f"- [**Control Panel**]({ELSA_CONTROL_PANEL_URL})\n- [**Grafana**]({ELSA_GRAFANA_URL})",
        )

        return embed

    async def fetch_thread(self, thread_id) -> Thread | None:
        thread = self.bot.get_channel(thread_id)
        if thread is None:
            logging.warning("Thread ID %s not found.", thread_id)
            return None

        if isinstance(thread, Thread):
            me = thread.guild.me
            if me.id not in thread.members:
                await thread.join()

        logging.info("Thread ID %s joined.", thread.id)

        return thread


# =============================================================================
# DISCORD UI COMPONENTS
# =============================================================================


class RefillButton(View):
    """Custom Discord UI View for the LN cold trap refill confirmation button.

    Provides an interactive button that users can click to confirm they have
    completed the LC cold trap refill task. The button becomes disabled
    after being clicked and shows who completed the task.

    Attributes:
        button_clicked (bool): Tracks whether the button has been clicked.

    Example:
        Use in messages requiring user confirmation:

            view = RefillButton()
            await channel.send("Please refill the LN trap", view=view)
    """

    def __init__(self) -> None:
        """Initialize the refill button view.

        Creates a green button with appropriate styling and callback function.
        Sets up the initial state as not clicked.

        Note:
            - Callback is automatically bound to the button
            - Initial state allows interaction
        """
        super().__init__()
        self.button_clicked: bool = False

        # Create the refill confirmation button
        button = Button(
            label="Refill LN Trap",
            style=ButtonStyle.green,
        )
        button.callback = self.refill_button
        self.add_item(button)

    async def refill_button(self, interaction: Interaction) -> None:
        """Callback function for the refill button interaction.

        Handles the button click event by disabling the button, updating the
        message, and sending a confirmation message with the user's name.

        Args:
            interaction (Interaction): Discord interaction object containing
                user information and response methods.

        Raises:
            discord.HTTPException: If updating the message fails.
            discord.Forbidden: If bot lacks permissions to respond.

        Note:
            - Disables the button to prevent multiple clicks
            - Updates the original message to show the disabled state
            - Sends follow-up message confirming the action
            - Logs the action with user information for tracking
        """
        # Mark button as clicked and disable it
        self.button_clicked = True
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

        # Update the original message with disabled button
        await interaction.response.edit_message(view=self)

        # Send confirmation message
        await interaction.followup.send(
            f"{interaction.user.mention} refilled **Elsa**'s cold trap with LN! ✅"
        )

        # Log the action for monitoring
        logging.info("%s pushed the LN refill button.", interaction.user.mention)


# =============================================================================
# COG SETUP FUNCTION
# =============================================================================


async def setup(bot: Bot) -> None:
    """Set up the Elsa cog for the bot.

    Entry point function called by Discord.py when loading this cog extension.
    Creates and adds the Elsa cog instance to the bot.

    Args:
        bot (Bot): The Discord bot instance to add the cog to.

    Example:
        Load this cog in the main bot setup:

            await bot.load_extension("cogs.elsa")

    Note:
        - Required function name and signature for Discord.py cog loading
        - Automatically called when the extension is loaded
        - Creates new Elsa instance with bot reference
    """
    await bot.add_cog(Elsa(bot=bot))

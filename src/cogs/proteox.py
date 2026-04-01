import logging
from dataclasses import dataclass
from os import getenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import ButtonStyle, Embed, Interaction, Thread
from discord.ext.commands import Bot, Cog, DefaultHelpCommand, command
from discord.ui import Button, View
from dotenv import load_dotenv
from qtics import Proteox

from utils.constants import COLOR_BLUE, ZONE_INFO
from utils.scheduler import ScheduledTime
from utils.utils import load_json

load_dotenv()

ELSA = {
    "thread_id": int(getenv("ELSA_STATUS_THREAD_ID")),
    "control_panel_url": getenv("ELSA_CONTROL_PANEL_URL"),
    "grafana_url": getenv("ELSA_GRAFANA_URL"),
    "logbook_url": getenv("ELSA_LOGBOOK_URL"),
    "wamp_url": getenv("ELSA_WAMP_ROUTER_URL"),
}

ANNA = {
    "thread_id": int(getenv("ANNA_STATUS_THREAD_ID")),
    "control_panel_url": getenv("ANNA_CONTROL_PANEL_URL"),
    "grafana_url": getenv("ANNA_GRAFANA_URL"),
    "logbook_url": getenv("ANNA_LOGBOOK_URL"),
    "wamp_url": getenv("ANNA_WAMP_ROUTER_URL"),
}

OLAF = {
    "thread_id": int(getenv("OLAF_STATUS_THREAD_ID")),
    "control_panel_url": getenv("OLAF_CONTROL_PANEL_URL"),
    "grafana_url": getenv("OLAF_GRAFANA_URL"),
    "wiki_url": getenv("OLAF_WIKI_URL"),
    "wamp_url": getenv("OLAF_WAMP_ROUTER_URL"),
}

DR = {"elsa": ELSA, "anna": ANNA, "olaf": OLAF}

config: dict[str, dict[str, dict[str, int]]] = load_json("config.json")


@dataclass
class ProteoxConfig:
    report: ScheduledTime
    ln_refill: ScheduledTime


proteox_config = ProteoxConfig(
    report=ScheduledTime(
        day=config["proteox"]["report"].get("day"),
        hour=config["proteox"]["report"]["hour"],
        minute=config["proteox"]["report"]["minute"],
    ),
    ln_refill=ScheduledTime(
        day=config["proteox"]["ln_refill"].get("day"),
        hour=config["proteox"]["ln_refill"]["hour"],
        minute=config["proteox"]["ln_refill"]["minute"],
    ),
)


class ProteoxCog(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone=ZONE_INFO)
        self._setup_scheduler()

    async def cog_load(self):
        logging.info("> %s cog loaded", self.__cog_name__)

    async def cog_unload(self):
        logging.info("> %s cog unloaded", self.__cog_name__)

    def _setup_scheduler(self):
        self.scheduler.add_job(
            self.send_report,
            proteox_config.report.to_cron_trigger(),
            id="send_report",
            max_instances=2,
        )
        self.scheduler.add_job(
            self.send_ln_refill,
            proteox_config.ln_refill.to_cron_trigger(),
            id="send_ln_refill",
            max_instances=2,
        )
        self.scheduler.start()

    @command(name="report")
    async def report(self, ctx):
        await self.bot.wait_until_ready()

        if ctx.channel.id not in (
            DR["elsa"]["thread_id"],
            DR["anna"]["thread_id"],
            DR["olaf"]["thread_id"],
        ):
            logging.warning("Report command was executed in the wrong channel.")
            return

        thread = await self.fetch_thread(ctx.channel.id)
        dr = ctx.channel.parent.name

        if dr == "data-taking":
            dr = "olaf"

        state, data = await self.get_data(dr)
        if state is None:
            logging.info(f"{dr.title()} is in LOCAL mode.")
            await thread.send("Cryostat is in LOCAL mode.")
            return

        embed = self.build_embed(dr, state, data)

        await thread.send(embed=embed)
        logging.info("Sent requested report.")

    async def send_report(self):
        await self.bot.wait_until_ready()
        for dr in DR:
            thread = await self.fetch_thread(DR[dr]["thread_id"])
            state, data = await self.get_data(dr)

            if state == "IDLE":
                logging.info(f"{dr.title()} is in the Idle state.")
                return
            if state is None:
                logging.info(f"{dr.title()} is in LOCAL mode.")
                await thread.send("Cryostat is in LOCAL mode.")
                return

            embed = self.build_embed(dr, state, data)

            await thread.send(embed=embed)
            logging.info("Sent scheduled report.")

    async def send_ln_refill(self):
        for dr in DR:
            thread = await self.fetch_thread(DR[dr]["thread_id"])
            state, _ = await self.get_data(dr)

            if state in ("IDLE", "WARMPING UP"):
                logging.info(f"{dr.title()} is in the Idle state.")
                break

            embed = Embed(
                title="📢 **LN cold trap refill**",
                description=f"Refill **{dr.title()}**'s cold trap with LN! ⚠️",
                color=COLOR_BLUE,
            )
            await thread.send(
                embed=embed,
                view=RefillButton(dr),
            )
            logging.info("Sent scheduled LN refill reminder.")

    async def get_data(self, dr):

        instrument = Proteox(url=DR[dr]["wamp_url"])
        immediate_return = False
        try:
            await instrument.connect()
        except ConnectionError as e:
            thread = await self.fetch_thread(DR[dr]["thread_id"])
            msg = f"Failed to query {dr.title()}: {type(e).__name__}: {e}"
            await thread.send(msg)
            logging.error(msg)
        finally:
            if instrument.is_in_remote():
                immediate_return = True

        if immediate_return:
            return None, (None, None, None, None)

        state = await instrument.get_state()

        flow = await instrument.get_3He_F()

        temps = {
            "pt1": await instrument.get_PT1_T1(),
            "pt2": await instrument.get_PT2_T1(),
            "still": await instrument.get_STILL_T(),
            "cp": await instrument.get_CP_T(),
            "mc": await instrument.get_MC_T(),
        }

        pressures = {
            "ovc": await instrument.get_OVC_P(),
            "p1": await instrument.get_P1_P(),
            "p2": await instrument.get_P2_P(),
        }

        heaters = {
            "still": await instrument.get_STILL_H(),
            "mc": await instrument.get_MC_H(),
        }

        await instrument.close()

        return state, (flow, temps, pressures, heaters)

    @staticmethod
    def format_flow(value: float) -> str:
        if value is None:
            return "N/A"
        return f"{value*1e6:.2f} μmol/s"

    @staticmethod
    def format_heaters(value: float) -> str:
        if value is None:
            return "N/A"

        if value >= 1:
            return f"{value:.2f} W"
        elif value >= 1e-3:
            return f"{value * 1e3:.2f} mW"
        elif value >= 1e-6:
            return f"{value * 1e6:.2f} µW"
        elif value >= 1e-9:
            return f"{value * 1e9:.2f} nW"
        else:
            return f"{value * 1e12:.2f} pW"

    @staticmethod
    def format_temp(value: float) -> str:
        if value is None:
            return "N/A"
        if value < 1.0:
            return f"{value * 1000:.2f} mK"
        return f"{value:.2f} K"

    @staticmethod
    def format_pressure(value: float) -> str:
        if value is None:
            return "N/A"
        if value > 1000:
            return f"{value / 1000:.2f} kPa"
        return f"{value:.2f} Pa"

    def build_embed(self, dr: str, state: str, data: dict) -> Embed:
        # Format all temperature values with appropriate units
        flow, temps, pressures, heaters = data

        flow = self.format_flow(flow)
        temps = {key: self.format_temp(value) for key, value in temps.items()}
        pressures = {
            key: self.format_pressure(value) for key, value in pressures.items()
        }
        heaters = {key: self.format_heaters(value) for key, value in heaters.items()}

        # Create the main embed structure
        embed = Embed(
            title=f"📋 **Report - {dr.upper()}**",
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

        embed.add_field(
            name="**PRESSURES**",
            value=(
                f"- **OVC**: {pressures['ovc']}\n"
                f"- **Dump**: {pressures['p1']}\n"
                f"- **Still**: {pressures['p2']}\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="**FLOWMETER**",
            value=(f"- **Flow**: {flow}\n"),
            inline=False,
        )

        embed.add_field(
            name="**HEATERS**",
            value=(
                f"- **Still**: {heaters['still']}\n"
                f"- **Mixing chamber**: {heaters['mc']}\n"
            ),
            inline=False,
        )

        if dr == "olaf":
            embed.add_field(
                name="**RESOURCES**",
                value=f"- [**Control Panel**]({DR[dr]['control_panel_url']})\n- [**Grafana**]({DR[dr]['grafana_url']})\n - [**Wiki**]({DR[dr]['wiki_url']})",
            )

        else:
            embed.add_field(
                name="**RESOURCES**",
                value=f"- [**Control Panel**]({DR[dr]['control_panel_url']})\n- [**Grafana**]({DR[dr]['grafana_url']})\n - [**Logbook**]({DR[dr]['logbook_url']})",
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

    @command(name="recognizedstates")
    async def recognizedstates(self, ctx):
        """
        List all available recognized state names.
        """
        await self.bot.wait_until_ready()

        dr = self.get_dr_from_context(ctx)
        if dr is None:
            logging.warning(
                "Recognizedstates command was executed in the wrong channel."
            )
            return

        try:
            from qtics.instruments.network.proteox.recognized_states import (
                RECOGNIZED_STATES,
            )

            state_names = sorted(RECOGNIZED_STATES.keys())

            message = "📚 **Available recognized states**\n" + "\n".join(
                f"- {name}" for name in state_names
            )

            await ctx.send(message)
            logging.info("Sent recognized-state list for %s.", dr)

        except Exception as e:
            msg = f"Failed to list recognized states for {dr.title()}: {type(e).__name__}: {e}"
            await ctx.send(f"❌ {msg}")
            logging.error(msg)

    @command(name="howto")
    async def howto(self, ctx, *, target_state: str = None):
        """
        Suggest how to reach a recognized state.

        Usage:
          !howto
          !howto Circulating
          !howto "Circulating Compressor Bypassed"
        """
        await self.bot.wait_until_ready()

        dr = self.get_dr_from_context(ctx)
        if dr is None:
            logging.warning("Howto command was executed in the wrong channel.")
            return

        instrument = None
        try:
            instrument = await self.get_instrument(dr)

            plan = await instrument.recognized_states.get_transition_plan(target_state)
            message = self.build_transition_plan_message(dr, plan)

            await ctx.send(message)

            if target_state is None:
                logging.info(
                    "Sent closest recognized-state transition plan for %s.", dr
                )
            else:
                logging.info(
                    "Sent transition plan for %s toward target state '%s'.",
                    dr,
                    target_state,
                )

        except ValueError as e:
            await ctx.send(f"❌ {e}")
            logging.warning(
                "Invalid recognized-state target requested for %s: %s", dr, e
            )

        except Exception as e:
            msg = f"Failed to compute transition plan for {dr.title()}: {type(e).__name__}: {e}"
            await ctx.send(f"❌ {msg}")
            logging.error(msg)

        finally:
            if instrument is not None:
                await instrument.close()

    @command(name="recognized")
    async def recognized(self, ctx):
        """
        Report whether the cryostat is currently in a recognized state.
        """
        await self.bot.wait_until_ready()

        dr = self.get_dr_from_context(ctx)
        if dr is None:
            logging.warning("Recognized command was executed in the wrong channel.")
            return

        instrument = None
        try:
            instrument = await self.get_instrument(dr)

            is_recognized = await instrument.is_in_recognized_state()
            states = await instrument.get_recognized_states()

            message = self.build_recognized_state_message(dr, is_recognized, states)
            await ctx.send(message)

            logging.info("Sent recognized-state status for %s.", dr)

        except Exception as e:
            msg = f"Failed to query recognized state for {dr.title()}: {type(e).__name__}: {e}"
            await ctx.send(f"❌ {msg}")
            logging.error(msg)

        finally:
            if instrument is not None:
                await instrument.close()

    def get_dr_from_context(self, ctx) -> str | None:
        """
        Infer the dilution refrigerator name from the current Discord context.
        Returns one of: 'elsa', 'anna', 'olaf', or None if invalid.
        """
        if ctx.channel.id not in (
            DR["elsa"]["thread_id"],
            DR["anna"]["thread_id"],
            DR["olaf"]["thread_id"],
        ):
            return None

        dr = ctx.channel.parent.name
        if dr == "data-taking":
            dr = "olaf"

        if dr not in DR:
            return None

        return dr

    async def get_instrument(self, dr: str) -> Proteox:
        """
        Create and connect a Proteox instrument for the selected DR.
        """
        instrument = Proteox(url=DR[dr]["wamp_url"])
        await instrument.connect()
        return instrument

    def build_recognized_state_message(
        self,
        dr: str,
        is_recognized: bool,
        states: list[str],
    ) -> str:
        """
        Build a Discord-friendly message for recognized-state status.
        """
        if is_recognized and states:
            if len(states) == 1:
                return (
                    f"✅ **{dr.title()}** is currently in a recognized state:\n"
                    f"**{states[0]}**"
                )

            return (
                f"⚠️ **{dr.title()}** matches multiple recognized states:\n"
                + "\n".join(f"- {s}" for s in states)
            )

        return f"❌ **{dr.title()}** is **not** currently in a recognized state."

    def build_transition_plan_message(self, dr: str, plan: dict) -> str:
        """
        Build a Discord-friendly message from a recognized-state transition plan.
        """
        target_state = plan.get("target_state")
        matched = plan.get("matched", False)
        mismatch_count = plan.get("mismatch_count")
        actions = plan.get("actions", [])

        if target_state is None:
            return f"❌ Could not determine a target recognized state for **{dr.title()}**."

        if matched:
            return (
                f"✅ **{dr.title()}** is already in the recognized state:\n"
                f"**{target_state}**"
            )

        lines = [
            f"🛠️ **{dr.title()}** transition suggestion",
            f"**Target state:** {target_state}",
            f"**Total mismatches:** {mismatch_count}",
            "",
        ]

        if not actions:
            lines.append("No actions available.")
            return "\n".join(lines)

        lines.append("**Suggested actions:**")
        for action in actions:
            label = action.get("label", action.get("condition", "Unknown condition"))
            suggestion = action.get("suggestion", "No suggestion available.")
            target_value = action.get("target_value")

            if target_value is True:
                prefix = "🟢"
            else:
                prefix = "🔴"

            lines.append(f"{prefix} **{label}** → {suggestion}")

        return "\n".join(lines)

    @command(name="help")
    async def help_command(self, ctx):
        """
        Show available Proteox bot commands.
        """
        await self.bot.wait_until_ready()

        embed = Embed(
            title="🤖 **Proteox Bot Commands**",
            description="Available commands for cryostat monitoring and state diagnostics.",
            color=COLOR_BLUE,
        )

        embed.add_field(
            name="**Monitoring**",
            value=(
                "`/report`\n"
                "Send a full cryostat report in the current status thread.\n\n"
                "`/recognized`\n"
                "Check whether the cryostat is currently in a recognized state.\n\n"
                "`/recognizedstates`\n"
                "List all available recognized states."
            ),
            inline=False,
        )

        embed.add_field(
            name="**State guidance**",
            value=(
                "`/howto`\n"
                "Suggest how to reach the closest recognized state.\n\n"
                "`/howto <state name>`\n"
                "Suggest how to reach a specific recognized state.\n"
                "Example: `/howto Circulating`\n"
                "Example: `/howto Circulating Compressor Bypassed`"
            ),
            inline=False,
        )

        embed.add_field(
            name="**Notes**",
            value=(
                "- These commands should be used in the Proteox status threads.\n"
                "- Recognized-state commands use the cryostat truth-table logic from the driver."
            ),
            inline=False,
        )

        await ctx.send(embed=embed)
        logging.info("Sent Proteox help command list.")


class RefillButton(View):
    def __init__(self, dr) -> None:
        super().__init__()
        self.button_clicked: bool = False
        self.dr: str = dr
        button = Button(
            label="Refill LN Trap",
            style=ButtonStyle.green,
        )
        button.callback = self.refill_button
        self.add_item(button)

    async def refill_button(self, interaction: Interaction) -> None:
        self.button_clicked = True
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

        await interaction.response.edit_message(view=self)

        await interaction.followup.send(
            f"{interaction.user.mention} refilled **{self.dr.title()}**'s cold trap with LN! ✅"
        )

        logging.info("%s pushed the LN refill button.", interaction.user.mention)


async def setup(bot: Bot) -> None:
    await bot.add_cog(ProteoxCog(bot=bot))

import asyncio
from datetime import date, datetime, timedelta
from mysecrets import ELSA_CHANNEL_ID
import discord
from discord.ext import tasks
from utils import seconds_until_target

class RefillView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.button_clicked = False

    @discord.ui.button(label="Refill LN Trap", style=discord.ButtonStyle.green)
    async def refill_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        self.button_clicked = True

        user = interaction.user
        button.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"{user.mention} refilled *Elsa*'s cold trap with LN! ✅")


def ln_refill_setup(bot):
    @tasks.loop(hours=168)
    async def weekly_reminder_task():
        channel = bot.get_channel(ELSA_CHANNEL_ID)

        class DummyContext:
            async def send(self, *args, **kwargs):
                return await channel.send(*args, **kwargs)

        ctx = DummyContext()
        await send_weekly_reminder(ctx)

    @bot.event
    async def on_ready():
        """
        Called when the bot is ready. Schedules the reminder tasks.
        """

        async def start_weekly_reminder():
            await asyncio.sleep(seconds_until_target(2, 10, 00))  # Wednesday at 10:00
            weekly_reminder_task.start()

        bot.loop.create_task(start_weekly_reminder())

    async def send_weekly_reminder(ctx):
        embed = discord.Embed(
            title="LN cold trap refill",
            description="**Reminder**: Refill *Elsa*'s cold trap with LN! ⚠️​",
            color=0x4285F4,
        )
        view = RefillView()
        await ctx.send(embed=embed, view=view)

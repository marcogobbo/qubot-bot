import asyncio
from datetime import date, datetime, timedelta
from mysecrets import GENERAL_CHANNEL_ID, MONDAY_MEETING_DOC_URL, MONDAY_MEETING_ZOOM_URL
import discord
from discord.ext import tasks
from utils import seconds_until_target

def monday_meeting_setup(bot):
    @tasks.loop(hours=168)
    async def weekly_reminder_task():
        channel = bot.get_channel(GENERAL_CHANNEL_ID)

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
            await asyncio.sleep(seconds_until_target(0, 9, 00))  # Monday at 9:00
            weekly_reminder_task.start()

        bot.loop.create_task(start_weekly_reminder())

    async def send_weekly_reminder(ctx):
        embed = discord.Embed(
            title="Monday Meeting",
            description=f"Good morning everyone! ☀️​\nThe **Monday Meeting** starts in 15 minutes! ☕\nCan’t make it in person? Join on [**Zoom**]({MONDAY_MEETING_ZOOM_URL})! And don't forget to take the [**minutes**]({MONDAY_MEETING_DOC_URL})! 📝", 
            color=0x4285F4,
        )
        await ctx.send(embed=embed)

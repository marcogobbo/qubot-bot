import asyncio
from datetime import date, datetime, timedelta

import discord
import gspread
from discord.ext import tasks
from mysecrets import JC_CHANNEL_ID, JC_SPREADSHEET_URL, SERVICE_ACCOUNT_FILE
from oauth2client.service_account import ServiceAccountCredentials
from utils import seconds_until_target


def get_journal_club_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE, scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(JC_SPREADSHEET_URL).sheet1
    all_values = sheet.get_all_values()
    headers = list(map(str.lower, all_values[0]))
    data_rows = all_values[1:]
    link = all_values[1][6] if len(all_values[1]) > 6 else ""

    today = date.today()
    if today.weekday() == 1:
        target_tuesday = today
    else:
        days_ahead = (1 - today.weekday() + 7) % 7
        target_tuesday = today + timedelta(days=days_ahead)

    for row in data_rows:
        try:
            row_date = datetime.strptime(row[0], "%d/%m/%Y").date()
            if row_date == target_tuesday:
                result = dict(zip(headers, row))
                result["link"] = link
                return result
        except ValueError:
            continue

    return {}


def journal_club_setup(bot):
    @bot.command(name="link")
    async def get_link(ctx):
        await ctx.send(f"Here the [QJC spreadsheet]({bot.SHEET_LINK})!")

    @bot.command(name="reminder")
    async def manual_reminder(ctx):
        await send_weekly_reminder(ctx)

    @tasks.loop(hours=168)
    async def weekly_reminder_task():
        channel = bot.get_channel(JC_CHANNEL_ID)

        class DummyContext:
            async def send(self, *args, **kwargs):
                return await channel.send(*args, **kwargs)

        ctx = DummyContext()
        await send_weekly_reminder(ctx)

    @tasks.loop(hours=168)
    async def reminder_30min_task():
        channel = bot.get_channel(JC_CHANNEL_ID)

        class DummyContext:
            async def send(self, *args, **kwargs):
                return await channel.send(*args, **kwargs)

        ctx = DummyContext()
        await send_30min_reminder(ctx)

    @bot.event
    async def on_ready():
        """
        Called when the bot is ready. Schedules the reminder tasks.
        """

        async def start_30min_reminder():
            await asyncio.sleep(seconds_until_target(1, 14, 00))  # Tuesday at 14:00
            reminder_30min_task.start()

        async def start_weekly_reminder():
            await asyncio.sleep(seconds_until_target(3, 10, 00))  # Thursday at 10:00
            weekly_reminder_task.start()

        bot.loop.create_task(start_30min_reminder())
        bot.loop.create_task(start_weekly_reminder())

    async def send_weekly_reminder(ctx):
        data = get_journal_club_data()
        embed = discord.Embed(
            title="Quantum Journal Club",
            description=f"Next Tuesday, **{data['speaker']}** will host the QJC in room **{data['room']}** and [**Zoom**]({data['link']}).",
            color=0x4285F4,
        )
        embed.add_field(
            name="Paper",
            value=f"[{data['paper']}]({data['doi']})\n\nDon’t forget to read the paper beforehand! 🤓",
            inline=False,
        )
        await ctx.send(embed=embed)

    async def send_30min_reminder(ctx):
        data = get_journal_club_data()
        embed = discord.Embed(
            title="Quantum Journal Club",
            description=f"In 30 minutes, **{data['speaker']}** will host the QJC in room **{data['room']}** and [**Online**]({data['link']}).",
            color=0x4285F4,
        )
        embed.add_field(
            name="Paper",
            value=f"[{data['paper']}]({data['doi']})\n\nMake sure to at least check out the abstract! 👀",
            inline=False,
        )
        await ctx.send(embed=embed)

import asyncio
from datetime import date, datetime, timedelta

import discord
import gspread
import pytz
from discord.ext import commands, tasks
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_name("../../config/service_account.json", scope)
client = gspread.authorize(creds)
link = "https://docs.google.com/spreadsheets/d/1Rr7zifIwBSO2Pw_6HJ3Y8GVu_EkeAdeH9QiPyzLVwXc/edit?usp=drive_link"
sheet = client.open_by_url(link).sheet1
all_values = sheet.get_all_values()
headers = list(map(str.lower, all_values[0]))
data_rows = all_values[1:]

today = date.today()
if today.weekday() == 1:
    target_tuesday = today
else:
    days_ahead = (1 - today.weekday() + 7) % 7
    target_tuesday = today + timedelta(days=days_ahead)

matched_row = None
for row in data_rows:
    try:
        row_date = datetime.strptime(row[0], "%d/%m/%Y").date()
        if row_date == target_tuesday:
            matched_row = row
            break
    except ValueError:
        continue

data = dict(zip(headers, matched_row))

DISCORD_TOKEN = (
    True
)
CHANNEL_ID = True

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


def seconds_until_target(day_of_week, hour, minute):
    """
    Calculate the number of seconds until the next specified day of the week at a given hour and minute.

    Args:
        day_of_week (int): Target weekday (0=Monday, 6=Sunday)
        hour (int): Hour of the day
        minute (int): Minute of the hour

    Returns:
        float: Number of seconds until the target datetime
    """
    now = datetime.now(pytz.timezone("Europe/Rome"))
    today = now.weekday()
    days_ahead = (day_of_week - today + 7) % 7
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if days_ahead == 0 and now > target:
        days_ahead = 7

    target += timedelta(days=days_ahead)
    return (target - now).total_seconds()


async def send_weekly_reminder(ctx):
    """
    Send the regular weekly reminder embed to the Discord channel.
    """
    embed = discord.Embed(
        title="Quantum Journal Club",
        description=f"Next Tuesday, **{data['speaker']}** will host the QJC in room **{data['room']}** and on [**Zoom**]({data['zoom']}).",
        color=0x4285F4,
    )
    embed.add_field(
        name="Paper",
        value=f"[{data['paper']}]({data['doi']})\n\nDon’t forget to read the paper beforehand! 🤓",
        inline=False,
    )
    await ctx.send(embed=embed)


async def send_30min_reminder(ctx):
    """
    Send a reminder 30 minutes before the session starts.
    """
    embed = discord.Embed(
        title="Quantum Journal Club",
        description=f"In 30 minutes, **{data['speaker']}** will host the QJC in room **{data['room']}** and on [**Zoom**]({data['zoom']}).",
        color=0x4285F4,
    )
    embed.add_field(
        name="Paper",
        value=f"[{data['paper']}]({data['doi']})\n\nMake sure to at least check out the abstract! 👀",
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command(name="link")
async def get_link(ctx):
    """
    Slash command to get the QJC spreadsheet link.
    """
    await ctx.send(f"Here the [QJC spreadsheet]({link})!")


@bot.command(name="reminder")
async def manual_reminder(ctx):
    """
    Slash command to manually trigger the weekly reminder.
    """
    await send_weekly_reminder(ctx)


@tasks.loop(hours=168)  # Repeat weekly
async def weekly_reminder_task():
    """
    Weekly task that sends the regular session reminder.
    """
    channel = bot.get_channel(CHANNEL_ID)

    class DummyContext:
        async def send(self, *args, **kwargs):
            return await channel.send(*args, **kwargs)

    ctx = DummyContext()
    await send_weekly_reminder(ctx)


@tasks.loop(hours=168)  # Repeat weekly
async def reminder_30min_task():
    """
    Weekly task that sends the 30-minute prior reminder.
    """
    channel = bot.get_channel(CHANNEL_ID)

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
    await asyncio.sleep(seconds_until_target(1, 14, 00))  # Tuesday at 14:00
    reminder_30min_task.start()

    await asyncio.sleep(seconds_until_target(3, 10, 00))  # Thursday at 10:00
    weekly_reminder_task.start()


# Start the bot
bot.run(DISCORD_TOKEN)

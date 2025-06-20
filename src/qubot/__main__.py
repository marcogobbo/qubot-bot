import discord
from discord.ext import commands

from ln_refill import ln_refill_setup
from journal_club import journal_club_setup
from monday_meeting import monday_meeting_setup
from mysecrets import DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Setup journal club commands and tasks
journal_club_setup(bot)
ln_refill_setup(bot)
monday_meeting_setup(bot)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

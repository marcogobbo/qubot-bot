import discord
from discord.ext import commands
from journal_club import journal_club_setup
from logbook import logbook_setup
from mysecrets import DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Setup journal club commands and tasks
journal_club_setup(bot)
logbook_setup(bot)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

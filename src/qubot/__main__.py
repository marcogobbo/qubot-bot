import discord
from discord.ext import commands
from secrets import DISCORD_TOKEN
from journal_club import journal_club_setup

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Setup journal club commands and tasks
journal_club_setup(bot)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

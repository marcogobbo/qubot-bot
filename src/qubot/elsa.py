import discord
from discord.ext import commands, tasks
from mysecrets import ELSA_CHANNEL_ID
from qtics import Proteox
from utils import is_cryo_active


def cryo_monitor_setup(bot: commands.Bot):
    @bot.tree.command(
        name="status", description="Get current cryostat temperatures and state"
    )
    async def status_command(interaction: discord.Interaction):
        await interaction.response.defer()

        instrument = Proteox()
        try:
            await instrument.connect()
        except Exception as e:
            channel = bot.get_channel(ELSA_CHANNEL_ID)
            await channel.send(f"⚠️ Failed to query Elsa: `{type(e).__name__}: {e}`")

        state = await instrument.get_state()
        mix = await instrument.get_MC_T()
        pt1 = await instrument.get_PT1_T1()
        pt2 = await instrument.get_PT2_T1()
        sti = await instrument.get_STILL_T()
        col = await instrument.get_CP_T()
        await instrument.close()

        embed = discord.Embed(
            title="Cryostat Status",
            description=f"**State**: `{state}`",
            color=discord.Color.blue(),
        )

        embed.add_field(name="MIX", value=f"{mix*1000:.2f} mK", inline=True)
        embed.add_field(name="STILL", value=f"{sti*1000:.2f} mK", inline=True)
        embed.add_field(name="COLD PLATE", value=f"{col*1000:.2f} mK", inline=True)
        embed.add_field(name="PT1", value=f"{pt1:.2f} K", inline=True)
        embed.add_field(name="PT2", value=f"{pt2:.2f} K", inline=True)

        await interaction.followup.send(embed=embed)

    @tasks.loop(hours=6)
    async def periodic_temp_report():
        if not is_cryo_active():
            return

        instrument = Proteox()
        try:
            await instrument.connect()
        except:
            return

        mix = await instrument.get_MC_T()
        pt1 = await instrument.get_PT1_T1()
        pt2 = await instrument.get_PT2_T1()
        sti = await instrument.get_STILL_T()
        col = await instrument.get_CP_T()
        await instrument.close()

        embed = discord.Embed(
            title="Automatic Cryostat Report",
            color=discord.Color.orange(),
        )
        embed.add_field(name="MIX", value=f"{mix*1000:.2f} mK", inline=True)
        embed.add_field(name="STILL", value=f"{sti*1000:.2f} mK", inline=True)
        embed.add_field(name="COLD PLATE", value=f"{col*1000:.2f} mK", inline=True)
        embed.add_field(name="PT1", value=f"{pt1:.2f} K", inline=True)
        embed.add_field(name="PT2", value=f"{pt2:.2f} K", inline=True)

        channel = bot.get_channel(ELSA_CHANNEL_ID)
        await channel.send(embed=embed)

    @bot.event
    async def on_ready():
        if not periodic_temp_report.is_running():
            periodic_temp_report.start()

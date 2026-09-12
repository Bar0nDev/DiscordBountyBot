import asyncio
from discord.ext import commands
from discord import app_commands
import dotenv
import os
import discord

dotenv.load_dotenv()
if not os.getenv("API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["API_KEY"] = os.environ["GEMINI_API_KEY"]


def run_discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix='>', intents=intents)
    bot.remove_command('help')

    async def change_status():
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=">help | Indexing..."))


    @bot.event
    async def on_ready():
        news_cog = bot.get_cog("NewsCog")
        if news_cog:
            await news_cog.handle_news_report()
        await change_status()
        print(f"{bot.user} online")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            if ctx.interaction is not None:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(
                        "🚫 You do not have the required role to use this command.",
                        ephemeral=True
                    )
                else:
                    await ctx.interaction.response.send_message(
                        "🚫 You do not have the required role to use this command.",
                        ephemeral=True
                    )
            else:
                await ctx.send("🚫 You do not have the required role.", delete_after=10)

    @bot.tree.error
    async def on_app_command_error(interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            message = "🚫 You do not have the required role to use this command."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        else:
            await app_commands.CommandTree.on_error(bot.tree, interaction, error)


    @bot.hybrid_command(name="help", description="Shows R0-U41's help menu")
    async def help(ctx):
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 0, 0),
            title="Help Menu"
        )
        embed.add_field(name="Show missions",
                        value="Run /all_missions (preferred) or >all_missions to show available missions for faction specified (Rogue, Imperial, Rebel, Mandalorian).\n\nExample Command: >all_missions Mando\n\n")
        embed.add_field(name="Show bounties",
                        value="Run /all_bounties (preferred) or >all_bounties to show available bounties.")
        embed.add_field(name="Add bounty",
                        value="`Moderator role required`\nRun /add_bounty (preferred) or >add_bounty to add a new bounty.\n\nExample Command: >add_bounty 'Jabba' 'I do not like him.' '300'\n\n")
        embed.add_field(name="Add mission",
                        value="`Moderator role required`\nRun /add_mission (preferred) or >add_mission to add a new mission.\n\nExample Command: >add_mission 'Destroy Rebel Base' 'A rebel base on Tatooine.' '200' 'Easy' 'Imperial'\n\n")
        embed.add_field(name="Edit/status missions",
                        value="`Moderator role required`\nUse /edit_mission or >edit_mission to update a mission, and /mission_status or >mission_status to toggle its availability.\n\n")
        embed.add_field(name="Delete mission",
                        value="`Moderator role required`\nRun /delete_mission (preferred) or >delete_mission to delete a mission.\n\nExample Command: >delete_mission 2 'Mandalorian'\n\n")
        embed.add_field(name="Delete bounty",
                        value="`Moderator role required`\nRun /delete_bounty (preferred) or >delete_bounty to delete a bounty.\n\nExample Command: >delete_bounty 2\n\n")
        embed.add_field(name="Generate items",
                        value="`Moderator role required`\nUse /generate_missions or /generate_bounties to fill the boards with AI-generated items.\n\n")
        embed.set_footer(text="Built by BaronViper#8694")
        await ctx.send(embed=embed)


    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        econ_cog = bot.get_cog("EconCog")
        if econ_cog:
            await econ_cog.process_bumps(message)

        chat_cog = bot.get_cog("ChatCog")
        if chat_cog:
            await chat_cog.handle_normal_chat(message)

        game_cog = bot.get_cog("GMCog")
        if game_cog:
            await game_cog.handle_gamemaster_message(message)

        await bot.process_commands(message)


    async def main():
        print("Loading Cogs...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await bot.load_extension(f"cogs.{filename[:-3]}")
        await bot.start(os.getenv('TOKEN'))


    asyncio.run(main())

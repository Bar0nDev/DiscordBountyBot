import asyncio
import traceback
from discord.ext import commands
import os
import discord
from discord import app_commands



def load_env_file(path=".env"):
    """Load simple KEY=VALUE entries without requiring a runtime package."""
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()


def run_discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix='>', intents=intents)
    bot.remove_command('help')

    async def change_status():
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=">help | Indexing..."))

    ALLOWED_GUILD_ID = 1389425312915263509

    async def verify_guild(guild):
        if guild.id != ALLOWED_GUILD_ID:
            print(f"Leaving unauthorized guild: {guild.name} ({guild.id})")
            await guild.leave()

    @bot.event
    async def on_guild_join(guild):
        await verify_guild(guild)

    @bot.event
    async def on_ready():
        for guild in bot.guilds:
            await verify_guild(guild)
        news_cog = bot.get_cog("NewsCog")
        if news_cog:
            await news_cog.handle_news_report()
        await change_status()
        print(f"{bot.user} online")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRole):
            try:
                await ctx.interaction.response.send_message(
                    "🚫 You do not have the required role to use this command.",
                    ephemeral=True
                )
            except:
                await ctx.send("🚫 You do not have the required role.", delete_after=10)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        original_error = getattr(error, "original", error)

        if isinstance(original_error, app_commands.MissingAnyRole):
            message = "🚫 You do not have any of the required roles to use this command."
        elif isinstance(original_error, app_commands.MissingRole):
            message = "🚫 You do not have the required role to use this command."
        else:
            traceback.print_exception(
                type(original_error),
                original_error,
                original_error.__traceback__
            )
            message = "❌ Something went wrong while processing that command. Please try again later."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            traceback.print_exc()


    @bot.hybrid_command(name="help", description="Shows R0-U41's help menu")
    async def help(ctx):
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 0, 0),
            title="Help Menu"
        )
        embed.add_field(name="Show missions",
                        value="Run /all_missions (preferred) or >all_missions to show available missions for a faction (Rogue, Imperial, Rebel, Mandalorian, CIS) or across all factions with Universal.\n\nExample Command: /all_missions faction:Universal\n\n")
        embed.add_field(name="Show bounties",
                        value="Run /all_bounties (preferred) or >all_bounties to show available bounties.")
        embed.add_field(name="Add bounty",
                        value="`Moderator role required`\nRun /add_bounty to add a new bounty.\n\nExample Command: /add_bounty target:Jabba description:\"Wanted for desertion.\" reward:300 stars:3 client:Hutt\n\n")
        embed.add_field(name="Add mission",
                        value="`Moderator role required`\nRun /add_mission (preferred) or >add_mission to add a new mission.\n\nExample Command: /add_mission title:\"Destroy Rebel Base\" description:\"A rebel base on Tatooine.\" reward:200 difficulty:Easy faction:Imperial\n\n")
        embed.add_field(name="Edit/status missions",
                        value="`Moderator role required`\nUse /edit_mission to update a mission and /mission_status to toggle its availability.\n\n")
        embed.add_field(name="Delete mission",
                        value="`Moderator role required`\nRun /delete_mission and choose a mission by name from autocomplete.\n\nExample Command: /delete_mission mission:\"Mission title\" faction:Mandalorian\n\n")
        embed.add_field(name="Delete bounty",
                        value="`Moderator role required`\nRun /delete_bounty to delete a bounty.\n\nExample Command: /delete_bounty b_id:2\n\n")
        embed.add_field(name="Generate mission/bounty boards",
                        value="`Moderator role required`\nUse /generate_missions or /generate_bounties to fill the boards with AI-generated entries.\n\n")
        embed.set_footer(text="Built by BaronViper#8694")
        await ctx.send(embed=embed)


    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        chat_cog = bot.get_cog("ChatCog")
        if chat_cog:
            await chat_cog.handle_normal_chat(message)

        game_cog = bot.get_cog("GMCog")
        if game_cog:
            await game_cog.handle_gamemaster_message(message)

        await bot.process_commands(message)


    async def setup_hook():
        print("Loading Cogs...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await bot.load_extension(f"cogs.{filename[:-3]}")
        guild = discord.Object(id=ALLOWED_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced_commands = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced_commands)} application commands to guild {ALLOWED_GUILD_ID}")

    bot.setup_hook = setup_hook

    async def main():
        await bot.start(os.getenv('TOKEN'))


    asyncio.run(main())

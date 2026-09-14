import asyncio
from discord.ext import commands
import os
import discord



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
                        value="Run /add_bounty (preferred) or >add_bounty to add a new bounty. If running >add_mission, the command takes in three inputs separated by spaces (title, description, reward).\n\nExample Command: >add_bounty 'Jabba' 'I don't like him. I heard he's chilling in his palace on Tatooine.' '300'\n\n")
        embed.add_field(name="Add mission",
                        value="`Only available to @Game Master`\nRun /add_mission (preferred) or >add_mission to add a new mission. If running >add_mission, the command takes in five inputs separated by spaces (title, description, reward, difficulty- Very Easy, Easy, Medium, Hard, Very Hard, Expert, faction- Rogue, Imperial, Rebel, Mandalorian).\n\nExample Command: >add_mission 'Destroy Rebel Base' 'A big rebel base on Kuwait' '200' 'Easy' 'Imperial'\n\n")
        embed.add_field(name="Delete mission",
                        value="`Only available to @Game Master`\nRun /delete_mission (preferred) or >delete_mission to delete a mission. If running >delete_mission, the command takes in two inputs (mission_id, faction- Rogue, Imperial, Rebel, Mandalorian).\n\nExample Command: >delete_mission 2 'Mandalorian'\n\n")
        embed.add_field(name="Delete bounty",
                        value="`Only available to @Game Master`\nRun /delete_bounty (preferred) or >delete_bounty to delete a bounty. If running >delete_bounty, the command takes in one input (bounty_id).\n\nExample Command: >delete_bounty 2\n\n")
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


    async def main():
        print("Loading Cogs...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await bot.load_extension(f"cogs.{filename[:-3]}")
        await bot.start(os.getenv('TOKEN'))


    asyncio.run(main())

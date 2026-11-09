import discord

from utils.utils import GUILD_ID


async def sync_guild_commands(tree):
    """Publish the guild schema and retire this bot's old global slash commands."""
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    synced = await tree.sync(guild=guild)

    legacy_names = {command.name for command in synced if command.type is discord.AppCommandType.chat_input}
    legacy_names.add("update_bounty")
    for command in await tree.fetch_commands():
        if command.type is discord.AppCommandType.chat_input and command.name in legacy_names:
            try:
                await command.delete()
            except discord.NotFound:
                # Another sync may have removed the command already.
                pass

    return synced

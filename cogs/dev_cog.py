import asyncio
import discord
from discord.ext import commands
import os


class DevCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="export", description="Download the current database contents")
    @commands.has_role("Owner")
    async def export(self, ctx):
        try:
            # List of files to export
            files_to_export = [
                ("info.db", "The database file does not exist."),
                ("nochat_channels.pk1", "The no-chat channels file does not exist."),
                ("chat_sessions.pk1", "The chat sessions file does not exist."),
                ("rp_sessions.pk1", "The rp-sessions file does not exist.")
            ]

            files_to_send: list[discord.File] = []
            for filename, error in files_to_export:
                files_to_send.append(discord.File(filename))

            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=True)

            for file_path, error_message in files_to_export:
                if not os.path.exists(file_path):
                    if ctx.interaction:
                        await ctx.followup.send(error_message, ephemeral=True)
                    else:
                        await ctx.send(error_message)
                    continue

                if ctx.interaction:
                    await ctx.send(files=files_to_send, ephemeral=True)
                else:
                    file_msg = await ctx.send(files=files_to_send)
                    await asyncio.sleep(10)
                    await file_msg.delete()

        except Exception as e:
            print(f"Error in export command: {e}")
            if ctx.interaction:
                await ctx.followup.send("An error occurred while exporting the files.", ephemeral=True)
            else:
                await ctx.send("An error occurred while exporting the files.")


    @commands.hybrid_command(name='reload', description="Reload the bot's command tree")
    @commands.has_role("Owner")
    async def reload(self, ctx):
        try:
            await ctx.send("Reloading command tree...")
            commands_synced = await self.bot.tree.sync()
            await ctx.send(f"Tree.sync reloaded. {len(commands_synced)} commands updated.")
        except Exception as e:
            print(f"Error in reload command: {e}")
            await ctx.send("An error occurred while reloading the command tree.")



async def setup(bot):
    await bot.add_cog(DevCog(bot))
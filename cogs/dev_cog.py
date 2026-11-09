import discord
from discord import app_commands
from discord.ext import commands
import os

from utils.command_sync import sync_guild_commands


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
                ("nochat_channels.pkl", "The no-chat channels file does not exist."),
                ("chat_sessions.pkl", "The legacy shared chat history file does not exist."),
                ("data/chat_sessions.pkl", "The channel chat history does not exist."),
                ("data/news.pkl", "The news file does not exist.")
            ]

            files_to_send: list[discord.File] = []
            missing_files = []

            # Check which files exist and prepare them for sending
            for file_path, error_message in files_to_export:
                if os.path.exists(file_path):
                    files_to_send.append(discord.File(file_path))
                else:
                    missing_files.append(error_message)

            # Handle interaction response deferral
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=True)

            # Send existing files
            if files_to_send:
                if ctx.interaction:
                    if ctx.interaction.response.is_done():
                        await ctx.interaction.followup.send(files=files_to_send, ephemeral=True)
                    else:
                        await ctx.interaction.response.send_message(files=files_to_send, ephemeral=True)
                else:
                    await ctx.author.send(files=files_to_send)
                    await ctx.send("I sent the export to your DMs.")

            # Report missing files
            if missing_files:
                missing_msg = "Some files were not found:\n" + "\n".join(missing_files)
                if ctx.interaction:
                    if ctx.interaction.response.is_done():
                        await ctx.interaction.followup.send(missing_msg, ephemeral=True)
                    else:
                        await ctx.interaction.response.send_message(missing_msg, ephemeral=True)
                else:
                    await ctx.send(missing_msg)

        except Exception as e:
            print(f"Error in export command: {e}")
            error_msg = "An error occurred while exporting the files."
            if ctx.interaction:
                try:
                    if ctx.interaction.response.is_done():
                        await ctx.interaction.followup.send(error_msg, ephemeral=True)
                    else:
                        await ctx.interaction.response.send_message(error_msg, ephemeral=True)
                except:
                    await ctx.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @commands.hybrid_command(name="export_rp", description="Download a specific RP session file")
    @app_commands.describe(channel_id="The channel ID of the RP session to export")
    @commands.has_role("Owner")
    async def export_rp(self, ctx, channel_id: str = None):
        try:
            if not channel_id:
                await ctx.send("❌ Please provide a channel ID. Usage: `/export_rp channel_id:123456789`",
                               ephemeral=True)
                return

            channel_id_clean = ''.join(filter(str.isdigit, channel_id))

            if not channel_id_clean:
                await ctx.send("❌ Invalid channel ID format.", ephemeral=True)
                return

            session_file = f"sessions/{channel_id_clean}.json"

            # Handle interaction response deferral
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=True)

            if not os.path.exists(session_file):
                error_msg = f"❌ No RP session file found for channel ID: {channel_id_clean}"
                if ctx.interaction:
                    if ctx.interaction.response.is_done():
                        await ctx.interaction.followup.send(error_msg, ephemeral=True)
                    else:
                        await ctx.interaction.response.send_message(error_msg, ephemeral=True)
                else:
                    await ctx.send(error_msg)
                return

            # Send the file
            discord_file = discord.File(session_file, filename=f"rp_session_{channel_id_clean}.json")
            success_msg = f"✅ RP session file for channel {channel_id_clean}:"

            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(success_msg, file=discord_file, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(success_msg, file=discord_file, ephemeral=True)
            else:
                await ctx.author.send(success_msg, file=discord_file)
                await ctx.send("I sent the RP export to your DMs.")

        except Exception as e:
            print(f"Error in export_rp command: {e}")
            error_msg = f"An error occurred while exporting the RP session: {str(e)}"
            if ctx.interaction:
                try:
                    if ctx.interaction.response.is_done():
                        await ctx.interaction.followup.send(error_msg, ephemeral=True)
                    else:
                        await ctx.interaction.response.send_message(error_msg, ephemeral=True)
                except:
                    await ctx.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)


    @commands.hybrid_command(name='reload', description="Resync R0's slash commands in this server")
    @commands.has_role("Owner")
    async def reload(self, ctx):
        try:
            await ctx.defer(ephemeral=True)
            commands_synced = await sync_guild_commands(self.bot.tree)
            await ctx.send(f"Synced {len(commands_synced)} server commands.", ephemeral=True)
        except discord.HTTPException as exc:
            print(f"Error resyncing server commands: {exc}")
            await ctx.send("Unable to resync server commands.", ephemeral=True)



async def setup(bot):
    await bot.add_cog(DevCog(bot))


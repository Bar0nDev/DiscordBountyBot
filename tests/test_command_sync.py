import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from utils.command_sync import GUILD_ID, sync_guild_commands


class CommandSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_syncs_guild_before_retiring_legacy_global_slash_commands(self):
        calls = []
        slash = discord.AppCommandType.chat_input
        guild_commands = [SimpleNamespace(name="reload", type=slash)]

        async def sync(*, guild):
            self.assertEqual(guild.id, GUILD_ID)
            calls.append("sync guild")
            return guild_commands

        def global_command(name, command_type=slash):
            async def delete():
                calls.append(f"delete {name}")

            return SimpleNamespace(name=name, type=command_type, delete=delete)

        tree = SimpleNamespace(
            copy_global_to=Mock(),
            sync=sync,
            fetch_commands=AsyncMock(return_value=[
                global_command("reload"),
                global_command("update_bounty"),
                global_command("unrelated"),
                global_command("reload", discord.AppCommandType.message),
            ]),
        )
        self.assertEqual(await sync_guild_commands(tree), guild_commands)
        self.assertEqual(calls, ["sync guild", "delete reload", "delete update_bounty"])

    async def test_failed_guild_sync_does_not_remove_global_commands(self):
        tree = SimpleNamespace(
            copy_global_to=Mock(),
            sync=AsyncMock(side_effect=RuntimeError("guild sync failed")),
            fetch_commands=AsyncMock(),
        )
        with self.assertRaisesRegex(RuntimeError, "guild sync failed"):
            await sync_guild_commands(tree)
        tree.fetch_commands.assert_not_awaited()

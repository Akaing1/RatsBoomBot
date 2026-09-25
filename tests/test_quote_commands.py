from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.services.channels.quotes import QuoteService
from bot.shared.commands.quotes import QuoteCommands
from storage.migration_runner import run_migrations


class EnabledFeatures:
    @staticmethod
    def is_global_command_enabled(broadcaster_id, command):
        return True


def context(channel="channel-1", user="viewer", moderator=False):
    return SimpleNamespace(
        broadcaster=SimpleNamespace(id=channel),
        chatter=SimpleNamespace(id=user, name=user, moderator=moderator),
        reply=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_quotes_are_channel_scoped_persistent_and_keep_numbers_after_removal(tmp_path):
    path = str(tmp_path / "quotes.db")
    async with asqlite.create_pool(path) as db:
        await run_migrations(db)
        service = QuoteService(db)
        assert await service.add("channel-1", "First quote", "viewer") == 1
        assert await service.add("channel-1", "Second quote", "viewer") == 2
        assert await service.add("channel-2", "Other channel", "viewer") == 1
        assert await service.remove("channel-1", 1)
        assert not await service.remove("channel-2", 2)
        assert await service.add("channel-1", "Third quote", "viewer") == 3
        assert await service.random("channel-1") in {(2, "Second quote"), (3, "Third quote")}

    async with asqlite.create_pool(path) as db:
        service = QuoteService(db)
        assert await service.get("channel-1", 1) is None
        assert await service.get("channel-1", 3) == "Third quote"
        assert await service.get("channel-2", 1) == "Other channel"


@pytest.mark.asyncio
async def test_quote_command_add_random_lookup_and_moderator_removal(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "quotes.db")) as db:
        await run_migrations(db)
        bot = SimpleNamespace(services=SimpleNamespace(features=EnabledFeatures(), quotes=QuoteService(db)))
        command = QuoteCommands(bot)
        viewer = context()
        await command.quote.callback(command, viewer, argument="add Hello chat!")
        viewer.reply.assert_awaited_with('Quote 1 added: "Hello chat!"')
        await command.quote.callback(command, viewer, argument="random")
        viewer.reply.assert_awaited_with('Quote 1: "Hello chat!"')
        await command.quote.callback(command, viewer, argument="1")
        viewer.reply.assert_awaited_with('Quote 1: "Hello chat!"')
        await command.quote.callback(command, viewer, argument="remove 1")
        viewer.reply.assert_awaited_with("Only the broadcaster or mods can remove quotes.")
        assert await bot.services.quotes.get("channel-1", 1) == "Hello chat!"

        moderator = context(moderator=True)
        await command.quote.callback(command, moderator, argument="remove 1")
        moderator.reply.assert_awaited_with("Quote 1 removed.")
        await command.quote.callback(command, moderator, argument="random")
        moderator.reply.assert_awaited_with("No quotes have been added yet. Use !quote add <message>.")

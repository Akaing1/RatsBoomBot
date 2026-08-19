from types import SimpleNamespace

import asqlite
import pytest

from bot.services.channels.chatter_identity import ChatterIdentityService
from storage.migrations.v008_chatter_identities import migrate


class FakeBot:

    def __init__(self, users):
        self.users = {str(user.id): user for user in users}

    async def fetch_user(self, *, id=None, login=None):
        if id is not None:
            return self.users.get(str(id))

        normalized_login = str(login).casefold()
        return next((user for user in self.users.values() if user.name.casefold() == normalized_login), None)


@pytest.mark.asyncio
async def test_localized_display_name_survives_service_restart(tmp_path) -> None:
    database_path = tmp_path / "chatters.db"
    chatter = SimpleNamespace(id="23556464", name="ascii_login", display_name="日本語の名前")
    bot = FakeBot([chatter])

    async with asqlite.create_pool(str(database_path)) as database:
        async with database.acquire() as connection:
            await migrate(connection)

        service = ChatterIdentityService(bot, database)
        await service.setup()
        await service.observe("channel-1", chatter)

        resolved = await service.resolve("channel-1", "@日本語の名前")
        assert resolved.id == "23556464"

        restarted_service = ChatterIdentityService(bot, database)
        await restarted_service.setup()

        resolved_after_restart = await restarted_service.resolve("channel-1", "日本語の名前")
        assert resolved_after_restart.id == "23556464"


@pytest.mark.asyncio
async def test_resolver_accepts_login_numeric_id_and_unicode_casefold(tmp_path) -> None:
    database_path = tmp_path / "chatters.db"
    chatter = SimpleNamespace(id="123", name="localized_user", display_name="Straße")
    bot = FakeBot([chatter])

    async with asqlite.create_pool(str(database_path)) as database:
        async with database.acquire() as connection:
            await migrate(connection)

        service = ChatterIdentityService(bot, database)
        await service.setup()
        await service.observe("channel-1", chatter)

        assert (await service.resolve("channel-1", "LOCALIZED_USER")).id == "123"
        assert (await service.resolve("channel-1", "STRASSE")).id == "123"
        assert (await service.resolve("channel-1", "123")).id == "123"


@pytest.mark.asyncio
async def test_repeat_messages_do_not_write_every_time(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "chatters.db"
    chatter = SimpleNamespace(id="123", name="localized_user", display_name="表示名")
    bot = FakeBot([chatter])

    async with asqlite.create_pool(str(database_path)) as database:
        async with database.acquire() as connection:
            await migrate(connection)

        service = ChatterIdentityService(bot, database)
        await service.setup()
        await service.observe("channel-1", chatter)

        persist_calls = 0
        original_persist = service._persist

        async def count_persist(*args, **kwargs):
            nonlocal persist_calls
            persist_calls += 1
            await original_persist(*args, **kwargs)

        monkeypatch.setattr(service, "_persist", count_persist)
        await service.observe("channel-1", chatter)

        assert persist_calls == 0

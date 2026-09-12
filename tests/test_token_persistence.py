import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.bot import TwitchBot
from app.runtime import load_stored_tokens


def make_bot(database):
    bot = TwitchBot.__new__(TwitchBot)
    bot.token_database = database
    bot._token_save_lock = asyncio.Lock()
    bot._http = SimpleNamespace(_tokens={}, add_token=AsyncMock())
    return bot


@pytest.mark.asyncio
async def test_refresh_on_add_persists_new_pair_and_reloads_after_restart(tmp_path):
    database_path = str(tmp_path / "tokens.db")
    async with asqlite.create_pool(database_path) as database:
        async with database.acquire() as connection:
            await connection.execute("CREATE TABLE tokens (user_id TEXT PRIMARY KEY, token TEXT, refresh TEXT)")
        bot = make_bot(database)

        async def refresh_on_add(token, refresh):
            bot._http._tokens["viewer"] = {"token": "new-access", "refresh": "new-refresh"}
            return SimpleNamespace(user_id="viewer")

        bot._http.add_token.side_effect = refresh_on_add
        await bot.add_token("expired-access", "old-refresh")

    async with asqlite.create_pool(database_path) as database:
        async with database.acquire() as connection:
            row = await connection.fetchone("SELECT user_id, token, refresh FROM tokens")
        assert tuple(row) == ("viewer", "new-access", "new-refresh")
        restarted = make_bot(database)

        async def accept_current(token, refresh):
            restarted._http._tokens["viewer"] = {"token": token, "refresh": refresh}
            return SimpleNamespace(user_id="viewer")

        restarted._http.add_token.side_effect = accept_current
        await load_stored_tokens(restarted, database, [tuple(row)])
        restarted._http.add_token.assert_awaited_once_with("new-access", "new-refresh")


@pytest.mark.asyncio
async def test_refresh_event_saves_latest_pair_not_delayed_payload(tmp_path, caplog):
    async with asqlite.create_pool(str(tmp_path / "tokens.db")) as database:
        async with database.acquire() as connection:
            await connection.execute("CREATE TABLE tokens (user_id TEXT PRIMARY KEY, token TEXT, refresh TEXT)")
            await connection.execute("INSERT INTO tokens VALUES ('viewer', 'old', 'old-refresh')")
        bot = make_bot(database)
        bot._http._tokens["viewer"] = {"token": "latest-secret", "refresh": "latest-refresh-secret"}
        payload = SimpleNamespace(user_id="viewer", token="stale-secret", refresh_token="stale-refresh")
        await bot.event_token_refreshed(payload)
        async with database.acquire() as connection:
            row = await connection.fetchone("SELECT token, refresh FROM tokens WHERE user_id = 'viewer'")
        assert tuple(row) == ("latest-secret", "latest-refresh-secret")
        assert "latest-secret" not in caplog.text
        assert "latest-refresh-secret" not in caplog.text


@pytest.mark.asyncio
async def test_delayed_refresh_does_not_recreate_removed_token(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "tokens.db")) as database:
        async with database.acquire() as connection:
            await connection.execute("CREATE TABLE tokens (user_id TEXT PRIMARY KEY, token TEXT, refresh TEXT)")
        bot = make_bot(database)
        await bot.event_token_refreshed(SimpleNamespace(user_id="removed"))
        async with database.acquire() as connection:
            assert await connection.fetchone("SELECT * FROM tokens") is None

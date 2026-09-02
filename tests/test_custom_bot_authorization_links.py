from types import SimpleNamespace

import asqlite
import pytest

import web.channel.routers.oauth as oauth_router
from storage.custom_bot_authorization_repository import CustomBotAuthorizationRequest, consume_custom_bot_authorization_request, create_custom_bot_authorization_request, get_custom_bot_authorization_request, hash_authorization_state
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_custom_bot_authorization_link_is_hashed_and_single_use(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "authorization.db")) as database:
        await run_migrations(database)
        state = await create_custom_bot_authorization_request(database, "channel-1", "bot-1", "characterbot", "CharacterBot")

        async with database.acquire() as connection:
            row = await connection.fetchone("SELECT state_hash FROM custom_bot_authorization_requests")

        assert state.startswith("custom_bot_")
        assert row["state_hash"] == hash_authorization_state(state)
        assert state not in row["state_hash"]
        assert (await get_custom_bot_authorization_request(database, state)).expected_bot_login == "characterbot"
        assert (await consume_custom_bot_authorization_request(database, state)).broadcaster_id == "channel-1"
        assert await consume_custom_bot_authorization_request(database, state) is None


@pytest.mark.asyncio
async def test_new_custom_bot_authorization_link_replaces_previous_channel_link(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "authorization.db")) as database:
        await run_migrations(database)
        first_state = await create_custom_bot_authorization_request(database, "channel-1", "bot-1", "firstbot", "FirstBot")
        second_state = await create_custom_bot_authorization_request(database, "channel-1", "bot-2", "secondbot", "SecondBot")

        assert await get_custom_bot_authorization_request(database, first_state) is None
        assert (await get_custom_bot_authorization_request(database, second_state)).expected_bot_user_id == "bot-2"


@pytest.mark.asyncio
async def test_expired_custom_bot_authorization_link_is_rejected(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "authorization.db")) as database:
        await run_migrations(database)
        state = await create_custom_bot_authorization_request(database, "channel-1", "bot-1", "characterbot", "CharacterBot")

        async with database.acquire() as connection:
            await connection.execute("UPDATE custom_bot_authorization_requests SET expires_at = datetime('now', '-1 minute')")

        assert await get_custom_bot_authorization_request(database, state) is None
        assert await consume_custom_bot_authorization_request(database, state) is None


@pytest.mark.asyncio
async def test_custom_bot_callback_rejects_a_different_authorized_account(monkeypatch) -> None:
    authorization = CustomBotAuthorizationRequest("channel-1", "expected-id", "expectedbot", "ExpectedBot")
    runtime_bot = SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(get_state=lambda broadcaster_id: SimpleNamespace(premium_enabled=True))))

    async def consume_request(database, state):
        return authorization

    async def exchange_token(**kwargs):
        return SimpleNamespace(access_token="token")

    async def fetch_user(access_token):
        return SimpleNamespace(user_id="wrong-id", login="wrongbot", display_name="WrongBot")

    monkeypatch.setattr(oauth_router, "get_db", lambda: object())
    monkeypatch.setattr(oauth_router, "get_bot", lambda: runtime_bot)
    monkeypatch.setattr(oauth_router, "consume_custom_bot_authorization_request", consume_request)
    monkeypatch.setattr(oauth_router, "exchange_code_for_token", exchange_token)
    monkeypatch.setattr(oauth_router, "fetch_twitch_user", fetch_user)
    monkeypatch.setattr(oauth_router, "render_custom_bot_result", lambda request, title, message, **kwargs: {"title": title, "message": message, **kwargs})

    result = await oauth_router.custom_bot_callback(SimpleNamespace(), "code", "custom_bot_state", None)

    assert result["title"] == "Wrong Twitch account"
    assert "@expectedbot" in result["message"]
    assert "@wrongbot" in result["message"]
    assert result["status_code"] == 400

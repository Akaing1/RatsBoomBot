import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

import web.channel.routers.dashboard as dashboard_router
from bot.profiles import ChannelProfile, activate_profile, clear_profiles
from bot.services.support.moderation import ModerationService
from web.channel.auth import CHANNEL_USER_ID_KEY


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


def channel_request(method: str = "GET") -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": "/channel/protected-users/search",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })


@pytest.mark.asyncio
async def test_protected_user_search_resolves_twitch_identity(monkeypatch) -> None:
    twitch_user = SimpleNamespace(id="123", name="viewer", display_name="Viewer")
    runtime_bot = SimpleNamespace(
        bot_id="bot-id",
        services=SimpleNamespace(),
        fetch_user=AsyncMock(return_value=twitch_user)
    )
    activate_profile("channel-1", ChannelProfile(channel_name="channel"))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)

    response = await dashboard_router.search_channel_protected_user(channel_request(), "@Viewer")
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["user"] == {
        "id": "123",
        "login": "viewer",
        "display_name": "Viewer",
        "already_protected": False,
        "automatic": False
    }
    runtime_bot.fetch_user.assert_awaited_once_with(login="viewer")


@pytest.mark.asyncio
async def test_protected_user_search_marks_existing_user(monkeypatch) -> None:
    twitch_user = SimpleNamespace(id="123", name="viewer", display_name="Viewer")
    runtime_bot = SimpleNamespace(
        bot_id="bot-id",
        services=SimpleNamespace(),
        fetch_user=AsyncMock(return_value=twitch_user)
    )
    activate_profile("channel-1", ChannelProfile(channel_name="channel", protected_user_ids=("123",)))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)

    response = await dashboard_router.search_channel_protected_user(channel_request(), "viewer")
    payload = json.loads(response.body)

    assert payload["user"]["already_protected"] is True


def test_automated_moderation_honors_profile_protected_users() -> None:
    activate_profile("channel-1", ChannelProfile(channel_name="channel", protected_user_ids=("protected",)))
    service = ModerationService(SimpleNamespace(bot_id="bot-id"), db=None)

    assert service.is_protected_user("channel-1", "protected") is True
    assert service.is_protected_user("channel-1", "viewer") is False

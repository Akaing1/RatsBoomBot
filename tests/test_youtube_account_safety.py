import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.channels.live_chat import LiveChatService, YouTubeConnection
from web.channel import auth
from web.channel.routers import youtube as youtube_router
from web.shared.youtube_oauth import YouTubeChannel, YouTubeTokenResponse


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["account-a", None])
async def test_youtube_callback_rejects_account_switch_or_unbound_state(monkeypatch, owner):
    request = SimpleNamespace(session={
        auth.CHANNEL_USER_ID_KEY: "account-b",
        auth.YOUTUBE_OAUTH_STATE_KEY: "valid-state",
        auth.YOUTUBE_OAUTH_OWNER_KEY: owner,
    })
    exchange = AsyncMock()
    monkeypatch.setattr(youtube_router, "exchange_youtube_code", exchange)
    response = await youtube_router.youtube_callback(request, code="code", state="valid-state")
    assert "youtube_result=error" in response.headers["location"]
    exchange.assert_not_awaited()
    assert auth.YOUTUBE_OAUTH_STATE_KEY not in request.session
    assert auth.YOUTUBE_OAUTH_OWNER_KEY not in request.session


@pytest.mark.asyncio
async def test_youtube_callback_accepts_initiating_account(monkeypatch):
    request = SimpleNamespace(session={
        auth.CHANNEL_USER_ID_KEY: "account-a",
        auth.YOUTUBE_OAUTH_STATE_KEY: "valid-state",
        auth.YOUTUBE_OAUTH_OWNER_KEY: "account-a",
    })
    token = SimpleNamespace(access_token="access")
    channel = YouTubeChannel("youtube-a", "Channel A")
    connect = AsyncMock()
    monkeypatch.setattr(youtube_router, "exchange_youtube_code", AsyncMock(return_value=token))
    monkeypatch.setattr(youtube_router, "fetch_youtube_channel", AsyncMock(return_value=channel))
    monkeypatch.setattr(youtube_router, "get_bot", lambda: SimpleNamespace(
        services=SimpleNamespace(live_chat=SimpleNamespace(connect_youtube=connect))
    ))
    response = await youtube_router.youtube_callback(request, code="code", state="valid-state")
    assert "youtube_result=success" in response.headers["location"]
    connect.assert_awaited_once_with("account-a", channel, token)


@pytest.mark.parametrize("action", ["logout", "switch"])
def test_channel_account_change_clears_pending_youtube_authorization(action):
    request = SimpleNamespace(session={
        auth.CHANNEL_USER_ID_KEY: "account-a",
        auth.YOUTUBE_OAUTH_STATE_KEY: "state",
        auth.YOUTUBE_OAUTH_OWNER_KEY: "account-a",
    })
    if action == "logout":
        auth.logout_channel_user(request)
    else:
        auth.login_channel_user(request, "account-b", "b", "B")
    assert auth.YOUTUBE_OAUTH_STATE_KEY not in request.session
    assert auth.YOUTUBE_OAUTH_OWNER_KEY not in request.session


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["connect", "disconnect", "send"])
async def test_youtube_connection_operations_wait_for_refresh(operation):
    service = LiveChatService(None)
    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()
    finished = []

    async def refresh(_):
        refresh_started.set()
        await release_refresh.wait()
        finished.append("refresh")
        return object()

    async def operation_body(*args):
        finished.append(operation)

    service._refresh_access_token_if_needed = refresh
    service._connect_youtube_locked = operation_body
    service._disconnect_youtube_locked = operation_body
    service._send_youtube_message_locked = operation_body
    refreshing = asyncio.create_task(service._ensure_access_token("channel"))
    await refresh_started.wait()
    if operation == "connect":
        changing = asyncio.create_task(service.connect_youtube("channel", None, None))
    elif operation == "disconnect":
        changing = asyncio.create_task(service.disconnect_youtube("channel"))
    else:
        changing = asyncio.create_task(service.send_youtube_message("channel", "hello"))
    await asyncio.sleep(0)
    assert finished == []
    release_refresh.set()
    await asyncio.wait_for(asyncio.gather(refreshing, changing), timeout=2)
    assert finished == ["refresh", operation]


@pytest.mark.asyncio
async def test_account_replacement_persists_new_credentials_after_inflight_refresh():
    writes = []

    class Database:
        def acquire(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql, args):
            writes.append(args)

    service = LiveChatService(Database())
    service.connections["channel"] = YouTubeConnection(
        "channel", "old-id", "Old", "old-access", "old-refresh", datetime.now(UTC).isoformat()
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def post(*args, **kwargs):
        started.set()
        await release.wait()
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None,
            json=lambda: {"access_token": "refreshed-old", "expires_in": 3600},
        )

    service.client = SimpleNamespace(post=post)
    refreshing = asyncio.create_task(service._ensure_access_token("channel"))
    await started.wait()
    token = YouTubeTokenResponse(
        "new-access", "new-refresh", (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )
    replacing = asyncio.create_task(service.connect_youtube(
        "channel", YouTubeChannel("new-id", "New"), token
    ))
    await asyncio.sleep(0)
    assert writes == []
    release.set()
    await asyncio.wait_for(asyncio.gather(refreshing, replacing), timeout=2)
    assert writes[0][0] == "refreshed-old"
    assert writes[-1][1:5] == ("new-id", "New", "new-access", "new-refresh")
    assert service.connections["channel"].access_token == "new-access"

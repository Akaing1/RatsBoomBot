import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import asqlite
import httpx
import pytest
from starlette.requests import Request

import web.channel.routers.dashboard as dashboard_router
from bot.services.channels.live_chat import LiveChatService, UnifiedChatMessage, message_matches_view, normalize_chat_view
from storage.migration_runner import run_migrations
from web.channel.routers.dashboard import get_ad_status
from web.admin.auth import CSRF_SESSION_KEY
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.shared.youtube_oauth import YOUTUBE_CHAT_SCOPE, YouTubeChannel, YouTubeTokenResponse, build_youtube_oauth_url


def twitch_payload(text: str, message_id: str = "message-1"):
    return SimpleNamespace(
        id=message_id,
        text=text,
        timestamp=datetime(2026, 9, 19, tzinfo=UTC),
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(
            id="viewer-1",
            name="viewer",
            display_name="Viewer",
            is_broadcaster=False,
            is_moderator=True,
            is_vip=False,
            is_subscriber=True
        )
    )


def test_twitch_messages_are_split_between_chat_and_commands():
    service = LiveChatService(None)
    chat = service.publish_twitch(twitch_payload("hello", "chat"))
    command = service.publish_twitch(twitch_payload("  !points", "command"))

    assert chat.kind == "chat"
    assert command.kind == "command"
    assert [item["message"] for item in service.history("channel-1", "chat")] == ["hello"]
    assert [item["message"] for item in service.history("channel-1", "commands")] == ["  !points"]
    assert [item["message"] for item in service.history("channel-1", "both")] == ["hello", "  !points"]
    assert chat.badges == ("Mod", "Subscriber")


def test_tagged_bot_response_is_kept_with_commands_without_classifying_all_bot_messages():
    service = LiveChatService(None)
    service.tag_command_response("channel-1", "command-response")

    response = service.publish_twitch(twitch_payload("You have 500 points.", "command-response"))
    unrelated = service.publish_twitch(twitch_payload("A raid boss is approaching!", "unrelated-bot-message"))

    assert response.kind == "command"
    assert unrelated.kind == "chat"
    assert [item["message"] for item in service.history("channel-1", "commands")] == ["You have 500 points."]
    assert [item["message"] for item in service.history("channel-1", "chat")] == ["A raid boss is approaching!"]


def test_youtube_messages_are_normalized_and_deduplicated():
    service = LiveChatService(None)
    item = {
        "id": "youtube-message",
        "snippet": {"displayMessage": "!raid", "hasDisplayContent": True, "publishedAt": "2026-09-19T12:00:00Z"},
        "authorDetails": {
            "channelId": "youtube-user",
            "displayName": "YouTube Viewer",
            "profileImageUrl": "https://example.com/avatar.png",
            "isChatModerator": True,
            "isChatSponsor": True
        }
    }

    service._publish_youtube_items("channel-1", [item, item])
    messages = service.history("channel-1")

    assert len(messages) == 1
    assert messages[0]["platform"] == "youtube"
    assert messages[0]["kind"] == "command"
    assert messages[0]["badges"] == ["Mod", "Member"]
    assert "avatar_url" not in messages[0]


def test_chat_view_normalization_and_matching():
    chat = UnifiedChatMessage("1", "twitch", "chat", "viewer", "Viewer", "hello", datetime.now(UTC).isoformat())
    command = UnifiedChatMessage("2", "youtube", "command", "viewer", "Viewer", "!hello", datetime.now(UTC).isoformat())

    assert normalize_chat_view("invalid") == "both"
    assert message_matches_view(chat, "chat")
    assert not message_matches_view(command, "chat")
    assert message_matches_view(command, "commands")
    assert message_matches_view(chat, "both")


@pytest.mark.asyncio
async def test_connections_and_widget_tokens_persist(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_ID", "client")
    monkeypatch.setattr("bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_SECRET", "secret")
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    async with asqlite.create_pool(str(tmp_path / "chat.db")) as db:
        await run_migrations(db)
        service = LiveChatService(db)
        await service.setup()
        first_token = await service.get_or_create_widget_token("channel-1")
        await service.connect_youtube(
            "channel-1",
            YouTubeChannel("youtube-channel", "Test Channel"),
            YouTubeTokenResponse("access", "refresh", expires_at)
        )

        restarted = LiveChatService(db)
        await restarted.setup()
        state = restarted.get_youtube_state("channel-1")

        assert restarted.resolve_widget_token(first_token) == "channel-1"
        assert state.connected
        assert state.channel_id == "youtube-channel"
        assert state.channel_title == "Test Channel"

        replacement = await restarted.regenerate_widget_token("channel-1")
        assert replacement != first_token
        assert restarted.resolve_widget_token(first_token) is None
        assert restarted.resolve_widget_token(replacement) == "channel-1"

        await restarted.disconnect_youtube("channel-1")
        assert not restarted.get_youtube_state("channel-1").connected


def test_youtube_authorization_uses_chat_write_scope(monkeypatch):
    monkeypatch.setattr("web.shared.youtube_oauth.settings.YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setattr("web.shared.youtube_oauth.settings.YOUTUBE_REDIRECT_URI", "https://example.com/oauth/youtube/connect")
    query = parse_qs(urlparse(build_youtube_oauth_url("secure-state")).query)

    assert query["scope"] == [YOUTUBE_CHAT_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["state"] == ["secure-state"]
    assert query["scope"] == ["https://www.googleapis.com/auth/youtube.force-ssl"]


@pytest.mark.asyncio
async def test_youtube_dashboard_message_uses_active_live_chat():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "sent-message"})

    service = LiveChatService(None)
    service.connections["channel-1"] = SimpleNamespace(
        access_token="access",
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )
    service.active_youtube_chat_ids["channel-1"] = "live-chat-1"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service.client = client
        result = await service.send_youtube_message("channel-1", "Hello both chats")

    assert result["id"] == "sent-message"
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/liveChat/messages")
    assert b'"liveChatId":"live-chat-1"' in requests[0].content
    assert b'"messageText":"Hello both chats"' in requests[0].content


@pytest.mark.asyncio
async def test_youtube_dashboard_message_requires_active_chat():
    service = LiveChatService(None)
    service.connections["channel-1"] = SimpleNamespace()

    with pytest.raises(ValueError, match="No active YouTube live chat"):
        await service.send_youtube_message("channel-1", "Hello")


@pytest.mark.asyncio
async def test_ad_status_reports_running_and_offline_states():
    now = datetime.now(UTC)
    live = SimpleNamespace(
        id="channel-1",
        is_live=True,
        fetch_ad_schedule=AsyncMock(return_value=SimpleNamespace(
            last_ad_at=now - timedelta(seconds=10),
            next_ad_at=now + timedelta(minutes=30),
            duration=60
        ))
    )
    offline = SimpleNamespace(id="channel-2", is_live=False)

    running = await get_ad_status(live)
    offline_status = await get_ad_status(offline)

    assert running["state"] == "running"
    assert running["ends_at"] is not None
    assert offline_status["state"] == "offline"


@pytest.mark.asyncio
async def test_dashboard_can_send_to_twitch_and_youtube(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    twitch_channel = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=True)))
    live_chat = SimpleNamespace(send_youtube_message=AsyncMock(return_value={"id": "youtube-message"}))
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        live_chat=live_chat
    )
    runtime_bot = SimpleNamespace(services=services, create_partialuser=lambda broadcaster_id: twitch_channel)
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/chat/send", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_send_chat_message(request, "Hello both chats", "both", "csrf")
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["sent"] == ["twitch", "youtube"]
    twitch_channel.send_message.assert_awaited_once_with(sender="channel-1", message="Hello both chats")
    live_chat.send_youtube_message.assert_awaited_once_with("channel-1", "Hello both chats")


@pytest.mark.asyncio
async def test_dashboard_both_target_uses_twitch_when_youtube_is_offline(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    twitch_channel = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=True)))
    live_chat = SimpleNamespace(send_youtube_message=AsyncMock(side_effect=ValueError("No active YouTube live chat is available.")))
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        live_chat=live_chat
    )
    runtime_bot = SimpleNamespace(services=services, create_partialuser=lambda broadcaster_id: twitch_channel)
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/chat/send", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_send_chat_message(request, "Twitch fallback", "both", "csrf")
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload == {"sent": ["twitch"], "errors": {}}
    twitch_channel.send_message.assert_awaited_once()
    live_chat.send_youtube_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_youtube_target_explains_when_youtube_is_offline(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    live_chat = SimpleNamespace(send_youtube_message=AsyncMock(side_effect=ValueError("No active YouTube live chat is available.")))
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        live_chat=live_chat
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/chat/send", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_send_chat_message(request, "YouTube only", "youtube", "csrf")
    payload = json.loads(response.body)

    assert response.status_code == 400
    assert payload["sent"] == []
    assert payload["errors"]["youtube"].startswith("YouTube is offline.")


def test_dashboard_templates_include_reply_composer_and_spanning_chat_layout():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    customization = open("web/templates/shared/profile_inputs.html", encoding="utf-8").read()
    dashboard_styles = open("web/static/css/style.css", encoding="utf-8").read()
    widget_styles = open("web/static/css/chat-widget.css", encoding="utf-8").read()
    chat_script = open("web/static/js/live-chat-feed.js", encoding="utf-8").read()

    assert 'data-stream-url="/channel/api/chat/stream?view=chat"' in dashboard
    assert 'data-stream-url="/channel/api/chat/stream?view=commands"' in dashboard
    assert 'data-activity-tab="redeems"' in dashboard
    assert 'data-activity-tab="checkins"' in dashboard
    assert dashboard.index("channel-live-layout") < dashboard.index('include "channel/raid_summary.html"')
    assert 'data-chat-composer' in dashboard
    assert 'data-chat-target="twitch"' in dashboard
    assert 'data-chat-target="youtube"' in dashboard
    assert 'data-chat-target="both"' in dashboard
    assert 'data-ad-status' in dashboard
    assert dashboard.count("Viewer queue") == 1
    assert "Connect YouTube Channel" in customization
    assert "('chat', 'Chat'" in customization
    assert "('commands', 'Commands'" in customization
    assert "('both', 'Both'" in customization
    assert ".live-chat-feed::-webkit-scrollbar" in dashboard_styles
    assert "#viewer-queue-content::-webkit-scrollbar" in dashboard_styles
    assert "#viewer-queue-content { max-height: 430px; overflow-y: auto;" in dashboard_styles
    assert "background: #0f1115" in widget_styles
    assert "background: transparent" not in widget_styles.split("body {", 1)[0]
    assert ".widget-chat-feed::-webkit-scrollbar" in widget_styles
    assert "overflow-y: auto" in widget_styles
    assert "shouldFollowNewest" in chat_script
    assert "if (shouldFollowNewest)" in chat_script
    assert 'grid-template-areas: "stream gambling chat" "queue activity chat"' in dashboard_styles
    assert "grid-template-rows: max-content minmax(540px,auto)" in dashboard_styles

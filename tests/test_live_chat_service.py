from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import asqlite
import pytest

from bot.services.channels.live_chat import LiveChatService, UnifiedChatMessage, message_matches_view, normalize_chat_view
from storage.migration_runner import run_migrations
from web.shared.youtube_oauth import YOUTUBE_READONLY_SCOPE, YouTubeChannel, YouTubeTokenResponse, build_youtube_oauth_url


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


def test_youtube_authorization_uses_read_only_scope(monkeypatch):
    monkeypatch.setattr("web.shared.youtube_oauth.settings.YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setattr("web.shared.youtube_oauth.settings.YOUTUBE_REDIRECT_URI", "https://example.com/oauth/youtube/connect")
    query = parse_qs(urlparse(build_youtube_oauth_url("secure-state")).query)

    assert query["scope"] == [YOUTUBE_READONLY_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["state"] == ["secure-state"]
    assert "youtube.force-ssl" not in query["scope"][0]


def test_dashboard_templates_keep_chat_read_only_and_raid_boss_below():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    customization = open("web/templates/shared/profile_inputs.html", encoding="utf-8").read()

    assert 'data-stream-url="/channel/api/chat/stream?view=chat"' in dashboard
    assert 'data-stream-url="/channel/api/chat/stream?view=commands"' in dashboard
    assert 'data-activity-tab="redeems"' in dashboard
    assert 'data-activity-tab="checkins"' in dashboard
    assert dashboard.index("channel-live-layout") < dashboard.index('include "channel/raid_summary.html"')
    assert "reply" not in dashboard.lower()
    assert "Connect YouTube Channel" in customization
    assert "('chat', 'Chat'" in customization
    assert "('commands', 'Commands'" in customization
    assert "('both', 'Both'" in customization

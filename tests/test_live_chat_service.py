import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import asqlite
import httpx
import pytest
from starlette.requests import Request

import web.channel.routers.dashboard as dashboard_router
from bot.services.channels.live_chat import ChatBadge, ChatSegment, LiveChatService, UnifiedChatMessage, message_matches_view, normalize_chat_view
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
    bot = SimpleNamespace(get_command=lambda name: object() if name == "points" else None)
    service = LiveChatService(None, bot=bot)
    chat = service.publish_twitch(twitch_payload("hello", "chat"))
    command = service.publish_twitch(twitch_payload("  !points", "command"))
    unknown = service.publish_twitch(twitch_payload("!not-a-command", "unknown"))

    assert chat.kind == "chat"
    assert command.kind == "command"
    assert unknown.kind == "chat"
    assert [item["message"] for item in service.history("channel-1", "chat")] == ["hello", "!not-a-command"]
    assert [item["message"] for item in service.history("channel-1", "commands")] == ["  !points"]
    assert [item["message"] for item in service.history("channel-1", "both")] == ["hello", "  !points", "!not-a-command"]
    assert chat.badges == (
        ChatBadge("moderator", "Mod"),
        ChatBadge("subscriber", "Subscriber")
    )
    assert chat.accent == "moderator"


def test_twitch_first_time_and_role_accents_follow_display_priority():
    service = LiveChatService(None)
    first_time = twitch_payload("Hello!", "first-time")
    first_time.type = "user_intro"
    broadcaster = twitch_payload("hello", "broadcaster")
    broadcaster.chatter.is_broadcaster = True
    broadcaster.badges = [SimpleNamespace(set_id="staff", id="1", info="")]
    staff = twitch_payload("hello", "staff")
    staff.badges = [SimpleNamespace(set_id="staff", id="1", info="")]
    vip = twitch_payload("hello", "vip")
    vip.chatter.is_moderator = False
    vip.chatter.is_vip = True
    artist = twitch_payload("hello", "artist")
    artist.chatter.is_moderator = False
    artist.badges = [SimpleNamespace(set_id="artist-badge", id="1", info="")]
    subscriber = twitch_payload("hello", "subscriber")
    subscriber.chatter.is_moderator = False

    assert service.publish_twitch(first_time).accent == "first-time"
    assert service.publish_twitch(broadcaster).accent == "broadcaster"
    assert service.publish_twitch(staff).accent == "staff"
    assert service.publish_twitch(vip).accent == "vip"
    assert service.publish_twitch(artist).accent == "artist"
    assert service.publish_twitch(subscriber).accent == "subscriber"


def test_twitch_eventsub_badges_use_cached_official_artwork():
    service = LiveChatService(None)
    badge = ChatBadge(
        "moderator",
        "Moderator",
        "https://static-cdn.jtvnw.net/badges/v1/mod/1",
        "https://static-cdn.jtvnw.net/badges/v1/mod/2",
        "https://static-cdn.jtvnw.net/badges/v1/mod/4"
    )
    service.twitch_badge_cache["channel-1"] = (0.0, {("moderator", "1"): badge})
    payload = twitch_payload("hello", "badged")
    payload.badges = [SimpleNamespace(set_id="moderator", id="1", info="")]

    message = service.publish_twitch(payload)

    assert message.badges == (badge,)
    assert message.as_dict()["badges"][0]["url_4x"].endswith("/4")


def test_twitch_message_fragments_preserve_native_emotes():
    service = LiveChatService(None)
    payload = twitch_payload("Hello Kappa!", "native-emote")
    payload.fragments = [
        SimpleNamespace(type="text", text="Hello ", emote=None),
        SimpleNamespace(type="emote", text="Kappa", emote=SimpleNamespace(id="25", format=["static"])),
        SimpleNamespace(type="text", text="!", emote=None)
    ]

    message = service.publish_twitch(payload)
    serialized = message.as_dict()["segments"]

    assert serialized == [
        {"type": "text", "text": "Hello ", "url": None, "provider": None},
        {
            "type": "emote",
            "text": "Kappa",
            "url": "https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0",
            "provider": "twitch"
        },
        {"type": "text", "text": "!", "url": None, "provider": None}
    ]


def test_twitch_message_prefers_animated_native_emotes_when_available():
    service = LiveChatService(None)
    payload = twitch_payload("Party", "animated-emote")
    payload.fragments = [
        SimpleNamespace(type="emote", text="Party", emote=SimpleNamespace(id="emote-id", format=["static", "animated"]))
    ]

    message = service.publish_twitch(payload)

    assert message.segments[0].url == "https://static-cdn.jtvnw.net/emoticons/v2/emote-id/animated/dark/2.0"


def test_7tv_emotes_are_applied_only_to_plain_text_fragments():
    service = LiveChatService(None)
    service.seventv_global_emotes = {
        "GlobalRat": ChatSegment("emote", "GlobalRat", "https://cdn.7tv.app/emote/global/2x.webp", "7tv")
    }
    service.seventv_channel_emotes["channel-1"] = {
        "ChannelRat": ChatSegment("emote", "ChannelRat", "https://cdn.7tv.app/emote/channel/2x.webp", "7tv")
    }
    payload = twitch_payload("GlobalRat ChannelRat", "7tv-emotes")

    message = service.publish_twitch(payload)

    assert [(segment.type, segment.text, segment.provider) for segment in message.segments] == [
        ("emote", "GlobalRat", "7tv"),
        ("text", " ", None),
        ("emote", "ChannelRat", "7tv")
    ]


def test_parse_7tv_emotes_builds_allowlisted_cdn_urls():
    emotes = LiveChatService._parse_seventv_emotes({
        "emotes": [
            {"name": "RatJam", "data": {"id": "01ABC123"}},
            {"name": "Unsafe", "data": {"id": "../not-safe"}},
            {"name": "", "data": {"id": "missing-name"}}
        ]
    })

    assert emotes == {
        "RatJam": ChatSegment("emote", "RatJam", "https://cdn.7tv.app/emote/01ABC123/2x.webp", "7tv")
    }


def test_parse_twitch_emotes_prefers_animated_cdn_assets():
    emotes = LiveChatService._parse_twitch_emotes({
        "data": [{"id": "emote/id", "name": "RatDance", "format": ["static", "animated"]}]
    }, "available")

    assert emotes == [{
        "id": "emote/id",
        "name": "RatDance",
        "url": "https://static-cdn.jtvnw.net/emoticons/v2/emote%2Fid/animated/dark/2.0",
        "provider": "twitch",
        "scope": "available",
        "owner_id": ""
    }]


@pytest.mark.asyncio
async def test_fetch_twitch_user_emotes_paginates_without_unsupported_page_size():
    service = LiveChatService(None)
    service._fetch_twitch_emote_page = AsyncMock(side_effect=[
        {
            "data": [{"id": "1", "name": "FirstChannel", "owner_id": "101", "format": ["static"]}],
            "pagination": {"cursor": "next-page"}
        },
        {
            "data": [{"id": "2", "name": "SecondChannel", "owner_id": "202", "format": ["static"]}],
            "pagination": {}
        },
        {
            "data": [
                {"id": "101", "display_name": "Channel One", "profile_image_url": "https://example.com/one.png"},
                {"id": "202", "display_name": "Channel Two", "profile_image_url": "https://example.com/two.png"}
            ]
        }
    ])

    emotes = await service._fetch_twitch_user_emotes("channel-1", "secret")

    first_params = service._fetch_twitch_emote_page.await_args_list[0].args[2]
    second_params = service._fetch_twitch_emote_page.await_args_list[1].args[2]
    assert first_params == {"user_id": "channel-1", "broadcaster_id": "channel-1"}
    assert "first" not in first_params
    assert second_params == {"user_id": "channel-1", "broadcaster_id": "channel-1", "after": "next-page"}
    assert [(item["group"], item["group_key"]) for item in emotes] == [
        ("Channel One", "twitch:101"),
        ("Channel Two", "twitch:202")
    ]


def test_twitch_messages_tagging_the_broadcaster_are_highlighted():
    service = LiveChatService(None)
    payload = twitch_payload("Hey @Channel!", "mention")
    payload.fragments = [
        SimpleNamespace(type="text", text="Hey ", mention=None, emote=None),
        SimpleNamespace(type="mention", text="@Channel", mention=SimpleNamespace(id="channel-1"), emote=None),
        SimpleNamespace(type="text", text="!", mention=None, emote=None)
    ]

    message = service.publish_twitch(payload)

    assert message.mentioned is True
    assert message.as_dict()["mentioned"] is True


def test_configured_chat_bot_messages_are_marked_for_quieter_display():
    chat_identity = SimpleNamespace(is_custom_bot=lambda user_id: user_id == "custom-bot")
    bot = SimpleNamespace(bot_id="rats-bot", services=SimpleNamespace(chat_identity=chat_identity))
    service = LiveChatService(None, bot=bot)
    rats_payload = twitch_payload("RatsBoomBot response", "rats-bot-message")
    rats_payload.chatter.id = "rats-bot"
    custom_payload = twitch_payload("Custom bot response", "custom-bot-message")
    custom_payload.chatter.id = "custom-bot"

    assert service.publish_twitch(rats_payload).is_bot is True
    assert service.publish_twitch(custom_payload).is_bot is True


def test_any_chatter_with_twitch_chat_bot_badge_is_marked_for_quieter_display():
    service = LiveChatService(None)
    payload = twitch_payload("Third-party bot response", "badged-bot-message")
    payload.chatter.id = "unconfigured-third-party-bot"
    payload.badges = [SimpleNamespace(set_id="bot", id="1", info="")]

    message = service.publish_twitch(payload)

    assert message.is_bot is True
    assert message.badges[0].title == "Chat Bot"


@pytest.mark.asyncio
async def test_twitch_owner_lookup_isolates_invalid_ids_without_losing_valid_channels():
    service = LiveChatService(None)

    async def fetch_page(_, path, params):
        assert path == "/users"
        owner_ids = params["id"]

        if "999" in owner_ids:
            request = httpx.Request("GET", "https://api.twitch.tv/helix/users")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("bad owner", request=request, response=response)

        return {"data": [
            {"id": owner_id, "display_name": f"Channel {owner_id}", "profile_image_url": f"https://example.com/{owner_id}.png"}
            for owner_id in owner_ids
        ]}

    service._fetch_twitch_emote_page = AsyncMock(side_effect=fetch_page)

    names = await service._fetch_twitch_owner_names("secret", {"101", "202", "999", "not-a-user"})

    assert names == {"101": "Channel 101", "202": "Channel 202"}
    assert service.twitch_emote_owner_images == {
        "101": "https://example.com/101.png",
        "202": "https://example.com/202.png"
    }


@pytest.mark.asyncio
async def test_emote_catalog_combines_twitch_and_live_7tv_caches():
    service = LiveChatService(None, bot=SimpleNamespace(tokens={"channel-1": {"token": "secret"}}))
    service.client = SimpleNamespace()
    service._fetch_twitch_user_emotes = AsyncMock(return_value=[{
        "name": "TwitchRat", "url": "https://static-cdn.jtvnw.net/emoticons/v2/1/static/dark/2.0",
        "provider": "twitch", "scope": "available"
    }])
    service.seventv_global_emotes["GlobalRat"] = ChatSegment(
        "emote", "GlobalRat", "https://cdn.7tv.app/emote/global/2x.webp", "7tv"
    )
    service.seventv_channel_emotes["channel-1"] = {
        "ChannelRat": ChatSegment("emote", "ChannelRat", "https://cdn.7tv.app/emote/channel/2x.webp", "7tv")
    }

    catalog = await service.get_emote_catalog("channel-1")

    assert catalog["complete_twitch_catalog"] is True
    assert catalog["twitch_reconnect_required"] is False
    assert [item["name"] for item in catalog["emotes"]] == ["TwitchRat", "ChannelRat", "GlobalRat"]
    assert {item["group"] for item in catalog["emotes"] if item["provider"] == "7tv"} == {"7TV"}


@pytest.mark.asyncio
async def test_emote_catalog_preserves_names_that_only_differ_by_case():
    service = LiveChatService(None, bot=SimpleNamespace(tokens={"channel-1": {"token": "secret"}}))
    service.client = SimpleNamespace()
    service._fetch_twitch_user_emotes = AsyncMock(return_value=[
        {
            "id": "1", "name": "RatJam", "url": "https://static-cdn.jtvnw.net/emoticons/v2/1/static/dark/2.0",
            "provider": "twitch", "scope": "available", "group": "Channel A", "group_key": "twitch:a"
        },
        {
            "id": "2", "name": "ratjam", "url": "https://static-cdn.jtvnw.net/emoticons/v2/2/static/dark/2.0",
            "provider": "twitch", "scope": "available", "group": "Channel B", "group_key": "twitch:b"
        }
    ])

    catalog = await service.get_emote_catalog("channel-1")

    assert [item["name"] for item in catalog["emotes"]] == ["RatJam", "ratjam"]


@pytest.mark.asyncio
async def test_emote_catalog_falls_back_when_user_emote_scope_is_missing():
    service = LiveChatService(None, bot=SimpleNamespace(tokens={"channel-1": {"token": "secret"}}))
    service.client = SimpleNamespace()
    response = httpx.Response(401, request=httpx.Request("GET", "https://api.twitch.tv/helix/chat/emotes/user"))
    service._fetch_twitch_user_emotes = AsyncMock(side_effect=httpx.HTTPStatusError("missing scope", request=response.request, response=response))
    fallback = [{
        "name": "Kappa", "url": "https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0",
        "provider": "twitch", "scope": "global"
    }]
    service._fetch_basic_twitch_emotes = AsyncMock(return_value=fallback)

    catalog = await service.get_emote_catalog("channel-1")

    assert catalog["emotes"] == fallback
    assert catalog["complete_twitch_catalog"] is False
    assert catalog["twitch_reconnect_required"] is True


@pytest.mark.asyncio
async def test_refresh_7tv_channel_replaces_cache_and_tracks_set_id():
    response = SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {
            "emote_set": {
                "id": "set-1",
                "emotes": [{"name": "FreshRat", "data": {"id": "01FRESH"}}]
            }
        }
    )
    service = LiveChatService(None)
    service.client = SimpleNamespace(get=AsyncMock(return_value=response))

    set_id = await service._refresh_seventv_channel("channel-1")

    assert set_id == "set-1"
    assert service.seventv_set_ids["channel-1"] == "set-1"
    assert service.seventv_channel_emotes["channel-1"]["FreshRat"].url == "https://cdn.7tv.app/emote/01FRESH/2x.webp"


@pytest.mark.asyncio
async def test_refresh_7tv_set_uses_direct_set_endpoint_for_live_updates():
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"emotes": [{"name": "AddedLive", "data": {"id": "01LIVE"}}]}
    )
    service = LiveChatService(None)
    service.client = SimpleNamespace(get=AsyncMock(return_value=response))

    await service._refresh_seventv_set("channel-1", "set-1")

    service.client.get.assert_awaited_once_with("https://7tv.io/v3/emote-sets/set-1")
    assert service.seventv_channel_emotes["channel-1"]["AddedLive"].url == "https://cdn.7tv.app/emote/01LIVE/2x.webp"


@pytest.mark.asyncio
async def test_7tv_dispatch_refreshes_the_active_set_without_restarting():
    class EventStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in ("event: dispatch", 'data: {"type":"emote_set.update"}', ""):
                yield line

    service = LiveChatService(None)
    service.started = True
    service.client = SimpleNamespace(stream=lambda *args, **kwargs: EventStream())
    service._refresh_seventv_set = AsyncMock()

    await service._stream_seventv_updates("channel-1", "set-1")

    service._refresh_seventv_set.assert_awaited_once_with("channel-1", "set-1")


@pytest.mark.asyncio
async def test_7tv_watcher_refreshes_channel_while_event_stream_is_quiet(monkeypatch):
    stream_cancelled = asyncio.Event()

    async def quiet_stream(*_):
        try:
            await asyncio.Event().wait()
        finally:
            stream_cancelled.set()

    service = LiveChatService(None)
    service.started = True
    service._stream_seventv_updates = quiet_stream

    async def refresh_channel(_):
        service.started = False
        return "set-1"

    service._refresh_seventv_channel = AsyncMock(side_effect=refresh_channel)
    monkeypatch.setattr("bot.services.channels.live_chat.SEVENTV_REFRESH_SECONDS", 0.01)

    await service._watch_seventv_set("channel-1", "set-1")

    service._refresh_seventv_channel.assert_awaited_once_with("channel-1")
    assert stream_cancelled.is_set()


def test_tagged_bot_response_is_kept_with_commands_without_classifying_all_bot_messages():
    service = LiveChatService(None)
    service.tag_command_response("channel-1", "command-response")

    response = service.publish_twitch(twitch_payload("You have 500 points.", "command-response"))
    unrelated = service.publish_twitch(twitch_payload("A raid boss is approaching!", "unrelated-bot-message"))

    assert response.kind == "command"
    assert unrelated.kind == "chat"
    assert [item["message"] for item in service.history("channel-1", "commands")] == ["You have 500 points."]
    assert [item["message"] for item in service.history("channel-1", "chat")] == ["A raid boss is approaching!"]


@pytest.mark.asyncio
async def test_deleted_chat_messages_remain_in_history_as_deleted_updates():
    service = LiveChatService(None)
    message = service.publish_twitch(twitch_payload("This will be deleted", "deleted-message"))
    subscriber = service.subscribe("channel-1")

    await service.remove_message("channel-1", message.id)

    history = service.history("channel-1")
    update = subscriber.get_nowait()
    assert history[0]["message"] == "This will be deleted"
    assert history[0]["deleted"] is True
    assert update.id == message.id
    assert update.deleted is True


def test_youtube_messages_are_normalized_and_deduplicated():
    bot = SimpleNamespace(get_command=lambda name: object() if name == "raid" else None)
    service = LiveChatService(None, bot=bot)
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


def test_youtube_error_details_extracts_google_reason_and_message():
    response = httpx.Response(403, json={
        "error": {
            "message": "The user is not enabled for live streaming.",
            "errors": [{"reason": "liveStreamingNotEnabled"}]
        }
    })

    assert LiveChatService._youtube_error_details(response) == (
        "liveStreamingNotEnabled",
        "The user is not enabled for live streaming."
    )


@pytest.mark.asyncio
async def test_youtube_watcher_squelches_forbidden_discovery_traceback(monkeypatch):
    request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/liveBroadcasts")
    response = httpx.Response(403, request=request, json={
        "error": {
            "message": "The user is not enabled for live streaming.",
            "errors": [{"reason": "liveStreamingNotEnabled"}]
        }
    })
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(side_effect=httpx.HTTPStatusError(
        "Forbidden", request=request, response=response
    ))
    monkeypatch.setattr(
        "bot.services.channels.live_chat.asyncio.sleep",
        AsyncMock(side_effect=asyncio.CancelledError)
    )

    with pytest.raises(asyncio.CancelledError):
        await service._watch_youtube("channel-1")

    assert service.youtube_statuses["channel-1"] == (
        "unavailable",
        "YouTube live streaming is not enabled for the connected channel."
    )


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
    assert running["started_at"] == (now - timedelta(seconds=10)).isoformat()
    assert running["ends_at"] is not None
    assert offline_status["state"] == "offline"


@pytest.mark.asyncio
@pytest.mark.parametrize("action,length", [("run-90", 90), ("run-180", 180)])
async def test_dashboard_ad_action_starts_commercial_for_connected_channel(monkeypatch, action, length):
    broadcaster = SimpleNamespace(id="channel-1", is_live=True)
    twitch_channel = SimpleNamespace(start_commercial=AsyncMock(return_value=SimpleNamespace(length=length, message="")))
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster})),
        create_partialuser=lambda _: twitch_channel
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/ads/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_ad_action(request, action, "csrf")

    assert response.status_code == 200
    status = json.loads(response.body)["status"]
    assert status["state"] == "running"
    assert (datetime.fromisoformat(status["ends_at"]) - datetime.fromisoformat(status["started_at"])) == timedelta(seconds=length)
    twitch_channel.start_commercial.assert_awaited_once_with(length=length)


@pytest.mark.asyncio
async def test_dashboard_ad_action_snoozes_next_ad(monkeypatch):
    next_ad_at = datetime.now(UTC) + timedelta(minutes=15)
    broadcaster = SimpleNamespace(id="channel-1", is_live=True)
    twitch_channel = SimpleNamespace(snooze_next_ad=AsyncMock(return_value=SimpleNamespace(
        next_ad_at=next_ad_at, snooze_count=2
    )))
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster})),
        create_partialuser=lambda _: twitch_channel
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/ads/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_ad_action(request, "snooze", "csrf")

    assert response.status_code == 200
    assert json.loads(response.body)["status"]["next_ad_at"] == next_ad_at.isoformat()
    twitch_channel.snooze_next_ad.assert_awaited_once()


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
    twitch_channel.send_message.assert_awaited_once_with(sender="channel-1", token_for="channel-1", message="Hello both chats")
    live_chat.send_youtube_message.assert_awaited_once_with("channel-1", "Hello both chats")


@pytest.mark.asyncio
async def test_dashboard_can_reply_to_a_twitch_message(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    twitch_channel = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=True)))
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        live_chat=SimpleNamespace()
    )
    runtime_bot = SimpleNamespace(services=services, create_partialuser=lambda broadcaster_id: twitch_channel)
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/chat/send", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_send_chat_message(
        request, "This is a reply", "twitch", "csrf", "twitch:parent-message"
    )

    assert response.status_code == 200
    twitch_channel.send_message.assert_awaited_once_with(
        sender="channel-1",
        token_for="channel-1",
        message="This is a reply",
        reply_to_message_id="parent-message"
    )


@pytest.mark.asyncio
async def test_dashboard_viewer_queue_actions_send_their_chat_response(monkeypatch):
    queue = SimpleNamespace(
        requeue=AsyncMock(return_value=(True, "Moved alice to position 1.")),
        size=lambda _: 2,
        list_queue=lambda _: ["alice", "bob"],
        list_queue_members=lambda _: [
            {"username": "alice", "display_name": "Alice", "label": "alice"},
            {"username": "bob", "display_name": "Bob", "label": "bob"}
        ],
        is_queue_open=lambda _: True
    )
    sent_message = SimpleNamespace(sent=True, id="queue-response")
    chat_identity = SimpleNamespace(send_message=AsyncMock(return_value=sent_message))
    live_chat = SimpleNamespace(tag_command_response=Mock())
    channel = SimpleNamespace(id="channel-1")
    services = SimpleNamespace(viewer_queue=queue, chat_identity=chat_identity, live_chat=live_chat)
    runtime_bot = SimpleNamespace(services=services, create_partialuser=lambda _: channel)
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/viewer-queue/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_viewer_queue_action(request, "top", "csrf", 2, 0)

    assert response.status_code == 200
    chat_identity.send_message.assert_awaited_once_with(channel, "Moved alice to position 1.")
    live_chat.tag_command_response.assert_called_once_with("channel-1", "queue-response")


@pytest.mark.asyncio
@pytest.mark.parametrize("next_count", [1, 4, 10])
async def test_dashboard_viewer_queue_next_uses_selected_count(monkeypatch, next_count):
    queue = SimpleNamespace(
        next_viewers=AsyncMock(return_value=(True, ["alice"], "Selected alice.")),
        list_queue=lambda _: [], list_queue_members=lambda _: [], is_queue_open=lambda _: True
    )
    services = SimpleNamespace(
        viewer_queue=queue,
        chat_identity=SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=False)))
    )
    runtime_bot = SimpleNamespace(services=services, create_partialuser=lambda _: SimpleNamespace(id="channel-1"))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/viewer-queue/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_viewer_queue_action(request, "next", "csrf", 0, 0, next_count)

    assert response.status_code == 200
    queue.next_viewers.assert_awaited_once_with("channel-1", next_count)


@pytest.mark.asyncio
@pytest.mark.parametrize("next_count", [0, 11])
async def test_dashboard_viewer_queue_next_rejects_out_of_range_count(monkeypatch, next_count):
    queue = SimpleNamespace(next_viewers=AsyncMock())
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=SimpleNamespace(viewer_queue=queue)))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/viewer-queue/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_viewer_queue_action(request, "next", "csrf", 0, 0, next_count)

    assert response.status_code == 400
    queue.next_viewers.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected_update", "expected_announcement", "expected_value"),
    [
        ("title", "New stream title", {"title": "New stream title"}, 'Stream title updated to "New stream title".', "New stream title"),
        ("game", "Just Chatting", {"game_id": "509658"}, 'Stream game updated to "Just Chatting".', "Just Chatting"),
        ("game", "", {"game_id": "0"}, "Stream category cleared.", "No category")
    ]
)
async def test_dashboard_metadata_edits_announce_changes_in_chat(
    monkeypatch, field, value, expected_update, expected_announcement, expected_value
):
    twitch_channel = SimpleNamespace(id="channel-1", modify_channel=AsyncMock())
    sent_message = SimpleNamespace(sent=True, id="metadata-response")
    chat_identity = SimpleNamespace(send_message=AsyncMock(return_value=sent_message))
    live_chat = SimpleNamespace(tag_command_response=Mock())
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(chat_identity=chat_identity, live_chat=live_chat),
        create_partialuser=lambda _: twitch_channel,
        fetch_game=AsyncMock(return_value=SimpleNamespace(id="509658", name="Just Chatting"))
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/channel-metadata", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.update_twitch_channel_metadata(request, field, value, "csrf")

    assert response.status_code == 200
    assert json.loads(response.body) == {"field": field, "value": expected_value, "announcement_sent": True}
    twitch_channel.modify_channel.assert_awaited_once_with(**expected_update)
    chat_identity.send_message.assert_awaited_once_with(twitch_channel, expected_announcement)
    live_chat.tag_command_response.assert_called_once_with("channel-1", "metadata-response")


@pytest.mark.asyncio
async def test_dashboard_metadata_chat_failure_does_not_undo_successful_twitch_edit(monkeypatch):
    twitch_channel = SimpleNamespace(id="channel-1", modify_channel=AsyncMock())
    chat_identity = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("Chat unavailable")))
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(chat_identity=chat_identity),
        create_partialuser=lambda _: twitch_channel
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/channel-metadata", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.update_twitch_channel_metadata(request, "title", "New title", "csrf")

    assert response.status_code == 200
    assert json.loads(response.body) == {"field": "title", "value": "New title", "announcement_sent": False}
    twitch_channel.modify_channel.assert_awaited_once_with(title="New title")


@pytest.mark.asyncio
async def test_dashboard_rejects_title_over_140_characters(monkeypatch):
    twitch_channel = SimpleNamespace(id="channel-1", modify_channel=AsyncMock())
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(),
        create_partialuser=lambda _: twitch_channel
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/channel-metadata", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.update_twitch_channel_metadata(request, "title", "x" * 141, "csrf")

    assert response.status_code == 400
    assert json.loads(response.body) == {"detail": "Titles must contain 1 to 140 characters."}
    twitch_channel.modify_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_unknown_category_returns_distinct_error_without_saving(monkeypatch):
    twitch_channel = SimpleNamespace(id="channel-1", modify_channel=AsyncMock())
    chat_identity = SimpleNamespace(send_message=AsyncMock())
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(chat_identity=chat_identity),
        create_partialuser=lambda _: twitch_channel,
        fetch_game=AsyncMock(return_value=None)
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/channel-metadata", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.update_twitch_channel_metadata(request, "game", "Unknown category", "csrf")

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "detail": "Twitch could not find that game or category.",
        "code": "category_not_found"
    }
    twitch_channel.modify_channel.assert_not_awaited()
    chat_identity.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_emote_catalog_is_scoped_to_authenticated_channel(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    live_chat = SimpleNamespace(get_emote_catalog=AsyncMock(return_value={"emotes": [], "complete_twitch_catalog": True}))
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        live_chat=live_chat
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/api/chat/emotes", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })

    response = await dashboard_router.channel_chat_emotes(request)

    assert response.status_code == 200
    live_chat.get_emote_catalog.assert_awaited_once_with("channel-1")


@pytest.mark.asyncio
async def test_twitch_ban_slash_command_uses_moderation_api():
    broadcaster = SimpleNamespace(ban_user=AsyncMock())
    chatters = SimpleNamespace(resolve=AsyncMock(return_value=SimpleNamespace(id="user-1")))
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(chatters=chatters),
        create_partialuser=lambda broadcaster_id: broadcaster
    )

    status = await dashboard_router.execute_twitch_slash_command(
        runtime_bot, "channel-1", "/ban @actual_login repeated spam"
    )

    assert status == "/ban completed."
    chatters.resolve.assert_awaited_once_with("channel-1", "@actual_login")
    broadcaster.ban_user.assert_awaited_once_with(
        moderator="channel-1", user="user-1", reason="repeated spam"
    )


@pytest.mark.asyncio
async def test_dashboard_chat_users_are_scoped_to_authenticated_channel(monkeypatch):
    broadcaster = SimpleNamespace(id="channel-1")
    chatters = SimpleNamespace(list_channel_identities=lambda broadcaster_id: [{
        "username": "actual_login", "display_name": "Display Name"
    }] if broadcaster_id == "channel-1" else [])
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        chatters=chatters
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/api/chat/users", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })

    response = await dashboard_router.channel_chat_users(request)

    assert response.status_code == 200
    assert json.loads(response.body) == {
        "users": [{"username": "actual_login", "display_name": "Display Name"}]
    }


@pytest.mark.asyncio
async def test_dashboard_updates_pinned_message_duration(monkeypatch):
    pinned = {"id": "twitch:message-1", "message": "Keep this visible"}
    live_chat = SimpleNamespace(get_pinned_message=lambda _: pinned)
    request_json = AsyncMock(return_value=None)
    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(live_chat=live_chat),
        _http=SimpleNamespace(request_json=request_json)
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/chat/moderate", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.moderate_channel_chat_message(
        request, "pin-duration", "twitch:message-1", "csrf", "5"
    )
    payload = json.loads(response.body)
    route = request_json.await_args.args[0]

    assert response.status_code == 200
    assert payload["duration_minutes"] == 5
    assert route.method == "PATCH"
    assert route.params["duration_seconds"] == "300"


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


@pytest.mark.asyncio
async def test_dashboard_header_stats_include_twitch_totals():
    twitch_user = SimpleNamespace(
        fetch_broadcaster_subscriptions=AsyncMock(return_value=SimpleNamespace(total=45, points=52)),
        fetch_followers=AsyncMock(return_value=SimpleNamespace(total=6789))
    )
    runtime_bot = SimpleNamespace(
        user=SimpleNamespace(id="bot-1"),
        create_partialuser=lambda broadcaster_id: twitch_user
    )
    broadcaster = SimpleNamespace(id="channel-1", viewer_count=12)

    stats = await dashboard_router.get_dashboard_header_stats(runtime_bot, broadcaster, points_lost=99)

    assert [(stat["key"], stat["value"], stat["display_value"]) for stat in stats] == [
        ("viewers", 12, "12"),
        ("followers", 6789, "6,789"),
        ("subscribers", 45, "45 (52 pts)"),
        ("points_lost", 99, "99")
    ]


@pytest.mark.asyncio
async def test_dashboard_header_stats_can_refresh_live_viewer_count():
    started_at = datetime.now(UTC)
    twitch_user = SimpleNamespace(
        fetch_stream=AsyncMock(return_value=SimpleNamespace(viewer_count=88, started_at=started_at)),
        fetch_broadcaster_subscriptions=AsyncMock(return_value=SimpleNamespace(total=45, points=51)),
        fetch_followers=AsyncMock(return_value=SimpleNamespace(total=67))
    )
    runtime_bot = SimpleNamespace(
        user=SimpleNamespace(id="bot-1"),
        create_partialuser=lambda broadcaster_id: twitch_user
    )
    broadcaster = SimpleNamespace(id="channel-1", is_live=False, viewer_count=0)

    stats = await dashboard_router.get_dashboard_header_stats(runtime_bot, broadcaster, refresh_viewers=True)

    assert stats[0]["value"] == 88
    assert broadcaster.viewer_count == 88
    assert broadcaster.is_live is True
    assert broadcaster.stream_started_at == started_at
    twitch_user.fetch_stream.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_dashboard_game_search_returns_twitch_categories(monkeypatch):
    calls = []

    async def games():
        yield SimpleNamespace(id="123", name="Retro")
        yield SimpleNamespace(id="509658", name="Just Chatting")
        yield SimpleNamespace(id="456", name="Chat")

    def search_categories(query, **kwargs):
        calls.append((query, kwargs))
        return games()

    monkeypatch.setattr(
        dashboard_router,
        "get_bot",
        lambda: SimpleNamespace(services=SimpleNamespace(), search_categories=search_categories)
    )
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/api/games", "headers": [],
        "query_string": b"query=chat", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })

    response = await dashboard_router.search_twitch_games(request, "chat")

    assert json.loads(response.body) == {"games": [
        {"id": "456", "name": "Chat"},
        {"id": "509658", "name": "Just Chatting"},
        {"id": "123", "name": "Retro"}
    ]}
    assert calls == [("chat", {"token_for": "channel-1", "first": 50, "max_results": 50})]


def test_dashboard_game_search_ranks_name_matches_and_preserves_top_games_order():
    games = [
        {"id": "1", "name": "Superchat"},
        {"id": "2", "name": "Just Chatting"},
        {"id": "3", "name": "Chatters"},
        {"id": "4", "name": "Chat"},
        {"id": "5", "name": "Retro"}
    ]

    ranked = dashboard_router.sort_twitch_games_by_match(games, "CHAT")

    assert [game["name"] for game in ranked] == [
        "Chat", "Chatters", "Just Chatting", "Superchat", "Retro"
    ]
    assert dashboard_router.sort_twitch_games_by_match(games, "") == games


@pytest.mark.parametrize(
    ("query", "literal_name", "popular_name"),
    [
        ("lol", "LOL", "League of Legends"),
        ("league", "League", "League of Legends"),
        ("wow", "WOW", "World of Warcraft"),
        ("dbd", "DBD", "Dead by Daylight")
    ]
)
def test_dashboard_game_search_uses_abbreviations_and_popularity(query, literal_name, popular_name):
    games = [
        {"id": "1", "name": literal_name},
        {"id": "2", "name": popular_name}
    ]

    ranked = dashboard_router.sort_twitch_games_by_match(games, query, [games[1]])

    assert ranked[0]["name"] == popular_name
    assert ranked[1] == games[0]


@pytest.mark.asyncio
async def test_dashboard_game_search_adds_matching_popular_category_when_search_omits_it(monkeypatch):
    async def games():
        yield SimpleNamespace(id="1", name="LOL")

    async def top_games():
        yield SimpleNamespace(id="21779", name="League of Legends")

    top_calls = []

    def fetch_top_games(**kwargs):
        top_calls.append(kwargs)
        return top_games()

    runtime_bot = SimpleNamespace(
        services=SimpleNamespace(),
        search_categories=lambda query, **kwargs: games(),
        fetch_top_games=fetch_top_games
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/api/games", "headers": [],
        "query_string": b"query=lol", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })

    response = await dashboard_router.search_twitch_games(request, "lol")

    assert json.loads(response.body) == {"games": [
        {"id": "21779", "name": "League of Legends"},
        {"id": "1", "name": "LOL"}
    ]}
    assert top_calls == [{"token_for": "channel-1", "first": 100, "max_results": 100}]

    await dashboard_router.search_twitch_games(request, "lol")
    assert len(top_calls) == 1


@pytest.mark.asyncio
async def test_pinned_chat_message_survives_service_restart(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "pinned-chat.db")) as database:
        await run_migrations(database)
        service = LiveChatService(database)
        await service.setup()
        message = twitch_payload("Pinned rat", "pin-1")
        serialized = service.publish_twitch(message).as_dict()

        await service.pin_message("channel-1", serialized)
        restarted = LiveChatService(database)
        await restarted.setup()

        assert restarted.get_pinned_message("channel-1")["id"] == "twitch:pin-1"
        await restarted.clear_pinned_message("channel-1")
        assert restarted.get_pinned_message("channel-1") is None


def test_live_chat_tracks_mod_actions_and_automod_queue():
    service = LiveChatService(None)
    broadcaster = SimpleNamespace(id="channel-1")
    timeout_ends = datetime.now(UTC) + timedelta(minutes=10)
    service.record_mod_action(SimpleNamespace(
        broadcaster=broadcaster,
        source_broadcaster=broadcaster,
        moderator=SimpleNamespace(id="mod-1", name="modrat", display_name="Mod Rat"),
        action="timeout",
        timeout=SimpleNamespace(
            user=SimpleNamespace(id="viewer-1", name="viewer", display_name="Viewer Name"),
            reason="spam",
            expires_at=timeout_ends
        )
    ))
    held = SimpleNamespace(
        broadcaster=broadcaster,
        user=SimpleNamespace(name="viewer", display_name="Viewer"),
        message_id="held-1",
        text="held message",
        reason="automod",
        category="aggression",
        level=2,
        held_at=datetime.now(UTC)
    )
    service.hold_automod_message(held)

    activity = service.get_moderation_activity("channel-1")

    assert activity["mod_actions"][0] | {"timestamp": None, "id": None} == {
        "id": None,
        "action": "Timeout",
        "action_key": "timeout",
        "moderator": "Mod Rat (modrat)",
        "moderator_login": "modrat",
        "target": "Viewer Name (viewer)",
        "target_login": "viewer",
        "reason": "spam",
        "expires_at": timeout_ends.isoformat(),
        "message": None,
        "note": None,
        "follow_duration": None,
        "wait_time": None,
        "viewer_count": None,
        "terms": [],
        "term_list": None,
        "from_automod": None,
        "chat_rules": [],
        "source_channel": None,
        "timestamp": None
    }
    assert activity["automod"][0]["id"] == "held-1"
    service.resolve_automod_message("channel-1", "held-1")
    assert service.get_moderation_activity("channel-1")["automod"] == []


def test_dashboard_templates_include_reply_composer_and_spanning_chat_layout():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    features = open("web/templates/channel/features.html", encoding="utf-8").read()
    channel_layout = open("web/templates/channel/layout.html", encoding="utf-8").read()
    customization = open("web/templates/shared/profile_inputs.html", encoding="utf-8").read()
    dashboard_styles = open("web/static/css/style.css", encoding="utf-8").read()
    widget_styles = open("web/static/css/chat-widget.css", encoding="utf-8").read()
    chat_script = open("web/static/js/live-chat-feed.js", encoding="utf-8").read()
    composer_script = open("web/static/js/dashboard-chat-send.js", encoding="utf-8").read()
    sidebar_script = open("web/static/js/channel-sidebar.js", encoding="utf-8").read()
    header_stats_script = open("web/static/js/dashboard-header-stats.js", encoding="utf-8").read()
    stream_player_script = open("web/static/js/dashboard-stream-player.js", encoding="utf-8").read()
    ad_status_script = open("web/static/js/dashboard-ad-status.js", encoding="utf-8").read()
    metadata_script = open("web/static/js/dashboard-channel-metadata.js", encoding="utf-8").read()
    queue_script = open("web/static/js/dashboard-viewer-queue.js", encoding="utf-8").read()

    assert 'data-stream-url="/channel/api/chat/stream?view=both"' in dashboard
    assert 'data-stream-url="/channel/api/chat/stream?view=commands"' in dashboard
    assert dashboard.count("data-connection-status-target") == 1
    assert "Waiting for chat messages" not in dashboard
    assert "Waiting for commands" not in dashboard
    assert 'data-activity-tab="redeems"' in dashboard
    assert 'data-activity-tab="checkins"' in dashboard
    assert '<h4 class="activity-subheading">Check-ins</h4>' not in dashboard
    assert '<h4>No commands yet</h4>' in dashboard
    assert '<p>Chat commands will appear here.</p>' in dashboard
    assert 'data-activity-tab="mod-actions"' in dashboard
    assert 'data-activity-tab="automod"' in dashboard
    assert '.dashboard-tabs.activity-tabs { flex-wrap: nowrap;' in dashboard_styles
    assert '.dashboard-tabs.activity-tabs .dashboard-tab { min-width: max-content; min-height: 34px; flex: 1 0 auto;' in dashboard_styles
    assert '.queue-toolbar button, .queue-toolbar a { display: inline-flex; width: 100%;' in dashboard_styles
    assert '@container (max-width: 500px)' not in dashboard_styles
    assert dashboard.count('data-activity-group>') == 2
    assert 'selectActivity(group, selected)' in dashboard
    assert 'tab.closest("[data-activity-group]")' in dashboard
    assert '.queue-toolbar { display: grid; grid-template-columns: repeat(3,minmax(0,1fr));' in dashboard_styles
    assert '.queue-toolbar .queue-next-control > button { min-width: 0; flex: 1; width: auto; gap: 4px;' in dashboard_styles
    assert '.queue-next-picker select' in dashboard_styles
    assert dashboard.index('data-activity-tab="raid"') < dashboard.index('include "channel/raid_summary.html"')
    assert 'data-chat-composer' in dashboard
    assert 'data-channel-id="{{ broadcaster.id }}"' in dashboard
    assert 'data-reply-context' in dashboard
    assert 'data-reply-cancel' in dashboard
    assert 'data-chat-target="twitch"' in dashboard
    assert 'data-chat-target="youtube"' in dashboard
    assert 'data-chat-target="both"' in dashboard
    assert "data-emote-picker" in dashboard
    assert "data-emote-toggle" in dashboard
    assert "data-dashboard-header-stats" in dashboard
    assert "data-dashboard-stat-value" in dashboard
    assert '{% if stat.key != "points_lost" %}' in dashboard
    assert '{% if stat.key == "points_lost" %}' in dashboard
    assert 'class="dashboard-points-stat" data-dashboard-points-lost' in dashboard
    assert 'class="dashboard-header-stat dashboard-points-stat"' not in dashboard
    assert '.dashboard-header-stats > .dashboard-header-stat { flex: 1 0 auto; justify-content: center; }' in dashboard_styles
    assert '.dashboard-points-stat { display: inline-flex; max-width: 65%; min-width: 0; min-height: 30px; align-items: center; gap: 6px; margin-left: auto; padding: 5px 9px; border: 0;' in dashboard_styles
    assert 'dashboard.querySelectorAll("[data-dashboard-stat]")' in header_stats_script
    assert 'dashboard.querySelector("[data-dashboard-points-lost]")' in header_stats_script
    assert "data-stream-status" in dashboard
    assert 'class="dashboard-ad-stat state-{{ ad_status.state }}"' in dashboard
    assert 'class="dashboard-header-stat dashboard-ad-stat' not in dashboard
    assert 'data-ad-panel' in dashboard
    assert 'data-started-at="{{ ad_status.started_at or \'\' }}"' in dashboard
    assert 'data-ad-progress-ring' in dashboard
    assert dashboard.index('<h3>Ads</h3>') < dashboard.index('data-ad-status data-state=') < dashboard.index('data-ad-action="run-90"')
    assert '.channel-dashboard-layout .panel { margin-bottom: 0; padding: 16px; }' in dashboard_styles
    assert '.channel-page-overview .streamer-main-content { padding: 16px; }' in dashboard_styles
    assert 'align-items: stretch; gap: 12px; margin-bottom: 16px;' in dashboard_styles
    assert 'padding: 5px 9px; border: 0;' in dashboard_styles
    assert 'data-ad-action="run-90"' in dashboard
    assert 'data-ad-action="run-180"' in dashboard
    assert 'data-ad-action="snooze"' in dashboard
    assert "stream-status-card" not in dashboard
    assert "Twitch ID:" not in dashboard
    assert 'data-user-id="{{ broadcaster.id }}"' in dashboard
    assert 'class="channel-heading dashboard-channel-heading"' in dashboard
    assert "dashboard-channel-identity" in dashboard
    assert 'aria-label="Open {{ broadcaster.name or broadcaster.login }} on Twitch"' in dashboard
    assert "Open Twitch" not in dashboard
    assert "Twitch + YouTube" not in dashboard
    assert "<h3>Combined Chat</h3>" in dashboard
    assert 'data-activity-link="commands"' not in dashboard
    assert "Stream activity" not in dashboard
    assert "Viewer games" not in dashboard
    assert 'data-refresh-url="/channel/api/dashboard-stats"' in dashboard
    assert "Back to Overview" not in features
    assert dashboard.index("data-emote-toggle") < dashboard.index("data-chat-send-status") < dashboard.index("dashboard-chat-composer-actions")
    assert 'fetch("/channel/api/chat/emotes")' in composer_script
    assert 'fetch("/channel/api/chat/users"' in composer_script
    assert 'const twitchCommands = [' in composer_script
    assert 'value: `@${user.username}`' in composer_script
    assert 'user.display_name.toLocaleLowerCase().includes(query)' in composer_script
    assert 'command.name.includes(query)' in composer_script
    assert '!key.includes(query)' in composer_script
    assert 'inputBeforeCursor.match(/^\\/([A-Za-z]*)$/)' in composer_script
    assert 'event.key === "Tab"' in composer_script
    assert "navigateMessageHistory(direction)" in composer_script
    assert "caretAtStart" in composer_script
    assert "caretAtEnd" in composer_script
    assert "const messageHistoryLimit = 20" in composer_script
    assert "slice(-messageHistoryLimit)" in composer_script
    assert "window.sessionStorage.setItem(messageHistoryKey" in composer_script
    live_chat_script = open("web/static/js/live-chat-feed.js", encoding="utf-8").read()
    assert '"pin-duration"' in live_chat_script
    assert '"live-chat-pinned-action live-chat-unpin"' in live_chat_script
    assert '["", "∞"]' in live_chat_script
    assert 'window.requestAnimationFrame(finishScroll)' in live_chat_script
    assert 'if (feed.followNewest) scrollToBottom(feed)' in live_chat_script
    assert 'const shouldFollowNewest = feed.followNewest && distanceFromBottom(feed.element) <= 24' in live_chat_script
    assert '["wheel", "touchmove"]' in live_chat_script
    assert 'feed.followRowObserver = new ResizeObserver' in live_chat_script
    assert 'feed.followRowObserver.observe(row)' in live_chat_script
    assert 'new CustomEvent("dashboard-chat-reply"' in live_chat_script
    assert '"live-chat-message-action reply"' in live_chat_script
    assert 'row.classList.add("is-deleted")' in live_chat_script
    assert 'row.classList.add("is-mentioned")' in live_chat_script
    assert 'row.classList.add("is-bot")' in live_chat_script
    assert 'feed.element.querySelector(".compact-empty-state")?.remove()' in live_chat_script
    assert '.live-chat-message.is-deleted' in dashboard_styles
    assert '.live-chat-message.is-mentioned' in dashboard_styles
    assert '.live-chat-message.is-bot:not(.is-deleted)' in dashboard_styles
    assert 'event.key !== "Escape" || !replyMessageId.value' in composer_script
    assert '"live-chat-pin-progress"' in live_chat_script
    assert 'window.setInterval(() => refreshPinned(feed), 2000)' in live_chat_script
    assert "live-chat-pin-countdown" in dashboard_styles
    assert 'addDetail("Reason", action.reason)' in dashboard
    assert 'addDetail("Deleted message"' in dashboard
    assert 'addDetail("Timeout ends"' in dashboard
    assert "Performed by ${action.moderator}" in dashboard
    assert 'addDetail("Message ID"' not in dashboard
    assert 'displayName.toLocaleLowerCase() !== username.toLocaleLowerCase()' in live_chat_script
    assert 'data-ad-status' in dashboard
    assert dashboard.count("<h3>Viewer queue</h3>") == 1
    assert "data-channel-metadata" in dashboard
    assert 'data-games-url="/channel/api/games"' in dashboard
    assert 'contenteditable="plaintext-only"' in dashboard
    assert dashboard.count('spellcheck="false"') >= 2
    assert "dashboard-channel-metadata.js" in dashboard
    assert "dashboard-viewer-queue.js" in dashboard
    assert 'data-queue-action="next"' in dashboard
    assert 'data-queue-next-select' in dashboard
    assert 'data-queue-next-count>4</span>' in dashboard
    assert 'range(1, 11)' in dashboard
    assert 'data-queue-action="clear"' in dashboard
    assert 'href="/channel/viewer-queue/blacklist"' in dashboard
    assert 'data-queue-count' in dashboard
    assert '.queue-panel-header [data-queue-count] { display: inline-flex; min-height: 30px; align-items: center; margin-inline: auto; padding: 5px 9px; border: 0;' in dashboard_styles
    assert 'color: var(--text); font-size: 13px; font-weight: 800;' in dashboard_styles
    assert 'item.draggable = true' in queue_script
    assert 'runAction("reorder", draggingPosition, position)' in queue_script
    assert 'moveIcon("top")' in queue_script
    assert 'moveIcon("bottom")' in queue_script
    assert 'actionButton("🗑"' in queue_script
    assert '.queue-item-action svg' in dashboard_styles
    assert 'fetch(endpoint' in metadata_script
    assert "searchGames" in metadata_script
    assert 'event.key === "Tab" || event.key === "Enter"' not in metadata_script
    assert 'button.addEventListener("pointerdown"' in metadata_script
    assert 'gameField.dataset.commitEdit = "true"' in metadata_script
    assert 'const shouldCommit = field.dataset.commitEdit === "true"' in metadata_script
    assert 'let savedValue = field.textContent.trim();' in metadata_script
    assert 'field.dataset.hasDraft = "true";' in metadata_script
    assert 'field.addEventListener("input", () => {' in metadata_script
    assert '.twitch-channel-field strong[data-has-draft="true"]' in dashboard_styles
    assert 'if (message !== "Unsaved. Press Enter to save.")' in metadata_script
    assert 'function refreshDraftWarning()' in metadata_script
    assert 'showStatus("Unsaved. Press Enter to save.", "warning")' in metadata_script
    assert 'field.textContent = savedValue;' in metadata_script
    assert 'error.code = result.code;' in metadata_script
    assert 'field === gameField && error.code === "category_not_found"' in metadata_script
    assert 'delete field.dataset.hasDraft;' in metadata_script
    assert 'field.textContent = originalValue;' not in metadata_script
    assert 'gameSearchController?.abort();' in metadata_script
    assert 'document.activeElement !== gameField' in metadata_script
    assert "twitch-game-suggestions" in dashboard_styles
    assert "Bitrate" not in dashboard
    assert 'window.setTimeout(() => status.classList.add("is-fading"), 3000)' in metadata_script
    assert 'window.setTimeout(() => status.classList.add("is-fading"), 3000)' in queue_script
    assert 'data-activity-notify="commands"' in dashboard
    assert 'data-moderation-url="/channel/api/chat/moderate"' in dashboard
    assert 'data-pinned-url="/channel/api/chat/pinned"' in dashboard
    assert "live-chat-message-actions" in chat_script
    assert "refreshPinned" in chat_script
    assert 'source.onopen = () => showConnectionStatus(true)' in chat_script
    assert 'source.onerror = () => showConnectionStatus(false)' in chat_script
    assert 'window.setTimeout(() => connectionStatus.classList.add("is-fading"), 3000)' in chat_script
    assert "<h3>Category</h3>" in dashboard
    assert '.twitch-channel-field [data-channel-field="title"], .twitch-channel-field [data-channel-field="game"] { color: var(--text); font-size: 17px; font-weight: 700;' in dashboard_styles
    assert 'data-channel-field="title"' in dashboard
    assert 'aria-label="Stream title (140 characters maximum)"' in dashboard
    assert 'titleField.addEventListener("beforeinput"' in metadata_script
    assert 'titleField.addEventListener("paste"' in metadata_script
    assert 'titleField.addEventListener("input"' in metadata_script
    assert 'selection.setBaseAndExtent(field, 0, field, field.childNodes.length);' in metadata_script
    assert 'field.scrollLeft = field.scrollWidth;' in metadata_script
    assert 'Array.from(titleField.textContent).slice(0, 140).join("")' in metadata_script
    assert 'window.setInterval(() => refreshPinned(feed), 2000)' in chat_script
    assert 'dashboard-activity-unread' in dashboard
    assert 'dashboard-activity-unread' in chat_script
    assert '.dashboard-tab.has-unseen:not(.active)' in dashboard_styles
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
    assert '"live-chat-jump", "↓ Jump to present"' in chat_script
    assert 'makeElement("div", "live-chat-feed-shell")' in chat_script
    assert 'element.addEventListener("scroll", () => {' in chat_script
    assert "updateJumpButton(feed);" in chat_script
    assert "feed.element.scrollTop = feed.element.scrollHeight;" in chat_script
    assert "feed.hasUnseenMessages = true" in chat_script
    assert 'maxMessages: Number(element.dataset.maxMessages || 100)' in chat_script
    assert 'data-max-messages="150"' in dashboard
    assert 'classList.toggle("has-unseen", feed.hasUnseenMessages && !atBottom)' in chat_script
    assert "display: flex; flex: 0 0 auto;" in dashboard_styles
    assert "display: flex; min-width: 0; flex: 1; flex-wrap: wrap;" in dashboard_styles
    assert ".live-chat-time { position: absolute; top: 1px; right: 0;" in dashboard_styles
    assert ".live-chat-time { position: absolute; top: 1px; right: 0;" in widget_styles
    assert "if (timestamp) content.appendChild(timestamp);" in chat_script
    assert ".live-chat-text { max-width: 100%; flex: 0 0 auto; margin: 0;" in dashboard_styles
    assert ".live-chat-text { max-width: 100%; flex: 0 0 auto; margin: 0;" in widget_styles
    assert ".live-chat-jump[hidden] { display: none; }" in dashboard_styles
    assert ".live-chat-jump.has-unseen {" in dashboard_styles
    assert "animation: live-chat-jump-alert 3s ease-in-out infinite" in dashboard_styles
    assert "@keyframes live-chat-jump-alert" in dashboard_styles
    assert "33.333% { background-color: rgba(255,59,59,.75); }" in dashboard_styles
    assert "66.666%, 100% { background-color: var(--jump-fill); }" in dashboard_styles
    assert chat_script.index("heading.appendChild(platform)") < chat_script.index("heading.appendChild(name)")
    assert 'emote.srcset = emoteSrcset(url)' in chat_script
    assert 'image.srcset = emoteSrcset(emote.url)' in composer_script
    assert 'replace(/\\/2x\\.webp$/, "/3x.webp")' in composer_script
    assert "data-emote-group" in dashboard
    assert "renderGroupOptions" in composer_script
    assert "matches.slice(0, 300)" not in composer_script
    assert "overflow-y: auto; overscroll-behavior: contain;" in dashboard_styles
    assert "seen.has(emote.name)" in composer_script
    assert ".chat-emote-picker[hidden], .chat-emote-suggestions[hidden] { display: none; }" in dashboard_styles
    assert ".chat-send-status { position: absolute;" in dashboard_styles
    assert "text-align: right; text-overflow: ellipsis;" in dashboard_styles
    assert "right: 15px; bottom: 11px;" in dashboard_styles
    assert "opacity: .8;" in dashboard_styles
    assert ".chat-send-status.is-fading { opacity: 0; }" in dashboard_styles
    assert "height: 66px;" in dashboard_styles
    assert "resize: none;" in dashboard_styles
    assert 'status.dataset.connectionState === "disconnected"' in composer_script
    assert 'status.classList.add("is-fading")' in composer_script
    assert 'grid-template-areas: "player queue chat" "activities activities chat"' in dashboard_styles
    assert "grid-template-rows: max-content minmax(540px,1fr)" in dashboard_styles
    assert '.channel-dashboard-layout > .dashboard-channel-profile[hidden] { display: none; }' in dashboard_styles
    assert 'grid-template-areas: "player" "queue" "activities" "chat"' in dashboard_styles
    assert 'grid-template-areas: "player queue" "activities activities" "chat chat"' in dashboard_styles
    assert '.dashboard-activity-grid { display: grid; grid-area: activities;' in dashboard_styles
    assert '<header class="page-header dashboard-channel-profile" hidden>' in dashboard
    assert dashboard.index('class="panel dashboard-video-card"') < dashboard.index('class="panel live-chat-panel"')
    assert dashboard.index('class="panel dashboard-video-card"') < dashboard.index('class="dashboard-chat-column"') < dashboard.index('class="dashboard-header-side"') < dashboard.index('class="panel live-chat-panel"')
    assert '<span>Stream</span>' not in dashboard
    assert '{% if broadcaster.is_live %}Online{% else %}Offline{% endif %}' in dashboard
    assert 'data-stream-status' in dashboard and 'aria-pressed="true"' in dashboard
    assert 'class="panel-header dashboard-video-header"' in dashboard
    assert '.dashboard-video-header { display: grid; min-width: 0; grid-template-columns: minmax(0,2fr) minmax(0,1fr);' in dashboard_styles
    assert '.dashboard-video-header [data-channel-field="title"]:is(:focus, .editing) { position: relative; z-index: 10; }' in dashboard_styles
    assert 'const maxWidth = Math.max(0, cardBounds.right - rightPadding - fieldBounds.left);' in metadata_script
    assert 'Math.max(fieldBounds.width, titleField.scrollWidth + 2)' in metadata_script
    assert 'titleField.style.removeProperty("width")' in metadata_script
    assert '[data-channel-field].metadata-truncated:not(:focus):not(.editing)::after' in dashboard_styles
    assert '[titleField, gameField].filter(Boolean).forEach(field => {' in metadata_script
    assert 'new MutationObserver(updateFieldPencil)' in metadata_script
    assert 'new ResizeObserver(updateFieldPencil)' in metadata_script
    assert 'if (document.activeElement !== gameField) gameField.scrollLeft = 0;' in metadata_script
    assert '<h3>Title</h3>' in dashboard
    assert '<h3>Category</h3>' in dashboard
    assert '<h3>Twitch stream</h3>' not in dashboard
    assert '<h3>Stream preview</h3>' not in dashboard
    assert '.dashboard-header-stats { display: flex; width: 100%; min-width: 0; flex-wrap: wrap; justify-content: flex-start; gap: 6px; }' in dashboard_styles
    assert 'dashboard-header-stat-break' not in dashboard
    assert 'data-stream-player' in dashboard
    assert 'dashboard-stream-player.js' in dashboard
    assert 'url.searchParams.set("parent", window.location.hostname)' in stream_player_script
    assert 'url.searchParams.set("autoplay", "false")' in stream_player_script
    assert 'url.searchParams.set("muted", "true")' in stream_player_script
    assert '.dashboard-video-frame { width: 100%; min-width: 0; overflow: hidden; }' in dashboard_styles
    assert '.dashboard-video-player { display: block; width: 100%; min-width: 0; max-width: 900px; height: auto; margin-inline: auto; aspect-ratio: 16 / 9;' in dashboard_styles
    assert 'aspect-ratio: 16 / 9;' in dashboard_styles
    assert 'grid-template-columns: minmax(0,1.3fr) minmax(0,1fr)' in dashboard_styles
    assert dashboard.index('<div class="channel-dashboard-layout">') < dashboard.index('<header class="page-header dashboard-channel-profile" hidden>')
    assert 'body class="dashboard-page channel-page channel-page-{{ active_page }}"' in channel_layout
    assert "data-sidebar-toggle" in channel_layout
    assert "channel-sidebar.js" in channel_layout
    assert 'localStorage.setItem(storageKey, String(collapsed))' in sidebar_script
    assert ".dashboard-page:not(.channel-page-overview) .main-content" in dashboard_styles
    assert "left: -36px; width: min(1250px,calc(100vw - 144px));" in dashboard_styles
    assert "justify-content: space-evenly; gap: 0;" in dashboard_styles
    assert ".navigation .nav-link { flex: 0 0 auto; justify-content: center; }" in dashboard_styles
    assert ".sidebar:not(:hover) .nav-link { gap: 11px; justify-content: center; padding: 11px 13px; }" in dashboard_styles
    assert ".sidebar:not(:hover) .sidebar-logout .button { gap: 10px; padding-right: 17px; padding-left: 17px; }" in dashboard_styles
    assert "window.localStorage.setItem(storageKey" in header_stats_script
    assert "dashboard-stat-visibility" in header_stats_script
    assert "const refreshInterval = 60000" in header_stats_script
    assert "window.setInterval(refreshStats, refreshInterval)" in header_stats_script
    assert 'fetch(refreshUrl, {headers: {Accept: "application/json"}, cache: "no-store"})' in header_stats_script
    assert 'actualStreamStatus = {isLive: payload.is_live, startedAt: payload.started_at || ""};' in header_stats_script
    assert "window.setInterval(renderStreamStatus, 1000)" in header_stats_script
    assert 'label.textContent = `Ends in ${formatDuration(remaining)}`' in ad_status_script
    assert 'label.textContent = remaining > 0 ? `Starts in ${formatDuration(remaining)}`' in ad_status_script
    assert 'remaining < 60' in ad_status_script
    assert 'setAppearance("ad-warning")' in ad_status_script
    assert 'setAppearance("ad-running")' in ad_status_script
    assert 'setAppearance("ad-scheduled")' in ad_status_script
    assert 'progressRing.style.strokeDashoffset = String(ringCircumference * (1 - fraction))' in ad_status_script
    assert 'if (progressRing && !ringIntroActive && !ringCountdownActive)' in ad_status_script
    assert 'if (enteringRunning && container.dataset.state === "running") beginRingIntro();' in ad_status_script
    assert '@keyframes dashboard-ad-ring-fill { from { stroke-dashoffset: 56.55; } to { stroke-dashoffset: 0; } }' in dashboard_styles
    assert 'animation: dashboard-ad-ring-countdown var(--ad-ring-duration) linear forwards;' in dashboard_styles
    assert 'progressRing.style.setProperty("--ad-ring-duration", `${remainingMs}ms`);' in ad_status_script
    assert 'window.dashboardAdTest = {' in ad_status_script
    assert 'schedule(secondsUntilStart = 5, durationSeconds = 15)' in ad_status_script
    assert 'if (simulationActive) startSimulatedAd(duration);' in ad_status_script
    assert 'scheduledRefreshAt = container.dataset.nextAdAt;' in ad_status_script
    assert 'displayStatus({state: "complete", label: "Ads finished"});' in ad_status_script
    assert 'window.getComputedStyle(completionCheck).animationDuration' in ad_status_script
    assert '}, 5000 + animationSeconds * 1000);' in ad_status_script
    assert '.dashboard-ad-stat.ad-complete .dashboard-ad-progress-check' in dashboard_styles
    assert 'setAppearance("ad-idle")' in ad_status_script
    assert 'container.dataset.state === "offline"' in ad_status_script
    assert 'setAppearance("ad-neutral")' in ad_status_script
    assert '.dashboard-ad-stat.ad-idle' in dashboard_styles
    assert '.dashboard-ad-stat.ad-running' in dashboard_styles
    assert '.dashboard-ads-panel .dashboard-ad-stat.ad-scheduled { background: rgba(139,92,246,.12); }' in dashboard_styles
    assert '.dashboard-ads-panel .dashboard-ad-stat.ad-running { background: rgba(139,92,246,.2); }' in dashboard_styles
    assert '.dashboard-ad-progress-ring { stroke: #c7b7ff;' in dashboard_styles
    assert 'animation: dashboard-ad-warning 1s ease-in-out 5' in dashboard_styles
    assert "transition-delay: 1s,1s;" in dashboard_styles
    assert ".dashboard-channel-heading { flex-direction: column; align-items: flex-start; gap: 10px; }" in dashboard_styles
    assert ".dashboard-channel-heading > .eyebrow { margin-bottom: 0; padding-left: 12px; }" in dashboard_styles
    assert ".dashboard-channel-identity:hover, .dashboard-channel-identity:focus-visible" in dashboard_styles
    assert ".channel-dashboard-layout .panel-header h3 { color: #c7b7ff; }" in dashboard_styles
    assert "width: 50px; height: 50px; flex-basis: 50px;" in dashboard_styles
    assert ".dashboard-channel-copy .page-description { margin-top: 1px; line-height: 1.15; }" in dashboard_styles
    assert ".channel-page-overview { height: 100dvh; overflow: hidden; }" in dashboard_styles
    assert ".channel-page-overview .dashboard-chat-column { grid-row: 1 / -1; }" in dashboard_styles
    assert 'grid-template-areas: "player queue chat" "activities activities chat";' in dashboard_styles
    assert '.dashboard-chat-column > .dashboard-header-side { flex: 0 0 auto; margin-bottom: 12px; }' in dashboard_styles
    assert 'grid-template-rows: max-content max-content minmax(540px,auto)' in dashboard_styles
    assert '.channel-page-overview .dashboard-chat-column { height: auto; grid-row: auto; overflow: visible; }' in dashboard_styles
    assert ".dashboard-chat-column { display: flex; grid-area: chat;" in dashboard_styles
    assert 'showTimer && streamStatus.dataset.startedAt ? ` · ${formatUptime(streamStatus.dataset.startedAt)}`' in header_stats_script
    assert 'container.querySelector("[data-stream-status]")?.addEventListener("click", () => {' in header_stats_script
    assert 'hiddenStats.has("stream_timer")' in header_stats_script
    assert 'window.dashboardLiveTest = {' in header_stats_script
    assert 'applyStreamStatus(true, new Date(Date.now() - elapsedMinutes * 60000).toISOString());' in header_stats_script
    assert 'viewerValue.textContent = (Math.floor(Math.random() * 500) + 1).toLocaleString();' in header_stats_script
    assert 'viewerValue.textContent = actualViewerCount;' in header_stats_script
    assert 'if (value && !(previewActive && stat.key === "viewers")) value.textContent = displayValue;' in header_stats_script
    assert 'if (!previewActive) applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);' in header_stats_script
    assert 'applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);' in header_stats_script
    assert ".dashboard-stream-stat.state-live .status-indicator { animation: dashboard-live-pulse" in dashboard_styles
    assert ".sidebar:not(:hover) .sidebar-toggle { top: 35px; right: -14px; }" in dashboard_styles


@pytest.mark.asyncio
@pytest.mark.parametrize("items, expected", [([], None), ([{"snippet": {"liveChatId": "chat-1"}}], "chat-1")])
async def test_youtube_discovery_uses_only_one_filter(items, expected):
    service = LiveChatService(None)
    service._youtube_get = AsyncMock(return_value={"items": items})

    assert await service._find_active_live_chat("channel-1") == expected
    service._youtube_get.assert_awaited_once_with(
        "channel-1", "/liveBroadcasts",
        {"part": "id,snippet", "broadcastStatus": "active", "broadcastType": "all", "maxResults": 10}
    )

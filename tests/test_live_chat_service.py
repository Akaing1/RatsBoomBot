import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import asqlite
import httpx
import grpc
import pytest
from starlette.requests import Request

import web.channel.routers.dashboard as dashboard_router
from bot.services.channels.live_chat import ChatBadge, ChatSegment, LiveChatService, UnifiedChatMessage, message_matches_view, normalize_chat_view
from bot.services.channels import youtube_live_chat_pb2
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


def test_sidebar_hover_labels_use_existing_names_for_channel_and_admin_navigation():
    script = open("web/static/js/channel-sidebar.js", encoding="utf-8").read()
    assert 'querySelectorAll(".nav-link, .sidebar-logout button")' in script
    assert 'querySelector(".nav-link-label, .sidebar-button-label")?.textContent.trim()' in script
    assert 'if (label) control.title = label;' in script
    for path in ("web/templates/channel/layout.html", "web/templates/admin/layout.html"):
        layout = open(path, encoding="utf-8").read()
        assert "channel-sidebar.js" in layout
        assert "hover-labels.js" in layout
        assert 'class="nav-link-label"' in layout
        assert 'class="sidebar-button-label"' in layout


def test_reward_related_chat_messages_expose_redemption_metadata():
    service = LiveChatService(None)
    custom = twitch_payload("reward input", "custom")
    custom.channel_points_id = "reward-1"
    highlighted = twitch_payload("highlighted message", "highlighted")
    highlighted.type = "channel_points_highlighted"
    assert service.publish_twitch(custom).as_dict()["is_redeem"] is True
    assert service.publish_twitch(highlighted).is_redeem is True
    assert service.publish_twitch(twitch_payload("normal", "normal")).is_redeem is False


def test_chat_filters_replace_command_toggle_and_only_apply_to_combined_chat():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    script = open("web/static/js/live-chat-feed.js", encoding="utf-8").read()
    assert 'data-chat-command-toggle' not in dashboard
    assert 'label class="chat-filter-row chat-filter-suboption"' in dashboard
    assert 'role="group" aria-label="{{ group }}"' in dashboard
    assert 'data-chat-filter-group-toggle' not in dashboard
    filters = open("web/static/js/dashboard-chat-filters.js", encoding="utf-8").read()
    assert "addEventListener('focusout'" not in filters
    assert "dashboard-chat-filters.js" in dashboard
    assert dashboard.index('data-chat-filter-toggle') < dashboard.index('data-chat-lock')
    assert 'row.hidden = feed.filters ? !feed.filters.allows(category) : false;' in script
    assert 'element.querySelectorAll(".live-chat-message").forEach(row => {' in script
    assert 'if (!row.hidden) feed.hasUnseenMessages = true;' in script


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
async def test_deleted_chat_messages_update_live_but_are_omitted_on_refresh():
    service = LiveChatService(None)
    message = service.publish_twitch(twitch_payload("This will be deleted", "deleted-message"))
    subscriber = service.subscribe("channel-1")

    await service.remove_message("channel-1", message.id)

    history = service.history("channel-1")
    update = subscriber.get_nowait()
    assert history == []
    assert update.id == message.id
    assert update.deleted is True


def test_clear_chat_removes_twitch_history_and_notifies_subscribers():
    service = LiveChatService(None)
    twitch = service.publish_twitch(twitch_payload("hello"))
    youtube = UnifiedChatMessage(id="youtube:1", platform="youtube", kind="chat", username="viewer",
                                 display_name="Viewer", message="keep me", timestamp=twitch.timestamp)
    service.publish("channel-1", youtube)
    queue = service.subscribe("channel-1")
    other = service.subscribe("other-channel")
    service.clear_chat("channel-1")
    assert [item["id"] for item in service.history("channel-1")] == [youtube.id]
    assert queue.get_nowait() == {"event": "chat-clear", "platform": "twitch"}
    assert other.empty()


@pytest.mark.parametrize("platform,connected,url", [
    ("twitch", False, "/connect"), ("youtube", False, "/channel/customization?social_tab=youtube#youtube-integration"),
    ("twitch", True, None), ("youtube", True, None)])
def test_platform_filter_connection_links(platform, connected, url):
    from pathlib import Path
    from jinja2 import Template
    source = Path("web/templates/channel/dashboard.html").read_text(encoding="utf-8")
    heading = source.split('<div class="chat-filter-platform-heading">', 1)[1].split('</div>', 1)[0]
    html = Template(heading).render(platform_key=platform, platform_label=platform.title(), connected=connected,
                                   twitch_connected=connected, youtube_chat=SimpleNamespace(connected=connected))
    if url:
        assert "Not connected" in html
        assert "disabled" in html
        assert f'href="{url}"' in html
    else:
        assert "Not connected" not in html
        assert ">Connected</a>" in html
        assert 'data-connected="true"' in html
        assert 'href="' in html


@pytest.mark.asyncio
async def test_slash_clear_only_clears_local_chat_after_twitch_accepts():
    channel = SimpleNamespace(delete_chat_messages=AsyncMock())
    live_chat = SimpleNamespace(clear_chat=Mock())
    bot = SimpleNamespace(create_partialuser=lambda _: channel, services=SimpleNamespace(live_chat=live_chat))
    await dashboard_router.execute_twitch_slash_command(bot, "channel-1", "/clear")
    live_chat.clear_chat.assert_called_once_with("channel-1")
    live_chat.clear_chat.reset_mock()
    channel.delete_chat_messages.side_effect = RuntimeError("Rejected")
    with pytest.raises(RuntimeError):
        await dashboard_router.execute_twitch_slash_command(bot, "channel-1", "/clear")
    live_chat.clear_chat.assert_not_called()


@pytest.mark.asyncio
async def test_clear_event_is_streamed_even_in_commands_view():
    from web.shared.live_chat import stream_chat_events
    service = LiveChatService(None)
    events = stream_chat_events(SimpleNamespace(is_disconnected=AsyncMock(return_value=False)),
                                service, "channel-1", "commands")
    try:
        assert (await anext(events)).startswith("retry:")
        assert (await anext(events)).startswith("event: history-complete")
        service.clear_chat("channel-1")
        assert (await anext(events)).startswith("event: chat-clear")
    finally:
        await events.aclose()
    assert "channel-1" not in service.subscribers


@pytest.mark.asyncio
@pytest.mark.parametrize("length,status", [(500, 200), (501, 400)])
async def test_dashboard_enforces_500_character_message_limit(monkeypatch, length, status):
    channel = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=True)))
    bot = SimpleNamespace(create_partialuser=lambda _: channel, services=SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": SimpleNamespace(id="channel-1")})))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: bot)
    request = Request({"type": "http", "session": {
        CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}})
    response = await dashboard_router.channel_send_chat_message(request, "x" * length, "twitch", "csrf", "")
    assert response.status_code == status
    assert channel.send_message.await_count == (1 if status == 200 else 0)


@pytest.mark.asyncio
async def test_youtube_stream_publishes_immediately_and_uses_existing_token(monkeypatch):
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace(access_token="access")
    service._ensure_access_token = AsyncMock(return_value=service.connections["channel-1"])
    service._poll_live_chat = AsyncMock()
    requests = []

    class FakeChannel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def unary_stream(self, method, **kwargs):
            assert method == "/youtube.api.v3.V3DataLiveChatMessageService/StreamList"

            def call(request, *, metadata):
                requests.append((request, metadata))

                async def events():
                    item = youtube_live_chat_pb2.LiveChatMessage(id="message-1")
                    item.snippet.display_message = "Hello from YouTube"
                    item.snippet.has_display_content = True
                    item.snippet.published_at = "2026-09-26T01:00:00Z"
                    item.author_details.channel_id = "author-1"
                    item.author_details.display_name = "Viewer"
                    yield youtube_live_chat_pb2.LiveChatMessageListResponse(
                        next_page_token="token-2", items=[item], offline_at="2026-09-26T01:01:00Z"
                    )

                return events()

            return call

    monkeypatch.setattr("bot.services.channels.live_chat.grpc.aio.secure_channel", lambda *args: FakeChannel())
    await service._stream_live_chat("channel-1", "live-chat-1")

    assert requests[0][0].live_chat_id == "live-chat-1"
    assert requests[0][1] == (("authorization", "Bearer access"),)
    assert service.history("channel-1")[0]["message"] == "Hello from YouTube"
    service._poll_live_chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_youtube_stream_falls_back_to_polling_after_disconnect(monkeypatch):
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace(access_token="access")
    service._ensure_access_token = AsyncMock(return_value=service.connections["channel-1"])
    service._poll_live_chat = AsyncMock()

    class FakeChannel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def unary_stream(self, method, **kwargs):
            def call(request, *, metadata):
                async def events():
                    yield youtube_live_chat_pb2.LiveChatMessageListResponse(next_page_token="last-token")
                    raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE)

                return events()

            return call

    monkeypatch.setattr("bot.services.channels.live_chat.grpc.aio.secure_channel", lambda *args: FakeChannel())
    await service._stream_live_chat("channel-1", "live-chat-1")
    service._poll_live_chat.assert_awaited_once_with("channel-1", "live-chat-1", page_token="last-token")


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


@pytest.mark.asyncio
async def test_youtube_watcher_waits_for_quota_reset(monkeypatch):
    request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/liveBroadcasts")
    response = httpx.Response(403, request=request, json={
        "error": {"message": "Daily quota exceeded", "errors": [{"reason": "quotaExceeded"}]}
    })
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(side_effect=httpx.HTTPStatusError(
        "Forbidden", request=request, response=response
    ))
    service._seconds_until_youtube_quota_reset = lambda: 9876.0
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr("bot.services.channels.live_chat.asyncio.sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await service._watch_youtube("channel-1")

    sleep.assert_awaited_once_with(9876.0)
    assert service.youtube_statuses["channel-1"] == (
        "unavailable", "YouTube API quota is exhausted. Chat discovery will resume after the daily reset."
    )


@pytest.mark.asyncio
async def test_youtube_watcher_logs_chat_attachment_for_stream_session(monkeypatch, caplog):
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(return_value="chat-1")
    service._stream_live_chat = AsyncMock(side_effect=asyncio.CancelledError)

    with caplog.at_level("INFO", logger="RatBoomBot"), pytest.raises(asyncio.CancelledError):
        await service._watch_youtube("channel-1")

    attachment = next(record for record in caplog.records if "Attached to YouTube live chat" in record.message)
    assert attachment.broadcaster_id == "channel-1"


@pytest.mark.asyncio
async def test_youtube_polling_quota_error_reaches_watcher():
    request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/liveChat/messages")
    response = httpx.Response(403, request=request, json={
        "error": {"errors": [{"reason": "quotaExceeded"}]}
    })
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace()
    service._youtube_get = AsyncMock(side_effect=httpx.HTTPStatusError(
        "Forbidden", request=request, response=response
    ))

    with pytest.raises(httpx.HTTPStatusError):
        await service._poll_live_chat("channel-1", "chat-1")


@pytest.mark.asyncio
async def test_youtube_watcher_reuses_known_chat_after_temporary_failure(monkeypatch, caplog):
    request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/liveChat/messages")
    response = httpx.Response(403, request=request, json={
        "error": {"errors": [{"reason": "quotaExceeded"}]}
    })
    service = LiveChatService(None)
    service.started = True
    service.connections["channel-1"] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(return_value="chat-1")
    service._stream_live_chat = AsyncMock(side_effect=[
        httpx.HTTPStatusError("Quota exceeded", request=request, response=response),
        asyncio.CancelledError(),
    ])
    service._seconds_until_youtube_quota_reset = lambda: 10.0
    sleep = AsyncMock()
    monkeypatch.setattr("bot.services.channels.live_chat.asyncio.sleep", sleep)

    with caplog.at_level("WARNING", logger="RatBoomBot"), pytest.raises(asyncio.CancelledError):
        await service._watch_youtube("channel-1")

    service._find_active_live_chat.assert_awaited_once_with("channel-1")
    assert service._stream_live_chat.await_count == 2
    sleep.assert_awaited_once_with(10.0)
    assert any("YouTube chat unavailable" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_youtube_watchers_only_run_during_twitch_stream(monkeypatch):
    monkeypatch.setattr("bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_ID", "client")
    monkeypatch.setattr("bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setattr("bot.services.channels.live_chat.httpx.AsyncClient", lambda **kwargs: SimpleNamespace(aclose=AsyncMock()))
    live = set()
    stream_logs = SimpleNamespace(get_active_session=lambda channel: object() if channel in live else None)
    broadcasters = SimpleNamespace(get_broadcasters=lambda: {})
    bot = SimpleNamespace(services=SimpleNamespace(stream_logs=stream_logs, broadcasters=broadcasters))
    service = LiveChatService(None, bot=bot)
    service.connections["channel-1"] = SimpleNamespace(channel_id="youtube-1", channel_title="Channel")
    service._refresh_seventv_global_loop = AsyncMock()
    service._start_watcher = Mock()

    await service.start()
    service._start_watcher.assert_not_called()
    assert service.get_youtube_state("channel-1").detail == "Waiting for the Twitch stream to go live."

    live.add("channel-1")
    service.start_youtube_for_twitch_stream("channel-1")
    service._start_watcher.assert_called_once_with("channel-1")

    live.clear()
    await service.stop_youtube_for_twitch_stream("channel-1")
    assert service.get_youtube_state("channel-1").detail == "Waiting for the Twitch stream to go live."
    await service.stop()

    service._start_watcher.reset_mock()
    live.add("channel-1")
    await service.start()
    service._start_watcher.assert_called_once_with("channel-1")
    await service.stop()


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
async def test_dashboard_viewer_queue_next_rejects_stale_highlight(monkeypatch):
    queue = SimpleNamespace(
        next_viewers=AsyncMock(),
        list_queue=lambda _: ["bob", "alice"]
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=SimpleNamespace(viewer_queue=queue)))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/api/viewer-queue/action", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
        "scheme": "http", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"}
    })

    response = await dashboard_router.channel_viewer_queue_action(request, "next", "csrf", 0, 0, 2, "alice,bob")

    assert response.status_code == 409
    queue.next_viewers.assert_not_awaited()


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
    expected = {"field": field, "value": expected_value, "announcement_sent": True}
    if field == "game":
        expected["box_art_url"] = ""
    assert json.loads(response.body) == expected
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
        yield SimpleNamespace(id="456", name="Chat", box_art=SimpleNamespace(url_for=lambda w, h: f"https://example.com/chat-{w}x{h}.jpg"))

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
        {"id": "456", "name": "Chat", "box_art_url": "https://example.com/chat-96x128.jpg"},
        {"id": "509658", "name": "Just Chatting"},
        {"id": "123", "name": "Retro"}
    ]}
    assert calls == [("chat", {"token_for": "channel-1", "first": 50, "max_results": 50})]


@pytest.mark.asyncio
async def test_current_category_artwork_uses_channel_category_id():
    artwork = SimpleNamespace(url_for=Mock(return_value="https://example.com/category.jpg"))
    runtime_bot = SimpleNamespace(
        create_partialuser=lambda _: SimpleNamespace(fetch_channel_info=AsyncMock(return_value=SimpleNamespace(
            title="Title", game_name="Retro", game_id="123"
        ))),
        fetch_game=AsyncMock(return_value=SimpleNamespace(id="123", name="Retro", box_art=artwork))
    )
    metadata = await dashboard_router.get_twitch_channel_metadata(runtime_bot, "channel-1")
    assert metadata == {"title": "Title", "game": "Retro", "box_art_url": "https://example.com/category.jpg"}
    runtime_bot.fetch_game.assert_awaited_once_with(id="123", token_for="channel-1")
    artwork.url_for.assert_called_once_with(96, 128)


@pytest.mark.asyncio
async def test_category_artwork_failure_keeps_channel_metadata_available():
    runtime_bot = SimpleNamespace(
        create_partialuser=lambda _: SimpleNamespace(fetch_channel_info=AsyncMock(return_value=SimpleNamespace(
            title="Title", game_name="Retro", game_id="123"
        ))),
        fetch_game=AsyncMock(side_effect=RuntimeError("Artwork unavailable"))
    )
    assert await dashboard_router.get_twitch_channel_metadata(runtime_bot, "channel-1") == {
        "title": "Title", "game": "Retro", "box_art_url": ""
    }
    assert await dashboard_router.get_category_artwork(runtime_bot, "channel-1", "0") == ""
    assert runtime_bot.fetch_game.await_count == 1


def test_category_artwork_spans_metadata_rows_and_previews_picker_selection():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    script = open("web/static/js/dashboard-channel-metadata.js", encoding="utf-8").read()
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    assert 'data-current-category-art' in dashboard
    assert 'aria-label="Select category"' in dashboard
    assert 'categoryArtHome?.addEventListener("click"' in script
    assert 'categoryArtHome?.setAttribute("aria-expanded", String(visible))' in script
    assert 'data-category-preview' not in dashboard
    assert 'data-game-options role="listbox"' in dashboard
    assert 'grid-row: 1 / span 2' in styles
    assert 'image.className = "twitch-category-art"' in script
    assert 'button.appendChild(image)' in script
    assert 'data-game-suggestions popover="manual"' not in dashboard
    assert 'gameSuggestions.showPopover()' not in script
    assert 'setCurrentCategoryArt(game?.box_art_url || "", game?.name || savedCategoryName)' in script
    assert 'categoryArtHome?.setAttribute("title", name)' in script
    assert styles.count('.dashboard-hover-tooltip {') == 1
    assert 'if (!visible && restoreArtwork) setCurrentCategoryArt(savedCategoryArt)' in script
    assert 'updateCategoryPreview(game);\n        setGameSuggestionsVisible(false, false)' in script
    assert 'savedCategoryArt = result.box_art_url || ""' in script
    assert 'card.classList.toggle("is-category-selecting", visible)' in script
    assert 'data-game-selection-preview' in dashboard
    assert 'visible ? selectionPreview : categoryArtHome' in script
    assert 'categoryArtAnimation = currentCategoryArt.animate([' in script
    assert 'if (gameSuggestions.hidden === !visible' in script
    assert 'oldRect.left - newRect.left' in script
    assert 'oldRect.width / newRect.width' in script
    assert 'grid-template-columns: minmax(0,1fr) minmax(0,min(30%,120px))' in styles
    assert 'dashboard-carousel-card-changed' in script
    assert 'gameOptionsList.replaceChildren()' in script
    assert 'updateCategoryPreview(gameOptions[selectedGame])' in script
    assert 'pointerenter", () => highlightGame(index, false)' in script
    assert 'gameOptionsList.children[selectedGame]?.scrollIntoView' in script
    assert 'normalizedQuery === renderedGameQuery ? gameOptionsList.scrollTop : 0' in script
    assert 'gameOptionsList.scrollTop = previousScroll' in script
    assert 'renderGameOptions(result.games, query, result.more_games)' in script


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


def test_dashboard_carousel_keeps_stream_player_mounted_across_breakpoints():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    carousel = open("web/static/js/dashboard-carousel.js", encoding="utf-8").read()

    assert dashboard.index("dashboard-carousel.js") < dashboard.index("dashboard-stream-player.js")
    assert ".dashboard-carousel-deck, .dashboard-carousel-slide { display: contents; }" in styles
    assert "playerSlide.append(player);" in carousel
    assert "slides = [playerSlide];" in carousel
    assert "index === 0 ? card.elements.slice(1) : card.elements" in carousel
    assert "slides.slice(1).forEach(slide => slide.remove());" in carousel
    assert "deck.replaceChildren()" not in carousel
    assert 'const media = window.matchMedia("(max-width: 768px)")' in carousel
    assert 'deck.setAttribute("aria-roledescription", "carousel")' in carousel
    assert 'deck.addEventListener("keydown", event =>' in carousel
    assert 'deck.addEventListener("touchmove", event =>' in carousel
    assert 'event.target.closest(".dashboard-tabs' not in carousel
    assert 'event.target.closest(".queue-list") && !event.target.closest("button")' in carousel
    assert 'if (!media.matches || event.touches.length !== 1) return;' in carousel
    assert 'suppressClickUntil = performance.now() + 350;' in carousel
    assert 'event.preventDefault()' in carousel


def test_dashboard_first_carousel_card_retains_shared_slide_animation():
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    selector = '.channel-page-overview .dashboard-carousel-slide[data-dashboard-carousel-slide="0"].is-active'
    first_card_rule = styles.split(selector, 1)[1].split("}", 1)[0]

    # Leave the embed untransformed at rest without snapping over the outgoing card.
    assert "transform: none;" in first_card_rule
    assert "transition:" not in first_card_rule
    assert '.dashboard-carousel-slide.is-active { opacity: 1; visibility: visible; pointer-events: auto; transform: translateX(0); transition: transform .3s ease, opacity .3s ease, visibility 0s; }' in styles


def test_mobile_dashboard_reclaims_card_space_and_places_stats_in_navbar():
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    mobile = styles.split('.channel-page-overview .dashboard-carousel-navbar-label {', 1)[1]
    stats_rule = mobile.split('.sidebar > .dashboard-header-side {', 1)[1].split('}', 1)[0]
    deck_rule = mobile.split('.dashboard-carousel-deck { position: absolute;', 1)[1].split('}', 1)[0]
    slide_rule = mobile.split('.dashboard-carousel-slide { position: absolute;', 1)[1].split('}', 1)[0]
    edge_rule = mobile.split('.dashboard-carousel-peek {', 1)[1].split('}', 1)[0]

    assert 'position: fixed;' in stats_rule
    assert 'top: calc(var(--mobile-nav-height) / 2);' in stats_rule
    assert 'transform: translateY(-50%);' in stats_rule
    assert 'top: 0;' in deck_rule
    assert 'left: 12px;' in slide_rule and 'right: 12px;' in slide_rule
    assert '.dashboard-carousel-slide.is-neighbor { opacity: .65; visibility: visible; transform: translateX(calc(100% + 8px));' in mobile
    assert '.dashboard-carousel-slide.is-before.is-neighbor { transform: translateX(calc(-100% - 8px)); }' in mobile
    assert 'overflow: hidden;' in slide_rule
    assert 'width: 16px;' in edge_rule
    gradient_rule = mobile.split('.dashboard-carousel-peek::before {', 1)[1].split('}', 1)[0]
    assert 'width: 28px;' in gradient_rule
    assert 'pointer-events: none;' in gradient_rule
    assert '.dashboard-carousel-peek[data-dashboard-carousel-next]::before { right: 0; left: auto; }' in mobile
    assert 'top: var(--mobile-nav-height);' in edge_rule
    assert 'height: calc(var(--dashboard-mobile-viewport-height, 100dvh) - var(--mobile-nav-height));' in edge_rule
    main_rule = mobile.split('.streamer-main-content {', 1)[1].split('}', 1)[0]
    assert 'padding: 8px 0;' in main_rule
    assert '.streamer-main-content > .channel-dashboard-layout.has-carousel { padding-inline: 4px; }' in mobile
    assert 'left: 4px;' in deck_rule and 'right: 4px;' in deck_rule
    assert '.app-shell.sidebar-collapsed .sidebar .brand-copy { display: none; }' in mobile
    assert '.app-shell:not(.sidebar-collapsed) .sidebar > .dashboard-header-side { opacity: 0; visibility: hidden; pointer-events: none; transition: none; }' in mobile
    assert '.app-shell.sidebar-collapsed .sidebar > .dashboard-header-side { opacity: 1; visibility: visible; }' in mobile
    carousel = open("web/static/js/dashboard-carousel.js", encoding="utf-8").read()
    stats = open("web/static/js/dashboard-header-stats.js", encoding="utf-8").read()
    assert 'if (sidebar && statsRow) sidebar.append(statsRow);' in carousel
    assert 'if (statsRow && statsMarker.parentNode) statsMarker.after(statsRow);' in carousel
    assert 'document.querySelector("[data-dashboard-carousel]")' in stats
    assert '.sidebar .brand { z-index: 52; }' in mobile
    assert 'z-index: 51;' in stats_rule
    assert '.sidebar .brand { pointer-events: none; }' in mobile
    assert '.sidebar .brand .sidebar-logo-toggle { pointer-events: auto; }' in mobile
    assert 'container.querySelectorAll("[data-dashboard-stat]").forEach' in stats
    assert ': container.querySelector(`[data-dashboard-stat=' in stats


def test_mobile_dashboard_feeds_do_not_reserve_empty_scrollbar_gutters():
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    assert 'html:has(> body.channel-page-overview) { height: 100dvh; min-height: 0; overflow: hidden; scrollbar-gutter: auto; }' in styles
    rule = styles.split('/* Reserve space only when a feed actually needs a scrollbar. */', 1)[1].split('}', 1)[0]

    assert '.live-chat-feed-shell > .dashboard-chat-feed' in rule
    assert '#viewer-queue-content' in rule
    assert '.activity-scroll' in rule
    assert '.dashboard-command-feed' in rule
    assert '.dashboard-raid-tab #dashboard-raid' in rule
    assert 'width: 100%; margin-right: 0; padding-right: 0; scrollbar-gutter: auto;' in rule


def test_mobile_channel_navigation_uses_accessible_logo_toggle():
    layout = open("web/templates/channel/layout.html", encoding="utf-8").read()
    script = open("web/static/js/channel-sidebar.js", encoding="utf-8").read()
    styles = open("web/static/css/style.css", encoding="utf-8").read()

    assert 'class="sidebar-logo-toggle" data-sidebar-mobile-toggle aria-controls="channel-navigation"' in layout
    assert 'document.currentScript.parentElement.classList.add("sidebar-collapsed");' in layout
    assert layout.index('document.currentScript.parentElement') < layout.index('id="channel-navigation"')
    assert layout.index('data-sidebar-mobile-back') < layout.index('data-sidebar-mobile-toggle')
    assert 'mobileBack?.addEventListener("click", () => {' in script
    assert 'mobileToggle?.focus({preventScroll: true});' in script
    assert '.sidebar-mobile-back { display: none; }' in styles
    assert '.sidebar-mobile-back { position: absolute; z-index: 1; top: 0; left: 0; display: block; width: 52px; height: 42px;' in styles
    back_rule = styles.split('.channel-page .sidebar-mobile-back { position: absolute;', 1)[1].split('}', 1)[0]
    assert 'transition:' not in back_rule
    assert '.app-shell:not(.sidebar-collapsed) .sidebar-mobile-back { opacity: 1; visibility: visible; pointer-events: auto; }' in styles
    assert '.sidebar-mobile-back svg { position: absolute; top: 50%; left: 8px; width: 24px; height: 24px;' in styles
    assert '.sidebar-logo-toggle { position: relative; z-index: 2;' in styles
    assert '.app-shell:not(.sidebar-collapsed) .sidebar-logo-toggle { margin-left: 40px; transition: margin-left .24s ease, outline-color .16s ease; }' in styles
    assert 'id="channel-navigation"' in layout
    assert 'mobileToggle.disabled = !mobile;' in script
    assert 'mobileToggle.setAttribute("aria-expanded", String(mobile && !collapsed));' in script
    assert 'if (mobileMedia.matches) toggleNavigation();' in script
    assert '☰' not in script
    assert '.channel-page .sidebar .sidebar-toggle { display: none !important; }' in styles
    assert '.channel-page .sidebar-logo-toggle:hover,' in styles
    assert '.channel-page .sidebar .brand { position: relative; overflow: visible; }' in styles
    assert 'transition: margin-left .24s ease, outline-color .16s ease;' in styles
    assert '.app-shell:not(.sidebar-collapsed) .sidebar-logo-toggle { transition: none; }' in styles
    assert '.sidebar-logo-toggle .brand-mark { transition: width .24s ease, height .24s ease, flex-basis .24s ease; }' in styles
    assert '.sidebar-logo-toggle .brand-mark { transition: none; }' in styles
    assert '.channel-page .sidebar-logo-toggle:focus-visible { outline-color: #fff; }' in styles


def test_queue_names_truncate_before_centered_drag_indicator():
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    script = open("web/static/js/dashboard-viewer-queue.js", encoding="utf-8").read()
    template = open("web/templates/channel/dashboard.html", encoding="utf-8").read()

    assert 'grid-template-columns: 30px minmax(0, calc(50% - 59px)) minmax(0, 1fr);' in styles
    base_row = styles.split('\n.queue-list-item {', 1)[1].split('}', 1)[0]
    assert 'grid-template-columns: 30px minmax(0, 1fr) auto;' in base_row
    assert '.queue-list-item:hover, .queue-list-item:focus-within, .queue-list-item.queue-drag-ghost { grid-template-columns: 30px minmax(0, calc(50% - 59px)) minmax(0, 1fr); }' in styles
    assert '@media (hover: none) { .queue-list-item { grid-template-columns: 30px minmax(0, calc(50% - 59px)) minmax(0, 1fr); } }' in styles
    assert 'justify-self: end;' in styles.split('\n.queue-item-actions {', 1)[1].split('}', 1)[0]
    assert 'text-overflow: ellipsis;' in styles.split('\n.queue-username {\n', 1)[1].split('}', 1)[0]
    assert 'usernameLabel.title = label;' in script
    assert 'class="queue-username" title="{{ member.label }}"' in template


def test_dashboard_scrollbars_appear_on_panel_hover_or_keyboard_focus():
    styles = open("web/static/css/style.css", encoding="utf-8").read()
    feeds = ':is(.dashboard-chat-feed, #viewer-queue-content, .activity-scroll, .dashboard-command-feed, #dashboard-raid)'

    assert '@media (hover: hover)' in styles
    assert f'.panel {feeds} {{ scrollbar-width: none; }}' in styles
    assert f'.panel:is(:hover, :focus-within) {feeds} {{ scrollbar-width: thin; }}' in styles
    assert f'.panel {feeds}::-webkit-scrollbar {{ width: 0; }}' in styles
    assert f'.panel:is(:hover, :focus-within) {feeds}::-webkit-scrollbar {{ width: 8px; }}' in styles


def test_activity_motion_covers_feeds_automod_commands_and_tabs_without_chat_changes():
    dashboard = open("web/templates/channel/dashboard.html", encoding="utf-8").read()
    motion = open("web/static/js/dashboard-activity-motion.js", encoding="utf-8").read()
    chat = open("web/static/js/live-chat-feed.js", encoding="utf-8").read()
    styles = open("web/static/css/style.css", encoding="utf-8").read()

    assert 'dashboardActivityMotion.reconcile(element, render)' in dashboard
    assert 'dashboardActivityMotion.remove(automodContent, row)' in dashboard
    assert 'if (wasHidden && !panel.hidden) window.dashboardActivityMotion?.switchTab(panel)' in dashboard
    assert 'if (feed.newestFirst) window.dashboardActivityMotion?.enter(feed.element, row, shouldFollowNewest)' in chat
    assert 'initialized.has(container) && visible(container) && !reduced.matches' in motion
    assert 'new Set(previous.map(key))' in motion
    assert '@keyframes activity-fold-in' in styles
    assert '@keyframes activity-slide-away' in styles
    assert 'row.inert = true;' in motion
    queue = open("web/static/js/dashboard-viewer-queue.js", encoding="utf-8").read()
    assert 'window.dashboardActivityMotion?.highlight(item, Math.min(index * 45, 600));' in queue
    assert 'if (!removing) highlight(row, delay);' in motion
    assert 'background: rgba(139,92,246,.16);' in styles
    assert '@keyframes entry-added-highlight' in styles


def test_dashboard_mobile_activity_panels_keep_tabs_above_scrollable_events():
    styles = open("web/static/css/style.css", encoding="utf-8").read()

    assert '.channel-page-overview .dashboard-carousel-slide > .dashboard-activity-panel > .activity-tabs { flex: 0 0 auto; }' in styles
    assert '.channel-page-overview .dashboard-carousel-slide > .dashboard-activity-panel > [data-activity-panel]:not([hidden]) { display: flex; min-height: 0; flex: 1 1 auto; flex-direction: column; overflow: hidden; }' in styles
    assert '.channel-page-overview .dashboard-carousel-slide .activity-scroll,' in styles


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
    assert 'data-activity-tab="redeems">Redeems</button>' in dashboard
    assert 'data-activity-tab="checkins"' not in dashboard
    assert 'data-activity-panel="checkins"' not in dashboard
    assert 'id="community-activity-content"' in dashboard
    assert '{% for entry in redemption_activity.feed %}' in dashboard
    assert 'renderFeed(feed)' in dashboard
    assert 'activity: "redeems"' in dashboard
    assert '<h4>No commands yet</h4>' in dashboard
    assert '<p>Chat commands will appear here.</p>' in dashboard
    assert 'data-activity-tab="mod-actions"' in dashboard
    assert 'data-activity-tab="automod"' in dashboard
    assert 'data-newest-first="true"' in dashboard
    assert dashboard.count('data-newest-first="true"') == 1
    assert 'const feedScroller = createTopScroller(feedContent);' in dashboard
    assert 'const modActionScroller = createTopScroller(modActionContent);' in dashboard
    assert 'const automodScroller = createTopScroller(automodContent);' in dashboard
    assert 'const activityEndpoint = "/channel/api/redemptions";' in dashboard
    assert 'window.setInterval(refreshActivity, 2000);' in dashboard
    assert 'renderModeration(data);' in dashboard
    assert 'const anchor = atTop ? null : [...element.querySelectorAll("[data-activity-key]")]' in dashboard
    assert 'element.scrollTop += replacement' in dashboard
    assert 'renderTopScroller(feedScroller, () => renderFeed(feed), lastFeedSignature !== null);' in dashboard
    assert '.activity-feed-shell { position: relative; display: flex; min-height: 0; flex: 1; flex-direction: column; }' in dashboard_styles
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
    assert 'data-activity-tab="raid"' not in dashboard
    boss_hunt = open("web/templates/channel/boss_hunt.html", encoding="utf-8").read()
    sidebar = open("web/templates/channel/layout.html", encoding="utf-8").read()
    assert 'include "channel/raid_summary.html"' in boss_hunt
    assert 'href="/channel/boss-hunt"' in sidebar
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
    assert 'container.querySelectorAll("[data-dashboard-stat]")' in header_stats_script
    assert 'dashboard.querySelector("[data-dashboard-points-lost]")' in header_stats_script
    assert "data-stream-status" in dashboard
    assert 'class="dashboard-ad-stat state-{{ ad_status.state }}"' in dashboard
    assert 'class="dashboard-header-stat dashboard-ad-stat' not in dashboard
    assert 'data-ad-panel' in dashboard
    assert 'data-started-at="{{ ad_status.started_at or \'\' }}"' in dashboard
    assert 'data-ad-progress-ring' in dashboard
    assert 'data-ad-progress-mirror-ring' in dashboard
    assert dashboard.index('data-ad-status-mirror') < dashboard.index('<h3>Ads</h3>') < dashboard.index('data-ad-status data-state=') < dashboard.index('data-ad-action="run-90"')
    assert 'stickyMirror.querySelector("[data-ad-status-mirror-text]").textContent = label.textContent;' in ad_status_script
    assert 'stickyProgressRing.style.setProperty("--ad-ring-duration", `${remainingMs}ms`);' in ad_status_script
    assert 'stickyProgressRing.style.strokeDashoffset = progressRing.style.strokeDashoffset;' in ad_status_script
    assert '...["ad-ring-intro", "ad-ring-countdown"].filter(name => container.classList.contains(name))' in ad_status_script
    assert 'stickyMedia.matches && window.scrollY > 32' in ad_status_script
    assert '.dashboard-header-stats > .dashboard-ad-sticky.is-visible' in dashboard_styles
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
    assert '<h3 class="chat-heading">Combined Chat' in dashboard
    assert 'data-chat-filter-toggle aria-label="Filter chat" aria-expanded="false"' in dashboard
    assert 'data-activity-link="commands"' not in dashboard
    assert "Stream activity" not in dashboard
    assert "Viewer games" not in dashboard
    assert 'data-refresh-url="/channel/api/dashboard-stats"' in dashboard
    assert "Back to Overview" not in features
    assert dashboard.index("dashboard-chat-composer-actions") < dashboard.index("data-chat-send-status") < dashboard.index("chat-send-button")
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
    assert 'if (feed.followNewest) scrollToNewest(feed)' in live_chat_script
    assert 'return feed.newestFirst ? feed.element.scrollTop <= 24 : distanceFromBottom(feed.element) <= 24;' in live_chat_script
    assert 'if (feed.newestFirst) feed.element.prepend(row);' in live_chat_script
    assert 'const oldest = feed.newestFirst ? messages[messages.length - 1] : messages[0];' in live_chat_script
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
    assert '.queue-next-picker:focus-within' not in dashboard_styles
    assert '.queue-next-picker select:focus-visible' in dashboard_styles
    assert 'nextCountPicker.classList.add("is-selection-committed")' in queue_script
    assert 'data-queue-next-count>4</span>' in dashboard
    assert '#viewer-queue-content { width: calc(100% + 8px); max-height: 430px; margin-right: -8px; padding-right: 8px;' in dashboard_styles
    assert 'range(1, 11)' in dashboard
    assert 'data-queue-action="clear"' in dashboard
    assert 'href="/channel/viewer-queue/blacklist"' in dashboard
    assert 'data-queue-count' in dashboard
    assert '.queue-panel-header [data-queue-count] { display: inline-flex; min-height: 30px; align-items: center; margin-left: auto; padding: 5px 9px; border: 0;' in dashboard_styles
    assert 'color: var(--text); font-size: 13px; font-weight: 800;' in dashboard_styles
    assert 'queueContent.addEventListener("pointerdown"' in queue_script
    assert 'runAction("reorder", originalPosition, newPosition)' in queue_script
    assert 'queueContent.addEventListener("touchstart"' in queue_script
    assert 'document.addEventListener("touchmove"' in queue_script
    assert 'list.insertBefore(placeholder, rows[destination] || null)' in queue_script
    assert 'shiftAnimations.set(item, item.animate(' in queue_script
    assert '.queue-drop-placeholder' in dashboard_styles
    assert '.queue-list .queue-list-item.dragging { display: none !important; }' in dashboard_styles
    assert '.queue-drag-ghost.is-dropping' in dashboard_styles
    assert 'ghost.querySelector(".queue-position").textContent = String(newPosition + 1)' in queue_script
    assert 'item.classList.toggle("is-next-preview", index < nextCount)' in queue_script
    assert 'highlightNext();' in queue_script
    assert 'const nextList = list || document.createElement("ul")' in queue_script
    assert 'if (!list) queueContent.replaceChildren(nextList)' in queue_script
    assert '.queue-list-item.is-next-preview' in dashboard_styles
    assert '#viewer-queue-content > .queue-list::before { position: absolute; z-index: 1; top: var(--queue-line-top, 0px); left: 22px; width: 3px; height: var(--queue-line-height, 0px);' in dashboard_styles
    assert 'list.style.setProperty("--queue-line-height", `${Math.max(0, center(last) - top)}px`)' in queue_script
    assert 'function updateDragPreviewOrder()' in queue_script
    assert 'const order = previewOrder(list, source, placeholder)' in queue_script
    assert 'item.classList.toggle("is-next-preview", index <= lastHighlighted)' in queue_script
    assert 'ghost.classList.toggle("is-next-preview", newPosition <= lastHighlighted)' in queue_script
    assert 'updatePreviewLine(list, order)' in queue_script
    assert 'item.style.setProperty("--queue-preview-delay"' in queue_script
    assert 'const removedRows = previousRows.filter(item => !currentNames.has(item.dataset.username))' in queue_script
    assert 'item.classList.add("is-removing")' in queue_script
    assert 'item.classList.add("is-appearing")' in queue_script
    assert 'trackPreviewLine(list, previousRows, exitDuration)' in queue_script
    assert 'generation !== previewLineGeneration || rows.some(row => row.parentElement !== list)' in queue_script
    assert '@keyframes queue-slide-away' in dashboard_styles
    assert '@keyframes queue-fold-in' in dashboard_styles
    assert 'window.dashboardQueueTest = {' in queue_script
    assert 'simulationActive = true;' in queue_script
    assert 'simulationActive = false;' in queue_script
    assert 'if (!simulationActive) renderQueue(actualState);' in queue_script
    assert 'if (simulationActive) {' in queue_script
    assert 'moveIcon("top")' in queue_script
    assert 'moveIcon("bottom")' in queue_script
    assert 'if (index > 0) actions.appendChild(actionButton(moveIcon("top")' in queue_script
    assert 'if (index < users.length - 1) actions.appendChild(actionButton(moveIcon("bottom")' in queue_script
    assert 'button.dataset.queueItemAction = action;' in queue_script
    assert '.queue-item-actions { display: grid; grid-template-columns: repeat(3, 28px);' in dashboard_styles
    assert '.queue-item-actions > [data-queue-item-action="top"] { grid-column: 1; }' in dashboard_styles
    assert '.queue-item-actions > [data-queue-item-action="bottom"] { grid-column: 2; }' in dashboard_styles
    assert 'const previousTops = movedUsername && !reduceMotion.matches' in queue_script
    assert 'renderQueue(result, false, action === "top" || action === "bottom" ? position : 0)' in queue_script
    assert '{duration: 320, easing: "cubic-bezier(.2,.8,.2,1)"}' in queue_script
    assert '.queue-list-item.is-moving { z-index: 3; }' in dashboard_styles
    assert 'actionButton("🗑"' in queue_script
    assert 'item.append(positionLabel, usernameLabel, grabIndicator(), actions);' in queue_script
    assert 'class="queue-grab-indicator" aria-hidden="true"' in dashboard
    assert '@media (hover: none) { .queue-item-actions { opacity: 1; pointer-events: auto; } .queue-grab-indicator { opacity: 1; } }' in dashboard_styles
    assert '.queue-grab-indicator { position: absolute; z-index: 2; top: 50%; left: calc(50% + 8px);' in dashboard_styles
    assert '.queue-grab-indicator::before, .queue-grab-indicator::after { width: 16px; height: 2px;' in dashboard_styles
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
    assert "padding-right: 8px; overflow-y: auto; scrollbar-gutter: stable;" in dashboard_styles
    assert '.queue-list .queue-list-item, .queue-list .queue-drop-placeholder { padding-left: 8px; }' in dashboard_styles
    assert '.queue-list-item.is-next-preview { border-top-color: transparent; background: rgba(139,92,246,.16); }' in dashboard_styles
    assert '.channel-page-overview .dashboard-activity-panel .activity-scroll,' in dashboard_styles
    assert '.channel-page-overview .dashboard-activity-panel .dashboard-command-feed,' in dashboard_styles
    assert '.channel-page-overview .dashboard-activity-panel .dashboard-raid-tab #dashboard-raid { width: calc(100% + 8px); margin-right: -8px; padding-right: 8px; scrollbar-gutter: stable; }' in dashboard_styles
    assert "background: #0f1115" in widget_styles
    assert "background: transparent" not in widget_styles.split("body {", 1)[0]
    assert ".widget-chat-feed::-webkit-scrollbar" in widget_styles
    assert "overflow-y: auto" in widget_styles
    assert "shouldFollowNewest" in chat_script
    assert "if (shouldFollowNewest)" in chat_script
    assert 'const jumpPath = feed.newestFirst ? "M12 19V5m-6 6 6-6 6 6" : "M12 5v14m-6-6 6 6 6-6";' in chat_script
    assert 'feed.jumpButton.title = "Jump to present";' in chat_script
    assert 'jumpButton.title = "Jump to present";' in dashboard
    assert 'makeElement("div", "live-chat-feed-shell")' in chat_script
    assert 'element.addEventListener("scroll", () => {' in chat_script
    assert "updateJumpButton(feed);" in chat_script
    assert "feed.element.scrollTop = feed.element.scrollHeight;" in chat_script
    assert "feed.hasUnseenMessages = true" in chat_script
    assert 'maxMessages: Number(element.dataset.maxMessages || 100)' in chat_script
    assert 'data-max-messages="150"' in dashboard
    assert 'classList.toggle("has-unseen", feed.hasUnseenMessages && !atPresent)' in chat_script
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
    assert ".chat-send-status { flex: 1 1 0; min-width: 0;" in dashboard_styles
    assert "text-align: right; text-overflow: ellipsis;" in dashboard_styles
    assert "opacity: .8;" in dashboard_styles
    assert ".chat-send-status.is-fading { opacity: 0; }" in dashboard_styles
    assert "height: calc(1.4em + 22px);" in dashboard_styles
    assert "resize: none;" in dashboard_styles
    assert 'status.dataset.connectionState === "disconnected"' in composer_script
    assert 'status.classList.add("is-fading")' in composer_script
    assert 'grid-template-areas: "player queue chat" "activities activities chat"' in dashboard_styles
    assert "grid-template-rows: max-content minmax(540px,1fr)" in dashboard_styles
    assert '.channel-dashboard-layout > .dashboard-channel-profile[hidden] { display: none; }' in dashboard_styles
    assert 'grid-template-areas: "stats" "player" "queue" "activities" "chat"' in dashboard_styles
    assert 'grid-template-areas: "stats stats" "player queue" "activities activities" "chat chat"' in dashboard_styles
    assert '@media (min-width: 769px) and (max-width: 1100px)' in dashboard_styles
    assert '@media (max-width: 600px) {\n    .channel-page-overview .dashboard-header-stats { grid-template-columns: repeat(6, minmax(0, 1fr)); }' in dashboard_styles
    assert 'height: calc(200dvh - var(--dashboard-stats-height, 36px) - 52px)' in dashboard_styles
    assert 'grid-template-rows: max-content minmax(0,3fr) minmax(0,2fr) calc(100dvh - var(--dashboard-stats-height, 36px) - 32px)' in dashboard_styles
    assert '.channel-page-overview .dashboard-chat-column > .dashboard-header-side { position: sticky; z-index: 20; top: 16px; display: flex; grid-area: stats; min-width: 0; margin-bottom: -6px; padding-bottom: 6px;' in dashboard_styles
    assert '.channel-page-overview .dashboard-chat-column > .dashboard-header-side { grid-area: stats; margin-bottom: 0;' not in dashboard_styles
    assert '.channel-page-overview .dashboard-chat-column > .dashboard-header-side::before { position: absolute; z-index: -1; top: -16px; right: -16px; bottom: -6px; left: -16px; background: var(--background);' in dashboard_styles
    assert '.channel-page-overview .viewer-queue-column > [data-viewer-queue-panel] { height: auto; min-height: 0; flex: 1 1 0; overflow-y: auto; }' in dashboard_styles
    assert '.channel-page-overview .live-chat-panel { height: 100%; min-height: 0; overflow: hidden; }' in dashboard_styles
    assert '.dashboard-activity-grid { display: grid; grid-area: activities;' in dashboard_styles
    assert '<header class="page-header dashboard-channel-profile" hidden>' in dashboard
    assert dashboard.index('class="panel dashboard-video-card"') < dashboard.index('class="panel live-chat-panel"')
    assert dashboard.index('class="panel dashboard-video-card"') < dashboard.index('class="dashboard-chat-column"') < dashboard.index('class="dashboard-header-side"') < dashboard.index('class="panel live-chat-panel"')
    assert '<span>Stream</span>' not in dashboard
    assert '{% if broadcaster.is_live %}Online{% else %}Offline{% endif %}' in dashboard
    assert 'data-stream-status' in dashboard and 'aria-pressed="true"' in dashboard
    assert 'class="panel-header dashboard-video-header"' in dashboard
    assert dashboard.index('data-channel-field="game"') < dashboard.index('data-channel-metadata-status') < dashboard.index('class="dashboard-video-frame"')
    assert '.dashboard-video-header .twitch-game-field { position: relative; }' in dashboard_styles
    assert '[data-channel-field="game"]:not(:focus):not(.editing) { padding-right: var(--metadata-status-padding, 8px); }' in dashboard_styles
    assert '[data-channel-field="game"].metadata-truncated:not(:focus):not(.editing)::after { right: var(--metadata-status-pencil-right, 8px); }' in dashboard_styles
    assert '.channel-metadata-status { position: absolute; z-index: 1; right: 0; bottom: 6px; max-width: min(60%,240px);' in dashboard_styles
    assert '.twitch-game-field:focus-within .channel-metadata-status { opacity: 0; }' in dashboard_styles
    assert 'setStatusSpace(Math.ceil(status.getBoundingClientRect().width))' in metadata_script
    assert 'statusSpaceTimer = window.setTimeout(() => setStatusSpace(0), 450)' in metadata_script
    assert '.dashboard-video-header { --metadata-label-width: 88px; display: grid; min-width: 0; grid-template-columns: minmax(0,1fr);' in dashboard_styles
    assert '.dashboard-video-header .twitch-channel-field { min-width: 0; grid-template-columns: var(--metadata-label-width) minmax(0,1fr);' in dashboard_styles
    assert '.dashboard-video-header .twitch-channel-field > h3 { margin: 0; line-height: 1.2; text-align: right;' in dashboard_styles
    assert '.dashboard-video-header .twitch-channel-field strong { box-sizing: border-box; width: 100%;' in dashboard_styles
    assert 'updateTitleEditingWidth' not in metadata_script
    assert 'range.selectNodeContents(field)' in metadata_script
    assert 'textWidth + pencilWidth > availableWidth + 1' in metadata_script
    assert '[data-channel-field].metadata-truncated:not(:focus):not(.editing)::after { position: absolute; top: 50%; right: 8px;' in dashboard_styles
    assert '[titleField, gameField].filter(Boolean).forEach(field => {' in metadata_script
    assert 'new MutationObserver(updateFieldPencil)' in metadata_script
    assert 'new ResizeObserver(updateFieldPencil)' in metadata_script
    assert 'field.addEventListener("blur", () => {' in metadata_script
    assert 'field.scrollLeft = 0;' in metadata_script
    assert 'if (document.activeElement === field) return;' in metadata_script
    assert '<h3>Title</h3>' in dashboard
    assert '<h3>Category</h3>' in dashboard
    assert '<h3>Twitch stream</h3>' not in dashboard
    assert '<h3>Stream preview</h3>' not in dashboard
    assert '.dashboard-header-stats { display: flex; width: 100%; min-width: 0; flex-wrap: wrap; justify-content: flex-start; gap: 6px; }' in dashboard_styles
    assert 'dashboard-header-stat-break' not in dashboard
    assert 'data-stream-player' in dashboard
    assert 'dashboard-stream-player.js' in dashboard
    assert 'https://player.twitch.tv/js/embed/v1.js' in dashboard
    assert dashboard.index('https://player.twitch.tv/js/embed/v1.js') < dashboard.index('dashboard-stream-player.js')
    assert 'data-is-live="{{ \'true\' if broadcaster.is_live else \'false\' }}"' in dashboard
    assert 'new Twitch.Player(mount.id, {' in stream_player_script
    assert 'parent: [window.location.hostname]' in stream_player_script
    assert 'autoplay: false' in stream_player_script
    assert 'muted: true' in stream_player_script
    assert 'twitchPlayer.addEventListener(Twitch.Player.PAUSE' in stream_player_script
    assert 'twitchPlayer.addEventListener(Twitch.Player.PLAYBACK_BLOCKED' in stream_player_script
    assert 'if (liveChanged) window.dispatchEvent(new CustomEvent("dashboard-stream-live-changed"' in header_stats_script
    assert '.dashboard-video-frame { width: 100%; min-width: 0; overflow: hidden; }' in dashboard_styles
    assert '.dashboard-video-player { display: block; width: 100%; min-width: 0; max-width: 900px; height: auto; margin-inline: auto; aspect-ratio: 16 / 9;' in dashboard_styles
    assert 'aspect-ratio: 16 / 9;' in dashboard_styles
    assert 'grid-template-columns: minmax(0,1.3fr) minmax(0,1fr)' in dashboard_styles
    assert dashboard.index('<div class="channel-dashboard-layout" data-dashboard-carousel>') < dashboard.index('<header class="page-header dashboard-channel-profile" hidden>')
    assert 'body class="dashboard-page channel-page channel-page-{{ active_page }}"' in channel_layout
    assert "data-sidebar-toggle" in channel_layout
    assert "channel-sidebar.js" in channel_layout
    assert 'localStorage.setItem(storageKey, String(desktopCollapsed))' in sidebar_script
    assert ".dashboard-page:not(.channel-page-overview) .main-content" in dashboard_styles
    assert "left: -36px; width: min(1250px,calc(100vw - 144px));" in dashboard_styles
    assert 'window.matchMedia("(max-width: 768px)")' in sidebar_script
    assert 'window.matchMedia("(min-width: 769px) and (max-width: 1100px)")' in sidebar_script
    assert 'compactMedia.matches ? !compactExpanded : desktopCollapsed' in sidebar_script
    assert 'enableTransitionsAfterLayout()' in sidebar_script
    assert 'sidebar-hover-locked' in sidebar_script
    assert '@media (min-width: 769px) {\n    .dashboard-page .app-shell.sidebar-collapsed.sidebar-hover-expanded .sidebar' in dashboard_styles
    assert dashboard_styles.index('.dashboard-page .app-shell.sidebar-collapsed.sidebar-hover-expanded { grid-template-columns: var(--sidebar-width) minmax(0, 1fr); }') < dashboard_styles.index('@media (min-width: 901px)')
    assert 'if (icon) icon.textContent = collapsed ? "›" : "‹";' in sidebar_script
    assert 'position: sticky;' in dashboard_styles
    assert '.navigation { display: flex; min-width: 0; min-height: 0; flex: 1; flex-direction: column; gap: 7px; overflow-x: hidden; overflow-y: auto; }' in dashboard_styles
    assert '.channel-page-overview .sidebar { position: fixed; z-index: 50; top: 0; right: 0; left: 0; width: 100%; height: 100dvh;' in dashboard_styles
    assert '.sidebar:hover { width: 100%; height: var(--mobile-nav-height); min-height: 0;' in dashboard_styles
    assert '.navigation { width: 100%; min-height: 0; flex-direction: column; justify-content: flex-start; gap: 7px; overflow-x: hidden; overflow-y: auto; }' in dashboard_styles
    assert '.sidebar-toggle span { display: block; transition: transform .24s ease, opacity .18s ease; }' in dashboard_styles
    assert 'transition: opacity .2s ease .08s, transform .24s ease .08s, visibility 0s linear 0s;' in dashboard_styles
    assert 'visibility: hidden; opacity: 0; transform: translateY(-10px); pointer-events: none;' in dashboard_styles
    assert '.navigation .nav-link { width: 100%; flex: 0 0 auto; justify-content: flex-start; }' in dashboard_styles
    assert '.sidebar .navigation,' in dashboard_styles
    assert ".sidebar:not(:hover) .sidebar-logout .button { gap: 10px; padding-right: 11px; padding-left: 11px; }" in dashboard_styles
    assert '.dashboard-page .sidebar-logout .button { justify-content: center; gap: 10px; overflow: hidden; padding-right: 11px; padding-left: 11px;' in dashboard_styles
    assert '.dashboard-page .app-shell.sidebar-collapsed .sidebar:not(.sidebar-hover-expanded) .sidebar-logout .button { gap: 0; justify-content: center; }' in dashboard_styles
    assert '.dashboard-page .app-shell.sidebar-collapsed.sidebar-hover-expanded .sidebar { width: var(--sidebar-width); padding-right: 14px; padding-left: 14px;' in dashboard_styles
    assert 'overflow: hidden;\n    padding: 11px 12px;\n    border-radius: 9px;' in dashboard_styles
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
    assert 'grid-template-rows: max-content max-content minmax(0,1fr) calc(100dvh - var(--dashboard-stats-height, 36px) - 16px)' not in dashboard_styles
    assert '.channel-page-overview .dashboard-video-frame { flex: 0 0 auto; aspect-ratio: 16 / 9; container-type: normal; }' in dashboard_styles
    assert '.channel-page-overview .dashboard-video-unavailable { width: 100%; height: 100%; aspect-ratio: auto; }' in dashboard_styles
    assert '--dashboard-video-height' not in dashboard_styles
    assert 'height: calc(200dvh - var(--dashboard-stats-height, 36px) - 20px)' not in dashboard_styles
    assert 'observer.observe(statsRow)' in header_stats_script
    assert 'observer.observe(videoCard)' not in header_stats_script
    assert '.channel-page-overview .dashboard-chat-column > .dashboard-header-side { position: sticky; z-index: 20; top: 0; display: flex; grid-area: stats; min-width: 0; margin-bottom: -12px; padding-block: 12px; background: var(--background); }' not in dashboard_styles
    assert '.channel-page-overview .dashboard-header-stats > .dashboard-header-stat { min-width: 0; flex: 1 1 0; }' in dashboard_styles
    assert '.channel-page-overview .dashboard-header-stats > .dashboard-ad-sticky.is-visible { max-width: 100%; flex-grow: 1; padding: 4px 9px; border: 1px solid var(--border);' in dashboard_styles
    assert 'classes.some(name => !stickyMirror.classList.contains(name))' in ad_status_script
    assert '.channel-page-overview .dashboard-ad-sticky:not(.is-visible) { background: transparent; box-shadow: none; }' in dashboard_styles
    assert '.channel-page-overview .dashboard-chat-column { display: contents; }' in dashboard_styles
    assert 'grid-template-rows: max-content max-content minmax(540px,auto)' not in dashboard_styles
    assert ".dashboard-chat-column { display: flex; grid-area: chat;" in dashboard_styles
    assert "(max-height: 780px)" not in dashboard_styles
    assert "grid-template-columns: minmax(0,1.35fr) minmax(0,.65fr) minmax(0,.8fr)" in dashboard_styles
    assert "width: min(100%, calc(100cqh * 16 / 9))" in dashboard_styles
    assert 'showTimer && streamStatus.dataset.startedAt ? ` · ${formatUptime(streamStatus.dataset.startedAt)}`' in header_stats_script
    assert 'container.querySelector("[data-stream-status]")?.addEventListener("click", () => {' in header_stats_script
    assert 'hiddenStats.has("stream_timer")' in header_stats_script
    assert 'window.dashboardLiveTest = {' in header_stats_script
    assert 'start(channelOrMinutes = 0, minutes = 0) {' in header_stats_script
    assert 'new CustomEvent("dashboard-stream-test-start", {detail: {channel: login}})' in header_stats_script
    assert 'new CustomEvent("dashboard-stream-test-stop", {detail: {isLive: actualStreamStatus.isLive}})' in header_stats_script
    assert 'twitchPlayer.setChannel(selectedChannel);' in stream_player_script
    assert 'window.addEventListener("dashboard-stream-test-start"' in stream_player_script
    assert 'window.addEventListener("dashboard-stream-test-stop"' in stream_player_script
    assert 'applyStreamStatus(true, new Date(Date.now() - elapsedMinutes * 60000).toISOString());' in header_stats_script
    assert 'viewerValue.textContent = (Math.floor(Math.random() * 500) + 1).toLocaleString();' in header_stats_script
    assert 'viewerValue.textContent = actualViewerCount;' in header_stats_script
    assert 'if (value && !(previewActive && stat.key === "viewers")) {' in header_stats_script
    assert 'applyVisibility(statContainer, hiddenStats.has(stat.key));' in header_stats_script
    assert 'if (!previewActive) applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);' in header_stats_script
    assert 'applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);' in header_stats_script
    assert ".dashboard-stream-stat.state-live .status-indicator { animation: dashboard-live-pulse" in dashboard_styles
    assert ".sidebar:not(.sidebar-hover-expanded) .sidebar-toggle { top: 35px; right: -14px; }" in dashboard_styles


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

@pytest.mark.asyncio
async def test_boss_hunt_dashboard_schedules_with_channel_config(monkeypatch):
    config = object()
    boss_service = SimpleNamespace(
        has_completed_tutorial=AsyncMock(return_value=False),
        schedule_spawn=AsyncMock(return_value=True),
        get_active_event=AsyncMock(return_value=None),
    )
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": SimpleNamespace(id="channel-1")}),
        features=SimpleNamespace(is_enabled=lambda *_: True),
        raid_bosses=boss_service,
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    monkeypatch.setattr(dashboard_router, "get_active_profile", lambda _: SimpleNamespace(raid_bosses=config))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/boss-hunt/action", "headers": [],
        "query_string": b"", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"},
    })

    response = await dashboard_router.channel_boss_hunt_action(request, "schedule", "csrf", "mini", "melee")
    assert response.status_code == 303
    assert response.headers["location"].endswith("result=scheduled")
    boss_service.schedule_spawn.assert_awaited_once_with("channel-1", config, "mini", "melee")


@pytest.mark.asyncio
async def test_boss_hunt_dashboard_ends_and_announces_active_encounter(monkeypatch):
    event = SimpleNamespace(boss_name="Training Dummy", boss_tier="tutorial", max_hp=1000, current_hp=600, stream_limit=2)
    boss_service = SimpleNamespace(
        get_active_event=AsyncMock(return_value=event),
        resolve=AsyncMock(return_value=200),
    )
    chat_identity = SimpleNamespace(send_message=AsyncMock())
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": SimpleNamespace(id="channel-1")}),
        features=SimpleNamespace(is_enabled=lambda *_: True),
        raid_bosses=boss_service,
        chat_identity=chat_identity,
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(
        services=services, create_partialuser=lambda _: SimpleNamespace(id="channel-1"),
    ))
    monkeypatch.setattr(dashboard_router, "get_active_profile", lambda _: SimpleNamespace(raid_bosses=object()))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/boss-hunt/action", "headers": [],
        "query_string": b"", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"},
    })

    response = await dashboard_router.channel_boss_hunt_action(request, "end", "csrf")
    assert response.status_code == 303
    assert response.headers["location"].endswith("result=ended")
    boss_service.resolve.assert_awaited_once_with("channel-1", defeated=False)
    chat_identity.send_message.assert_awaited_once()

@pytest.mark.asyncio
async def test_boss_hunt_page_renders_for_connected_channel(monkeypatch):
    from web.app import app

    broadcaster = SimpleNamespace(id="channel-1", name="Test Channel", login="testchannel")
    raid_bosses = SimpleNamespace(
        get_dashboard_metrics=AsyncMock(return_value=None),
        get_active_event=AsyncMock(return_value=None),
        get_contributors=AsyncMock(return_value=[]),
        spawn_tasks={},
    )
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        features=SimpleNamespace(is_enabled=lambda *_: True),
        raid_bosses=raid_bosses,
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/boss-hunt", "headers": [],
        "query_string": b"", "scheme": "http", "server": ("testserver", 80),
        "root_path": "", "app": app,
        "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"},
    })

    response = await dashboard_router.channel_boss_hunt(request)
    assert response.status_code == 200
    assert b"Schedule boss" in response.body
    assert b"Boss Hunt activity" in response.body
    assert b"Current Leaderboard" in response.body
    assert b"No active encounter yet." in response.body
    assert b"/channel/boss-hunt" in response.body

@pytest.mark.asyncio
async def test_boss_hunt_action_requires_matching_csrf(monkeypatch):
    boss_service = SimpleNamespace(resolve=AsyncMock(), schedule_spawn=AsyncMock())
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=SimpleNamespace(raid_bosses=boss_service)))
    request = Request({
        "type": "http", "method": "POST", "path": "/channel/boss-hunt/action", "headers": [],
        "query_string": b"", "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"},
    })

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await dashboard_router.channel_boss_hunt_action(request, "end", "wrong-token")
    assert error.value.status_code == 403
    boss_service.resolve.assert_not_awaited()

@pytest.mark.asyncio
async def test_boss_hunt_leaderboard_shows_current_contributors(monkeypatch):
    from web.app import app

    broadcaster = SimpleNamespace(id="channel-1", name="Test Channel", login="testchannel")
    event = SimpleNamespace(boss_name="Training Dummy", current_hp=7600, max_hp=10000)
    raid_bosses = SimpleNamespace(
        get_dashboard_metrics=AsyncMock(return_value={
            "boss_name": "Training Dummy", "status": "active", "boss_tier": "tutorial", "boss_type": "melee",
            "current_hp": 7600, "max_hp": 10000, "hp_percent": 76,
            "unique_attackers": 2, "total_attacks": 2, "total_damage": 2400, "streams_used": 1,
        }),
        get_active_event=AsyncMock(return_value=event),
        get_contributors=AsyncMock(return_value=[("alice", 1500), ("bob", 900)]),
        spawn_tasks={},
    )
    services = SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"channel-1": broadcaster}),
        features=SimpleNamespace(is_enabled=lambda *_: True),
        raid_bosses=raid_bosses,
    )
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: SimpleNamespace(services=services))
    request = Request({
        "type": "http", "method": "GET", "path": "/channel/boss-hunt", "headers": [],
        "query_string": b"", "scheme": "http", "server": ("testserver", 80),
        "root_path": "", "app": app,
        "session": {CHANNEL_USER_ID_KEY: "channel-1", CSRF_SESSION_KEY: "csrf"},
    })

    response = await dashboard_router.channel_boss_hunt(request)
    markup = response.body.decode()
    assert markup.index("Boss Hunt activity") < markup.index("Current Leaderboard")
    assert markup.index("#1") < markup.index("alice") < markup.index("#2") < markup.index("bob")
    assert "1,500 damage" in markup and "900 damage" in markup
    raid_bosses.get_contributors.assert_awaited_once_with("channel-1")

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from web.admin.auth import CSRF_SESSION_KEY
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import dashboard
from web.shared import raid_chat


def request(user="1"):
    return Request({"type": "http", "session": {CHANNEL_USER_ID_KEY: user, CSRF_SESSION_KEY: "valid"} if user else {}})


@pytest.fixture
def bot(monkeypatch):
    target = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(sent=True)))
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {"1": object()})),
                          create_partialuser=lambda id_: target, _http=SimpleNamespace(request_json=AsyncMock()))
    monkeypatch.setattr(dashboard, "get_bot", lambda: bot)
    return bot, target


@pytest.mark.asyncio
async def test_send_identity_csrf_and_auth(bot):
    _, target = bot
    assert (await dashboard.channel_raid_chat_send(request(None), "2", "hi", "valid")).status_code == 401
    with pytest.raises(HTTPException):
        await dashboard.channel_raid_chat_send(request(), "2", "hi", "invalid")
    assert (await dashboard.channel_raid_chat_send(request(), "2", "hi", "valid")).status_code == 200
    target.send_message.assert_awaited_once_with(sender="1", token_for="1", message="hi")


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["", " " * 3, "x" * 501, "/raid target", ".ban user"])
async def test_send_validation(bot, message):
    assert (await dashboard.channel_raid_chat_send(request(), "2", message, "valid")).status_code == 400
    bot[1].send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_restrictions_and_target(bot):
    bot[1].send_message.return_value.sent = False
    assert (await dashboard.channel_raid_chat_send(request(), "2", "hello", "valid")).status_code == 409
    assert (await dashboard.channel_raid_chat_stream(request(), "../2")).status_code == 400
    assert (await dashboard.channel_raid_chat_stream(request(None), "2")).status_code == 401
    assert (await dashboard.channel_raid_chat_stream(request("9"), "2")).status_code == 404


def test_message_normalization_preserves_safe_emotes_and_identity():
    event = {"message_id": "m", "chatter_user_id": "3", "chatter_user_login": "viewer",
             "chatter_user_name": "Viewer", "badges": [{"set_id": "moderator"}], "message": {
                 "text": "<script>Kappa", "fragments": [{"type": "text", "text": "<script>"},
                    {"type": "emote", "text": "Kappa", "emote": {"id": "25"}},
                    {"type": "emote", "text": "bad", "emote": {"id": "../../bad"}}]}}
    message = raid_chat.chat_event("channel.chat.message", event)["message"]
    assert message["user_id"] == "3" and message["accent"] == "moderator"
    assert message["segments"][1]["url"].endswith("/25/default/dark/2.0")
    assert message["segments"][2]["type"] == "text"
    for kind in ("clear", "message_delete", "clear_user_messages"):
        assert raid_chat.chat_event(f"channel.chat.{kind}", {"message_id": "m", "target_user_id": "3"}) == {
            "type": kind, "id": "m", "user_id": "3"}


@pytest.mark.asyncio
async def test_official_badge_artwork_is_cached_and_channel_versions_override_global(bot):
    runtime = bot[0]
    def response(route):
        prefix = "channel" if route.path == "chat/badges" else "global"
        return {"data": [{"set_id": "subscriber", "versions": [{"id": "12", "title": "One year subscriber",
            "image_url_1x": f"https://static-cdn.jtvnw.net/badges/v1/{prefix}/1",
            "image_url_2x": f"https://static-cdn.jtvnw.net/badges/v1/{prefix}/2",
            "image_url_4x": f"https://static-cdn.jtvnw.net/badges/v1/{prefix}/4"}]}]}
    runtime._http.request_json.side_effect = response
    catalog = await raid_chat.badge_catalog(runtime, "1", "2")
    await raid_chat.badge_catalog(runtime, "1", "2")
    assert runtime._http.request_json.await_count == 2
    event = {"badges": [{"set_id": "subscriber", "id": "12"}, {"set_id": "vip", "id": "1"}]}
    badges = raid_chat.chat_event("channel.chat.message", event, badge_catalog=catalog)["message"]["badges"]
    assert badges[0]["url"].endswith("/channel/1")
    assert badges[0]["url_2x"].endswith("/channel/2")
    assert badges[0]["url_4x"].endswith("/channel/4")
    assert badges[0]["title"] == "One year subscriber"
    assert badges[1]["name"] == "vip" and badges[1]["url"] is None


@pytest.mark.asyncio
async def test_badge_failure_uses_labels_without_breaking_chat_or_retrying_immediately(bot):
    bot[0]._http.request_json.side_effect = RuntimeError("unavailable")
    assert await raid_chat.badge_catalog(bot[0], "1", "2") == {}
    assert await raid_chat.badge_catalog(bot[0], "1", "2") == {}
    assert bot[0]._http.request_json.await_count == 2
    result = raid_chat.chat_event("channel.chat.message", {"badges": [{"set_id": "moderator", "id": "1"}]})
    assert result["message"]["badges"][0]["title"] == "Mod"


def emote_service(bot, response):
    service = SimpleNamespace(client=SimpleNamespace(get=AsyncMock(return_value=response)), seventv_tasks={},
        seventv_global_emotes={"Global": raid_chat.ChatSegment("emote", "Global", "https://cdn.7tv.app/emote/global/2x.webp", "7tv")},
        seventv_channel_emotes={})
    bot.services.live_chat = service
    return service


@pytest.mark.asyncio
async def test_preview_completion_catalog_keeps_viewer_twitch_emotes_but_replaces_own_channel_7tv(bot, monkeypatch):
    catalog = AsyncMock(return_value={"personal_group_key": "twitch:1", "emotes": [
        {"name": "Kappa", "provider": "twitch", "url": "https://static-cdn.jtvnw.net/emotes/25/2.0"},
        {"name": "OwnChannelOnly", "provider": "7tv", "url": "https://cdn.7tv.app/emote/own/2x.webp"}]})
    bot[0].services.live_chat = SimpleNamespace(get_emote_catalog=catalog)
    preview = AsyncMock(return_value={"TargetWave": raid_chat.ChatSegment("emote", "TargetWave", "https://cdn.7tv.app/emote/target/2x.webp", "7tv")})
    monkeypatch.setattr(dashboard, "preview_emotes", preview)
    response = await dashboard.channel_raid_chat_emotes(request(), "2")
    payload = json.loads(response.body)
    assert {emote["name"] for emote in payload["emotes"]} == {"Kappa", "TargetWave"}
    assert payload["personal_group_key"] == "twitch:1"
    assert next(emote for emote in payload["emotes"] if emote["name"] == "TargetWave")["group_key"] == "7tv"
    catalog.assert_awaited_once_with("1")
    preview.assert_awaited_once_with(bot[0], "2")
    assert (await dashboard.channel_raid_chat_emotes(request(None), "2")).status_code == 401
    assert (await dashboard.channel_raid_chat_emotes(request(), "../2")).status_code == 400


@pytest.mark.asyncio
async def test_preview_loads_selected_channel_7tv_set_with_global_emotes_and_caches(bot):
    response = SimpleNamespace(status_code=200, raise_for_status=lambda: None,
        json=lambda: {"emote_set": {"emotes": [{"name": "Channel", "data": {"id": "abc123"}}]}})
    service = emote_service(bot[0], response)
    first = await raid_chat.preview_emotes(bot[0], "2")
    assert {"Global", "Channel"} <= first.keys()
    assert first["Channel"].url == "https://cdn.7tv.app/emote/abc123/2x.webp"
    await raid_chat.preview_emotes(bot[0], "2")
    service.client.get.assert_awaited_once_with("https://7tv.io/v3/users/twitch/2")
    await raid_chat.preview_emotes(bot[0], "3")
    assert service.client.get.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_first", [False, True])
async def test_concurrent_preview_emote_requests_share_lookup_and_survive_one_cancellation(bot, cancel_first):
    response = SimpleNamespace(status_code=200, raise_for_status=lambda: None,
        json=lambda: {"emote_set": {"emotes": [{"name": "Channel", "data": {"id": "abc123"}}]}})
    service = emote_service(bot[0], response)
    started, release = asyncio.Event(), asyncio.Event()

    async def fetch(_url):
        started.set()
        await release.wait()
        return response

    service.client.get.side_effect = fetch
    first = asyncio.create_task(raid_chat.preview_emotes(bot[0], "2"))
    await asyncio.wait_for(started.wait(), 1)
    second = asyncio.create_task(raid_chat.preview_emotes(bot[0], "2"))
    await asyncio.sleep(0)
    if cancel_first:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
    release.set()
    result = await asyncio.wait_for(second, 1)
    assert {"Global", "Channel"} <= result.keys()
    if not cancel_first:
        assert await first == result
    service.client.get.assert_awaited_once_with("https://7tv.io/v3/users/twitch/2")
    assert bot[0]._raid_preview_emote_pending == {}


@pytest.mark.asyncio
async def test_failed_shared_emote_request_retains_stale_catalog_and_backoff(bot):
    service = emote_service(bot[0], None)
    stale = {"Old": raid_chat.ChatSegment("emote", "Old", "https://cdn.7tv.app/emote/old/2x.webp", "7tv")}
    bot[0]._raid_preview_emote_cache = {"2": (0, stale)}
    service.client.get.side_effect = RuntimeError("unavailable")
    results = await asyncio.gather(*(raid_chat.preview_emotes(bot[0], "2") for _ in range(3)))
    assert all(set(result) == {"Global", "Old"} for result in results)
    await raid_chat.preview_emotes(bot[0], "2")
    assert service.client.get.await_count == 1
    assert bot[0]._raid_preview_emote_pending == {}


@pytest.mark.asyncio
async def test_preview_7tv_missing_or_unavailable_does_not_break_global_emotes(bot):
    service = emote_service(bot[0], SimpleNamespace(status_code=404))
    assert set(await raid_chat.preview_emotes(bot[0], "2")) == {"Global"}
    service.client.get.side_effect = RuntimeError("down")
    assert set(await raid_chat.preview_emotes(bot[0], "3")) == {"Global"}


@pytest.mark.asyncio
async def test_connected_channel_reuses_existing_live_7tv_catalog_without_request(bot):
    service = emote_service(bot[0], None)
    service.seventv_tasks["2"] = object()
    service.seventv_channel_emotes["2"] = {"Channel": raid_chat.ChatSegment("emote", "Channel", "https://cdn.7tv.app/emote/local/2x.webp", "7tv")}
    assert "Channel" in await raid_chat.preview_emotes(bot[0], "2")
    service.client.get.assert_not_awaited()


def test_preview_7tv_replaces_whole_names_preserving_whitespace_and_twitch_emotes():
    catalog = {"Wave": raid_chat.ChatSegment("emote", "Wave", "https://cdn.7tv.app/emote/abc/2x.webp", "7tv")}
    event = {"message": {"text": "Wave  Wave! Kappa", "fragments": [
        {"type": "text", "text": "Wave  Wave! "},
        {"type": "emote", "text": "Kappa", "emote": {"id": "25"}}]}}
    segments = raid_chat.chat_event("channel.chat.message", event, emotes=catalog)["message"]["segments"]
    assert segments[0]["provider"] == "7tv"
    assert "".join(part["text"] for part in segments) == "Wave  Wave! Kappa"
    assert segments[-1]["provider"] == "twitch"
    assert any(part["type"] == "text" and part["text"] == "Wave!" for part in segments)


class Context:
    def __init__(self, value): self.value = value; self.closed = False
    async def __aenter__(self): return self.value
    async def __aexit__(self, *args): self.closed = True


@pytest.mark.asyncio
async def test_relay_subscribes_with_user_token_and_cleans_up_on_close(monkeypatch, bot):
    socket = SimpleNamespace(receive_json=AsyncMock(return_value={"metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "session", "keepalive_timeout_seconds": 10}}}))
    socket_context = Context(socket)
    client_context = Context(SimpleNamespace(ws_connect=lambda *args, **kwargs: socket_context))
    monkeypatch.setattr(raid_chat.aiohttp, "ClientSession", lambda: client_context)
    generator = raid_chat.preview_chat_events(SimpleNamespace(is_disconnected=AsyncMock(return_value=False)), bot[0], "1", "2")
    assert "retry: 15000" in await anext(generator)
    assert "Connected" in await anext(generator)
    calls = [call for call in bot[0]._http.request_json.call_args_list if call.args[0].method == "POST"]
    assert len(calls) == 5
    assert any(call.args[0].json["type"] == "channel.chat.notification" for call in calls)
    for call in calls:
        route = call.args[0]
        assert route.token_for == "1"
        assert route.json["condition"] == {"broadcaster_user_id": "2", "user_id": "1"}
        assert route.json["transport"] == {"method": "websocket", "session_id": "session"}
    assert "1" in raid_chat.ACTIVE_READERS
    await generator.aclose()
    assert "1" not in raid_chat.ACTIVE_READERS
    assert socket_context.closed and client_context.closed


@pytest.mark.asyncio
async def test_duplicate_reader_does_not_open_another_socket():
    raid_chat.ACTIVE_READERS.add("duplicate")
    try:
        values = [value async for value in raid_chat.preview_chat_events(None, None, "duplicate", "2")]
        assert "already open" in values[0]
    finally:
        raid_chat.ACTIVE_READERS.discard("duplicate")


@pytest.mark.asyncio
async def test_relay_deduplicates_checks_channel_and_forwards_deletions(monkeypatch, bot):
    def notification(identity, channel, kind="message"):
        return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps({
            "metadata": {"message_type": "notification", "message_id": identity},
            "payload": {"subscription": {"type": f"channel.chat.{kind}"}, "event": {
                "broadcaster_user_id": channel, "message_id": "m", "message": {"text": "hello"}}}}))
    socket = SimpleNamespace(receive_json=AsyncMock(return_value={"metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "session"}}}), receive=AsyncMock(side_effect=[
            notification("first", "2"), notification("first", "2"), notification("other", "9"),
            notification("deleted", "2", "message_delete"), SimpleNamespace(type=aiohttp.WSMsgType.CLOSED)]))
    monkeypatch.setattr(raid_chat.aiohttp, "ClientSession", lambda: Context(SimpleNamespace(ws_connect=lambda *args, **kwargs: Context(socket))))
    values = [value async for value in raid_chat.preview_chat_events(
        SimpleNamespace(is_disconnected=AsyncMock(return_value=False)), bot[0], "1", "2")]
    assert len(values) == 5  # retry, connected, one message, deletion, reconnect
    assert '"type":"message"' in values[2]
    assert '"type":"message_delete"' in values[3]
    assert "1" not in raid_chat.ACTIVE_READERS

"""Short-lived, authenticated Twitch chat relay for the raid preview.

The websocket (and its subscriptions) live only as long as the SSE request.
No Twitch credentials or main-dashboard chat history are sent to the browser.
"""
import asyncio
import json
import logging
import time
from dataclasses import asdict

import aiohttp
from twitchio import HTTPException
from twitchio.http import Route
from bot.services.channels.live_chat import ChatBadge, ChatSegment, LiveChatService, SEVENTV_API_URL, SEVENTV_REFRESH_SECONDS
from bot.services.channels.chat_notices import notification_details

LOGGER = logging.getLogger("RatBoomBot")
ACTIVE_READERS = set()
CHAT_EVENTS = ("message", "notification", "clear", "clear_user_messages", "message_delete")


async def badge_catalog(bot, reader, target):
    cache = getattr(bot, "_raid_preview_badge_cache", None)
    if cache is None:
        cache = bot._raid_preview_badge_cache = {}

    async def load(channel=None):
        key = channel or "global"
        cached = cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            response = await asyncio.wait_for(bot._http.request_json(Route(
                "GET", "chat/badges" if channel else "chat/badges/global", token_for=reader,
                params={"broadcaster_id": channel} if channel else {})), 4)
            catalog = LiveChatService._parse_twitch_badges(response) if isinstance(response, dict) else {}
            ttl = 3600
        except Exception:
            LOGGER.warning("[Raid preview] Could not load chat badges for %s", key)
            catalog, ttl = {}, 30
        if len(cache) >= 128 and key not in cache:
            cache.pop(next(iter(cache)))
        cache[key] = (time.monotonic() + ttl, catalog)
        return catalog

    global_badges, channel_badges = await asyncio.gather(load(), load(target))
    return {**global_badges, **channel_badges}


async def preview_emotes(bot, target):
    service = getattr(bot.services, "live_chat", None)
    if service is None or service.client is None:
        return {}
    globals_ = service.seventv_global_emotes
    # Connected channels already have a live 7TV watcher; share its catalog.
    if target in service.seventv_tasks:
        return {**globals_, **service.seventv_channel_emotes.get(target, {})}
    cache = getattr(bot, "_raid_preview_emote_cache", None)
    if cache is None:
        cache = bot._raid_preview_emote_cache = {}
    cached = cache.get(target)
    if cached and cached[0] > time.monotonic():
        return {**globals_, **cached[1]}
    # Chat startup and autocomplete may request this same public catalog at once.
    pending = getattr(bot, "_raid_preview_emote_pending", None)
    if pending is None:
        pending = bot._raid_preview_emote_pending = {}

    async def load():
        try:
            response = await asyncio.wait_for(service.client.get(f"{SEVENTV_API_URL}/users/twitch/{target}"), 3)
            if response.status_code == 404:
                catalog = {}
            else:
                response.raise_for_status()
                catalog = LiveChatService._parse_seventv_emotes(response.json().get("emote_set") or {})
            ttl = SEVENTV_REFRESH_SECONDS
        except Exception:
            LOGGER.warning("[Raid preview] Could not load 7TV emotes for %s", target)
            catalog, ttl = cached[1] if cached else {}, 30
        if len(cache) >= 128 and target not in cache:
            cache.pop(next(iter(cache)))
        cache[target] = (time.monotonic() + ttl, catalog)
        return catalog

    task = pending.get(target)
    if task is None:
        task = pending[target] = asyncio.create_task(load())
        task.add_done_callback(lambda completed: pending.pop(target, None) if pending.get(target) is completed else None)
    # Closing one preview must not cancel another caller's shared lookup.
    catalog = await asyncio.shield(task)
    return {**globals_, **catalog}


def chat_event(kind, event, timestamp="", badge_catalog=None, emotes=None):
    notice = {}
    if kind == "channel.chat.notification":
        notice_type = event.get("notice_type", "")
        notice = notification_details(notice_type, event.get("system_message", ""), event.get(notice_type))
        if notice is None:
            return None
    elif kind != "channel.chat.message":
        return {"type": kind.rsplit(".", 1)[-1], "id": event.get("message_id", ""),
                "user_id": event.get("target_user_id", "")}
    content = event.get("message", {})
    message_text = content.get("text", "")
    segments = []
    for fragment in content.get("fragments", []):
        emote = fragment.get("emote") or {}
        segment = {"type": "text", "text": fragment.get("text", "")}
        emote_id = str(emote.get("id", ""))
        if fragment.get("type") == "emote" and emote_id and all(c.isalnum() or c in "_-" for c in emote_id):
            segment.update(type="emote", provider="twitch",
                           url=f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/2.0")
        if segment["text"] or segment["type"] == "emote":
            segments.append(segment)
    if emotes and (segments or message_text):
        source = tuple(ChatSegment(**segment) for segment in segments) or (ChatSegment("text", message_text),)
        segments = [asdict(segment) for segment in LiveChatService.apply_emote_catalog(source, emotes)]
    catalog = badge_catalog or {}
    badges = []
    for badge in event.get("badges", []):
        set_id, version = str(badge.get("set_id") or ""), str(badge.get("id") or "")
        if set_id:
            badges.append(asdict(catalog.get((set_id, version), ChatBadge(set_id, LiveChatService._badge_label(set_id)))))
    names = {badge["name"] for badge in badges}
    accent = next((name for name in ("broadcaster", "staff", "moderator", "vip", "subscriber") if name in names), "")
    is_redeem = bool(event.get("channel_points_custom_reward_id")) or event.get("message_type") in {"channel_points_highlighted", "channel_points_sub_only"}
    if is_redeem:
        notice = {"notice_type": "redemption", "notice_label": "Redeem", "notice": "Redeemed a channel points reward"}
    return {"type": "message", "message": {
        "id": event.get("message_id", ""), "user_id": "" if event.get("chatter_is_anonymous") else event.get("chatter_user_id", ""),
        "platform": "twitch", "kind": "message", "username": "Anonymous" if event.get("chatter_is_anonymous") else event.get("chatter_user_login", ""),
        "display_name": "Anonymous" if event.get("chatter_is_anonymous") else event.get("chatter_user_name", ""), "color": event.get("color", ""),
        "timestamp": timestamp, "message": message_text,
        "segments": segments, "badges": badges, "accent": accent, "is_redeem": is_redeem, **notice}}


def sse(payload):
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def preview_chat_events(request, bot, reader, target):
    # Bound concurrent previews per account without touching the main bot socket.
    if reader in ACTIVE_READERS:
        yield sse({"type": "status", "error": True, "terminal": True,
                   "text": "Preview chat is already open in another tab."})
        return
    ACTIVE_READERS.add(reader)
    try:
        yield "retry: 15000\n\n"
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect("wss://eventsub.wss.twitch.tv/ws", heartbeat=20) as socket:
                welcome = await asyncio.wait_for(socket.receive_json(), 15)
                if welcome.get("metadata", {}).get("message_type") != "session_welcome":
                    raise ValueError("Missing EventSub welcome")
                session = welcome["payload"]["session"]
                async with asyncio.timeout(10):
                    for event in CHAT_EVENTS:
                        await bot._http.request_json(Route("POST", "eventsub/subscriptions", token_for=reader, json={
                            "type": f"channel.chat.{event}", "version": "1",
                            "condition": {"broadcaster_user_id": target, "user_id": reader},
                            "transport": {"method": "websocket", "session_id": session["id"]}}))
                badges, emotes = await asyncio.gather(badge_catalog(bot, reader, target), preview_emotes(bot, target))
                next_emote_refresh = time.monotonic() + SEVENTV_REFRESH_SECONDS
                yield sse({"type": "status", "text": "Connected"})
                seen = set()
                timeout = max(15, min(90, session.get("keepalive_timeout_seconds", 10) + 10))
                while not await request.is_disconnected():
                    message = await asyncio.wait_for(socket.receive(), timeout)
                    if message.type != aiohttp.WSMsgType.TEXT:
                        break
                    packet = json.loads(message.data)
                    if time.monotonic() >= next_emote_refresh:
                        emotes = await preview_emotes(bot, target)
                        next_emote_refresh = time.monotonic() + SEVENTV_REFRESH_SECONDS
                    metadata = packet.get("metadata", {})
                    kind = metadata.get("message_type")
                    if kind == "notification":
                        payload = packet.get("payload", {})
                        event = payload.get("event", {})
                        identity = metadata.get("message_id")
                        if identity in seen or str(event.get("broadcaster_user_id")) != target:
                            continue
                        if len(seen) >= 1000:
                            seen.clear()
                        seen.add(identity)
                        rendered = chat_event(payload["subscription"]["type"], event, metadata.get("message_timestamp", ""), badges, emotes)
                        if rendered is not None:
                            yield sse(rendered)
                    elif kind in ("session_reconnect", "revocation"):
                        # Close the old socket; EventSource reconnects with fresh authorization.
                        break
                    else:
                        yield ": keepalive\n\n"
        yield sse({"type": "status", "text": "Reconnecting…"})
    except HTTPException as error:
        authorization = error.status in (401, 403)
        yield sse({"type": "status", "error": True, "terminal": authorization,
                   "text": "Reconnect Twitch in Settings to enable preview chat." if authorization
                   else "Chat unavailable. Retrying…"})
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError):
        LOGGER.warning("[Raid preview] Chat connection interrupted for %s", reader)
        yield sse({"type": "status", "error": True, "text": "Chat unavailable. Retrying…"})
    finally:
        ACTIVE_READERS.discard(reader)

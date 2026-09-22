import asyncio
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from twitchio import HTTPException
from twitchio.http import Route

from bot.command_registry import build_command_help_groups
from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName, get_active_profile
from bot.services.channels.profile_settings import LOYALTY_GROUP
from bot.services.channels.stream_metadata import (
    StreamCategoryNotFoundError, clear_stream_category, update_stream_game, update_stream_title
)
from config.settings import settings
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY, logout_channel_user
from web.shared.common import templates
from web.shared.live_chat import stream_chat_events
from web.shared.protected_users import (
    ProtectedUserError,
    add_protected_user,
    get_protected_user_rows,
    lookup_protected_user,
    remove_protected_user
)
from web.state import get_bot

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
CHAT_SEND_TARGETS = {"twitch", "youtube", "both"}
CHAT_MESSAGE_MAX_LENGTH = 200
TOP_GAMES_CACHE_SECONDS = 300


def protected_users_redirect(result: str, message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/channel/customization?protected_result={result}&protected_message={quote_plus(message)}&command_tab=protected#protected-users",
        status_code=303
    )


async def execute_twitch_slash_command(runtime_bot, broadcaster_id: str, message: str) -> str | None:
    command_token, _, argument_text = message.strip().partition(" ")
    command = command_token.removeprefix("/").lower()
    argument_text = argument_text.strip()
    broadcaster = runtime_bot.create_partialuser(str(broadcaster_id))
    moderator_id = str(broadcaster_id)

    def require_argument(label: str = "an argument") -> str:
        if not argument_text:
            raise ValueError(f"/{command} requires {label}.")
        return argument_text

    async def resolve_user(value: str):
        user = await runtime_bot.services.chatters.resolve(str(broadcaster_id), value)
        if user is None:
            raise ValueError(f"Twitch could not find user {value}.")
        return user

    if command.startswith("announce"):
        colors = {
            "announce": "primary", "announceblue": "blue", "announcegreen": "green",
            "announceorange": "orange", "announcepurple": "purple"
        }
        if command not in colors:
            raise ValueError(f"Unknown Twitch command: /{command}.")
        await broadcaster.send_announcement(
            moderator=moderator_id, message=require_argument("a message"), color=colors[command]
        )
    elif command == "ban":
        username, _, reason = require_argument("a username").partition(" ")
        user = await resolve_user(username)
        await broadcaster.ban_user(moderator=moderator_id, user=str(user.id), reason=reason or None)
    elif command == "timeout":
        values = require_argument("a username").split()
        user = await resolve_user(values.pop(0))
        duration = int(values.pop(0)) if values and values[0].isdigit() else 600
        await broadcaster.timeout_user(
            moderator=moderator_id, user=str(user.id), duration=duration, reason=" ".join(values) or None
        )
    elif command == "unban":
        user = await resolve_user(require_argument("a username"))
        await broadcaster.unban_user(moderator=moderator_id, user_id=str(user.id))
    elif command == "clear":
        await broadcaster.delete_chat_messages(moderator=moderator_id)
    elif command == "commercial":
        await broadcaster.start_commercial(length=int(require_argument("a duration in seconds")))
    elif command == "marker":
        await broadcaster.create_stream_marker(token_for=moderator_id, description=argument_text or None)
    elif command in {"emoteonly", "emoteonlyoff", "subscribers", "subscribersoff", "uniquechat", "uniquechatoff", "slow", "slowoff", "followers", "followersoff"}:
        settings_by_command = {
            "emoteonly": {"emote_mode": True}, "emoteonlyoff": {"emote_mode": False},
            "subscribers": {"subscriber_mode": True}, "subscribersoff": {"subscriber_mode": False},
            "uniquechat": {"unique_chat_mode": True}, "uniquechatoff": {"unique_chat_mode": False},
            "slow": {"slow_mode": True, **({"slow_mode_wait_time": int(argument_text)} if argument_text else {})},
            "slowoff": {"slow_mode": False},
            "followers": {"follower_mode": True, **({"follower_mode_duration": int(argument_text)} if argument_text else {})},
            "followersoff": {"follower_mode": False}
        }
        await broadcaster.update_chat_settings(moderator_id, **settings_by_command[command])
    elif command in {"mod", "unmod", "vip", "unvip"}:
        user = await resolve_user(require_argument("a username"))
        method = {
            "mod": broadcaster.add_moderator, "unmod": broadcaster.remove_moderator,
            "vip": broadcaster.add_vip, "unvip": broadcaster.remove_vip
        }[command]
        await method(str(user.id))
    elif command in {"raid", "shoutout"}:
        user = await resolve_user(require_argument("a channel username"))
        if command == "raid":
            await broadcaster.start_raid(str(user.id))
        else:
            await broadcaster.send_shoutout(to_broadcaster=str(user.id), moderator=moderator_id)
    elif command == "unraid":
        await broadcaster.cancel_raid()
    elif command == "warn":
        username, _, reason = require_argument("a username and reason").partition(" ")
        if not reason:
            raise ValueError("/warn requires a username and reason.")
        user = await resolve_user(username)
        await broadcaster.warn_user(moderator=moderator_id, user_id=str(user.id), reason=reason)
    else:
        raise ValueError(f"Unknown or unsupported Twitch command: /{command}.")

    return f"/{command} completed."


async def get_dashboard_header_stats(runtime_bot, broadcaster, *, refresh_viewers: bool = False, points_lost: int = 0) -> list[dict[str, object]]:
    broadcaster_id = str(broadcaster.id)
    user = runtime_bot.create_partialuser(broadcaster_id)

    async def fetch_total(name: str, fetcher) -> int | None:
        try:
            result = await fetcher()
            total = getattr(result, "total", None)
            return int(total) if total is not None else None
        except Exception as exc:
            LOGGER.warning("[Dashboard] Failed to fetch %s count for broadcaster %s: %s", name, broadcaster_id, exc)
            return None

    async def fetch_viewers() -> int:
        cached_count = int(getattr(broadcaster, "viewer_count", 0) or 0)
        if not refresh_viewers:
            return cached_count
        try:
            stream = await user.fetch_stream()
            broadcaster.is_live = stream is not None
            broadcaster.viewer_count = int(getattr(stream, "viewer_count", 0) or 0) if stream is not None else 0
            broadcaster.stream_started_at = getattr(stream, "started_at", None) if stream is not None else None
            return broadcaster.viewer_count
        except Exception as exc:
            LOGGER.warning("[Dashboard] Failed to refresh viewer count for broadcaster %s: %s", broadcaster_id, exc)
            return cached_count

    async def fetch_subscribers() -> tuple[int | None, int | None]:
        try:
            result = await user.fetch_broadcaster_subscriptions(first=1, max_results=1)
            total = getattr(result, "total", None)
            points = getattr(result, "points", None)
            return (int(total) if total is not None else None, int(points) if points is not None else None)
        except Exception as exc:
            LOGGER.warning("[Dashboard] Failed to fetch subscribers count for broadcaster %s: %s", broadcaster_id, exc)
            return None, None

    viewers, followers, subscriber_summary = await asyncio.gather(
        fetch_viewers(),
        fetch_total("followers", lambda: user.fetch_followers(first=1, max_results=1)),
        fetch_subscribers()
    )
    subscribers, subscriber_points = subscriber_summary
    subscriber_display = "—" if subscribers is None else f"{subscribers:,} ({subscriber_points or 0:,} pts)"
    values = (
        ("viewers", "Viewers", viewers),
        ("followers", "Followers", followers),
        ("subscribers", "Subs", subscribers, subscriber_display),
        ("points_lost", "Lost to RatsBoomBot", int(points_lost or 0))
    )
    return [
        {
            "key": item[0],
            "label": item[1],
            "value": item[2],
            "display_value": item[3] if len(item) > 3 else (f"{item[2]:,}" if item[2] is not None else "—")
        }
        for item in values
    ]


async def get_twitch_channel_metadata(runtime_bot, broadcaster_id: str) -> dict[str, str]:
    try:
        info = await runtime_bot.create_partialuser(str(broadcaster_id)).fetch_channel_info(token_for=str(broadcaster_id))
        return {"title": str(info.title or "Untitled stream"), "game": str(info.game_name or "No category")}
    except Exception as exc:
        LOGGER.warning("[Dashboard] Failed to fetch Twitch channel metadata for broadcaster %s: %s", broadcaster_id, exc)
        return {"title": "Unavailable", "game": "Unavailable"}


def category_match_type(name: str, query: str) -> int:
    if name == query:
        return 0
    words = re.findall(r"[\w]+", name)
    if len(words) > 1 and "".join(word[0] for word in words) == query:
        return 1
    if name.startswith(query):
        return 2
    if re.search(rf"(?<!\w){re.escape(query)}", name):
        return 3
    if query in name:
        return 4
    return 5


def sort_twitch_games_by_match(
    games: list[dict[str, str]], query: str, popular_games: list[dict[str, str]] | None = None
) -> list[dict[str, str]]:
    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        return games
    popular_positions = {game["id"]: index for index, game in enumerate(popular_games or ())}

    def rank(game: dict[str, str]) -> tuple[float, float, int, str]:
        name = " ".join(game["name"].casefold().split())
        match_type = category_match_type(name, normalized_query)
        similarity = SequenceMatcher(None, normalized_query, name).ratio()
        match_score = (100, 95, 80, 70, 55, 0)[match_type]
        position = popular_positions.get(game["id"])
        popularity_bonus = max(0, 40 - position * 0.2) if position is not None else 0
        return -(match_score + popularity_bonus), -similarity, len(name), name

    return sorted(games, key=rank)


async def get_top_games_for_search(runtime_bot, broadcaster_id: str) -> list[dict[str, str]]:
    cached = getattr(runtime_bot, "_dashboard_top_games_cache", None)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]
    iterator = runtime_bot.fetch_top_games(token_for=str(broadcaster_id), first=100, max_results=100)
    games = [{"id": str(game.id), "name": str(game.name)} async for game in iterator]
    runtime_bot._dashboard_top_games_cache = (now + TOP_GAMES_CACHE_SECONDS, games)
    return games


def format_dashboard_username(services, broadcaster_id: str, username: str) -> str:
    formatter = getattr(getattr(services, "chatters", None), "format_name", None)
    return formatter(str(broadcaster_id), str(username)) if callable(formatter) else str(username)


def get_queue_members(services, broadcaster_id: str) -> list[dict[str, str]]:
    members = []
    for member in services.viewer_queue.list_queue_members(broadcaster_id):
        username = member["username"]
        display_name = member.get("display_name") or username
        label = (
            f"{display_name} ({username})"
            if display_name.casefold() != username.casefold()
            else username
        )
        members.append({"username": username, "label": label})
    return members


async def get_redemption_dashboard_data(services, broadcaster_id: str) -> dict[str, object]:
    activity = await services.redeems.get_dashboard_activity(broadcaster_id=broadcaster_id)
    for collection in (activity.get("checkins", []), activity.get("redemptions", [])):
        for entry in collection:
            entry["user_label"] = format_dashboard_username(services, broadcaster_id, entry.get("username", ""))
    activity.update(services.live_chat.get_moderation_activity(broadcaster_id))

    return activity


async def get_raid_contributor_data(services, broadcaster_id: str) -> dict[str, object]:
    event = await services.raid_bosses.get_active_event(broadcaster_id)

    if event is None:
        return {"active": False, "contributors": []}

    contributors = await services.raid_bosses.get_contributors(broadcaster_id)

    return {
        "active": True,
        "boss_name": event.boss_name,
        "current_hp": event.current_hp,
        "max_hp": event.max_hp,
        "contributors": [
            {
                "rank": rank,
                "username": username,
                "user_label": format_dashboard_username(services, broadcaster_id, username),
                "damage": damage
            }
            for rank, (username, damage) in enumerate(contributors, start=1)
        ]
    }


async def get_ad_status(broadcaster, twitch_user=None) -> dict[str, object]:
    if not broadcaster.is_live:
        return {"state": "offline", "label": "Stream offline", "next_ad_at": None, "ends_at": None, "snoozes_available": None}

    try:
        schedule = await (twitch_user or broadcaster).fetch_ad_schedule()
    except Exception:
        LOGGER.exception("[Dashboard] Failed to fetch ad schedule for broadcaster %s.", broadcaster.id)
        return {"state": "unavailable", "label": "Ad schedule unavailable", "next_ad_at": None, "ends_at": None, "snoozes_available": None}

    now = datetime.now(UTC)
    snoozes_available = getattr(schedule, "snooze_count", None)
    last_ad_at = schedule.last_ad_at
    ends_at = last_ad_at + timedelta(seconds=schedule.duration) if last_ad_at is not None else None

    if ends_at is not None and last_ad_at <= now < ends_at:
        return {"state": "running", "label": "Ad running", "next_ad_at": None, "started_at": last_ad_at.isoformat(), "ends_at": ends_at.isoformat(), "snoozes_available": snoozes_available}

    if schedule.next_ad_at is not None:
        return {"state": "scheduled", "label": "Next ad", "next_ad_at": schedule.next_ad_at.isoformat(), "ends_at": None, "snoozes_available": snoozes_available}

    return {"state": "none", "label": "No ad scheduled", "next_ad_at": None, "ends_at": None, "snoozes_available": snoozes_available}


@router.get("/channel/api/raid-contributors", response_class=JSONResponse)
async def channel_raid_contributors(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await get_raid_contributor_data(services, broadcaster_id))


@router.get("/channel/api/dashboard-stats", response_class=JSONResponse)
async def channel_dashboard_stats(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    points_lost = await runtime_bot.services.points.get_gambling_loss_total(broadcaster_id)
    stats = await get_dashboard_header_stats(runtime_bot, broadcaster, refresh_viewers=True, points_lost=points_lost)
    started_at = getattr(broadcaster, "stream_started_at", None)
    return JSONResponse({
        "stats": stats,
        "is_live": bool(broadcaster.is_live),
        "started_at": started_at.isoformat() if started_at is not None else None
    })


@router.get("/channel/api/redemptions", response_class=JSONResponse)
async def channel_redemption_activity(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await get_redemption_dashboard_data(services, broadcaster_id))


@router.get("/channel/api/viewer-queue", response_class=JSONResponse)
async def channel_viewer_queue_state(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    viewer_queue = services.viewer_queue
    queue_users = viewer_queue.list_queue(broadcaster_id)

    return JSONResponse({
        "open": viewer_queue.is_queue_open(broadcaster_id),
        "size": len(queue_users),
        "users": get_queue_members(services, broadcaster_id)
    })


@router.post("/channel/api/viewer-queue/action", response_class=JSONResponse)
async def channel_viewer_queue_action(
    request: Request,
    action: str = Form(...),
    csrf_token: str = Form(...),
    position: int = Form(0),
    new_position: int = Form(0),
    count: int = Form(4)
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    queue = runtime_bot.services.viewer_queue
    message = "Queue updated."
    selected: list[str] = []

    if action == "toggle":
        message = await (queue.close_queue(broadcaster_id) if queue.is_queue_open(broadcaster_id) else queue.open_queue(broadcaster_id))
    elif action in {"next", "next4", "next5"}:
        next_count = count if action == "next" else (4 if action == "next4" else 5)
        if not 1 <= next_count <= 10:
            return JSONResponse({"detail": "Choose between 1 and 10 viewers."}, status_code=400)
        _, selected, message = await queue.next_viewers(broadcaster_id, next_count)
    elif action == "clear":
        message = await queue.clear(broadcaster_id)
    elif action == "remove":
        _, _, message = await queue.remove_position(broadcaster_id, position)
    elif action == "top":
        _, message = await queue.requeue(broadcaster_id, position, 1)
    elif action == "bottom":
        _, message = await queue.requeue(broadcaster_id, position, queue.size(broadcaster_id))
    elif action == "reorder":
        _, message = await queue.requeue(broadcaster_id, position, new_position)
    else:
        return JSONResponse({"detail": "Unknown queue action."}, status_code=400)

    try:
        channel = runtime_bot.create_partialuser(str(broadcaster_id))
        sent_message = await runtime_bot.services.chat_identity.send_message(channel, message)
        sent = getattr(sent_message, "sent", getattr(sent_message, "is_sent", False))
        sent_message_id = getattr(sent_message, "id", None)
        if sent and sent_message_id:
            runtime_bot.services.live_chat.tag_command_response(str(broadcaster_id), str(sent_message_id))
    except Exception:
        LOGGER.exception(
            "[Dashboard] Viewer queue action succeeded, but its Twitch chat response could not be sent for broadcaster %s.",
            broadcaster_id
        )

    users = queue.list_queue(broadcaster_id)
    return JSONResponse({
        "open": queue.is_queue_open(broadcaster_id),
        "size": len(users),
        "users": get_queue_members(runtime_bot.services, broadcaster_id),
        "selected": selected,
        "message": message
    })


@router.post("/channel/api/channel-metadata", response_class=JSONResponse)
async def update_twitch_channel_metadata(
    request: Request,
    field: str = Form(...),
    value: str = Form(...),
    csrf_token: str = Form(...)
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    value = value.strip()

    try:
        if field == "title":
            if not value or len(value) > 140:
                return JSONResponse({"detail": "Titles must contain 1 to 140 characters."}, status_code=400)
            update = await update_stream_title(runtime_bot, broadcaster_id, value)
        elif field == "game":
            if len(value) > 100:
                return JSONResponse({"detail": "Category names are limited to 100 characters."}, status_code=400)
            if value:
                update = await update_stream_game(runtime_bot, broadcaster_id, value, token_for=broadcaster_id)
            else:
                update = await clear_stream_category(runtime_bot, broadcaster_id)
        else:
            return JSONResponse({"detail": "Only the title and game can be edited."}, status_code=400)
    except StreamCategoryNotFoundError:
        return JSONResponse({"detail": "Twitch could not find that game or category.", "code": "category_not_found"}, status_code=400)
    except Exception:
        LOGGER.exception("[Dashboard] Failed to update Twitch %s for broadcaster %s.", field, broadcaster_id)
        return JSONResponse({"detail": f"The Twitch {field} could not be updated."}, status_code=502)

    announcement_sent = False
    try:
        twitch_user = runtime_bot.create_partialuser(str(broadcaster_id))
        sent_message = await runtime_bot.services.chat_identity.send_message(twitch_user, update.announcement)
        announcement_sent = bool(getattr(sent_message, "sent", getattr(sent_message, "is_sent", False)))
        sent_message_id = getattr(sent_message, "id", None)
        if announcement_sent and sent_message_id:
            runtime_bot.services.live_chat.tag_command_response(str(broadcaster_id), str(sent_message_id))
    except Exception:
        LOGGER.exception(
            "[Dashboard] Twitch %s updated, but its chat announcement could not be sent for broadcaster %s.",
            field, broadcaster_id
        )

    return JSONResponse({"field": field, "value": update.value, "announcement_sent": announcement_sent})


@router.get("/channel/api/chat/pinned", response_class=JSONResponse)
async def channel_pinned_chat_message(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    live_chat = runtime_bot.services.live_chat
    try:
        route = Route("GET", "chat/pins", params={
            "broadcaster_id": str(broadcaster_id),
            "moderator_id": str(broadcaster_id)
        }, token_for=str(broadcaster_id))
        payload = await runtime_bot._http.request_json(route)
        pins = payload.get("data", []) if isinstance(payload, dict) else []
        if not pins:
            if live_chat.get_pinned_message(broadcaster_id) is not None:
                await live_chat.clear_pinned_message(broadcaster_id)
            return JSONResponse({"message": None, "duration_minutes": None, "ends_at": None})

        pin = pins[0]
        message_id = f"twitch:{pin.get('message_id', '')}"
        message = live_chat.find_message(broadcaster_id, message_id)
        if message is None:
            message_data = pin.get("message") or {}
            message = {
                "id": message_id,
                "platform": "twitch",
                "kind": "chat",
                "username": str(pin.get("sender_user_login") or "unknown"),
                "display_name": str(pin.get("sender_user_name") or pin.get("sender_user_login") or "Unknown"),
                "message": str(message_data.get("text") or ""),
                "timestamp": str(pin.get("updated_at") or datetime.now(UTC).isoformat()),
                "color": None,
                "badges": [],
                "segments": []
            }
        current = live_chat.get_pinned_message(broadcaster_id)
        if current is None or current.get("id") != message_id:
            await live_chat.pin_message(broadcaster_id, message)
        duration_minutes = None
        if pin.get("ends_at"):
            try:
                ends_at = datetime.fromisoformat(str(pin["ends_at"]).replace("Z", "+00:00"))
                starts_at = datetime.fromisoformat(
                    str(pin.get("updated_at") or pin.get("starts_at")).replace("Z", "+00:00")
                )
                duration_minutes = round((ends_at - starts_at).total_seconds() / 60)
            except (TypeError, ValueError):
                duration_minutes = None
        return JSONResponse({
            "message": message,
            "duration_minutes": duration_minutes,
            "ends_at": pin.get("ends_at")
        })
    except Exception:
        LOGGER.warning("[Dashboard] Could not synchronize Twitch pinned message for broadcaster %s.", broadcaster_id)
        return JSONResponse({"message": live_chat.get_pinned_message(broadcaster_id), "sync_unavailable": True})


@router.post("/channel/api/chat/moderate", response_class=JSONResponse)
async def moderate_channel_chat_message(
    request: Request,
    action: str = Form(...),
    message_id: str = Form(...),
    csrf_token: str = Form(...),
    duration_minutes: str = Form("")
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    if not message_id.startswith("twitch:"):
        return JSONResponse({"detail": "Only Twitch messages can be moderated here."}, status_code=400)

    raw_message_id = message_id.removeprefix("twitch:")
    live_chat = runtime_bot.services.live_chat
    try:
        if action == "delete":
            broadcaster = runtime_bot.create_partialuser(str(broadcaster_id))
            await broadcaster.delete_chat_messages(moderator=str(broadcaster_id), message_id=raw_message_id)
            await live_chat.remove_message(broadcaster_id, message_id)
            return JSONResponse({"action": "deleted", "message_id": message_id, "pinned": None})
        if action == "pin-duration":
            pinned = live_chat.get_pinned_message(broadcaster_id)
            if pinned is None or pinned.get("id") != message_id:
                return JSONResponse({"detail": "That message is no longer pinned."}, status_code=409)
            allowed_durations = {str(value) for value in range(1, 11)} | {"15", "20", "25", "30"}
            if duration_minutes and duration_minutes not in allowed_durations:
                return JSONResponse({"detail": "That pinned-message duration is not supported."}, status_code=400)
            params = {
                "broadcaster_id": str(broadcaster_id),
                "moderator_id": str(broadcaster_id),
                "message_id": raw_message_id
            }
            if duration_minutes:
                params["duration_seconds"] = str(int(duration_minutes) * 60)
            route = Route("PATCH", "chat/pins", params=params, token_for=str(broadcaster_id))
            await runtime_bot._http.request_json(route)
            ends_at = (
                (datetime.now(UTC) + timedelta(minutes=int(duration_minutes))).isoformat()
                if duration_minutes else None
            )
            return JSONResponse({
                "action": "duration-updated",
                "message_id": message_id,
                "pinned": pinned,
                "duration_minutes": int(duration_minutes) if duration_minutes else None,
                "ends_at": ends_at
            })
        if action != "pin":
            return JSONResponse({"detail": "Unknown chat moderation action."}, status_code=400)

        pinned = live_chat.get_pinned_message(broadcaster_id)
        if pinned is not None and pinned.get("id") == message_id:
            route = Route("DELETE", "chat/pins", params={
                "broadcaster_id": str(broadcaster_id),
                "moderator_id": str(broadcaster_id),
                "message_id": raw_message_id
            }, token_for=str(broadcaster_id))
            await runtime_bot._http.request_json(route)
            await live_chat.clear_pinned_message(broadcaster_id)
            return JSONResponse({"action": "unpinned", "message_id": message_id, "pinned": None})

        message = live_chat.find_message(broadcaster_id, message_id)
        if message is None:
            return JSONResponse({"detail": "That message is no longer available in the chat history."}, status_code=404)
        route = Route("PUT", "chat/pins", params={
            "broadcaster_id": str(broadcaster_id),
            "moderator_id": str(broadcaster_id),
            "message_id": raw_message_id
        }, token_for=str(broadcaster_id))
        await runtime_bot._http.request_json(route)
        await live_chat.pin_message(broadcaster_id, message)
        return JSONResponse({"action": "pinned", "message_id": message_id, "pinned": message})
    except HTTPException as error:
        LOGGER.warning(
            "[Dashboard] Twitch rejected %s for message %s with status %s: %s",
            action, raw_message_id, error.status, error
        )
        if error.status == 401:
            detail = "Reconnect Twitch to grant the permission required to manage pinned messages."
        elif error.status == 403:
            detail = "Twitch says this account is not allowed to manage pinned messages in this channel."
        elif error.status == 404:
            detail = "Twitch could not find that message. It may be too old or already removed."
        elif error.status == 409:
            detail = "That message is already pinned."
        elif error.status == 429:
            detail = "Twitch's pin rate limit was reached. Try again shortly."
        else:
            detail = "Twitch rejected the pinned-message request."
        return JSONResponse({"detail": detail}, status_code=error.status if 400 <= error.status < 600 else 502)
    except Exception:
        LOGGER.exception("[Dashboard] Failed to %s Twitch message %s.", action, raw_message_id)
        return JSONResponse({
            "detail": "The pinned-message request failed before Twitch could complete it."
        }, status_code=502)


@router.post("/channel/api/automod/action", response_class=JSONResponse)
async def moderate_automod_message(
    request: Request,
    action: str = Form(...),
    message_id: str = Form(...),
    csrf_token: str = Form(...)
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    if action not in {"approve", "deny"}:
        return JSONResponse({"detail": "Unknown AutoMod action."}, status_code=400)
    try:
        moderator = runtime_bot.create_partialuser(str(broadcaster_id))
        if action == "approve":
            await moderator.approve_automod_messages(message_id)
        else:
            await moderator.deny_automod_messages(message_id)
        runtime_bot.services.live_chat.resolve_automod_message(broadcaster_id, message_id)
        return JSONResponse({"action": action, "message_id": message_id})
    except Exception:
        LOGGER.exception("[Dashboard] Failed to %s AutoMod message %s.", action, message_id)
        return JSONResponse({
            "detail": "Twitch rejected the AutoMod action. Reconnect the channel if the AutoMod permission has not been granted."
        }, status_code=502)


@router.get("/channel/api/games", response_class=JSONResponse)
async def search_twitch_games(request: Request, query: str = ""):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    try:
        normalized_query = query.strip()
        if not normalized_query:
            return JSONResponse({"games": (await get_top_games_for_search(runtime_bot, broadcaster_id))[:50]})

        iterator = runtime_bot.search_categories(
            normalized_query, token_for=str(broadcaster_id), first=50, max_results=50
        )
        games = [{"id": str(game.id), "name": str(game.name)} async for game in iterator]
        popular_games = []
        if callable(getattr(runtime_bot, "fetch_top_games", None)):
            try:
                popular_games = await get_top_games_for_search(runtime_bot, broadcaster_id)
            except Exception:
                LOGGER.warning("[Dashboard] Could not rank categories by current popularity.", exc_info=True)

        existing_ids = {game["id"] for game in games}
        normalized_name = " ".join(normalized_query.casefold().split())
        for game in popular_games:
            if game["id"] not in existing_ids and category_match_type(game["name"].casefold(), normalized_name) < 5:
                games.append(game)
                existing_ids.add(game["id"])
        games = sort_twitch_games_by_match(games, normalized_query, popular_games)[:50]
        return JSONResponse({"games": games})
    except Exception:
        LOGGER.exception("[Dashboard] Failed to search Twitch games for broadcaster %s.", broadcaster_id)
        return JSONResponse({"detail": "Twitch game search is temporarily unavailable."}, status_code=502)


@router.get("/channel/api/chat/stream")
async def channel_chat_stream(request: Request, view: str = "both"):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    if runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return StreamingResponse(
        stream_chat_events(request, runtime_bot.services.live_chat, str(broadcaster_id), view),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/channel/api/chat/emotes", response_class=JSONResponse)
async def channel_chat_emotes(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    if runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await runtime_bot.services.live_chat.get_emote_catalog(str(broadcaster_id)))


@router.get("/channel/api/chat/users", response_class=JSONResponse)
async def channel_chat_users(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    if runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse({
        "users": runtime_bot.services.chatters.list_channel_identities(str(broadcaster_id))
    })


@router.get("/channel/api/ad-status", response_class=JSONResponse)
async def channel_ad_status(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    twitch_user = runtime_bot.create_partialuser(str(broadcaster_id))
    return JSONResponse(await get_ad_status(broadcaster, twitch_user))


@router.post("/channel/api/ads/action", response_class=JSONResponse)
async def channel_ad_action(request: Request, action: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    if action not in {"run-90", "run-180", "snooze"}:
        return JSONResponse({"detail": "Unknown ad action."}, status_code=400)

    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    twitch_user = runtime_bot.create_partialuser(str(broadcaster_id))
    try:
        if action == "snooze":
            result = await twitch_user.snooze_next_ad()
            return JSONResponse({
                "message": "Next ad snoozed by 5 minutes.",
                "status": {
                    "state": "scheduled" if result.next_ad_at else "none",
                    "label": "Next ad" if result.next_ad_at else "No ad scheduled",
                    "next_ad_at": result.next_ad_at.isoformat() if result.next_ad_at else None, "ends_at": None,
                    "snoozes_available": result.snooze_count
                }
            })

        duration = 90 if action == "run-90" else 180
        result = await twitch_user.start_commercial(length=duration)
        if result.message:
            return JSONResponse({"detail": result.message}, status_code=409)
        actual_duration = result.length or duration
        started_at = datetime.now(UTC)
        return JSONResponse({
            "message": f"{actual_duration}-second ad started.",
            "status": {
                "state": "running", "label": "Ad running", "next_ad_at": None,
                "started_at": started_at.isoformat(),
                "ends_at": (started_at + timedelta(seconds=actual_duration)).isoformat(),
                "snoozes_available": None
            }
        })
    except HTTPException as error:
        LOGGER.warning("[Dashboard] Twitch rejected ad action %s for %s with status %s: %s", action, broadcaster_id, error.status, error)
        if error.status == 401:
            detail = "Reconnect Twitch to grant the permission required to manage ads."
        elif error.status == 403:
            detail = "Twitch says this account cannot manage ads for this channel."
        elif error.status == 429:
            detail = "No ad snoozes are available, or the ad cooldown has not ended."
        elif error.status == 400:
            detail = "This ad action is unavailable while offline or at this point in the ad schedule."
        else:
            detail = "Twitch rejected the ad action."
        return JSONResponse({"detail": detail}, status_code=error.status if 400 <= error.status < 600 else 502)
    except Exception:
        LOGGER.exception("[Dashboard] Failed ad action %s for %s.", action, broadcaster_id)
        return JSONResponse({"detail": "Could not manage ads right now."}, status_code=502)


@router.post("/channel/api/chat/send", response_class=JSONResponse)
async def channel_send_chat_message(
    request: Request,
    message: str = Form(...),
    target: str = Form(...),
    csrf_token: str = Form(...),
    reply_parent_message_id: str = Form("")
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    validate_csrf_token(request, csrf_token)
    message = message.strip()
    target = target.strip().lower()
    reply_parent_message_id = reply_parent_message_id.strip() if isinstance(reply_parent_message_id, str) else ""

    if not message:
        return JSONResponse({"detail": "Enter a message to send."}, status_code=400)

    if len(message) > CHAT_MESSAGE_MAX_LENGTH:
        return JSONResponse({"detail": f"Messages are limited to {CHAT_MESSAGE_MAX_LENGTH} characters."}, status_code=400)

    if target not in CHAT_SEND_TARGETS:
        return JSONResponse({"detail": "Choose Twitch, YouTube, or Both."}, status_code=400)

    if reply_parent_message_id and not reply_parent_message_id.startswith("twitch:"):
        return JSONResponse({"detail": "That reply target is not a Twitch message."}, status_code=400)

    if reply_parent_message_id and target == "youtube":
        return JSONResponse({"detail": "Twitch replies cannot be sent only to YouTube."}, status_code=400)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    sent = []
    errors = {}
    command_status = None
    is_twitch_command = message.startswith("/")

    if is_twitch_command and target == "youtube":
        return JSONResponse({"detail": "Twitch slash commands can only be sent to Twitch."}, status_code=400)

    if is_twitch_command and reply_parent_message_id:
        return JSONResponse({"detail": "Twitch slash commands cannot be sent as replies."}, status_code=400)

    if target in {"twitch", "both"}:
        try:
            if is_twitch_command:
                command_status = await execute_twitch_slash_command(runtime_bot, str(broadcaster_id), message)
                sent.append("twitch")
            else:
                twitch_channel = runtime_bot.create_partialuser(str(broadcaster_id))
                send_options = {
                    "sender": str(broadcaster_id),
                    "token_for": str(broadcaster_id),
                    "message": message
                }
                if reply_parent_message_id:
                    send_options["reply_to_message_id"] = reply_parent_message_id.removeprefix("twitch:")
                result = await twitch_channel.send_message(**send_options)
                if getattr(result, "sent", False):
                    sent.append("twitch")
                else:
                    errors["twitch"] = getattr(result, "dropped_message", None) or "Twitch did not send the message."
        except ValueError as error:
            errors["twitch"] = str(error)
        except Exception:
            LOGGER.exception("[Dashboard] Failed to send Twitch message for broadcaster %s.", broadcaster_id)
            errors["twitch"] = (
                "Twitch rejected that command. Reconnect Twitch if the command permission has not been granted."
                if is_twitch_command else "Reconnect Twitch to enable dashboard replies."
            )

    if target in {"youtube", "both"} and not is_twitch_command:
        try:
            await services.live_chat.send_youtube_message(str(broadcaster_id), message)
            sent.append("youtube")
        except ValueError as error:
            youtube_error = str(error)

            if target == "youtube" or not sent:
                errors["youtube"] = (
                    "YouTube is offline. Start a YouTube livestream with live chat enabled before sending a message."
                    if "No active YouTube live chat" in youtube_error
                    else youtube_error
                )
        except Exception:
            LOGGER.exception("[Dashboard] Failed to send YouTube message for broadcaster %s.", broadcaster_id)

            if target == "youtube" or not sent:
                errors["youtube"] = "Reconnect YouTube to enable dashboard replies."

    if not sent:
        detail = " ".join(errors.values()) or "The message could not be sent."
        return JSONResponse({"detail": detail, "sent": sent, "errors": errors}, status_code=400)

    status_code = 207 if errors else 200
    payload = {"sent": sent, "errors": errors}
    if command_status is not None:
        payload["message"] = command_status
    return JSONResponse(payload, status_code=status_code)


@router.get("/channel", response_class=HTMLResponse)
async def channel_dashboard(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(
            request=request,
            name="channel/dashboard.html",
            context={
                "active_page": "overview",
                "broadcaster": None,
                "runtime_unavailable": True,
                "csrf_token": get_csrf_token(request)
            },
            status_code=503
        )

    services = runtime_bot.services
    broadcaster_service = services.broadcasters
    broadcaster = broadcaster_service.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    await broadcaster_service.refresh_live_statuses()

    channel_settings = await services.broadcaster_settings.get_settings(broadcaster_id)
    viewer_queue = services.viewer_queue
    redemption_activity = await get_redemption_dashboard_data(services, broadcaster_id)
    gambling_loss_total = await services.points.get_gambling_loss_total(broadcaster_id)
    raid_enabled = services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES)
    raid_metrics = await services.raid_bosses.get_dashboard_metrics(broadcaster_id) if raid_enabled else None
    ad_status = await get_ad_status(broadcaster, runtime_bot.create_partialuser(str(broadcaster_id)))
    dashboard_header_stats = await get_dashboard_header_stats(runtime_bot, broadcaster, points_lost=gambling_loss_total)
    twitch_channel_metadata = await get_twitch_channel_metadata(runtime_bot, broadcaster_id)

    return templates.TemplateResponse(
        request=request,
        name="channel/dashboard.html",
        context={
            "active_page": "overview",
            "broadcaster": broadcaster,
            "runtime_unavailable": False,
            "channel_settings": channel_settings,
            "queue_open": viewer_queue.is_queue_open(broadcaster_id),
            "queue_users": viewer_queue.list_queue(broadcaster_id),
            "queue_members": get_queue_members(services, broadcaster_id),
            "queue_size": viewer_queue.size(broadcaster_id),
            "redemption_activity": redemption_activity,
            "gambling_loss_total": gambling_loss_total,
            "raid_enabled": raid_enabled,
            "raid_metrics": raid_metrics,
            "youtube_chat": services.live_chat.get_youtube_state(broadcaster_id),
            "ad_status": ad_status,
            "dashboard_header_stats": dashboard_header_stats,
            "twitch_channel_metadata": twitch_channel_metadata,
            "queue_result": request.query_params.get("queue_result"),
            "queue_message": request.query_params.get("queue_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/viewer-queue/blacklist", response_class=HTMLResponse)
async def channel_viewer_queue_blacklist(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)
    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="channel/viewer_queue_blacklist.html",
        context={
            "active_page": "overview",
            "broadcaster": broadcaster,
            "blacklist": [
                {"username": username, "label": format_dashboard_username(runtime_bot.services, broadcaster_id, username)}
                for username in runtime_bot.services.viewer_queue.list_blacklist(broadcaster_id)
            ],
            "blacklist_result": request.query_params.get("result"),
            "blacklist_message": request.query_params.get("message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.post("/channel/viewer-queue/blacklist")
async def update_channel_viewer_queue_blacklist(
    request: Request,
    action: str = Form(...),
    username: str = Form(...),
    csrf_token: str = Form(...)
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)
    queue = runtime_bot.services.viewer_queue
    if action == "add":
        changed, message = await queue.add_to_blacklist(broadcaster_id, username)
    elif action == "remove":
        changed, message = await queue.remove_from_blacklist(broadcaster_id, username)
    else:
        changed, message = False, "Unknown blacklist action."
    result = "success" if changed else "error"
    return RedirectResponse(
        url=f"/channel/viewer-queue/blacklist?result={result}&message={quote_plus(message)}",
        status_code=303
    )


@router.get("/channel/help", response_class=HTMLResponse)
async def channel_help_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    profile = get_active_profile(broadcaster_id)

    if broadcaster is None or profile is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    command_groups = build_command_help_groups(services.features, broadcaster_id, profile)
    command_count = sum(len(group.commands) for group in command_groups)
    enabled_command_count = sum(group.enabled_count for group in command_groups)
    raid_contributor_data = await get_raid_contributor_data(services, broadcaster_id)

    return templates.TemplateResponse(
        request=request,
        name="channel/help.html",
        context={
            "active_page": "help",
            "broadcaster": broadcaster,
            "command_groups": command_groups,
            "command_count": command_count,
            "enabled_command_count": enabled_command_count,
            "raid_contributor_data": raid_contributor_data,
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/features", response_class=HTMLResponse)
async def channel_features_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="channel/features.html",
        context={
            "active_page": "features",
            "broadcaster": broadcaster,
            "channel_features": services.features.get_channel_features(broadcaster_id),
            "profile_features": services.features.get_profile_features(broadcaster_id),
            "global_groups": services.features.get_global_groups(broadcaster_id),
            "global_commands": services.features.get_global_commands(broadcaster_id),
            "toggle_result": request.query_params.get("toggle_result"),
            "toggle_message": request.query_params.get("toggle_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/loyalty", response_class=HTMLResponse)
@router.get("/channel/customization", response_class=HTMLResponse)
async def channel_customization_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None or get_active_profile(broadcaster_id) is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    loyalty_page = request.url.path == "/channel/loyalty"
    groups = services.profile_settings.get_setting_groups(broadcaster_id, {feature.value for feature in services.features.get_profile_features(broadcaster_id)})
    widget_urls = {}

    if not loyalty_page:
        widget_token = await services.live_chat.get_or_create_widget_token(broadcaster_id)
        widget_base_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/widgets/chat/{widget_token}"
        widget_urls = {view: f"{widget_base_url}?view={view}" for view in ("chat", "commands", "both")}

    return templates.TemplateResponse(
        request=request,
        name="channel/loyalty.html" if loyalty_page else "channel/customization.html",
        context={
            "active_page": "loyalty" if loyalty_page else "customization",
            "customization_action": "/channel/loyalty" if loyalty_page else "/channel/customization",
            "show_social_links": not loyalty_page,
            "loyalty_alias": get_active_profile(broadcaster_id).points.command_alias,
            "broadcaster": broadcaster,
            "channel_settings": await services.broadcaster_settings.get_settings(broadcaster_id),
            "setting_groups": {name: entries for name, entries in groups.items() if (name == LOYALTY_GROUP) == loyalty_page},
            "chat_identity": services.chat_identity.get_state(broadcaster_id),
            "youtube_chat": services.live_chat.get_youtube_state(broadcaster_id),
            "widget_urls": widget_urls,
            "setting_result": request.query_params.get("setting_result"),
            "setting_message": request.query_params.get("setting_message"),
            "identity_result": request.query_params.get("identity_result"),
            "identity_message": request.query_params.get("identity_message"),
            "youtube_result": request.query_params.get("youtube_result"),
            "youtube_message": request.query_params.get("youtube_message"),
            "social_tab": request.query_params.get("social_tab", "links"),
            "command_tab": request.query_params.get("command_tab", "responses"),
            "protected_users": await get_protected_user_rows(runtime_bot, str(broadcaster_id)) if not loyalty_page else [],
            "protected_result": request.query_params.get("protected_result"),
            "protected_message": request.query_params.get("protected_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.post("/channel/loyalty")
@router.post("/channel/customization")
async def update_channel_customization(request: Request, setting_name: str = Form(...), value: str = Form(""), action: str = Form(...), csrf_token: str = Form(...)):
    destination = "/channel/loyalty" if request.url.path == "/channel/loyalty" else "/channel/customization"
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url=f"{destination}?setting_result=error&setting_message=Runtime+unavailable.", status_code=303)

    services = runtime_bot.services

    try:
        if destination == "/channel/loyalty" and services.profile_settings.get_definition(setting_name).group != LOYALTY_GROUP:
            raise ValueError("Only loyalty point names and responses can be edited here.")
        if setting_name == "social.discord_url":
            await services.broadcaster_settings.set_discord_url(broadcaster_id, value.strip())
            message = "Discord URL was updated."
        elif setting_name == "social.youtube_url":
            await services.broadcaster_settings.set_youtube_url(broadcaster_id, value.strip())
            message = "YouTube URL was updated."
        else:
            definition = services.profile_settings.get_definition(setting_name)

            if action == "save":
                await services.profile_settings.set_override(broadcaster_id, setting_name, value, f"streamer:{broadcaster_id}")
                message = f"{definition.label} was updated."
            elif action == "reset":
                await services.profile_settings.clear_override(broadcaster_id, setting_name, f"streamer:{broadcaster_id}")
                message = f"{definition.label} was reset to its channel default."
            else:
                raise ValueError("Unknown customization action.")
    except (TypeError, ValueError) as error:
        return RedirectResponse(url=f"{destination}?setting_result=error&setting_message={quote_plus(str(error))}", status_code=303)

    return RedirectResponse(url=f"{destination}?setting_result=success&setting_message={quote_plus(message)}", status_code=303)


@router.get("/channel/protected-users/search")
async def search_channel_protected_user(request: Request, query: str = ""):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Connect your Twitch channel first."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "The bot runtime is unavailable."}, status_code=503)

    try:
        user = await lookup_protected_user(runtime_bot, str(broadcaster_id), query)
    except ProtectedUserError as error:
        return JSONResponse({"detail": str(error)}, status_code=error.status_code)

    return JSONResponse({"user": user})


@router.post("/channel/protected-users/add")
async def add_channel_protected_user(request: Request, user_id: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return protected_users_redirect("error", "The bot runtime is unavailable.")

    try:
        message = await add_protected_user(runtime_bot, str(broadcaster_id), user_id)
    except ProtectedUserError as error:
        return protected_users_redirect("error", str(error))

    return protected_users_redirect("success", message)


@router.post("/channel/protected-users/remove")
async def remove_channel_protected_user(request: Request, user_id: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return protected_users_redirect("error", "The bot runtime is unavailable.")

    try:
        message = await remove_protected_user(runtime_bot, str(broadcaster_id), user_id)
    except ProtectedUserError as error:
        return protected_users_redirect("error", str(error))

    return protected_users_redirect("success", message)


@router.post("/channel/features/toggles")
async def update_channel_feature(request: Request, toggle_type: str = Form(...), toggle_name: str = Form(...), action: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Runtime+unavailable.", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    if action not in {"enable", "disable", "reset"}:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+action.", status_code=303)

    enabled = action == "enable"
    updated_by = f"streamer:{broadcaster_id}"

    try:
        if toggle_type == "feature":
            toggle = FeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = toggle.value.replace("_", " ").title()

        elif toggle_type == "profile_feature":
            toggle = ProfileFeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_profile_feature_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_profile_feature_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = "League of Legends" if toggle is ProfileFeatureName.LEAGUE else "Overwatch"

        elif toggle_type == "global_group":
            toggle = GlobalCommandGroup(toggle_name)

            if action == "reset":
                state = await services.features.clear_global_group_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_global_group_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = toggle.value.replace("_", " ").title()

        elif toggle_type == "global_command":
            toggle = GlobalCommandName(toggle_name)

            if action == "reset":
                state = await services.features.clear_global_command_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_global_command_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = f"!{toggle.value}"

        else:
            return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+type.", status_code=303)

    except ValueError:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle.", status_code=303)
    except Exception:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=The+toggle+could+not+be+updated.", status_code=303)

    if action == "reset":
        message = f"{display_name} was reset to its profile default."
    else:
        effective_state = "enabled" if state.effective_enabled else "disabled"
        message = f"{display_name} is now {effective_state}."

    return RedirectResponse(url=f"/channel/features?toggle_result=success&toggle_message={quote_plus(message)}", status_code=303)


@router.post("/channel/viewer-queue/remove")
async def remove_viewer_from_channel_queue(request: Request, position: int = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(
            url="/channel?queue_result=remove_failed&queue_message=The+bot+runtime+is+unavailable.", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    removed, _, message = await services.viewer_queue.remove_position(broadcaster_id, position)

    result = "removed" if removed else "remove_failed"

    return RedirectResponse(
        url=f"/channel?queue_result={result}&queue_message={quote_plus(message)}", status_code=303)


@router.post("/channel/logout")
async def channel_logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    logout_channel_user(request)

    return RedirectResponse(url="/connect", status_code=303)

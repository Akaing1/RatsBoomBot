import asyncio
import logging
import re
import time
import unicodedata

import httpx
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from twitchio import HTTPException
from twitchio.http import Route

from bot.command_registry import build_command_help_groups
from bot.shared.pending_raids import raid_lock, raid_state, raid_viewer_count, remember_raid
from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName, get_active_profile
from bot.services.channels.profile_settings import LOYALTY_GROUP
from bot.services.channels.stream_metadata import (
    StreamCategoryNotFoundError, clear_stream_category, update_stream_game, update_stream_title
)
from config.settings import settings
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY, logout_channel_user
from web.shared.common import templates
from web.shared.category_relevance import low_relevance_category_ids
from web.shared.raid_suggestions import get_suggested_streamers
from web.shared.raid_directory import get_sorted_directory
from web.shared.live_chat import clear_stale_chat_on_refresh, stream_chat_events
from web.shared.raid_chat import preview_chat_events, preview_emotes
from web.shared.protected_users import (
    ProtectedUserError,
    add_protected_user,
    get_protected_user_rows,
    lookup_protected_user,
    remove_protected_user
)
from web.state import get_bot
from storage.incoming_raids import recent_incoming_raids

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
CHAT_SEND_TARGETS = {"twitch", "youtube", "both"}
CHAT_MESSAGE_MAX_LENGTH = 500
TOP_GAMES_CACHE_SECONDS = 300
RAID_BROWSER_DEV_CHANNELS = {"minamichimaa", "ninjakaing"}


def raid_channel_search_score(query, login, display_name="", category=""):
    def normalize(value):
        return "".join(char for char in unicodedata.normalize("NFKC", str(value)).casefold() if char.isalnum())

    needle = normalize(query)
    if not needle:
        return 0

    def match(value):
        value = normalize(value)[:128]
        if not value:
            return 0
        if needle == value:
            return 1000
        if value.startswith(needle):
            return 900
        if needle in value:
            return 800
        # Avoid broad, accidental matches from one- or two-letter searches.
        if len(needle) < 4:
            return 0
        ratio = SequenceMatcher(None, needle, value).ratio()
        if len(needle) <= 40 and len(value) > len(needle):
            for width in (len(needle) - 1, len(needle), len(needle) + 1):
                for start in range(max(0, len(value) - width + 1)):
                    ratio = max(ratio, SequenceMatcher(None, needle, value[start:start + width]).ratio())
        return round(700 * ratio) if ratio >= .75 else 0

    return max(match(login), match(display_name), match(category) * .5)


RAID_BROWSER_MUTUAL_BONUS = 80


def raid_size_bonus(own, candidate, maximum):
    # Unknown/zero counts aren't evidence of similar channel size. Ratios make
    # the bonus scale equally for small and large communities, in either direction.
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in (own, candidate)):
        return 0
    return round(maximum * min(own, candidate) / max(own, candidate))


def raid_relevance_breakdown(*, same_category=False, shared_tags=(), same_team=False,
                         both_vtubers=False, followed=False, mutual=False, suggested=False, same_language=False, recent_raid=0,
                         own_viewers=None, viewers=None, own_followers=None, followers=None):
    # Compatibility outweighs simply being followed/suggested. Treat VTuber
    # separately so it isn't counted again among generic shared tags.
    other_tags = {str(tag).strip().casefold() for tag in shared_tags} - {"vtuber", ""}
    return {
        "Same category": 400 * same_category,
        "Same team": 200 * same_team,
        "Both VTubers": 250 * both_vtubers,
        "Team + VTuber": 50 * (same_team and both_vtubers),
        "Shared tags": 40 * min(len(other_tags), 5),
        "Following": 400 * followed,
        "Mutual following": RAID_BROWSER_MUTUAL_BONUS * (followed and mutual),
        "Suggested": 120 * suggested,
        "Same language": 20 * same_language,
        "Recent raid": round(300 * max(0, min(1, recent_raid))),
        "Similar viewer count": raid_size_bonus(own_viewers, viewers, 180),
        "Similar channel size": raid_size_bonus(own_followers, followers, 120),
    }


def raid_relevance_score(**matches):
    return sum(raid_relevance_breakdown(**matches).values())


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
        runtime_bot.services.live_chat.clear_chat(broadcaster_id)
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
            async with raid_lock(runtime_bot, broadcaster_id):
                result = await broadcaster.start_raid(str(user.id))
                remember_raid(runtime_bot, broadcaster_id, user, getattr(result, "created_at", None))
        else:
            await broadcaster.send_shoutout(to_broadcaster=str(user.id), moderator=moderator_id)
    elif command == "unraid":
        async with raid_lock(runtime_bot, broadcaster_id):
            await broadcaster.cancel_raid()
            raid_state(runtime_bot).pop(str(broadcaster_id), None)
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
        return {"title": str(info.title or "Untitled stream"), "game": str(info.game_name or "No category"),
                "box_art_url": await get_category_artwork(runtime_bot, broadcaster_id, getattr(info, "game_id", None))}
    except Exception as exc:
        LOGGER.warning("[Dashboard] Failed to fetch Twitch channel metadata for broadcaster %s: %s", broadcaster_id, exc)
        return {"title": "Unavailable", "game": "Unavailable"}


def serialize_category(game) -> dict[str, str]:
    category = {"id": str(game.id), "name": str(game.name)}
    artwork = getattr(game, "box_art", None)
    if artwork:
        category["box_art_url"] = artwork.url_for(96, 128)
    return category


async def get_category_artwork(runtime_bot, broadcaster_id: str, game_id: str | None) -> str:
    if not game_id or str(game_id) == "0":
        return ""
    try:
        game = await runtime_bot.fetch_game(id=str(game_id), token_for=str(broadcaster_id))
        return serialize_category(game).get("box_art_url", "") if game else ""
    except Exception as exc:
        LOGGER.warning("[Dashboard] Category artwork unavailable for %s: %s", game_id, exc)
        return ""


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
    games = [serialize_category(game) async for game in iterator]
    runtime_bot._dashboard_top_games_cache = (now + TOP_GAMES_CACHE_SECONDS, games)
    return games


async def category_picker_results(runtime_bot, broadcaster_id: str, games: list[dict[str, str]]) -> dict:
    secondary_ids = await low_relevance_category_ids(runtime_bot, games, broadcaster_id)
    if not secondary_ids:
        return {"games": games}
    return {
        "games": [game for game in games if game["id"] not in secondary_ids],
        "more_games": [game for game in games if game["id"] in secondary_ids]
    }


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


def dashboard_activity_time(value: object) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)


async def get_redemption_dashboard_data(services, broadcaster_id: str) -> dict[str, object]:
    activity = await services.redeems.get_dashboard_activity(broadcaster_id=broadcaster_id)
    for collection in (activity.get("checkins", []), activity.get("redemptions", [])):
        for entry in collection:
            entry["user_label"] = format_dashboard_username(services, broadcaster_id, entry.get("username", ""))
    activity["feed"] = sorted(
        [{**entry, "kind": kind} for kind, entries in (
            ("checkin", activity.get("checkins", [])),
            ("redemption", activity.get("redemptions", []))
        ) for entry in entries],
        key=lambda entry: dashboard_activity_time(entry.get("redeemed_at")),
        reverse=True
    )
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
    count: int = Form(4),
    expected_users: str = Form("")
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
        if isinstance(expected_users, str) and expected_users:
            highlighted = expected_users.split(",")
            if queue.list_queue(broadcaster_id)[:next_count] != highlighted:
                return JSONResponse({"detail": "The queue changed. Review the next viewers again."}, status_code=409)
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


@router.get("/channel/api/raid-browser/pending", response_class=JSONResponse)
async def channel_pending_raid(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    if str(broadcaster_id) not in runtime_bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    raid = getattr(runtime_bot, "_dashboard_pending_raids", {}).get(str(broadcaster_id))
    if raid and not raid.get("completed"):
        raid["viewer_count"] = raid_viewer_count(runtime_bot, broadcaster_id)
    return JSONResponse({"raid": raid})


@router.post("/channel/api/raid-browser/action", response_class=JSONResponse)
async def channel_raid_action(request: Request, action: str = Form(...),
                              target_id: str = Form(""), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster_id = str(broadcaster_id)
    if broadcaster_id not in runtime_bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    if action not in {"start", "cancel"}:
        return JSONResponse({"detail": "Unknown raid action."}, status_code=400)
    if action == "start" and (not re.fullmatch(r"\d{1,25}", target_id) or target_id == broadcaster_id):
        return JSONResponse({"detail": "Select another channel to raid."}, status_code=400)
    lock = raid_lock(runtime_bot, broadcaster_id)
    async with lock:
        pending = runtime_bot._dashboard_pending_raids.get(broadcaster_id)
        if action == "start" and pending and pending["expires_at"] > time.time():
            return JSONResponse({"detail": "A raid is already pending. Cancel it before starting another."}, status_code=409)
        try:
            broadcaster = runtime_bot.create_partialuser(broadcaster_id)
            if action == "cancel":
                if not pending:
                    return JSONResponse({"detail": "No dashboard raid is pending."}, status_code=404)
                await broadcaster.cancel_raid()
                runtime_bot._dashboard_pending_raids.pop(broadcaster_id, None)
                return JSONResponse({"raid": None, "detail": "Raid cancelled."})
            target = await runtime_bot.fetch_user(id=target_id)
            if target is None:
                return JSONResponse({"detail": "Twitch could not find that channel."}, status_code=404)
            result = await broadcaster.start_raid(target_id)
            raid = remember_raid(runtime_bot, broadcaster_id, target, getattr(result, "created_at", None))
            return JSONResponse({"raid": raid})
        except Exception as error:
            status = getattr(error, "status", None)
            if action == "cancel" and status == 404:
                runtime_bot._dashboard_pending_raids.pop(broadcaster_id, None)
                return JSONResponse({"raid": None, "detail": "Twitch has no pending raid to cancel."})
            if status in {401, 403}:
                detail = "Reconnect Twitch to grant permission to manage raids."
            elif status == 409:
                detail = "Twitch already has a raid in progress. Check Twitch chat before trying again."
            elif status == 429:
                detail = "Twitch's raid limit was reached. Try again later."
            elif status == 400:
                detail = "Twitch rejected the raid. The target may not accept raids from this channel."
            else:
                detail = "Could not confirm the raid action. Check Twitch chat before trying again."
            LOGGER.warning("[Dashboard] Raid action %s failed for %s (status %s).", action, broadcaster_id, status)
            return JSONResponse({"detail": detail}, status_code=status if status in {400, 401, 403, 409, 429} else 502)


@router.get("/channel/api/raid-browser/preview", response_class=JSONResponse)
async def channel_raid_preview(request: Request, target_id: str = ""):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster_id = str(broadcaster_id)
    if broadcaster_id not in runtime_bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    if not re.fullmatch(r"\d{1,25}", target_id):
        return JSONResponse({"detail": "Invalid channel."}, status_code=400)
    try:
        followers = await raid_browser_cached_request(runtime_bot, broadcaster_id, "channels/followers",
            {"broadcaster_id": target_id, "first": 1})
        total = followers.get("total")
        count = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
        return JSONResponse({"follower_count": count})
    except Exception:
        LOGGER.warning("[Dashboard] Raid preview follower count unavailable for %s.", target_id)
        return JSONResponse({"follower_count": None})


@router.get("/channel/api/raid-browser", response_class=JSONResponse)
async def channel_raid_browser(
    request: Request, query: str = "", after: str = "", same_category: bool = False,
    same_tags: bool = False, tags: str = "", tag_match: str = "all", language: str = "", following: bool = False, not_following: bool = False,
    mutual: bool = False, recommended: bool = False, same_team: bool = False, team: str = "", favorites: str = "",
    favorites_only: bool = False, blocked: str = "", category_id: str = "", suggested: bool = False, sort: str = "", event: str = "", developer_only: bool = False,
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster_id = str(broadcaster_id)
    if broadcaster_id not in runtime_bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    query = query.strip()
    language = language.strip().lower()
    if event not in {"", "drops_enabled"}:
        return JSONResponse({"detail": "Select a valid event."}, status_code=400)
    raw_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if any(len(tag) > 25 for tag in raw_tags):
        return JSONResponse({"detail": "Each tag must be 25 characters or fewer."}, status_code=400)
    selected_tags = {tag.casefold() for tag in raw_tags}
    if tag_match not in {"any", "all"}:
        return JSONResponse({"detail": "Select a valid tag matching mode."}, status_code=400)
    favorite_ids = list(dict.fromkeys(part.strip() for part in favorites.split(",") if part.strip()))
    blocked_ids = {part.strip() for part in blocked.split(",") if part.strip()}
    if len(blocked) > 2000 or len(blocked_ids) > 100 or any(not re.fullmatch(r"\d{1,25}", item) for item in blocked_ids):
        return JSONResponse({"detail": "Invalid recommendation blacklist."}, status_code=400)
    if len(favorites) > 2000 or len(favorite_ids) > 100 or any(not re.fullmatch(r"\d{1,25}", item) for item in favorite_ids):
        return JSONResponse({"detail": "Invalid favorite channel list."}, status_code=400)
    if len(query) > 100 or len(after) > 500 or len(tags) > 250 or len(selected_tags) > 10:
        return JSONResponse({"detail": "The search or page cursor is too long."}, status_code=400)
    if language and not re.fullmatch(r"[a-z]{2}|other", language):
        return JSONResponse({"detail": "Select a valid stream language."}, status_code=400)
    sort = sort or ("for_you" if recommended else "viewers_desc")
    if sort not in {"for_you", "viewers_asc", "viewers_desc", "name_asc", "name_desc", "uptime_asc", "uptime_desc"}:
        return JSONResponse({"detail": "Select a valid sorting option."}, status_code=400)
    if sort == "for_you":
        recommended = True
    if favorites_only:
        recommended = sort == "for_you"
        suggested = False
    if len(team) > 200:
        return JSONResponse({"detail": "Invalid stream team."}, status_code=400)
    if not_following and (following or mutual):
        return JSONResponse({"detail": "Select either Following or Not following."}, status_code=400)
    params = {"first": 20}
    if after:
        params["after"] = after
    try:
        if category_id and (not category_id.isdigit() or len(category_id) > 25):
            return JSONResponse({"detail": "Invalid category."}, status_code=400)
        if mutual:
            validation = await raid_browser_cached_request(runtime_bot, broadcaster_id, "oauth2/validate", {})
            if not {"user:read:follows", "moderator:read:followers"}.issubset(set(validation.get("scopes", []))):
                return JSONResponse({"detail": "Reconnect Twitch to enable mutual-following filters."}, status_code=403)
        own_category = ""
        own_tags = set()
        channel_tags = None
        own_language = ""
        if same_category or same_tags or recommended:
            info = await raid_browser_cached_request(runtime_bot, broadcaster_id, "channels", {"broadcaster_id": broadcaster_id})
            own = next(iter(info.get("data", [])), {})
            channel_tags = own.get("tags") or []
            own_category = str(own.get("game_id") or "")
            own_tags = {str(tag).strip().casefold() for tag in channel_tags}
            own_language = str(own.get("broadcaster_language") or "").lower()
            if same_category and not own_category:
                return JSONResponse({"detail": "Set your channel category before using Same category."}, status_code=400)
            if same_tags and not own_tags:
                return JSONResponse({"detail": "Your channel has no tags to match yet."}, status_code=400)
        followed_streams = []
        suggested_streams, suggested_ids = [], set()
        suggested_status = None
        if recommended or suggested:
            broadcaster = runtime_bot.services.broadcasters.get_broadcasters()[broadcaster_id]
            shelf, suggested_status = await get_suggested_streamers(runtime_bot, broadcaster_id, getattr(broadcaster, "login", None))
            suggested_ids = {channel["id"] for channel in shelf}
            if (suggested or not after) and suggested_ids and not favorites_only:
                ids = sorted(suggested_ids)
                for offset in range(0, len(ids), 100):
                    live = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": ids[offset:offset + 100], "first": 100})
                    suggested_streams.extend(live.get("data", []))
        team_streams, team_members = await raid_browser_team_streams(runtime_bot, broadcaster_id) if recommended or same_team else ([], {})
        if ((recommended or not_following) and not (following or mutual)) or ((favorites_only or same_team) and (following or mutual)):
            try:
                followed_streams = await raid_browser_followed_streams(runtime_bot, broadcaster_id)
            except HTTPException as error:
                # Favorites remain usable without follow scopes; compatibility
                # scores still apply even when following bonuses are unknown.
                if not favorites_only or following or mutual or not_following or error.status not in {401, 403}:
                    raise
                LOGGER.warning("[Dashboard] Following bonuses unavailable for favorites in %s.", broadcaster_id)
        recent_raiders = {}
        if recommended:
            try:
                recent_raiders = await recent_incoming_raids(getattr(runtime_bot.services, "db", None), broadcaster_id)
            except Exception:
                LOGGER.warning("[Dashboard] Recent incoming raids unavailable for %s.", broadcaster_id)
        recent_raid_streams = []
        if recent_raiders and not after and not (following or mutual or same_team or suggested or favorites_only):
            recent_page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {
                "user_id": list(recent_raiders), "first": 100})
            recent_raid_streams = recent_page.get("data", [])
        discovery_prefix = "fy-discovery:"
        dev_streams = await raid_browser_dev_streams(runtime_bot, broadcaster_id) if not after else []
        broad_for_you = (sort == "for_you" and not (developer_only or favorites_only or following or mutual or same_team or suggested or query or category_id or same_category)
                        and bool(own_category) and bool(language or own_language or raw_tags or own_tags))
        tag_discovery = (sort == "for_you" and bool(raw_tags)
                         and not (developer_only or favorites_only or following or mutual or same_team or suggested or query))
        discovery_page = ((broad_for_you or tag_discovery) and after.startswith(discovery_prefix)) or (tag_discovery and not after)
        if developer_only:
            page = {"data": dev_streams, "pagination": {}}
            streams = page
        elif favorites_only:
            page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": favorite_ids, "first": 100}) if favorite_ids else {"data": [], "pagination": {}}
            streams = page
        elif same_team:
            page = {"data": team_streams, "pagination": {}}
            streams = page
        elif following or mutual:
            if sort in {"viewers_asc", "uptime_asc", "uptime_desc", "name_asc", "name_desc"}:
                followed_streams = await raid_browser_followed_streams(runtime_bot, broadcaster_id)
                page = {"data": followed_streams, "pagination": {}}
            else:
                params["user_id"] = broadcaster_id
                page = await runtime_bot._http.request_json(Route(
                    "GET", "streams/followed", params=params, token_for=broadcaster_id))
            streams = page
        elif suggested:
            page = {"data": suggested_streams, "pagination": {}}
            streams = page
        elif discovery_page:
            discovery_cursor = after[len(discovery_prefix):] if after else ""
            discovery_category = category_id or (own_category if same_category else "")
            if raw_tags and not discovery_cursor:
                try:
                    streams = await raid_browser_tag_directory(runtime_bot, broadcaster_id,
                        tags=raw_tags, tag_match=tag_match, category_id=discovery_category, language=language)
                    next_cursor = "official-start" if streams.pop("has_more", False) else ""
                except (httpx.HTTPError, ValueError, TypeError, KeyError):
                    streams = await raid_browser_official_directory(runtime_bot, broadcaster_id,
                        category_id=discovery_category, language=language)
                    next_cursor = streams.get("pagination", {}).get("cursor", "")
            else:
                streams = await raid_browser_official_directory(runtime_bot, broadcaster_id,
                    after="" if discovery_cursor == "official-start" else discovery_cursor,
                    category_id=discovery_category, language=language or ("" if raw_tags else own_language))
                next_cursor = streams.get("pagination", {}).get("cursor", "")
            page = {**streams, "pagination": {"cursor": discovery_prefix + next_cursor if next_cursor else ""}}
        elif query:
            fuzzy_prefix = "fuzzy-search:"
            fuzzy_page = after.startswith(fuzzy_prefix) and len(query) >= 4
            search_query = query[:max(2, min(5, len(query) // 2))] if fuzzy_page else query
            if fuzzy_page:
                params["after"] = after[len(fuzzy_prefix):]
            params.update(query=search_query, live_only="true")
            page = await runtime_bot._http.request_json(Route(
                "GET", "search/channels", params=params, token_for=broadcaster_id))
            if not page.get("data") and not after and len(query) >= 4:
                # A bounded broader lookup supplies candidates when Twitch's
                # literal search cannot find the misspelled channel name.
                fuzzy_page = True
                params["query"] = query[:max(2, min(5, len(query) // 2))]
                page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "search/channels", params)
            if fuzzy_page:
                next_page = page.get("pagination", {}).get("cursor", "")
                page = {**page, "pagination": {"cursor": fuzzy_prefix + next_page if next_page else ""}}
            ids = [str(item["id"]) for item in page.get("data", [])
                   if item.get("is_live") and str(item.get("id", "")) != broadcaster_id]
            streams = await runtime_bot._http.request_json(Route(
                "GET", "streams", params={"user_id": ids, "first": 20}, token_for=broadcaster_id)) if ids else {"data": []}
        elif sort in {"viewers_asc", "uptime_asc"} or (recommended and sort == "viewers_desc") or event == "drops_enabled":
            discovery_category = category_id or (own_category if recommended or same_category else "")
            discovery_language = language or (own_language if recommended else "")
            preferred_tags = [tag for tag in (channel_tags or []) if isinstance(tag, str) and 0 < len(tag) <= 25]
            if "vtuber" in own_tags:
                preferred_tags = ["VTuber"]
            discovery_tags = raw_tags or (preferred_tags[:1] if recommended else [])
            if event == "drops_enabled":
                discovery_tags = ["DropsEnabled"]
            directory_sort = sort if sort in {"viewers_asc", "viewers_desc", "uptime_asc"} else "viewers_desc"
            official_fallback = after.startswith("official:")
            try:
                if official_fallback:
                    directory = None
                elif recommended and not (discovery_category or discovery_language or discovery_tags):
                    directory = {"ids": [], "cursor": ""}
                else:
                    directory = await get_sorted_directory(runtime_bot, sort=directory_sort, after=after,
                        category_id=discovery_category, language=discovery_language, tags=discovery_tags, tag_match=tag_match)
                    # Implicit preferences should not turn a quiet category
                    # into an empty browser; explicit user filters stay strict.
                    if not directory["ids"] and not after and not raw_tags and discovery_tags and not event:
                        directory = await get_sorted_directory(runtime_bot, sort=directory_sort,
                            category_id=discovery_category, language=discovery_language)
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                LOGGER.warning("[Dashboard] Raid directory unavailable; using official stream lookup for %s.", broadcaster_id)
                official_fallback = True
            if official_fallback:
                streams = await raid_browser_official_directory(runtime_bot, broadcaster_id,
                    after=after if after.startswith("official:") else "",
                    category_id=discovery_category, language=discovery_language)
                page = {**streams, "sort_scope": "fetched"}
            else:
                streams = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {
                    "user_id": directory["ids"], "first": 100}) if directory["ids"] else {"data": []}
                page = {"pagination": {"cursor": directory["cursor"]}}
        else:
            if category_id or same_category or (recommended and own_category):
                params["game_id"] = category_id or own_category
            if language or (recommended and not own_category and own_language):
                params["language"] = language or own_language
            # Do not substitute a generic top-stream list when there is no
            # channel context: followed channels are still meaningful candidates.
            page = await runtime_bot._http.request_json(Route(
                "GET", "streams", params=params, token_for=broadcaster_id)) if category_id or not recommended or own_category or own_language else {"data": [], "pagination": {}}
            streams = page
        if broad_for_you and not discovery_page and not page.get("pagination", {}).get("cursor"):
            # Exhausting the current category is not the end of recommendations.
            # Continue with compatible channels outside that narrow candidate pool.
            page = {**page, "pagination": {"cursor": discovery_prefix}}
        followed_ids = {str(stream.get("user_id", "")) for stream in followed_streams}
        if (following or mutual) and not (favorites_only or same_team):
            followed_ids.update(str(stream.get("user_id", "")) for stream in streams.get("data", []))
        favorite_streams = []
        if favorite_ids and not after and not favorites_only and (recommended or sort not in {"viewers_asc", "uptime_asc"}):
            favorite_page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": favorite_ids, "first": 100})
            favorite_streams = favorite_page.get("data", [])
        candidates = [*dev_streams, *favorite_streams, *recent_raid_streams, *(followed_streams if not after else []),
                      *(suggested_streams if recommended and not after else []),
                      *(team_streams if recommended and not after and not (following or mutual) else []), *streams.get("data", [])]
        if favorites_only:
            candidates = streams.get("data", [])
        channels = []
        emitted = set()
        for stream in candidates:
            user_id = str(stream.get("user_id", ""))
            login = str(stream.get("user_login", ""))
            dev_priority = login.casefold() in RAID_BROWSER_DEV_CHANNELS
            if developer_only and not dev_priority:
                continue
            if (user_id == broadcaster_id and not dev_priority) or user_id in blocked_ids or user_id in emitted or not re.fullmatch(r"[A-Za-z0-9_]{1,25}", login):
                continue
            if favorites_only and user_id not in favorite_ids:
                continue
            stream_tags = {str(tag).strip().casefold() for tag in (stream.get("tags") or [])}
            if event == "drops_enabled" and "dropsenabled" not in stream_tags:
                continue
            if (following or mutual) and user_id not in followed_ids:
                continue
            if not_following and user_id in followed_ids:
                continue
            if suggested and user_id not in suggested_ids:
                continue
            if (category_id or same_category) and str(stream.get("game_id", "")) != (category_id or own_category):
                continue
            if same_tags and not own_tags.intersection(stream_tags):
                continue
            if selected_tags and not (selected_tags.issubset(stream_tags) if tag_match == "all"
                                      else selected_tags.intersection(stream_tags)):
                continue
            if language and str(stream.get("language", "")).lower() != language:
                continue
            if same_team and user_id not in team_members:
                continue
            if same_team and team and team not in team_members.get(user_id, []):
                continue
            search_score = raid_channel_search_score(query, login, stream.get("user_name") or "", stream.get("game_name") or "") if query else 0
            if query and not search_score:
                continue
            if mutual:
                follower = await raid_browser_cached_request(runtime_bot, broadcaster_id, "channels/followers", {
                    "broadcaster_id": broadcaster_id, "user_id": str(stream.get("user_id", ""))})
                if not follower.get("data"):
                    continue
            emitted.add(user_id)
            is_followed = user_id in followed_ids
            teams = team_members.get(user_id, [])
            category_match = bool(own_category and str(stream.get("game_id", "")) == own_category)
            language_match = bool(own_language and str(stream.get("language", "")).lower() == own_language)
            shared_tags = own_tags.intersection(stream_tags)
            both_vtubers = "vtuber" in shared_tags
            match_breakdown = raid_relevance_breakdown(same_category=category_match, shared_tags=shared_tags,
                same_team=bool(teams), both_vtubers=both_vtubers, followed=is_followed,
                suggested=user_id in suggested_ids, same_language=language_match,
                recent_raid=recent_raiders.get(user_id, 0)) if recommended else {}
            channels.append({
                "id": str(stream.get("user_id", "")), "login": login,
                "display_name": str(stream.get("user_name") or login),
                "title": str(stream.get("title") or ""),
                "category": str(stream.get("game_name") or ""),
                "search_score": search_score,
                "dev_priority": dev_priority,
                "is_self": user_id == broadcaster_id,
                "events": ["Drops Enabled"] if "dropsenabled" in stream_tags else [],
                "viewers": int(stream.get("viewer_count") or 0),
                "started_at": str(stream.get("started_at") or ""),
                "followed": is_followed,
                "suggested": user_id in suggested_ids,
                "recent_raider": user_id in recent_raiders,
                "teams": teams,
                "relevance": sum(match_breakdown.values()),
                "match_breakdown": match_breakdown,
                "reasons": [label for active, label in ((category_match, "Same category"), (both_vtubers, "Both VTubers"),
                           (bool(teams), "Same stream team"), (bool(shared_tags), "Shared tags"),
                           (is_followed, "Following"), (user_id in suggested_ids, "Suggested streamer"),
                           (user_id in recent_raiders, "Raided you recently"), (language_match, "Same language")) if active],
                "language": str(stream.get("language") or ""),
                "tags": sorted((str(tag) for tag in (stream.get("tags") or [])),
                               key=lambda tag: (tag.casefold() != "vtuber", tag.casefold())),
                "thumbnail_url": str(stream.get("thumbnail_url") or "").replace("{width}", "320").replace("{height}", "180"),
                "thumbnail_url_medium": str(stream.get("thumbnail_url") or "").replace("{width}", "640").replace("{height}", "360"),
                "thumbnail_url_large": str(stream.get("thumbnail_url") or "").replace("{width}", "1280").replace("{height}", "720"),
            })
        relationships = await raid_browser_relationships(runtime_bot, broadcaster_id, channels,
            followed_ids if recommended or following or mutual or not_following else None)
        sizes = await raid_browser_channel_sizes(runtime_bot, broadcaster_id, [channel["id"] for channel in channels]) if sort == "for_you" and channels else {}
        own_viewers = getattr(runtime_bot.services.broadcasters.get_broadcasters()[broadcaster_id], "viewer_count", None)
        for channel in channels:
            channel.update(relationships.get(channel["id"], {}))
            if recommended and channel.get("followed") and channel.get("mutual") is True:
                channel["match_breakdown"]["Mutual following"] = RAID_BROWSER_MUTUAL_BONUS
            if sort == "for_you":
                channel["match_breakdown"]["Similar viewer count"] = raid_size_bonus(own_viewers, channel["viewers"], 180)
                channel["match_breakdown"]["Similar channel size"] = raid_size_bonus(sizes.get(broadcaster_id), sizes.get(channel["id"]), 120)
            if recommended:
                channel["relevance"] = sum(channel["match_breakdown"].values())
        if sort == "for_you":
            channels.sort(key=lambda item: (item["search_score"], item["relevance"], item["viewers"]), reverse=True)
        elif sort == "viewers_asc":
            channels.sort(key=lambda item: (item["viewers"], item["login"]))
        elif sort in {"name_asc", "name_desc"}:
            channels.sort(key=lambda item: (item["display_name"].casefold(), item["login"]), reverse=sort == "name_desc")
        elif sort in {"uptime_asc", "uptime_desc"}:
            def started_at(item):
                try:
                    return datetime.fromisoformat(item["started_at"].replace("Z", "+00:00")).timestamp()
                except (ValueError, TypeError, OverflowError):
                    return 0
            channels.sort(key=lambda item: (started_at(item) == 0,
                started_at(item) if sort == "uptime_desc" else -started_at(item)))
        else:
            channels.sort(key=lambda item: item["viewers"], reverse=True)
        channels.sort(key=lambda item: (item["id"] not in favorite_ids, not item["dev_priority"]))
        # Stream objects don't contain Partner status. Get Users is authoritative.
        profiles = {}
        try:
            ids = [channel["id"] for channel in channels]
            for offset in range(0, len(ids), 100):
                users = await raid_browser_cached_request(runtime_bot, broadcaster_id, "users", {"id": ids[offset:offset + 100]})
                profiles.update({str(user["id"]): user for user in users.get("data", [])})
        except Exception:
            LOGGER.warning("[Dashboard] Partner status unavailable for raid-browser channels.")
        for channel in channels:
            profile = profiles.get(channel["id"])
            channel["verified"] = profile.get("broadcaster_type") == "partner" if profile else None
            channel["profile_image_url"] = str(profile.get("profile_image_url") or "") if profile else ""
            channel["description"] = str(profile.get("description") or "") if profile else ""
        collection_visibility = await raid_browser_collection_visibility(runtime_bot, broadcaster_id, favorite_ids, blocked_ids) if not after else {}
        return JSONResponse({"channels": channels, "cursor": page.get("pagination", {}).get("cursor", ""), "suggested_status": suggested_status,
                             **({"teams": sorted({label for labels in team_members.values() for label in labels}, key=str.casefold)} if same_team else {}),
                             "sort_scope": page.get("sort_scope", ""), "search_limited": page.get("search_limited", False),
                             **collection_visibility,
                             **({"developers_live": bool(dev_streams)} if not after else {}),
                             **({"channel_tags": channel_tags} if channel_tags is not None else {})})
    except HTTPException as error:
        detail = ("Reconnect Twitch to enable following and mutual-following filters."
                  if error.status in (401, 403) and (following or not_following or mutual or recommended) else
                  "Reconnect Twitch to browse live channels." if error.status == 401 else
                  "Twitch could not load live channels. Try again shortly.")
        return JSONResponse({"detail": detail}, status_code=error.status if error.status in (401, 403, 429) else 502)
    except Exception:
        LOGGER.exception("[Dashboard] Could not load raid browser for %s.", broadcaster_id)
        return JSONResponse({"detail": "Live channels could not be loaded. Try again."}, status_code=502)


async def raid_browser_tag_directory(runtime_bot, broadcaster_id, *, tags, tag_match, category_id="", language=""):
    """One public first page per ANY tag, or one page requiring ALL tags."""
    groups = [list(dict.fromkeys(tags))] if tag_match == "all" else [[tag] for tag in dict.fromkeys(tags)]
    semaphore = asyncio.Semaphore(3)

    async def lookup(group):
        async with semaphore:
            return await get_sorted_directory(runtime_bot, sort="viewers_desc", tags=group,
                tag_match="all", category_id=category_id, language=language)

    pages = await asyncio.gather(*(lookup(group) for group in groups))
    ids = list(dict.fromkeys(id_ for page in pages for id_ in page["ids"]))
    streams = []
    for offset in range(0, len(ids), 100):
        page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": ids[offset:offset + 100], "first": 100})
        streams.extend(page.get("data", []))
    return {"data": streams, "has_more": any(page["cursor"] for page in pages)}


async def raid_browser_official_directory(runtime_bot, broadcaster_id, *, after="", category_id="", language=""):
    """Bound discovery to five cached Helix pages (at most 500 candidates)."""
    checked = 0
    cursor = ""
    if after:
        prefix, count, cursor = after.split(":", 2)
        if prefix != "official" or not count.isdigit() or not 1 <= int(count) < 5 or not cursor:
            raise ValueError("Invalid official directory cursor.")
        checked = int(count)
    params = {"first": 100}
    if cursor:
        params["after"] = cursor
    if category_id:
        params["game_id"] = category_id
    if language:
        params["language"] = language
    response = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", params)
    next_cursor = response.get("pagination", {}).get("cursor", "")
    checked += 1
    return {"data": response.get("data", []),
            "pagination": {"cursor": f"official:{checked}:{next_cursor}" if next_cursor and checked < 5 else ""},
            "search_limited": bool(next_cursor and checked >= 5)}


async def raid_browser_collection_visibility(runtime_bot, broadcaster_id, favorite_ids, blocked_ids):
    def has_visible_stream(streams):
        return any(str(stream.get("user_id", "")) not in blocked_ids
                   and (str(stream.get("user_id", "")) != broadcaster_id or str(stream.get("user_login", "")).casefold() in RAID_BROWSER_DEV_CHANNELS)
                   for stream in streams)

    visibility = {}
    try:
        favorites = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": favorite_ids, "first": 100}) if favorite_ids else {"data": []}
        visibility["favorites_live"] = has_visible_stream(favorites.get("data", []))
        visibility["live_favorite_ids"] = [str(stream.get("user_id", "")) for stream in favorites.get("data", []) if has_visible_stream([stream])]
    except Exception:
        LOGGER.warning("[Dashboard] Live favorites availability could not be checked.")
    try:
        teams, _ = await raid_browser_team_streams(runtime_bot, broadcaster_id)
        visibility["team_live"] = has_visible_stream(teams)
    except Exception:
        LOGGER.warning("[Dashboard] Live stream-team availability could not be checked.")
    return visibility


async def raid_browser_dev_streams(runtime_bot, broadcaster_id):
    try:
        users = await raid_browser_cached_request(runtime_bot, broadcaster_id, "users", {"login": sorted(RAID_BROWSER_DEV_CHANNELS)})
        ids = [str(user["id"]) for user in users.get("data", [])
               if str(user.get("login", "")).casefold() in RAID_BROWSER_DEV_CHANNELS and re.fullmatch(r"\d{1,25}", str(user.get("id", "")))]
        if not ids:
            return []
        streams = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {"user_id": ids, "first": 100})
        return streams.get("data", [])
    except Exception:
        LOGGER.warning("[Dashboard] Development raid-browser channels unavailable.")
        return []


async def raid_browser_relationships(runtime_bot, broadcaster_id, channels, followed_ids=None):
    """Decorate visible candidates without making missing follow scopes fatal."""
    if not channels:
        return {}
    try:
        if followed_ids is None:
            followed_ids = {str(item.get("user_id", "")) for item in await raid_browser_followed_streams(runtime_bot, broadcaster_id)}
        relationships = {channel["id"]: {"followed": channel["id"] in followed_ids, "mutual": None} for channel in channels}
        candidates = [channel["id"] for channel in channels if channel["id"] in followed_ids]
        if not candidates:
            return relationships
        validation = await raid_browser_cached_request(runtime_bot, broadcaster_id, "oauth2/validate", {})
        if "moderator:read:followers" not in validation.get("scopes", []):
            return relationships
        semaphore = asyncio.Semaphore(5)

        async def check(user_id):
            async with semaphore:
                try:
                    follower = await raid_browser_cached_request(runtime_bot, broadcaster_id, "channels/followers", {
                        "broadcaster_id": broadcaster_id, "user_id": user_id})
                    relationships[user_id]["mutual"] = bool(follower.get("data"))
                except Exception:
                    # Unknown isn't evidence that a channel follows you.
                    pass

        await asyncio.gather(*(check(user_id) for user_id in candidates))
        return relationships
    except Exception:
        LOGGER.warning("[Dashboard] Follow badges could not be fully verified for %s.", broadcaster_id)
        return {}


async def raid_browser_channel_sizes(runtime_bot, reader, targets):
    """Public follower totals, cached for an hour, with a short discovery budget."""
    cache = getattr(runtime_bot, "_raid_browser_size_cache", None)
    if cache is None:
        cache = runtime_bot._raid_browser_size_cache = {}
    totals = {}
    semaphore = asyncio.Semaphore(6)
    limited = False

    async def load(target):
        nonlocal limited
        key = (reader, target)
        cached = cache.get(key)
        if cached and cached[0] > time.monotonic():
            totals[target] = cached[1]
            return
        async with semaphore:
            if limited:
                return
            try:
                payload = await asyncio.wait_for(runtime_bot._http.request_json(Route("GET", "channels/followers",
                    token_for=reader, params={"broadcaster_id": target, "first": 1})), 1)
                total = payload.get("total")
                total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
            except Exception as error:
                if getattr(error, "status", None) in {401, 403, 429}:
                    limited = True
                total = None
            if len(cache) >= 1000 and key not in cache:
                cache.pop(next(iter(cache)))
            cache[key] = (time.monotonic() + (3600 if total is not None else 60), total)
            totals[target] = total

    tasks = [asyncio.create_task(load(target)) for target in dict.fromkeys([reader, *targets])]
    try:
        _, pending = await asyncio.wait(tasks, timeout=2)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return totals
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def raid_browser_cached_request(runtime_bot, broadcaster_id: str, path: str, params: dict, *, refresh: bool = False):
    """Cache channel metadata and mutual-follow checks briefly, scoped to this runtime/account."""
    cache = getattr(runtime_bot, "_raid_browser_cache", None)
    if cache is None:
        cache = runtime_bot._raid_browser_cache = {}
    key = (broadcaster_id, path, tuple((name, tuple(value) if isinstance(value, list) else value)
                                    for name, value in sorted(params.items())))
    cached = cache.get(key)
    if not refresh and cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    payload = await runtime_bot._http.request_json(Route(
        "GET", path, use_id=path == "oauth2/validate", params=params, token_for=broadcaster_id))
    if len(cache) >= 500:
        cache.pop(next(iter(cache)))
    cache[key] = (time.monotonic(), payload)
    return payload


async def raid_browser_followed_streams(runtime_bot, broadcaster_id: str):
    streams = []
    cursor = ""
    cursors = set()
    while True:
        params = {"user_id": broadcaster_id, "first": 100}
        if cursor:
            params["after"] = cursor
        page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams/followed", params)
        streams.extend(page.get("data", []))
        cursor = page.get("pagination", {}).get("cursor", "")
        if not cursor or cursor in cursors:
            return streams
        cursors.add(cursor)


async def raid_browser_team_streams(runtime_bot, broadcaster_id: str):
    teams = await raid_browser_cached_request(runtime_bot, broadcaster_id, "teams/channel", {"broadcaster_id": broadcaster_id})
    members = {}
    for team in teams.get("data", []):
        team_id = str(team.get("team_id") or team.get("id") or "")
        if not team_id:
            continue
        details = await raid_browser_cached_request(runtime_bot, broadcaster_id, "teams", {"id": team_id})
        for detail in details.get("data", []):
            label = str(detail.get("team_display_name") or detail.get("team_name") or team_id)
            for user in detail.get("users", []):
                user_id = str(user.get("user_id", ""))
                if user_id and user_id != broadcaster_id:
                    labels = members.setdefault(user_id, [])
                    if label not in labels:
                        labels.append(label)
    streams = []
    ids = sorted(members)
    for offset in range(0, len(ids), 100):
        page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "streams", {
            "user_id": ids[offset:offset + 100], "first": 100})
        streams.extend(page.get("data", []))
    return streams, members


@router.get("/channel/api/raid-browser/lists", response_class=JSONResponse)
async def channel_raid_browser_lists(request: Request, ids: str = ""):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster_id = str(broadcaster_id)
    if broadcaster_id not in runtime_bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    user_ids = list(dict.fromkeys(item.strip() for item in ids.split(",") if item.strip()))
    if len(ids) > 4000 or len(user_ids) > 200 or any(not re.fullmatch(r"\d{1,25}", item) for item in user_ids):
        return JSONResponse({"detail": "Invalid saved channel list."}, status_code=400)
    try:
        users = []
        for offset in range(0, len(user_ids), 100):
            page = await raid_browser_cached_request(runtime_bot, broadcaster_id, "users", {"id": user_ids[offset:offset + 100]})
            users.extend({"id": str(user["id"]), "login": str(user["login"]),
                          "display_name": str(user.get("display_name") or user["login"])} for user in page.get("data", []))
        return JSONResponse({"channels": users})
    except Exception:
        LOGGER.warning("[Dashboard] Saved raid-browser channel names could not be loaded.")
        return JSONResponse({"detail": "Saved channel names could not be loaded. Try again."}, status_code=502)


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

    result = {"field": field, "value": update.value, "announcement_sent": announcement_sent}
    if field == "game":
        result["box_art_url"] = await get_category_artwork(runtime_bot, broadcaster_id, update.game_id)
    return JSONResponse(result)


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
async def search_twitch_games(request: Request, query: str = "", current_first: bool = False):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    try:
        normalized_query = query.strip()
        if not normalized_query:
            games = (await get_top_games_for_search(runtime_bot, broadcaster_id))[:50]
            payload = await category_picker_results(runtime_bot, broadcaster_id, games)
            if current_first:
                payload = await prioritize_raid_current_category(runtime_bot, broadcaster_id, payload)
            return JSONResponse(payload)

        iterator = runtime_bot.search_categories(
            normalized_query, token_for=str(broadcaster_id), first=50, max_results=50
        )
        games = [serialize_category(game) async for game in iterator]
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
        payload = await category_picker_results(runtime_bot, broadcaster_id, games)
        if current_first:
            payload = await prioritize_raid_current_category(runtime_bot, broadcaster_id, payload)
        return JSONResponse(payload)
    except Exception:
        LOGGER.exception("[Dashboard] Failed to search Twitch games for broadcaster %s.", broadcaster_id)
        return JSONResponse({"detail": "Twitch game search is temporarily unavailable."}, status_code=502)


async def prioritize_raid_current_category(runtime_bot, broadcaster_id, payload):
    try:
        # The picker must reflect category changes immediately, including
        # changes made outside this dashboard, rather than reuse the 60s cache.
        info = await raid_browser_cached_request(runtime_bot, str(broadcaster_id), "channels", {"broadcaster_id": str(broadcaster_id)}, refresh=True)
        own = next(iter(info.get("data", [])), {})
        game_id, name = str(own.get("game_id") or ""), str(own.get("game_name") or "")
        if not game_id or game_id == "0" or not name:
            return payload
        candidates = [*payload.get("games", []), *payload.get("more_games", [])]
        current = next((game for game in candidates if str(game["id"]) == game_id), None)
        if current is None:
            current = {"id": game_id, "name": name, "box_art_url": await get_category_artwork(runtime_bot, broadcaster_id, game_id)}
        return {**payload, "games": [current, *[game for game in payload.get("games", []) if str(game["id"]) != game_id]],
                "more_games": [game for game in payload.get("more_games", []) if str(game["id"]) != game_id]}
    except Exception:
        LOGGER.warning("[Dashboard] Current raid-browser category unavailable.")
        return payload


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


def preview_chat_runtime(request, target_id):
    reader = request.session.get(CHANNEL_USER_ID_KEY)
    if not reader:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    if not re.fullmatch(r"\d{1,25}", target_id):
        return JSONResponse({"detail": "Invalid channel."}, status_code=400)
    bot = get_bot()
    if bot is None or bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    if str(reader) not in bot.services.broadcasters.get_broadcasters():
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    return bot, str(reader)


@router.get("/channel/api/raid-browser/chat/stream")
async def channel_raid_chat_stream(request: Request, target_id: str = ""):
    runtime = preview_chat_runtime(request, target_id)
    if isinstance(runtime, JSONResponse):
        return runtime
    bot, reader = runtime
    return StreamingResponse(preview_chat_events(request, bot, reader, target_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/channel/api/raid-browser/chat/send")
async def channel_raid_chat_send(request: Request, target_id: str = Form(""), message: str = Form(""),
                                 csrf_token: str = Form("")):
    runtime = preview_chat_runtime(request, target_id)
    if isinstance(runtime, JSONResponse):
        return runtime
    validate_csrf_token(request, csrf_token)
    bot, reader = runtime
    message = message.strip()
    if not message or len(message) > CHAT_MESSAGE_MAX_LENGTH or message.startswith(("/", ".")):
        return JSONResponse({"detail": "Enter a message up to 500 characters. Commands aren't supported here."}, status_code=400)
    try:
        result = await bot.create_partialuser(target_id).send_message(sender=reader, token_for=reader, message=message)
        if not result.sent:
            return JSONResponse({"detail": "Twitch didn't send this message. Check the channel's chat restrictions."}, status_code=409)
        return JSONResponse({"sent": True})
    except HTTPException as error:
        return JSONResponse({"detail": "Twitch couldn't send this message. Check your connection and chat permissions."},
                            status_code=429 if error.status == 429 else 502)


@router.get("/channel/api/raid-browser/chat/emotes")
async def channel_raid_chat_emotes(request: Request, target_id: str = ""):
    runtime = preview_chat_runtime(request, target_id)
    if isinstance(runtime, JSONResponse):
        return runtime
    bot, reader = runtime
    catalog, channel_emotes = await asyncio.gather(bot.services.live_chat.get_emote_catalog(reader), preview_emotes(bot, target_id))
    # The user's available Twitch emotes apply everywhere. 7TV names must come
    # from the channel being previewed, not the user's own channel catalog.
    emotes = [emote for emote in catalog.get("emotes", []) if emote.get("provider") != "7tv"]
    emotes.extend({"name": name, "url": segment.url, "provider": "7tv", "group": "7TV", "group_key": "7tv"}
                  for name, segment in channel_emotes.items())
    return JSONResponse({"emotes": emotes, "personal_group_key": catalog.get("personal_group_key", "")},
                        headers={"Cache-Control": "no-store"})


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
    message_ids = {}
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
                    if isinstance(getattr(result, "id", None), str) and result.id:
                        message_ids["twitch"] = f"twitch:{result.id}"
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
            youtube_result = await services.live_chat.send_youtube_message(str(broadcaster_id), message)
            sent.append("youtube")
            if isinstance(youtube_result, dict) and isinstance(youtube_result.get("id"), str) and youtube_result["id"]:
                message_ids["youtube"] = f"youtube:{youtube_result['id']}"
        except ValueError as error:
            youtube_error = str(error)

            if target == "youtube" or not sent or "No active YouTube live chat" not in youtube_error:
                errors["youtube"] = (
                    "YouTube is offline. Start a YouTube livestream with live chat enabled before sending a message."
                    if "No active YouTube live chat" in youtube_error
                    else youtube_error
                )
        except httpx.HTTPStatusError as error:
            reason, _ = services.live_chat._youtube_error_details(error.response)
            errors["youtube"] = {
                "quotaExceeded": "YouTube API quota is exhausted; try after the daily reset.",
                "dailyLimitExceeded": "YouTube API quota is exhausted; try after the daily reset.",
                "rateLimitExceeded": "YouTube is rate limiting messages; wait before sending again.",
                "liveChatEnded": "The YouTube livestream has ended.",
                "liveChatDisabled": "Live chat is disabled for this YouTube stream.",
                "forbidden": "YouTube denied permission to send this message.",
            }.get(reason, "YouTube rejected the message; try again later.")
            if error.response.status_code == 401:
                errors["youtube"] = "Reconnect YouTube to restore authorization."
        except httpx.RequestError:
            errors["youtube"] = "YouTube connection failed; delivery could not be confirmed."
        except Exception:
            LOGGER.exception("[Dashboard] Failed to send YouTube message for broadcaster %s.", broadcaster_id)
            errors["youtube"] = "YouTube could not send the message; try again later."

    if not sent:
        detail = " ".join(errors.values()) or "The message could not be sent."
        return JSONResponse({"detail": detail, "sent": sent, "errors": errors}, status_code=400)

    status_code = 207 if errors else 200
    payload = {"sent": sent, "errors": errors}
    if message_ids:
        payload["message_ids"] = message_ids
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
    clear_stale_chat_on_refresh(services.live_chat, broadcaster)

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
            "twitch_connected": bool((getattr(runtime_bot, "tokens", {}).get(str(broadcaster_id)) or {}).get("token")),
            "ad_status": ad_status,
            "dashboard_header_stats": dashboard_header_stats,
            "twitch_channel_metadata": twitch_channel_metadata,
            "queue_result": request.query_params.get("queue_result"),
            "queue_message": request.query_params.get("queue_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/boss-hunt", response_class=HTMLResponse)
async def channel_boss_hunt(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return HTMLResponse("Bot runtime unavailable.", status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    enabled = services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES)
    return templates.TemplateResponse(
        request=request,
        name="channel/boss_hunt.html",
        context={
            "active_page": "boss-hunt",
            "broadcaster": broadcaster,
            "boss_hunt_enabled": enabled,
            "raid_metrics": await services.raid_bosses.get_dashboard_metrics(broadcaster_id) if enabled else None,
            "raid_contributor_data": await get_raid_contributor_data(services, broadcaster_id) if enabled else {"active": False, "contributors": []},
            "active_encounter": await services.raid_bosses.get_active_event(broadcaster_id) if enabled else None,
            "spawn_scheduled": str(broadcaster_id) in services.raid_bosses.spawn_tasks if enabled else False,
            "action_result": request.query_params.get("result"),
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/channel/boss-hunt/action", response_class=RedirectResponse)
async def channel_boss_hunt_action(
    request: Request,
    action: str = Form(...),
    csrf_token: str = Form(...),
    tier: str = Form(""),
    boss_type: str = Form(""),
):
    validate_csrf_token(request, csrf_token)
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return HTMLResponse("Bot runtime unavailable.", status_code=503)

    services = runtime_bot.services
    if services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)
    profile = get_active_profile(str(broadcaster_id))
    if profile is None or not services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES):
        return RedirectResponse(url="/channel/boss-hunt?result=disabled", status_code=303)

    if action == "schedule":
        if tier not in {"tutorial", "mini", "main"} or boss_type not in {"melee", "ranged", "magic", "random"}:
            result = "invalid"
        elif tier == "tutorial" and await services.raid_bosses.has_completed_tutorial(broadcaster_id):
            result = "tutorial-complete"
        else:
            import random
            selected_type = random.choice(("melee", "ranged", "magic")) if boss_type == "random" else boss_type
            scheduled = await services.raid_bosses.schedule_spawn(broadcaster_id, profile.raid_bosses, tier, selected_type)
            result = "scheduled" if scheduled else "already-active"
    elif action == "end":
        event = await services.raid_bosses.get_active_event(broadcaster_id)
        if event is None:
            result = "no-encounter"
        else:
            from bot.services.engagement.raid_boss import raid_conclusion_message
            reward = await services.raid_bosses.resolve(broadcaster_id, defeated=False)
            damage_dealt = event.max_hp - event.current_hp
            await services.chat_identity.send_message(
                runtime_bot.create_partialuser(str(broadcaster_id)),
                raid_conclusion_message(event, damage_dealt, reward),
            )
            result = "ended"
    else:
        result = "invalid"

    return RedirectResponse(url=f"/channel/boss-hunt?result={result}", status_code=303)


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
        if setting_name == "dashboard.follow_raid":
            if action != "save" or value not in {"0", "1"}:
                raise ValueError("Choose On or Off.")
            await services.broadcaster_settings.set_follow_raid(broadcaster_id, value == "1")
            message = "Follow raid preference saved."
        elif setting_name == "social.discord_url":
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


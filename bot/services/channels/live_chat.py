import asyncio
import json
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
import grpc

from bot.profiles import get_active_profile
from bot.services.channels import youtube_live_chat_pb2
from config.settings import settings
from web.shared.youtube_oauth import YOUTUBE_API_URL, YOUTUBE_TOKEN_URL, YouTubeChannel, YouTubeTokenResponse

LOGGER = logging.getLogger("RatBoomBot")
CHAT_VIEWS = {"chat", "commands", "both"}
TWITCH_EMOTE_CDN_URL = "https://static-cdn.jtvnw.net/emoticons/v2/{id}/{format}/dark/2.0"
TWITCH_API_URL = "https://api.twitch.tv/helix"
SEVENTV_API_URL = "https://7tv.io/v3"
SEVENTV_EVENT_API_URL = "https://events.7tv.io/v3"
SEVENTV_EMOTE_CDN_URL = "https://cdn.7tv.app/emote/{id}/2x.webp"
SEVENTV_REFRESH_SECONDS = 300
SEVENTV_RECONNECT_SECONDS = 10
SEVENTV_EMOTE_ID = re.compile(r"^[A-Za-z0-9]+$")
TWITCH_EMOTE_CACHE_SECONDS = 300
TWITCH_BADGE_CACHE_SECONDS = 3600


@dataclass(frozen=True)
class ChatSegment:
    type: str
    text: str
    url: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class ChatBadge:
    name: str
    title: str
    url: str | None = None
    url_2x: str | None = None
    url_4x: str | None = None


@dataclass(frozen=True)
class UnifiedChatMessage:
    id: str
    platform: str
    kind: str
    username: str
    display_name: str
    message: str
    timestamp: str
    color: str | None = None
    badges: tuple[ChatBadge | str, ...] = ()
    segments: tuple[ChatSegment, ...] = ()
    accent: str | None = None
    deleted: bool = False
    mentioned: bool = False
    is_bot: bool = False

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["badges"] = [asdict(badge) if isinstance(badge, ChatBadge) else badge for badge in self.badges]
        payload["segments"] = [asdict(segment) for segment in self.segments]
        return payload


@dataclass
class YouTubeConnection:
    broadcaster_id: str
    channel_id: str
    channel_title: str
    access_token: str
    refresh_token: str
    expires_at: str


@dataclass(frozen=True)
class YouTubeChatState:
    configured: bool
    connected: bool
    channel_id: str | None
    channel_title: str | None
    status: str
    detail: str


def normalize_chat_view(view: str | None) -> str:
    return view if view in CHAT_VIEWS else "both"


def message_matches_view(message: UnifiedChatMessage, view: str) -> bool:
    view = normalize_chat_view(view)
    return view == "both" or (view == "chat" and message.kind == "chat") or (view == "commands" and message.kind == "command")


class LiveChatService:

    def __init__(self, db, *, bot=None):
        self.db = db
        self.bot = bot
        self.connections: dict[str, YouTubeConnection] = {}
        self.youtube_statuses: dict[str, tuple[str, str]] = {}
        self.active_youtube_chat_ids: dict[str, str] = {}
        self.widget_tokens: dict[str, str] = {}
        self.token_broadcasters: dict[str, str] = {}
        self.messages: dict[str, deque[UnifiedChatMessage]] = defaultdict(lambda: deque(maxlen=250))
        self.pinned_messages: dict[str, dict[str, object]] = {}
        self.mod_actions: dict[str, deque[dict[str, object]]] = defaultdict(lambda: deque(maxlen=100))
        self.automod_messages: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
        self.message_ids: dict[str, set[str]] = defaultdict(set)
        self.message_id_order: dict[str, deque[str]] = defaultdict(deque)
        self.command_response_ids: dict[str, set[str]] = defaultdict(set)
        self.command_response_id_order: dict[str, deque[str]] = defaultdict(deque)
        self.subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self.tasks: dict[str, asyncio.Task] = {}
        self.seventv_tasks: dict[str, asyncio.Task] = {}
        self.seventv_global_task: asyncio.Task | None = None
        self.seventv_global_emotes: dict[str, ChatSegment] = {}
        self.seventv_channel_emotes: dict[str, dict[str, ChatSegment]] = {}
        self.seventv_set_ids: dict[str, str] = {}
        self.twitch_emote_cache: dict[str, tuple[float, list[dict[str, str]], bool]] = {}
        self.twitch_emote_owner_images: dict[str, str] = {}
        self.twitch_badge_cache: dict[str, tuple[float, dict[tuple[str, str], ChatBadge]]] = {}
        self.twitch_badge_tasks: dict[str, asyncio.Task] = {}
        self.client: httpx.AsyncClient | None = None
        self.started = False

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            connection_rows = await connection.fetchall(
                "SELECT broadcaster_id, youtube_channel_id, youtube_channel_title, access_token, refresh_token, expires_at FROM youtube_chat_connections"
            )
            widget_rows = await connection.fetchall("SELECT broadcaster_id, token FROM chat_widget_tokens")
            pinned_rows = await connection.fetchall("SELECT broadcaster_id, message_json FROM pinned_chat_messages")

        self.connections = {
            str(row["broadcaster_id"]): YouTubeConnection(
                broadcaster_id=str(row["broadcaster_id"]),
                channel_id=str(row["youtube_channel_id"]),
                channel_title=str(row["youtube_channel_title"]),
                access_token=str(row["access_token"]),
                refresh_token=str(row["refresh_token"]),
                expires_at=str(row["expires_at"])
            )
            for row in connection_rows
        }
        self.widget_tokens = {str(row["broadcaster_id"]): str(row["token"]) for row in widget_rows}
        self.token_broadcasters = {token: broadcaster_id for broadcaster_id, token in self.widget_tokens.items()}
        self.pinned_messages = {
            str(row["broadcaster_id"]): json.loads(str(row["message_json"]))
            for row in pinned_rows
        }
        LOGGER.info("[Live Chat] Loaded %d YouTube connection(s) and %d OBS widget token(s).", len(self.connections), len(self.widget_tokens))

    async def start(self) -> None:
        self.started = True
        self.client = httpx.AsyncClient(timeout=20)
        self.seventv_global_task = asyncio.create_task(self._refresh_seventv_global_loop(), name="seventv-global-emotes")

        services = getattr(self.bot, "services", None)
        broadcasters = getattr(services, "broadcasters", None)

        if broadcasters is not None:
            for broadcaster_id in broadcasters.get_broadcasters():
                broadcaster_id = str(broadcaster_id)
                self._ensure_seventv_watcher(broadcaster_id)
                self._ensure_twitch_badge_loader(broadcaster_id)

        if not settings.YOUTUBE_CONFIGURED:
            LOGGER.warning("[Live Chat] YouTube OAuth is not configured; Twitch feeds and OBS widgets remain available.")
            return

        for broadcaster_id in self.connections:
            self._start_watcher(broadcaster_id)

    async def stop(self) -> None:
        self.started = False
        tasks = tuple(self.tasks.values()) + tuple(self.seventv_tasks.values()) + tuple(self.twitch_badge_tasks.values())

        if self.seventv_global_task is not None:
            tasks += (self.seventv_global_task,)

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.tasks.clear()
        self.seventv_tasks.clear()
        self.twitch_badge_tasks.clear()
        self.seventv_global_task = None
        self.active_youtube_chat_ids.clear()

        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def publish_twitch(self, payload) -> UnifiedChatMessage:
        broadcaster_id = str(payload.broadcaster.id)
        self._ensure_seventv_watcher(broadcaster_id)
        chatter = payload.chatter
        message_text = str(payload.text)
        username = str(getattr(chatter, "name", None) or "unknown")
        display_name = str(getattr(chatter, "display_name", None) or username)
        self._ensure_twitch_badge_loader(broadcaster_id)
        badges = self._twitch_message_badges(broadcaster_id, payload)

        timestamp = getattr(payload, "timestamp", None)
        timestamp_value = timestamp.isoformat() if hasattr(timestamp, "isoformat") else datetime.now(UTC).isoformat()
        message_id = str(getattr(payload, "id", None) or secrets.token_urlsafe(12))
        message = UnifiedChatMessage(
            id=f"twitch:{message_id}",
            platform="twitch",
            kind="command" if self._consume_command_response(broadcaster_id, message_id) else self._classify(broadcaster_id, message_text),
            username=username,
            display_name=display_name,
            message=message_text,
            timestamp=timestamp_value,
            color=str(getattr(payload, "color", None) or "") or None,
            badges=badges,
            segments=self._twitch_message_segments(broadcaster_id, payload, message_text),
            accent=self._twitch_message_accent(payload),
            mentioned=any(
                getattr(fragment, "type", None) == "mention"
                and str(getattr(getattr(fragment, "mention", None), "id", "")) == broadcaster_id
                for fragment in (getattr(payload, "fragments", None) or ())
            ),
            is_bot=self._has_chat_bot_badge(payload, badges) or self._is_chat_bot(getattr(chatter, "id", None))
        )
        self.publish(broadcaster_id, message)
        return message

    @staticmethod
    def _has_chat_bot_badge(payload, badges: tuple[ChatBadge, ...]) -> bool:
        badge_set_ids = {
            str(getattr(badge, "set_id", "") or "").casefold().replace("_", "-")
            for badge in (getattr(payload, "badges", ()) or ())
        }
        badge_set_ids.update(badge.name.casefold().replace("_", "-") for badge in badges)
        if badge_set_ids.intersection({"bot", "chatbot", "chat-bot"}):
            return True

        return any(
            badge.title.casefold().replace("-", " ") in {"bot", "chatbot", "chat bot", "chat bot badge"}
            for badge in badges
        )

    def _is_chat_bot(self, user_id) -> bool:
        if user_id is None or self.bot is None:
            return False
        user_id = str(user_id)
        if user_id == str(getattr(self.bot, "bot_id", "")):
            return True
        chat_identity = getattr(getattr(self.bot, "services", None), "chat_identity", None)
        is_custom_bot = getattr(chat_identity, "is_custom_bot", None)
        return bool(callable(is_custom_bot) and is_custom_bot(user_id))

    @staticmethod
    def _badge_label(set_id: str) -> str:
        labels = {
            "broadcaster": "Broadcaster",
            "moderator": "Mod",
            "vip": "VIP",
            "subscriber": "Subscriber",
            "founder": "Founder",
            "bits": "Bits",
            "staff": "Staff",
            "admin": "Admin",
            "global_mod": "Global Mod",
            "partner": "Partner",
            "turbo": "Turbo",
            "bot": "Chat Bot",
            "chatbot": "Chat Bot",
            "chat-bot": "Chat Bot",
            "artist-badge": "Artist"
        }
        return labels.get(set_id, set_id.replace("-", " ").replace("_", " ").title())

    def _twitch_message_badges(self, broadcaster_id: str, payload) -> tuple[ChatBadge, ...]:
        catalog = self.twitch_badge_cache.get(broadcaster_id, (0.0, {}))[1]
        badges = []

        for badge in getattr(payload, "badges", ()) or ():
            set_id = str(getattr(badge, "set_id", "") or "")
            version = str(getattr(badge, "id", "") or "")

            if not set_id:
                continue

            badges.append(catalog.get(
                (set_id, version),
                ChatBadge(set_id, self._badge_label(set_id))
            ))

        if badges:
            return tuple(badges)

        chatter = payload.chatter

        for role, set_id in (
            ("broadcaster", "broadcaster"),
            ("moderator", "moderator"),
            ("vip", "vip"),
            ("subscriber", "subscriber")
        ):
            if self._chatter_has_role(chatter, role):
                badges.append(ChatBadge(set_id, self._badge_label(set_id)))

        return tuple(badges)

    @staticmethod
    def _chatter_has_role(chatter, role: str) -> bool:
        return bool(getattr(chatter, f"is_{role}", False) or getattr(chatter, role, False))

    @staticmethod
    def _twitch_message_accent(payload) -> str | None:
        chatter = payload.chatter
        message_type = str(getattr(payload, "type", "") or "")
        badge_names = {
            str(getattr(badge, "set_id", "") or "")
            for badge in (getattr(payload, "badges", ()) or ())
        }

        if message_type == "user_intro" or bool(getattr(payload, "first_message", False)):
            return "first-time"
        if LiveChatService._chatter_has_role(chatter, "broadcaster"):
            return "broadcaster"
        if badge_names.intersection({"staff", "admin", "global_mod"}):
            return "staff"
        if LiveChatService._chatter_has_role(chatter, "moderator"):
            return "moderator"
        if LiveChatService._chatter_has_role(chatter, "vip"):
            return "vip"
        if "artist-badge" in badge_names:
            return "artist"
        if LiveChatService._chatter_has_role(chatter, "subscriber") or "founder" in badge_names:
            return "subscriber"
        return None

    def _twitch_message_segments(self, broadcaster_id: str, payload, message_text: str) -> tuple[ChatSegment, ...]:
        fragments = getattr(payload, "fragments", None)

        if not fragments:
            return self._apply_seventv_emotes(broadcaster_id, (ChatSegment("text", message_text),))

        segments: list[ChatSegment] = []

        for fragment in fragments:
            text = str(getattr(fragment, "text", ""))
            emote = getattr(fragment, "emote", None)

            if getattr(fragment, "type", None) == "emote" and emote is not None:
                emote_id = str(getattr(emote, "id", ""))
                formats = tuple(getattr(emote, "format", ()) or ())

                if emote_id:
                    image_format = "animated" if "animated" in formats else "static"
                    segments.append(ChatSegment(
                        "emote",
                        text,
                        TWITCH_EMOTE_CDN_URL.format(id=quote(emote_id, safe=""), format=image_format),
                        "twitch"
                    ))
                    continue

            if text:
                segments.append(ChatSegment("text", text))

        return self._apply_seventv_emotes(broadcaster_id, tuple(segments))

    def _apply_seventv_emotes(self, broadcaster_id: str, segments: tuple[ChatSegment, ...]) -> tuple[ChatSegment, ...]:
        emotes = dict(self.seventv_global_emotes)
        emotes.update(self.seventv_channel_emotes.get(str(broadcaster_id), {}))

        if not emotes:
            return segments

        rendered: list[ChatSegment] = []

        for segment in segments:
            if segment.type != "text":
                rendered.append(segment)
                continue

            for token in re.split(r"(\s+)", segment.text):
                if not token:
                    continue

                rendered.append(emotes.get(token, ChatSegment("text", token)))

        return tuple(rendered)

    def _ensure_seventv_watcher(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)

        if not self.started or self.client is None or broadcaster_id in self.seventv_tasks:
            return

        task = asyncio.create_task(self._watch_seventv_channel(broadcaster_id), name=f"seventv-emotes-{broadcaster_id}")
        self.seventv_tasks[broadcaster_id] = task

    async def _refresh_seventv_global_loop(self) -> None:
        while self.started:
            try:
                await self._refresh_seventv_global()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.warning("[Live Chat] Unable to refresh 7TV global emotes.", exc_info=True)

            await asyncio.sleep(SEVENTV_REFRESH_SECONDS)

    async def _refresh_seventv_global(self) -> None:
        if self.client is None:
            return

        response = await self.client.get(f"{SEVENTV_API_URL}/emote-sets/global")
        response.raise_for_status()
        self.seventv_global_emotes = self._parse_seventv_emotes(response.json())

    async def _refresh_seventv_channel(self, broadcaster_id: str) -> str | None:
        if self.client is None:
            return None

        response = await self.client.get(f"{SEVENTV_API_URL}/users/twitch/{quote(str(broadcaster_id), safe='')}")

        if response.status_code == 404:
            self.seventv_channel_emotes[str(broadcaster_id)] = {}
            self.seventv_set_ids.pop(str(broadcaster_id), None)
            return None

        response.raise_for_status()
        emote_set = response.json().get("emote_set") or {}
        set_id = str(emote_set.get("id") or "")
        self.seventv_channel_emotes[str(broadcaster_id)] = self._parse_seventv_emotes(emote_set)

        if set_id:
            self.seventv_set_ids[str(broadcaster_id)] = set_id
            return set_id

        self.seventv_set_ids.pop(str(broadcaster_id), None)
        return None

    async def _refresh_seventv_set(self, broadcaster_id: str, set_id: str) -> None:
        if self.client is None:
            return

        response = await self.client.get(f"{SEVENTV_API_URL}/emote-sets/{quote(set_id, safe='')}")
        response.raise_for_status()
        self.seventv_channel_emotes[str(broadcaster_id)] = self._parse_seventv_emotes(response.json())

    @staticmethod
    def _parse_seventv_emotes(emote_set: dict) -> dict[str, ChatSegment]:
        result: dict[str, ChatSegment] = {}

        for entry in emote_set.get("emotes", ()):
            data = entry.get("data") or entry.get("emote") or entry
            name = str(entry.get("name") or entry.get("alias") or data.get("name") or "")
            emote_id = str(data.get("id") or entry.get("id") or "")

            if not name or not SEVENTV_EMOTE_ID.fullmatch(emote_id):
                continue

            result[name] = ChatSegment(
                "emote",
                name,
                SEVENTV_EMOTE_CDN_URL.format(id=emote_id),
                "7tv"
            )

        return result

    @staticmethod
    def _parse_twitch_emotes(payload: dict, scope: str) -> list[dict[str, str]]:
        emotes = []

        for entry in payload.get("data", ()):
            name = str(entry.get("name") or "")
            emote_id = str(entry.get("id") or "")

            if not name or not emote_id:
                continue

            formats = entry.get("format") or ()
            image_format = "animated" if "animated" in formats else "static"
            emotes.append({
                "id": emote_id,
                "name": name,
                "url": TWITCH_EMOTE_CDN_URL.format(id=quote(emote_id, safe=""), format=image_format),
                "provider": "twitch",
                "scope": scope,
                "owner_id": str(entry.get("owner_id") or "")
            })

        return emotes

    async def _fetch_twitch_emote_page(self, access_token: str, path: str, params: dict[str, object]) -> dict:
        if self.client is None:
            raise RuntimeError("Live chat HTTP client is unavailable.")

        response = await self.client.get(
            f"{TWITCH_API_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}", "Client-Id": settings.CLIENT_ID}
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def _parse_twitch_badges(cls, payload: dict) -> dict[tuple[str, str], ChatBadge]:
        badges = {}

        for badge_set in payload.get("data", ()):
            set_id = str(badge_set.get("set_id") or "")

            if not set_id:
                continue

            for version in badge_set.get("versions", ()):
                version_id = str(version.get("id") or "")

                if not version_id:
                    continue

                badges[(set_id, version_id)] = ChatBadge(
                    name=set_id,
                    title=str(version.get("title") or cls._badge_label(set_id)),
                    url=str(version.get("image_url_1x") or "") or None,
                    url_2x=str(version.get("image_url_2x") or "") or None,
                    url_4x=str(version.get("image_url_4x") or "") or None
                )

        return badges

    async def _load_twitch_badges(self, broadcaster_id: str) -> None:
        try:
            token = (getattr(self.bot, "tokens", {}).get(broadcaster_id) or {}).get("token")

            if not token or self.client is None:
                return

            global_payload, channel_payload = await asyncio.gather(
                self._fetch_twitch_emote_page(str(token), "/chat/badges/global", {}),
                self._fetch_twitch_emote_page(str(token), "/chat/badges", {"broadcaster_id": broadcaster_id})
            )
            catalog = self._parse_twitch_badges(global_payload)
            catalog.update(self._parse_twitch_badges(channel_payload))
            self.twitch_badge_cache[broadcaster_id] = (time.monotonic(), catalog)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.warning("[Live Chat] Unable to load Twitch badges for %s.", broadcaster_id, exc_info=True)
        finally:
            current = self.twitch_badge_tasks.get(broadcaster_id)

            if current is asyncio.current_task():
                self.twitch_badge_tasks.pop(broadcaster_id, None)

    def _ensure_twitch_badge_loader(self, broadcaster_id: str) -> None:
        if not self.started or self.client is None:
            return
        if not (getattr(self.bot, "tokens", {}).get(broadcaster_id) or {}).get("token"):
            return

        cached = self.twitch_badge_cache.get(broadcaster_id)

        if cached is not None and time.monotonic() - cached[0] < TWITCH_BADGE_CACHE_SECONDS:
            return
        if broadcaster_id in self.twitch_badge_tasks:
            return

        self.twitch_badge_tasks[broadcaster_id] = asyncio.create_task(
            self._load_twitch_badges(broadcaster_id),
            name=f"twitch-badges-{broadcaster_id}"
        )

    async def _fetch_twitch_user_emotes(self, broadcaster_id: str, access_token: str) -> list[dict[str, str]]:
        emotes = []
        params = {"user_id": broadcaster_id, "broadcaster_id": broadcaster_id}

        while True:
            payload = await self._fetch_twitch_emote_page(access_token, "/chat/emotes/user", dict(params))
            emotes.extend(self._parse_twitch_emotes(payload, "available"))
            cursor = str((payload.get("pagination") or {}).get("cursor") or "")

            if not cursor:
                break

            params["after"] = cursor

        owner_names = await self._fetch_twitch_owner_names(access_token, {
            emote["owner_id"] for emote in emotes if emote["owner_id"] not in {"", "0"}
        })

        for emote in emotes:
            owner_id = emote["owner_id"]
            if owner_id in {"", "0"}:
                emote["group"] = "Twitch Global"
                emote["group_key"] = "twitch:global"
            else:
                emote["group"] = owner_names.get(owner_id, "Unavailable Twitch channel")
                emote["group_key"] = f"twitch:{owner_id}"
                emote["group_image"] = self.twitch_emote_owner_images.get(owner_id, "")

        return emotes

    async def _fetch_twitch_owner_names(self, access_token: str, owner_ids: set[str]) -> dict[str, str]:
        names = {}
        ordered_ids = sorted(owner_id for owner_id in owner_ids if owner_id.isdigit())

        for offset in range(0, len(ordered_ids), 100):
            users = await self._fetch_twitch_owner_batch(access_token, ordered_ids[offset:offset + 100])

            names.update({
                str(user.get("id")): str(user.get("display_name") or user.get("login") or user.get("id"))
                for user in users if user.get("id")
            })
            self.twitch_emote_owner_images.update({
                str(user["id"]): str(user.get("profile_image_url") or "")
                for user in users if user.get("id")
            })

        return names

    async def _fetch_twitch_owner_batch(self, access_token: str, owner_ids: list[str]) -> list[dict]:
        if not owner_ids:
            return []

        try:
            payload = await self._fetch_twitch_emote_page(access_token, "/users", {"id": owner_ids})
            return list(payload.get("data", ()))
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 400 and len(owner_ids) > 1:
                midpoint = len(owner_ids) // 2
                left, right = await asyncio.gather(
                    self._fetch_twitch_owner_batch(access_token, owner_ids[:midpoint]),
                    self._fetch_twitch_owner_batch(access_token, owner_ids[midpoint:])
                )
                return left + right

            if error.response.status_code == 400:
                LOGGER.info("[Live Chat] Twitch emote owner %s is no longer resolvable.", owner_ids[0])
                return []

            LOGGER.warning("[Live Chat] Unable to resolve Twitch emote owner names.", exc_info=True)
            return []
        except Exception:
            LOGGER.warning("[Live Chat] Unable to resolve Twitch emote owner names.", exc_info=True)
            return []

    async def _fetch_basic_twitch_emotes(self, broadcaster_id: str, access_token: str) -> list[dict[str, str]]:
        global_payload, channel_payload = await asyncio.gather(
            self._fetch_twitch_emote_page(access_token, "/chat/emotes/global", {}),
            self._fetch_twitch_emote_page(access_token, "/chat/emotes", {"broadcaster_id": broadcaster_id})
        )
        channel_emotes = self._parse_twitch_emotes(channel_payload, "channel")
        global_emotes = self._parse_twitch_emotes(global_payload, "global")
        owner_names = await self._fetch_twitch_owner_names(access_token, {broadcaster_id})
        channel_name = owner_names.get(broadcaster_id, "This channel")

        for emote in channel_emotes:
            emote["owner_id"] = broadcaster_id
            emote["group"] = channel_name
            emote["group_key"] = f"twitch:{broadcaster_id}"
            emote["group_image"] = self.twitch_emote_owner_images.get(broadcaster_id, "")

        for emote in global_emotes:
            emote["group"] = "Twitch Global"
            emote["group_key"] = "twitch:global"

        return channel_emotes + global_emotes

    async def get_emote_catalog(self, broadcaster_id: str) -> dict[str, object]:
        broadcaster_id = str(broadcaster_id)
        now = time.monotonic()
        cached = self.twitch_emote_cache.get(broadcaster_id)

        if cached is None or now - cached[0] >= TWITCH_EMOTE_CACHE_SECONDS:
            twitch_emotes: list[dict[str, str]] = []
            complete_twitch_catalog = False
            token = (getattr(self.bot, "tokens", {}).get(broadcaster_id) or {}).get("token")

            if token and self.client is not None:
                try:
                    twitch_emotes = await self._fetch_twitch_user_emotes(broadcaster_id, str(token))
                    complete_twitch_catalog = True
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in {401, 403}:
                        LOGGER.warning("[Live Chat] Unable to load Twitch user emotes for %s.", broadcaster_id, exc_info=True)

                    try:
                        twitch_emotes = await self._fetch_basic_twitch_emotes(broadcaster_id, str(token))
                    except Exception:
                        LOGGER.warning("[Live Chat] Unable to load fallback Twitch emotes for %s.", broadcaster_id, exc_info=True)
                except Exception:
                    LOGGER.warning("[Live Chat] Unable to load Twitch emotes for %s.", broadcaster_id, exc_info=True)

            cached = (now, twitch_emotes, complete_twitch_catalog)
            self.twitch_emote_cache[broadcaster_id] = cached

        _, twitch_emotes, complete_twitch_catalog = cached
        seventv_channel = self.seventv_channel_emotes.get(broadcaster_id, {})
        emotes = list(twitch_emotes)
        emotes.extend({
            "name": name, "url": item.url or "", "provider": "7tv", "scope": "channel",
            "group": "7TV", "group_key": "7tv"
        } for name, item in seventv_channel.items())
        emotes.extend({
            "name": name, "url": item.url or "", "provider": "7tv", "scope": "global",
            "group": "7TV", "group_key": "7tv"
        } for name, item in self.seventv_global_emotes.items())

        for item in twitch_emotes:
            if "group" not in item:
                item["group"] = "Twitch Global" if item["scope"] == "global" else "Twitch"
                item["group_key"] = "twitch:global" if item["scope"] == "global" else "twitch:unknown"

        unique = {(item["provider"], item["url"], item["name"]): item for item in emotes if item["url"]}
        sorted_emotes = sorted(unique.values(), key=lambda item: (
            item["provider"] == "7tv", item.get("group", "").casefold(), item["name"].casefold(), item["name"]
        ))

        return {
            "emotes": sorted_emotes,
            "personal_group_key": f"twitch:{broadcaster_id}",
            "complete_twitch_catalog": complete_twitch_catalog,
            "twitch_reconnect_required": not complete_twitch_catalog
        }

    async def _watch_seventv_channel(self, broadcaster_id: str) -> None:
        try:
            while self.started:
                try:
                    set_id = await self._refresh_seventv_channel(broadcaster_id)

                    if set_id is None:
                        await asyncio.sleep(SEVENTV_REFRESH_SECONDS)
                        continue

                    await self._watch_seventv_set(broadcaster_id, set_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.warning(
                        "[Live Chat] 7TV emote updates failed for broadcaster %s; retrying.",
                        broadcaster_id,
                        exc_info=True
                    )
                    await asyncio.sleep(SEVENTV_RECONNECT_SECONDS)
        finally:
            current = self.seventv_tasks.get(broadcaster_id)

            if current is asyncio.current_task():
                self.seventv_tasks.pop(broadcaster_id, None)

    async def _watch_seventv_set(self, broadcaster_id: str, set_id: str) -> None:
        stream_task = asyncio.create_task(self._stream_seventv_updates(broadcaster_id, set_id))

        try:
            while self.started:
                done, _ = await asyncio.wait((stream_task,), timeout=SEVENTV_REFRESH_SECONDS)

                if stream_task in done:
                    await stream_task
                    return

                current_set_id = await self._refresh_seventv_channel(broadcaster_id)

                if current_set_id != set_id:
                    return
        finally:
            if not stream_task.done():
                stream_task.cancel()
                await asyncio.gather(stream_task, return_exceptions=True)

    async def _stream_seventv_updates(self, broadcaster_id: str, set_id: str) -> None:
        if self.client is None:
            return

        subscription = quote(f"emote_set.update<object_id={set_id}>", safe="")
        event_url = f"{SEVENTV_EVENT_API_URL}@{subscription}"
        event_type = ""
        data_lines: list[str] = []
        timeout = httpx.Timeout(20, read=None)

        async with self.client.stream("GET", event_url, headers={"Accept": "text/event-stream"}, timeout=timeout) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not self.started:
                    return

                if line.startswith("event:"):
                    event_type = line.removeprefix("event:").strip().casefold()
                elif line.startswith("data:"):
                    data_lines.append(line.removeprefix("data:").lstrip())
                elif not line:
                    should_refresh = event_type == "dispatch"

                    if data_lines and not should_refresh:
                        try:
                            event_data = json.loads("\n".join(data_lines))
                            should_refresh = event_data.get("type") == "emote_set.update"
                        except (AttributeError, json.JSONDecodeError):
                            pass

                    if should_refresh:
                        await self._refresh_seventv_set(broadcaster_id, set_id)

                    event_type = ""
                    data_lines.clear()

    def tag_command_response(self, broadcaster_id: str, message_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        message_id = str(message_id)

        if not message_id or message_id in self.command_response_ids[broadcaster_id]:
            return

        self.command_response_ids[broadcaster_id].add(message_id)
        self.command_response_id_order[broadcaster_id].append(message_id)

        while len(self.command_response_id_order[broadcaster_id]) > 1000:
            expired_id = self.command_response_id_order[broadcaster_id].popleft()
            self.command_response_ids[broadcaster_id].discard(expired_id)

    def _consume_command_response(self, broadcaster_id: str, message_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        message_id = str(message_id)

        if message_id not in self.command_response_ids.get(broadcaster_id, set()):
            return False

        self.command_response_ids[broadcaster_id].discard(message_id)
        return True

    def publish(self, broadcaster_id: str, message: UnifiedChatMessage) -> bool:
        broadcaster_id = str(broadcaster_id)

        if message.id in self.message_ids[broadcaster_id]:
            return False

        self.message_ids[broadcaster_id].add(message.id)
        self.message_id_order[broadcaster_id].append(message.id)

        while len(self.message_id_order[broadcaster_id]) > 1000:
            expired_id = self.message_id_order[broadcaster_id].popleft()
            self.message_ids[broadcaster_id].discard(expired_id)

        self.messages[broadcaster_id].append(message)

        for queue in tuple(self.subscribers.get(broadcaster_id, ())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)

        return True

    def history(self, broadcaster_id: str, view: str = "both") -> list[dict[str, object]]:
        return [message.as_dict() for message in self.messages.get(str(broadcaster_id), ()) if message_matches_view(message, view)]

    def find_message(self, broadcaster_id: str, message_id: str) -> dict[str, object] | None:
        message_id = str(message_id)
        return next(
            (message.as_dict() for message in reversed(self.messages.get(str(broadcaster_id), ())) if message.id == message_id),
            None
        )

    async def pin_message(self, broadcaster_id: str, message: dict[str, object]) -> None:
        broadcaster_id = str(broadcaster_id)
        self.pinned_messages[broadcaster_id] = message
        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO pinned_chat_messages (broadcaster_id, message_id, message_json, pinned_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id) DO UPDATE SET
                    message_id = excluded.message_id,
                    message_json = excluded.message_json,
                    pinned_at = CURRENT_TIMESTAMP
                """,
                (broadcaster_id, str(message.get("id", "")), json.dumps(message, separators=(",", ":")))
            )
            await connection.commit()

    async def clear_pinned_message(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        self.pinned_messages.pop(broadcaster_id, None)
        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM pinned_chat_messages WHERE broadcaster_id = ?", (broadcaster_id,))
            await connection.commit()

    def get_pinned_message(self, broadcaster_id: str) -> dict[str, object] | None:
        return self.pinned_messages.get(str(broadcaster_id))

    async def remove_message(self, broadcaster_id: str, message_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        messages = self.messages.get(broadcaster_id)
        if messages is not None:
            deleted_message = None
            updated_messages = deque(maxlen=messages.maxlen)
            for message in messages:
                if message.id == message_id:
                    message = replace(message, deleted=True)
                    deleted_message = message
                updated_messages.append(message)
            self.messages[broadcaster_id] = updated_messages
            if deleted_message is not None:
                for queue in tuple(self.subscribers.get(broadcaster_id, ())):
                    if queue.full():
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    queue.put_nowait(deleted_message)
        if self.pinned_messages.get(broadcaster_id, {}).get("id") == message_id:
            await self.clear_pinned_message(broadcaster_id)

    def record_mod_action(self, payload) -> None:
        broadcaster = getattr(payload, "broadcaster", None)
        broadcaster_id = getattr(broadcaster, "id", None)
        if broadcaster_id is None:
            return
        action_key = str(getattr(payload, "action", None) or "moderation")
        action_labels = {
            "emoteonly": "Enabled emote-only mode", "emoteonlyoff": "Disabled emote-only mode",
            "followers": "Enabled followers-only mode", "followersoff": "Disabled followers-only mode",
            "uniquechat": "Enabled unique-chat mode", "uniquechatoff": "Disabled unique-chat mode",
            "slow": "Enabled slow mode", "slowoff": "Disabled slow mode",
            "subscribers": "Enabled subscribers-only mode", "subscribersoff": "Disabled subscribers-only mode",
            "add_blocked_term": "Added blocked term", "remove_blocked_term": "Removed blocked term",
            "add_permitted_term": "Added permitted term", "remove_permitted_term": "Removed permitted term",
            "approve_unban_request": "Approved unban request", "deny_unban_request": "Denied unban request",
            "shared_chat_ban": "Shared-chat ban", "shared_chat_unban": "Shared-chat unban",
            "shared_chat_timeout": "Shared-chat timeout", "shared_chat_untimeout": "Shared-chat untimeout",
            "shared_chat_delete": "Shared-chat message deletion"
        }
        action = action_labels.get(action_key, action_key.replace("_", " ").title())
        moderator = getattr(payload, "moderator", None)
        detail = None
        detail_attributes = {
            "add_blocked_term": "automod_terms", "remove_blocked_term": "automod_terms",
            "add_permitted_term": "automod_terms", "remove_permitted_term": "automod_terms",
            "approve_unban_request": "unban_request", "deny_unban_request": "unban_request",
            "shared_chat_ban": "shared_ban", "shared_chat_unban": "shared_unban",
            "shared_chat_timeout": "shared_timeout", "shared_chat_untimeout": "shared_untimeout",
            "shared_chat_delete": "shared_delete"
        }
        for attribute in (detail_attributes.get(action_key, action_key), "ban", "timeout", "delete", "warn", "unban", "untimeout", "mod", "unmod", "vip", "unvip"):
            candidate = getattr(payload, attribute, None)
            if candidate is not None:
                detail = candidate
                break

        def user_summary(user) -> tuple[str | None, str | None, str | None]:
            if user is None:
                return None, None, None
            login = getattr(user, "name", None)
            display_name = getattr(user, "display_name", None) or login
            label = (
                f"{display_name} ({login})"
                if display_name and login and str(display_name).casefold() != str(login).casefold()
                else display_name or login
            )
            user_id = getattr(user, "id", None)
            return label, str(login) if login else None, str(user_id) if user_id is not None else None

        target = getattr(detail, "user", None) or detail
        target_name, target_login, _ = user_summary(target)
        moderator_name, moderator_login, _ = user_summary(moderator)
        reason = getattr(detail, "reason", None)
        expires_at = getattr(detail, "expires_at", None)
        source_broadcaster = getattr(payload, "source_broadcaster", None)
        source_name, _, source_id = user_summary(source_broadcaster)
        is_shared_action = action_key.startswith("shared_chat_")
        self.mod_actions[str(broadcaster_id)].appendleft({
            "id": secrets.token_urlsafe(9),
            "action": action,
            "action_key": action_key,
            "moderator": moderator_name or "Twitch",
            "moderator_login": moderator_login,
            "target": target_name,
            "target_login": target_login,
            "reason": reason,
            "expires_at": expires_at.isoformat() if expires_at is not None else None,
            "message": getattr(detail, "text", None) if action_key in {"delete", "shared_chat_delete"} else None,
            "note": getattr(detail, "text", None) if action_key in {"approve_unban_request", "deny_unban_request"} else None,
            "follow_duration": getattr(detail, "follow_duration", None),
            "wait_time": getattr(detail, "wait_time", None),
            "viewer_count": getattr(detail, "viewer_count", None),
            "terms": list(getattr(detail, "terms", None) or ()),
            "term_list": getattr(detail, "list", None),
            "from_automod": getattr(detail, "from_automod", None),
            "chat_rules": list(getattr(detail, "chat_rules", None) or ()),
            "source_channel": source_name if is_shared_action and source_id != str(broadcaster_id) else None,
            "timestamp": datetime.now(UTC).isoformat()
        })

    def hold_automod_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        user = payload.user
        self.automod_messages[broadcaster_id][str(payload.message_id)] = {
            "id": str(payload.message_id),
            "username": str(user.name),
            "display_name": str(getattr(user, "display_name", None) or user.name),
            "message": str(payload.text),
            "reason": str(getattr(payload, "reason", None) or getattr(payload, "category", None) or "AutoMod"),
            "level": getattr(payload, "level", None),
            "held_at": payload.held_at.isoformat() if getattr(payload, "held_at", None) else datetime.now(UTC).isoformat()
        }

    def resolve_automod_message(self, broadcaster_id: str, message_id: str) -> None:
        self.automod_messages[str(broadcaster_id)].pop(str(message_id), None)

    def get_moderation_activity(self, broadcaster_id: str) -> dict[str, list[dict[str, object]]]:
        broadcaster_id = str(broadcaster_id)
        return {
            "mod_actions": list(self.mod_actions.get(broadcaster_id, ())),
            "automod": sorted(
                self.automod_messages.get(broadcaster_id, {}).values(),
                key=lambda item: str(item.get("held_at", "")),
                reverse=True
            )
        }

    def subscribe(self, broadcaster_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        self.subscribers[str(broadcaster_id)].add(queue)
        return queue

    def unsubscribe(self, broadcaster_id: str, queue: asyncio.Queue) -> None:
        broadcaster_id = str(broadcaster_id)
        channel_subscribers = self.subscribers.get(broadcaster_id)

        if channel_subscribers is None:
            return

        channel_subscribers.discard(queue)

        if not channel_subscribers:
            self.subscribers.pop(broadcaster_id, None)

    async def get_or_create_widget_token(self, broadcaster_id: str) -> str:
        broadcaster_id = str(broadcaster_id)
        existing = self.widget_tokens.get(broadcaster_id)

        if existing:
            return existing

        return await self.regenerate_widget_token(broadcaster_id)

    async def regenerate_widget_token(self, broadcaster_id: str) -> str:
        broadcaster_id = str(broadcaster_id)
        token = secrets.token_urlsafe(32)

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO chat_widget_tokens (broadcaster_id, token, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id) DO UPDATE SET token = excluded.token, created_at = CURRENT_TIMESTAMP
                """,
                (broadcaster_id, token)
            )

        previous = self.widget_tokens.get(broadcaster_id)

        if previous:
            self.token_broadcasters.pop(previous, None)

        self.widget_tokens[broadcaster_id] = token
        self.token_broadcasters[token] = broadcaster_id
        return token

    def resolve_widget_token(self, token: str) -> str | None:
        return self.token_broadcasters.get(token)

    def get_youtube_state(self, broadcaster_id: str) -> YouTubeChatState:
        broadcaster_id = str(broadcaster_id)
        connection = self.connections.get(broadcaster_id)
        status, detail = self.youtube_statuses.get(
            broadcaster_id,
            ("waiting", "Waiting for an active YouTube livestream.") if connection else ("disconnected", "Connect a YouTube channel to include its live chat.")
        )
        return YouTubeChatState(
            configured=settings.YOUTUBE_CONFIGURED,
            connected=connection is not None,
            channel_id=connection.channel_id if connection else None,
            channel_title=connection.channel_title if connection else None,
            status=status,
            detail=detail
        )

    async def connect_youtube(self, broadcaster_id: str, channel: YouTubeChannel, token: YouTubeTokenResponse) -> YouTubeChatState:
        broadcaster_id = str(broadcaster_id)
        connection = YouTubeConnection(broadcaster_id, channel.channel_id, channel.title, token.access_token, token.refresh_token, token.expires_at)

        async with self.db.acquire() as database_connection:
            await database_connection.execute(
                """
                INSERT INTO youtube_chat_connections (
                    broadcaster_id, youtube_channel_id, youtube_channel_title,
                    access_token, refresh_token, expires_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id) DO UPDATE SET
                    youtube_channel_id = excluded.youtube_channel_id,
                    youtube_channel_title = excluded.youtube_channel_title,
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expires_at = excluded.expires_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (broadcaster_id, channel.channel_id, channel.title, token.access_token, token.refresh_token, token.expires_at)
            )

        self.connections[broadcaster_id] = connection
        self.youtube_statuses[broadcaster_id] = ("waiting", "Waiting for an active YouTube livestream.")

        if self.started and settings.YOUTUBE_CONFIGURED:
            self._start_watcher(broadcaster_id)

        LOGGER.info("[Live Chat] Connected YouTube channel %s to broadcaster %s.", channel.channel_id, broadcaster_id)
        return self.get_youtube_state(broadcaster_id)

    async def disconnect_youtube(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        task = self.tasks.pop(broadcaster_id, None)

        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM youtube_chat_connections WHERE broadcaster_id = ?", (broadcaster_id,))

        self.connections.pop(broadcaster_id, None)
        self.youtube_statuses.pop(broadcaster_id, None)
        self.active_youtube_chat_ids.pop(broadcaster_id, None)
        LOGGER.info("[Live Chat] Disconnected YouTube from broadcaster %s.", broadcaster_id)

    def _start_watcher(self, broadcaster_id: str) -> None:
        existing = self.tasks.pop(str(broadcaster_id), None)

        if existing:
            existing.cancel()

        task = asyncio.create_task(self._watch_youtube(str(broadcaster_id)), name=f"youtube-chat-{broadcaster_id}")
        self.tasks[str(broadcaster_id)] = task

    async def _watch_youtube(self, broadcaster_id: str) -> None:
        try:
            while self.started and broadcaster_id in self.connections:
                try:
                    live_chat_id = await self._find_active_live_chat(broadcaster_id)

                    if live_chat_id is None:
                        self.active_youtube_chat_ids.pop(broadcaster_id, None)
                        self.youtube_statuses[broadcaster_id] = ("waiting", "Waiting for an active YouTube livestream.")
                        await asyncio.sleep(settings.YOUTUBE_CHAT_DISCOVERY_SECONDS)
                        continue

                    self.active_youtube_chat_ids[broadcaster_id] = live_chat_id
                    self.youtube_statuses[broadcaster_id] = ("live", "Receiving YouTube live-chat messages.")
                    try:
                        await self._stream_live_chat(broadcaster_id, live_chat_id)
                    finally:
                        self.active_youtube_chat_ids.pop(broadcaster_id, None)
                except asyncio.CancelledError:
                    raise
                except httpx.HTTPStatusError as error:
                    if error.response.status_code != 403:
                        raise

                    reason, api_message = self._youtube_error_details(error.response)
                    detail = {
                        "liveStreamingNotEnabled": "YouTube live streaming is not enabled for the connected channel.",
                        "insufficientLivePermissions": "Reconnect YouTube to grant live-stream access."
                    }.get(reason, "YouTube live-chat discovery is unavailable; retrying automatically.")
                    status = ("unavailable", detail)

                    if self.youtube_statuses.get(broadcaster_id) != status:
                        LOGGER.warning(
                            "[Live Chat] YouTube discovery unavailable for broadcaster %s (%s): %s",
                            broadcaster_id,
                            reason or "forbidden",
                            api_message or "The YouTube API returned HTTP 403."
                        )

                    self.active_youtube_chat_ids.pop(broadcaster_id, None)
                    self.youtube_statuses[broadcaster_id] = status
                    await asyncio.sleep(settings.YOUTUBE_CHAT_DISCOVERY_SECONDS)
                except Exception:
                    self.youtube_statuses[broadcaster_id] = ("error", "YouTube chat is temporarily unavailable; retrying automatically.")
                    LOGGER.exception("[Live Chat] YouTube watcher failed for broadcaster %s.", broadcaster_id)
                    await asyncio.sleep(settings.YOUTUBE_CHAT_DISCOVERY_SECONDS)
        finally:
            current = self.tasks.get(broadcaster_id)

            if current is asyncio.current_task():
                self.tasks.pop(broadcaster_id, None)

    async def _find_active_live_chat(self, broadcaster_id: str) -> str | None:
        response = await self._youtube_get(
            broadcaster_id,
            "/liveBroadcasts",
            {"part": "id,snippet", "broadcastStatus": "active", "broadcastType": "all", "maxResults": 10}
        )

        for item in response.get("items", []):
            live_chat_id = item.get("snippet", {}).get("liveChatId")

            if live_chat_id:
                return str(live_chat_id)

        return None

    async def _stream_live_chat(self, broadcaster_id: str, live_chat_id: str) -> None:
        """Receive new messages as YouTube publishes them, with REST polling as a fallback."""
        page_token = None

        try:
            async with grpc.aio.secure_channel("youtube.googleapis.com:443", grpc.ssl_channel_credentials()) as channel:
                stream_list = channel.unary_stream(
                    "/youtube.api.v3.V3DataLiveChatMessageService/StreamList",
                    request_serializer=youtube_live_chat_pb2.LiveChatMessageListRequest.SerializeToString,
                    response_deserializer=youtube_live_chat_pb2.LiveChatMessageListResponse.FromString,
                )

                while self.started and broadcaster_id in self.connections:
                    connection = await self._ensure_access_token(broadcaster_id)
                    request = youtube_live_chat_pb2.LiveChatMessageListRequest(
                        live_chat_id=live_chat_id,
                        part=["id", "snippet", "authorDetails"],
                        page_token=page_token,
                    )
                    stream = stream_list(request, metadata=(("authorization", f"Bearer {connection.access_token}"),))

                    async for response in stream:
                        self._publish_youtube_items(broadcaster_id, [self._stream_message_item(item) for item in response.items])
                        if response.next_page_token:
                            page_token = response.next_page_token
                        if response.offline_at:
                            return

                    # YouTube may close an otherwise healthy stream. Resume at its last token.
                    await asyncio.sleep(1)
        except grpc.aio.AioRpcError as error:
            if error.code() in {grpc.StatusCode.NOT_FOUND, grpc.StatusCode.FAILED_PRECONDITION}:
                return
            LOGGER.warning(
                "[Live Chat] YouTube streaming failed for broadcaster %s (%s); falling back to polling.",
                broadcaster_id, error.code().name,
            )
            if error.code() == grpc.StatusCode.UNAUTHENTICATED:
                self.connections[broadcaster_id].expires_at = datetime.now(UTC).isoformat()
            await self._poll_live_chat(broadcaster_id, live_chat_id, page_token=page_token)

    @staticmethod
    def _stream_message_item(item) -> dict:
        snippet = item.snippet
        author = item.author_details
        message = snippet.display_message
        return {
            "id": item.id,
            "snippet": {
                "displayMessage": message,
                "hasDisplayContent": snippet.has_display_content if snippet.HasField("has_display_content") else bool(message),
                "publishedAt": snippet.published_at,
            },
            "authorDetails": {
                "channelId": author.channel_id,
                "displayName": author.display_name,
                "isVerified": author.is_verified,
                "isChatOwner": author.is_chat_owner,
                "isChatSponsor": author.is_chat_sponsor,
                "isChatModerator": author.is_chat_moderator,
            },
        }

    async def _poll_live_chat(self, broadcaster_id: str, live_chat_id: str, *, page_token: str | None = None) -> None:

        while self.started and broadcaster_id in self.connections:
            params = {"part": "id,snippet,authorDetails", "liveChatId": live_chat_id, "maxResults": 200}

            if page_token:
                params["pageToken"] = page_token

            try:
                payload = await self._youtube_get(broadcaster_id, "/liveChat/messages", params)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {403, 404}:
                    return
                raise

            self._publish_youtube_items(broadcaster_id, payload.get("items", []))
            page_token = payload.get("nextPageToken")

            if payload.get("offlineAt"):
                return

            interval = max(1.0, int(payload.get("pollingIntervalMillis", 5000)) / 1000)
            await asyncio.sleep(interval)

    def _publish_youtube_items(self, broadcaster_id: str, items: list[dict]) -> None:
        for item in items:
            snippet = item.get("snippet", {})
            message_text = str(snippet.get("displayMessage") or "").strip()

            if not snippet.get("hasDisplayContent", bool(message_text)) or not message_text:
                continue

            author = item.get("authorDetails", {})
            username = str(author.get("channelId") or "unknown")
            display_name = str(author.get("displayName") or username)
            badges = []

            for key, label in (
                ("isChatOwner", "Owner"),
                ("isChatModerator", "Mod"),
                ("isChatSponsor", "Member"),
                ("isVerified", "Verified")
            ):
                if author.get(key):
                    badges.append(label)

            message = UnifiedChatMessage(
                id=f"youtube:{item.get('id') or secrets.token_urlsafe(12)}",
                platform="youtube",
                kind=self._classify(broadcaster_id, message_text),
                username=username,
                display_name=display_name,
                message=message_text,
                timestamp=str(snippet.get("publishedAt") or datetime.now(UTC).isoformat()),
                badges=tuple(badges)
            )
            self.publish(broadcaster_id, message)

    async def _youtube_get(self, broadcaster_id: str, path: str, params: dict[str, object]) -> dict:
        if self.client is None:
            raise RuntimeError("YouTube HTTP client is not running.")

        connection = await self._ensure_access_token(broadcaster_id)
        response = await self.client.get(
            f"{YOUTUBE_API_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {connection.access_token}"}
        )

        if response.status_code == 401:
            connection.expires_at = datetime.now(UTC).isoformat()
            connection = await self._ensure_access_token(broadcaster_id)
            response = await self.client.get(
                f"{YOUTUBE_API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {connection.access_token}"}
            )

        response.raise_for_status()
        return response.json()

    async def send_youtube_message(self, broadcaster_id: str, message: str) -> dict:
        broadcaster_id = str(broadcaster_id)
        live_chat_id = self.active_youtube_chat_ids.get(broadcaster_id)

        if broadcaster_id not in self.connections:
            raise ValueError("Connect a YouTube channel before sending messages.")

        if live_chat_id is None:
            raise ValueError("No active YouTube live chat is available.")

        if self.client is None:
            raise RuntimeError("YouTube chat is not running.")

        connection = await self._ensure_access_token(broadcaster_id)
        request = {
            "params": {"part": "snippet"},
            "json": {
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message}
                }
            }
        }
        response = await self.client.post(
            f"{YOUTUBE_API_URL}/liveChat/messages",
            headers={"Authorization": f"Bearer {connection.access_token}"},
            **request
        )

        if response.status_code == 401:
            connection.expires_at = datetime.now(UTC).isoformat()
            connection = await self._ensure_access_token(broadcaster_id)
            response = await self.client.post(
                f"{YOUTUBE_API_URL}/liveChat/messages",
                headers={"Authorization": f"Bearer {connection.access_token}"},
                **request
            )

        response.raise_for_status()
        return response.json()

    async def _ensure_access_token(self, broadcaster_id: str) -> YouTubeConnection:
        connection = self.connections[broadcaster_id]
        expires_at = datetime.fromisoformat(connection.expires_at.replace("Z", "+00:00"))

        if expires_at > datetime.now(UTC) + timedelta(seconds=60):
            return connection

        if self.client is None:
            raise RuntimeError("YouTube HTTP client is not running.")

        response = await self.client.post(
            YOUTUBE_TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "refresh_token": connection.refresh_token,
                "grant_type": "refresh_token"
            }
        )
        response.raise_for_status()
        payload = response.json()
        connection.access_token = str(payload["access_token"])
        connection.expires_at = (datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600)))).isoformat()

        async with self.db.acquire() as database_connection:
            await database_connection.execute(
                "UPDATE youtube_chat_connections SET access_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP WHERE broadcaster_id = ?",
                (connection.access_token, connection.expires_at, broadcaster_id)
            )

        return connection

    @staticmethod
    def _youtube_error_details(response: httpx.Response) -> tuple[str | None, str | None]:
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
        except (TypeError, ValueError):
            return None, None

        reasons = error.get("errors") or []
        reason = reasons[0].get("reason") if reasons and isinstance(reasons[0], dict) else None
        message = error.get("message")
        return str(reason) if reason else None, str(message) if message else None

    def _classify(self, broadcaster_id: str, message: str) -> str:
        prefix = settings.PREFIX or "!"
        stripped = message.lstrip()

        if not stripped.startswith(prefix):
            return "chat"

        invoked_with = stripped[len(prefix):].split(maxsplit=1)[0].casefold()

        if not invoked_with:
            return "chat"

        if self.bot is not None and self.bot.get_command(invoked_with) is not None:
            return "command"

        profile = get_active_profile(str(broadcaster_id))

        if profile is not None and invoked_with == profile.points.command_alias.casefold():
            return "command"

        return "chat"

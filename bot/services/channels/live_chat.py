import asyncio
import logging
import secrets
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import httpx

from config.settings import settings
from web.shared.youtube_oauth import YOUTUBE_API_URL, YOUTUBE_TOKEN_URL, YouTubeChannel, YouTubeTokenResponse

LOGGER = logging.getLogger("RatBoomBot")
CHAT_VIEWS = {"chat", "commands", "both"}


@dataclass(frozen=True)
class UnifiedChatMessage:
    id: str
    platform: str
    kind: str
    username: str
    display_name: str
    message: str
    timestamp: str
    avatar_url: str | None = None
    color: str | None = None
    badges: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["badges"] = list(self.badges)
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

    def __init__(self, db):
        self.db = db
        self.connections: dict[str, YouTubeConnection] = {}
        self.youtube_statuses: dict[str, tuple[str, str]] = {}
        self.widget_tokens: dict[str, str] = {}
        self.token_broadcasters: dict[str, str] = {}
        self.messages: dict[str, deque[UnifiedChatMessage]] = defaultdict(lambda: deque(maxlen=250))
        self.message_ids: dict[str, set[str]] = defaultdict(set)
        self.message_id_order: dict[str, deque[str]] = defaultdict(deque)
        self.subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self.tasks: dict[str, asyncio.Task] = {}
        self.client: httpx.AsyncClient | None = None
        self.started = False

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            connection_rows = await connection.fetchall(
                "SELECT broadcaster_id, youtube_channel_id, youtube_channel_title, access_token, refresh_token, expires_at FROM youtube_chat_connections"
            )
            widget_rows = await connection.fetchall("SELECT broadcaster_id, token FROM chat_widget_tokens")

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
        LOGGER.info("[Live Chat] Loaded %d YouTube connection(s) and %d OBS widget token(s).", len(self.connections), len(self.widget_tokens))

    async def start(self) -> None:
        self.started = True
        self.client = httpx.AsyncClient(timeout=20)

        if not settings.YOUTUBE_CONFIGURED:
            LOGGER.warning("[Live Chat] YouTube OAuth is not configured; Twitch feeds and OBS widgets remain available.")
            return

        for broadcaster_id in self.connections:
            self._start_watcher(broadcaster_id)

    async def stop(self) -> None:
        self.started = False
        tasks = tuple(self.tasks.values())

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.tasks.clear()

        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def publish_twitch(self, payload) -> UnifiedChatMessage:
        broadcaster_id = str(payload.broadcaster.id)
        chatter = payload.chatter
        message_text = str(payload.text)
        username = str(getattr(chatter, "name", None) or "unknown")
        display_name = str(getattr(chatter, "display_name", None) or username)
        badges = []

        for attribute, label in (
            ("is_broadcaster", "Broadcaster"),
            ("is_moderator", "Mod"),
            ("is_vip", "VIP"),
            ("is_subscriber", "Subscriber")
        ):
            if bool(getattr(chatter, attribute, False)):
                badges.append(label)

        timestamp = getattr(payload, "timestamp", None)
        timestamp_value = timestamp.isoformat() if hasattr(timestamp, "isoformat") else datetime.now(UTC).isoformat()
        message = UnifiedChatMessage(
            id=f"twitch:{getattr(payload, 'id', None) or secrets.token_urlsafe(12)}",
            platform="twitch",
            kind=self._classify(message_text),
            username=username,
            display_name=display_name,
            message=message_text,
            timestamp=timestamp_value,
            color=str(getattr(payload, "color", None) or "") or None,
            badges=tuple(badges)
        )
        self.publish(broadcaster_id, message)
        return message

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
                        self.youtube_statuses[broadcaster_id] = ("waiting", "Waiting for an active YouTube livestream.")
                        await asyncio.sleep(settings.YOUTUBE_CHAT_DISCOVERY_SECONDS)
                        continue

                    self.youtube_statuses[broadcaster_id] = ("live", "Receiving YouTube live-chat messages.")
                    await self._poll_live_chat(broadcaster_id, live_chat_id)
                except asyncio.CancelledError:
                    raise
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
            {"part": "id,snippet", "broadcastStatus": "active", "broadcastType": "all", "mine": "true", "maxResults": 10}
        )

        for item in response.get("items", []):
            live_chat_id = item.get("snippet", {}).get("liveChatId")

            if live_chat_id:
                return str(live_chat_id)

        return None

    async def _poll_live_chat(self, broadcaster_id: str, live_chat_id: str) -> None:
        page_token = None

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
                kind=self._classify(message_text),
                username=username,
                display_name=display_name,
                message=message_text,
                timestamp=str(snippet.get("publishedAt") or datetime.now(UTC).isoformat()),
                avatar_url=author.get("profileImageUrl"),
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
    def _classify(message: str) -> str:
        prefix = settings.PREFIX or "!"
        return "command" if message.lstrip().startswith(prefix) else "chat"

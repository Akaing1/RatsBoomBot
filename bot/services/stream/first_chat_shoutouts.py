import logging

from bot.profiles import FirstChatShoutout, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


class FirstChatShoutoutService:

    def __init__(self, bot, db, shoutouts, stream_logs):
        self.bot = bot
        self.db = db
        self.shoutouts = shoutouts
        self.stream_logs = stream_logs

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS first_chat_shoutouts (
                    broadcaster_id TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (broadcaster_id, stream_id, user_id)
                )
                """
            )

    async def handle_message(self, *, broadcaster_id: str, user_id: str, username: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        configured = self.get_configured_user(broadcaster_id, user_id)

        if configured is None:
            return False

        stream_id = await self.get_live_stream_id(broadcaster_id)

        if stream_id is None:
            return False

        if not await self.mark_seen(broadcaster_id=broadcaster_id, stream_id=stream_id, user_id=user_id, username=username):
            return False

        await self.shoutouts.send_chat_message(broadcaster_id, configured.username or username, configured.message)

        if configured.native_shoutout:
            self.shoutouts.enqueue(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=configured.username or username,
                requested_by="first-chat"
            )

        LOGGER.info("[First Chat Shoutouts] Triggered first-message shoutout for %s (%s) in stream %s.", username, user_id, stream_id)
        return True

    def get_configured_user(self, broadcaster_id: str, user_id: str) -> FirstChatShoutout | None:
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return None

        return next((entry for entry in profile.first_chat_shoutouts if str(entry.user_id) == str(user_id)), None)

    async def get_live_stream_id(self, broadcaster_id: str) -> str | None:
        active_session = self.stream_logs.active_sessions.get(str(broadcaster_id))

        if active_session is not None:
            return active_session.stream_id

        try:
            stream = await self.bot.create_partialuser(str(broadcaster_id)).fetch_stream()
        except Exception:
            LOGGER.exception("[First Chat Shoutouts] Failed to fetch stream state for broadcaster %s.", broadcaster_id)
            return None

        if stream is None:
            return None

        stream_id = getattr(stream, "id", None) or getattr(stream, "stream_id", None)
        return str(stream_id) if stream_id is not None else None

    async def mark_seen(self, *, broadcaster_id: str, stream_id: str, user_id: str, username: str) -> bool:
        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT OR IGNORE INTO first_chat_shoutouts (broadcaster_id, stream_id, user_id, username)
                VALUES (?, ?, ?, ?)
                """,
                (str(broadcaster_id), str(stream_id), str(user_id), username)
            )
            row = await connection.fetchone("SELECT changes() AS inserted")

        return bool(row and row["inserted"])

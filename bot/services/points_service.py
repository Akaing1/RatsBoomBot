import logging
import time

from config.settings import settings

LOGGER = logging.getLogger("Bot")


class PointsService:
    BREAD_PER_MESSAGE = 10
    MESSAGE_COOLDOWN_SECONDS = 60

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.cooldowns: dict[str, float] = {}

    async def setup(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS viewers (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            messages INTEGER NOT NULL DEFAULT 0
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

    async def track_message(self, payload) -> None:
        user_id = payload.chatter.id
        username = payload.chatter.name
        username_key = username.lower()

        if username_key in settings.IGNORED_USERS:
            return

        now = time.time()
        last_message = self.cooldowns.get(user_id, 0)

        if now - last_message < self.MESSAGE_COOLDOWN_SECONDS:
            return

        self.cooldowns[user_id] = now

        query = """
        INSERT INTO viewers (user_id, username, points, messages)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points,
            messages = messages + 1
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (user_id, username, self.BREAD_PER_MESSAGE),
            )

        LOGGER.info(
            "Added %s stale bread to %s",
            self.BREAD_PER_MESSAGE,
            username,
        )

    async def get_points(self, user_id: str) -> int:
        query = "SELECT points FROM viewers WHERE user_id = ?"

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (user_id,))

        if not row:
            return 0

        return row["points"]

    async def add_points(
        self,
        user_id: str,
        username: str,
        amount: int,
    ) -> None:
        query = """
        INSERT INTO viewers (user_id, username, points, messages)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (user_id, username, amount),
            )

    async def get_leaderboard(self, limit: int = 5):
        query = """
        SELECT username, points
        FROM viewers
        ORDER BY points DESC
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            return await connection.fetchall(query, (limit,))
import logging
import time
from dataclasses import dataclass

from config.settings import settings

LOGGER = logging.getLogger("Bot")


@dataclass
class PendingDuel:
    challenger_id: str
    challenger_name: str
    opponent_id: str
    opponent_name: str
    amount: int
    created_at: float


class PointsService:
    BREAD_PER_MESSAGE = 10
    MESSAGE_COOLDOWN_SECONDS = 60
    DUEL_EXPIRATION_SECONDS = 60

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.cooldowns: dict[str, float] = {}
        self.pending_duels: dict[str, PendingDuel] = {}

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
        ON CONFLICT(user_id) DO UPDATE SET
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

    async def add_points(self, user_id: str, username: str, amount: int, ) -> None:
        query = """
        INSERT INTO viewers (user_id, username, points, messages)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (user_id, username, amount),
            )

    async def remove_points(self, user_id: str, amount: int) -> None:
        query = """
        UPDATE viewers
        SET points = MAX(points - ?, 0)
        WHERE user_id = ?
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (amount, user_id))

    async def set_points(self, user_id: str, amount: int) -> None:
        query = """
        UPDATE viewers
        SET points = ?
        WHERE user_id = ?
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (amount, user_id))

    async def reset_all_points(self) -> None:
        query = """
        UPDATE viewers
        SET points = 0
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

        LOGGER.warning("All stale bread points were reset.")

    async def get_leaderboard(self, limit: int = 5):
        query = """
        SELECT username, points
        FROM viewers
        ORDER BY points DESC
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            return await connection.fetchall(query, (limit,))

    def create_duel(
            self,
            challenger_id: str,
            challenger_name: str,
            opponent_id: str,
            opponent_name: str,
            amount: int,
    ) -> None:
        self.pending_duels[opponent_id] = PendingDuel(
            challenger_id=challenger_id,
            challenger_name=challenger_name,
            opponent_id=opponent_id,
            opponent_name=opponent_name,
            amount=amount,
            created_at=time.time(),
        )

    def get_duel_for_user(self, user_id: str) -> PendingDuel | None:
        duel = self.pending_duels.get(user_id)

        if not duel:
            return None

        now = time.time()

        if now - duel.created_at > self.DUEL_EXPIRATION_SECONDS:
            self.pending_duels.pop(user_id, None)
            return None

        return duel

    def remove_duel_for_user(self, user_id: str) -> None:
        self.pending_duels.pop(user_id, None)

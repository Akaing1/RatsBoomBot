import logging
import time
from dataclasses import dataclass

from config.settings import settings
from bot.profiles import get_active_profile

LOGGER = logging.getLogger("Bot")


@dataclass
class PendingDuel:
    broadcaster_id: str
    challenger_id: str
    challenger_name: str
    opponent_id: str
    opponent_name: str
    amount: int
    expiration_seconds: int
    created_at: float


class PointsService:

    LEGACY_BROADCASTER_ID = "shared"

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.cooldowns: dict[str, float] = {}
        self.pending_duels: dict[str, PendingDuel] = {}

    async def setup(self) -> None:
        await self._migrate_viewers_table_if_needed()

        query = """
        CREATE TABLE IF NOT EXISTS viewers (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

    async def _migrate_viewers_table_if_needed(self) -> None:
        async with self.db.acquire() as connection:
            table = await connection.fetchone(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'viewers'
                """
            )

            if table is None:
                return

            columns = await connection.fetchall("PRAGMA table_info(viewers)")
            column_names = {column["name"] for column in columns}
            primary_key_columns = [
                column["name"]
                for column in sorted(columns, key=lambda column: column["pk"])
                if column["pk"]
            ]

            already_per_broadcaster = (
                    column_names == {
                "broadcaster_id",
                "user_id",
                "username",
                "points",
                "messages"
            }
                    and primary_key_columns == ["broadcaster_id", "user_id"]
            )

            if already_per_broadcaster:
                return

            LOGGER.warning(
                "Migrating viewers table from shared points to per-broadcaster points. "
                "Existing balances will be stored under broadcaster_id=%s.",
                self.LEGACY_BROADCASTER_ID
            )

            await connection.execute("DROP TABLE IF EXISTS viewers_legacy")
            await connection.execute("ALTER TABLE viewers RENAME TO viewers_legacy")

            await connection.execute(
                """
                CREATE TABLE viewers (
                    broadcaster_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    messages INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (broadcaster_id, user_id)
                )
                """
            )

            await connection.execute(
                """
                INSERT INTO viewers (
                    broadcaster_id,
                    user_id,
                    username,
                    points,
                    messages
                )
                SELECT
                    ?,
                    user_id,
                    username,
                    points,
                    messages
                FROM viewers_legacy
                """,
                (self.LEGACY_BROADCASTER_ID,),
            )

    async def track_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name
        username_key = username.lower()
        profile = get_active_profile(broadcaster_id)

        if profile is None or not profile.points.enabled:
            return

        if username_key in settings.IGNORED_USERS:
            return

        points_config = profile.points
        now = time.time()
        cooldown_key = self._user_key(broadcaster_id, user_id)
        last_message = self.cooldowns.get(cooldown_key, 0)

        if now - last_message < points_config.message_cooldown_seconds:
            return

        self.cooldowns[cooldown_key] = now

        query = """
        INSERT INTO viewers (broadcaster_id, user_id, username, points, messages)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points,
            messages = messages + 1
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (
                    broadcaster_id,
                    user_id,
                    username,
                    points_config.points_per_message,
                ),
            )

        LOGGER.info(
            "[%s] Added %s points to %s.",
            broadcaster_id,
            points_config.points_per_message,
            username,
        )

    async def get_points(self, broadcaster_id: str, user_id: str) -> int:
        query = """
        SELECT points
        FROM viewers
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (broadcaster_id, user_id))

        if not row:
            return 0

        return row["points"]

    async def add_points(self, broadcaster_id: str, user_id: str, username: str, amount: int) -> None:
        query = """
        INSERT INTO viewers (broadcaster_id, user_id, username, points, messages)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (
                    broadcaster_id,
                    user_id,
                    username,
                    amount
                )
            )

    async def remove_points(self, broadcaster_id: str, user_id: str, amount: int) -> None:
        query = """
        UPDATE viewers
        SET points = MAX(points - ?, 0)
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (
                    amount,
                    broadcaster_id,
                    user_id
                )
            )

    async def set_points(self, broadcaster_id: str, user_id: str, amount: int) -> None:
        query = """
        UPDATE viewers
        SET points = ?
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (
                    amount,
                    broadcaster_id,
                    user_id
                )
            )

    async def reset_all_points(self, broadcaster_id: str) -> None:
        query = """
        UPDATE viewers
        SET points = 0
        WHERE broadcaster_id = ?
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id,))

        LOGGER.warning("[%s] All channel points were reset.", broadcaster_id)

    async def get_leaderboard(self, broadcaster_id: str, limit: int = 5):
        query = """
        SELECT username, points
        FROM viewers
        WHERE broadcaster_id = ?
        ORDER BY points DESC
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            return await connection.fetchall(
                query,
                (
                    broadcaster_id,
                    limit
                )
            )

    def create_duel(self, broadcaster_id: str, challenger_id: str, challenger_name: str, opponent_id: str,
                    opponent_name: str, amount: int, expiration_seconds: int) -> None:
        duel_key = self._user_key(
            str(broadcaster_id),
            str(opponent_id),
        )

        self.pending_duels[duel_key] = PendingDuel(
            broadcaster_id=str(broadcaster_id),
            challenger_id=str(challenger_id),
            challenger_name=challenger_name,
            opponent_id=str(opponent_id),
            opponent_name=opponent_name,
            amount=amount,
            expiration_seconds=expiration_seconds,
            created_at=time.time(),
        )

    def get_duel_for_user(self, broadcaster_id: str, user_id: str) -> PendingDuel | None:
        duel_key = self._user_key(
            str(broadcaster_id),
            str(user_id),
        )

        duel = self.pending_duels.get(duel_key)

        if not duel:
            return None

        now = time.time()

        if now - duel.created_at > duel.expiration_seconds:
            self.pending_duels.pop(duel_key, None)
            return None

        return duel

    def remove_duel_for_user(self, broadcaster_id: str, user_id: str) -> None:
        duel_key = self._user_key(
            str(broadcaster_id),
            str(user_id),
        )

        self.pending_duels.pop(duel_key, None)

    @staticmethod
    def _user_key(broadcaster_id: str, user_id: str) -> str:
        return f"{str(broadcaster_id)}:{str(user_id)}"

import logging
import time
from dataclasses import dataclass

from config.settings import settings

from bot.profiles import FeatureName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


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
        LOGGER.info("[Points] Preparing points storage.")

        try:
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
        except Exception:
            LOGGER.exception("[Points] Failed to prepare points storage.")
            raise

        LOGGER.info("[Points] Points storage ready.")

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
                LOGGER.debug(
                    "[Points] No existing viewers table found. Migration is not required."
                )
                return

            columns = await connection.fetchall("PRAGMA table_info(viewers)")
            column_names = {column["name"] for column in columns}
            primary_key_columns = [
                column["name"]
                for column in sorted(columns, key=lambda column: column["pk"])
                if column["pk"]
            ]

            expected_columns = {
                "broadcaster_id",
                "user_id",
                "username",
                "points",
                "messages"
            }

            already_per_broadcaster = (
                column_names == expected_columns
                and primary_key_columns == ["broadcaster_id", "user_id"]
            )

            if already_per_broadcaster:
                LOGGER.debug(
                    "[Points] Viewers table already uses per-broadcaster balances."
                )
                return

            LOGGER.warning(
                "[Points] Migrating shared viewer balances to per-broadcaster storage under broadcaster %s.",
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
                (self.LEGACY_BROADCASTER_ID,)
            )

        LOGGER.info("[Points] Legacy viewer balances migrated successfully.")

    async def track_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name
        username_key = username.lower()
        profile = get_active_profile(broadcaster_id)
        services = self.bot.services

        if profile is None:
            return

        if services is None:
            return

        if not services.features.is_enabled(broadcaster_id, FeatureName.POINTS):
            return

        if username_key in settings.IGNORED_USERS:
            LOGGER.debug(
                "[Points] Ignored message-point tracking for user %s in broadcaster %s.",
                username,
                broadcaster_id
            )
            return

        points_config = profile.points
        now = time.time()
        cooldown_key = self._user_key(broadcaster_id, user_id)
        last_message = self.cooldowns.get(cooldown_key, 0)

        if now - last_message < points_config.message_cooldown_seconds:
            return

        self.cooldowns[cooldown_key] = now

        query = """
        INSERT INTO viewers (
            broadcaster_id,
            user_id,
            username,
            points,
            messages
        )
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points,
            messages = messages + 1
        """

        values = (
            broadcaster_id,
            user_id,
            username,
            points_config.points_per_message
        )

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
        except Exception:
            LOGGER.exception(
                "[Points] Failed to award message points to %s for broadcaster %s.",
                username,
                broadcaster_id
            )
            raise

        LOGGER.debug(
            "[Points] Awarded %d message points to %s for broadcaster %s.",
            points_config.points_per_message,
            username,
            broadcaster_id
        )

    async def get_points(self, broadcaster_id: str, user_id: str) -> int:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        SELECT points
        FROM viewers
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (broadcaster_id, user_id))
        except Exception:
            LOGGER.exception(
                "[Points] Failed to load points for user %s in broadcaster %s.",
                user_id,
                broadcaster_id
            )
            raise

        if not row:
            return 0

        return int(row["points"])

    async def add_points(self, broadcaster_id: str, user_id: str, username: str, amount: int) -> None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        INSERT INTO viewers (
            broadcaster_id,
            user_id,
            username,
            points,
            messages
        )
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            username = excluded.username,
            points = points + excluded.points
        """

        values = (broadcaster_id, user_id, username, amount)

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
        except Exception:
            LOGGER.exception(
                "[Points] Failed to add %d points to %s for broadcaster %s.",
                amount,
                username,
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Points] Added %d points to %s for broadcaster %s.",
            amount,
            username,
            broadcaster_id
        )

    async def remove_points(self, broadcaster_id: str, user_id: str, amount: int) -> None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        UPDATE viewers
        SET points = MAX(points - ?, 0)
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        values = (amount, broadcaster_id, user_id)

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
        except Exception:
            LOGGER.exception(
                "[Points] Failed to remove %d points from user %s for broadcaster %s.",
                amount,
                user_id,
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Points] Removed up to %d points from user %s for broadcaster %s.",
            amount,
            user_id,
            broadcaster_id
        )

    async def set_points(self, broadcaster_id: str, user_id: str, amount: int) -> None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        UPDATE viewers
        SET points = ?
        WHERE broadcaster_id = ?
          AND user_id = ?
        """

        values = (amount, broadcaster_id, user_id)

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
        except Exception:
            LOGGER.exception(
                "[Points] Failed to set points for user %s in broadcaster %s.",
                user_id,
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Points] Set user %s to %d points for broadcaster %s.",
            user_id,
            amount,
            broadcaster_id
        )

    async def reset_all_points(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)

        query = """
        UPDATE viewers
        SET points = 0
        WHERE broadcaster_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id,))
        except Exception:
            LOGGER.exception(
                "[Points] Failed to reset points for broadcaster %s.",
                broadcaster_id
            )
            raise

        LOGGER.warning(
            "[Points] Reset all viewer points for broadcaster %s.",
            broadcaster_id
        )

    async def get_leaderboard(self, broadcaster_id: str, limit: int = 5):
        broadcaster_id = str(broadcaster_id)

        query = """
        SELECT username, points
        FROM viewers
        WHERE broadcaster_id = ?
        ORDER BY points DESC
        LIMIT ?
        """

        try:
            async with self.db.acquire() as connection:
                rows = await connection.fetchall(query, (broadcaster_id, limit))
        except Exception:
            LOGGER.exception(
                "[Points] Failed to load leaderboard for broadcaster %s.",
                broadcaster_id
            )
            raise

        LOGGER.debug(
            "[Points] Loaded %d leaderboard entries for broadcaster %s.",
            len(rows),
            broadcaster_id
        )

        return rows

    def create_duel(self, broadcaster_id: str, challenger_id: str, challenger_name: str, opponent_id: str, opponent_name: str, amount: int, expiration_seconds: int) -> None:
        broadcaster_id = str(broadcaster_id)
        challenger_id = str(challenger_id)
        opponent_id = str(opponent_id)
        duel_key = self._user_key(broadcaster_id, opponent_id)

        self.pending_duels[duel_key] = PendingDuel(
            broadcaster_id=broadcaster_id,
            challenger_id=challenger_id,
            challenger_name=challenger_name,
            opponent_id=opponent_id,
            opponent_name=opponent_name,
            amount=amount,
            expiration_seconds=expiration_seconds,
            created_at=time.time()
        )

        LOGGER.info(
            "[Points] Created duel between %s and %s for %d points in broadcaster %s.",
            challenger_name,
            opponent_name,
            amount,
            broadcaster_id
        )

    def get_duel_for_user(self, broadcaster_id: str, user_id: str) -> PendingDuel | None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        duel_key = self._user_key(broadcaster_id, user_id)
        duel = self.pending_duels.get(duel_key)

        if duel is None:
            return None

        if time.time() - duel.created_at > duel.expiration_seconds:
            self.pending_duels.pop(duel_key, None)

            LOGGER.info(
                "[Points] Duel for %s expired in broadcaster %s.",
                duel.opponent_name,
                broadcaster_id
            )

            return None

        return duel

    def remove_duel_for_user(self, broadcaster_id: str, user_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        duel_key = self._user_key(broadcaster_id, user_id)
        duel = self.pending_duels.pop(duel_key, None)

        if duel is None:
            LOGGER.debug(
                "[Points] No pending duel found for user %s in broadcaster %s.",
                user_id,
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Points] Removed duel between %s and %s for broadcaster %s.",
            duel.challenger_name,
            duel.opponent_name,
            broadcaster_id
        )

    @staticmethod
    def _user_key(broadcaster_id: str, user_id: str) -> str:
        return f"{str(broadcaster_id)}:{str(user_id)}"
    
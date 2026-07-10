import logging
import random
import sqlite3
from dataclasses import dataclass

from config.settings import settings

LOGGER = logging.getLogger("Bot")


@dataclass
class RedeemResult:
    handled: bool
    message: str | None = None


class RedeemService:
    DAILY_REDEEM_TYPE = "daily"
    FIRST_REDEEM_TYPE = "first"

    DAILY_DOUBLE_CHANCE = 0.05
    CLAIM_MILESTONES = {10, 25, 50, 100, 250, 500, 1000}

    def __init__(self, bot, db, points_service):
        self.bot = bot
        self.db = db
        self.points = points_service

    async def setup(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS redeem_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            redeem_type TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            redemption_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

            columns = await connection.fetchall("PRAGMA table_info(redeem_claims)")
            column_names = {column["name"] for column in columns}

            if "stream_id" not in column_names:
                await connection.execute(
                    """
                    ALTER TABLE redeem_claims
                    ADD COLUMN stream_id TEXT NOT NULL DEFAULT 'legacy'
                    """
                )

            await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_daily")
            await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_first")

            await connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_daily
                ON redeem_claims (
                    broadcaster_id,
                    user_id,
                    redeem_type,
                    stream_id
                )
                WHERE redeem_type = 'daily'
                """
            )

            await connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_first
                ON redeem_claims (
                    broadcaster_id,
                    redeem_type,
                    stream_id
                )
                WHERE redeem_type = 'first'
                """
            )

    async def handle_redemption(self, *, broadcaster_id: str, user_id: str, username: str, reward_title: str, redemption_id: str | None = None) -> RedeemResult:
        normalized_reward = reward_title.strip().lower()

        daily_title = settings.DAILY_REDEEM_TITLE.strip().lower()
        first_title = settings.FIRST_REDEEM_TITLE.strip().lower()

        if normalized_reward not in {daily_title, first_title}:
            return RedeemResult(handled=False)

        stream_id = await self.get_current_stream_id(broadcaster_id)

        if stream_id is None:
            return RedeemResult(
                handled=True,
                message=f"@{username}, this redeem only works while the stream is live."
            )

        if normalized_reward == daily_title:
            return await self.claim_daily(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                stream_id=stream_id,
                redemption_id=redemption_id
            )

        if normalized_reward == first_title:
            return await self.claim_first(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                stream_id=stream_id,
                redemption_id=redemption_id
            )

        return RedeemResult(handled=False)

    async def claim_daily(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str, redemption_id: str | None = None) -> RedeemResult:
        try:
            await self._insert_claim(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                redeem_type=self.DAILY_REDEEM_TYPE,
                stream_id=stream_id,
                redemption_id=redemption_id
            )
        except sqlite3.IntegrityError:
            return RedeemResult(
                handled=True,
                message=f"@{username}, you already claimed your stream daily stale bread."
            )

        claim_count = await self.get_claim_count(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            redeem_type=self.DAILY_REDEEM_TYPE
        )

        is_double = self.is_daily_double()
        bread_amount = settings.DAILY_REDEEM_BREAD * 2 if is_double else settings.DAILY_REDEEM_BREAD

        await self.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            amount=bread_amount
        )

        if is_double:
            message = (
                f"Lucky day! @{username} found an extra stale loaf and received "
                f"{bread_amount} bread! They have collected their daily stale bread "
                f"{claim_count} times!"
            )
        else:
            message = (
                f"@{username} claimed their stream daily stale bread and received "
                f"{bread_amount} bread! They have collected their daily stale bread "
                f"{claim_count} times!"
            )

        if self.is_milestone(claim_count):
            message += (
                f" Milestone! @{username} has collected their daily stale bread "
                f"{claim_count} times!"
            )

        return RedeemResult(handled=True, message=message)

    async def claim_first(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str, redemption_id: str | None = None) -> RedeemResult:
        try:
            await self._insert_claim(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                redeem_type=self.FIRST_REDEEM_TYPE,
                stream_id=stream_id,
                redemption_id=redemption_id
            )
        except sqlite3.IntegrityError:
            winner = await self.get_first_winner(
                broadcaster_id=broadcaster_id,
                stream_id=stream_id
            )

            if winner:
                return RedeemResult(
                    handled=True,
                    message=(
                        f"@{username}, this stream's first redeem was already "
                        f"claimed by @{winner}."
                    )
                )

            return RedeemResult(
                handled=True,
                message=f"@{username}, this stream's first redeem was already claimed."
            )

        await self.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            amount=settings.FIRST_REDEEM_BREAD
        )

        claim_count = await self.get_claim_count(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            redeem_type=self.FIRST_REDEEM_TYPE
        )

        message = (
            f"@{username} was first in the basement this stream and received "
            f"{settings.FIRST_REDEEM_BREAD} bread! They have stolen the first bread "
            f"{claim_count} times!"
        )

        if self.is_milestone(claim_count):
            message += (
                f" Milestone! @{username} has stolen the first bread "
                f"{claim_count} times!"
            )

        return RedeemResult(handled=True, message=message)

    async def get_claim_count(self, *, broadcaster_id: str, user_id: str, redeem_type: str) -> int:
        query = """
        SELECT COUNT(*) AS claim_count
        FROM redeem_claims
        WHERE broadcaster_id = ?
          AND user_id = ?
          AND redeem_type = ?
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(
                query,
                (
                    broadcaster_id,
                    user_id,
                    redeem_type
                )
            )

        if not row:
            return 0

        return int(row["claim_count"])

    async def get_first_winner(self, *, broadcaster_id: str, stream_id: str) -> str | None:
        query = """
        SELECT username
        FROM redeem_claims
        WHERE broadcaster_id = ?
          AND redeem_type = ?
          AND stream_id = ?
        LIMIT 1
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(
                query,
                (
                    broadcaster_id,
                    self.FIRST_REDEEM_TYPE,
                    stream_id
                )
            )

        if not row:
            return None

        return row["username"]

    async def get_current_stream_id(self, broadcaster_id: str) -> str | None:
        try:
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            stream = await broadcaster.fetch_stream()

            if stream is None:
                return None

            stream_id = getattr(stream, "id", None)

            if stream_id is None:
                stream_id = getattr(stream, "stream_id", None)

            if stream_id is None:
                LOGGER.warning(
                    "Live stream object for broadcaster %s did not expose an id: %r",
                    broadcaster_id,
                    stream
                )
                return None

            return str(stream_id)

        except Exception as error:
            LOGGER.error(
                "Failed to fetch current stream for broadcaster %s: %r",
                broadcaster_id,
                error
            )
            return None

    def is_daily_double(self) -> bool:
        return random.random() < self.DAILY_DOUBLE_CHANCE

    def is_milestone(self, claim_count: int) -> bool:
        return claim_count in self.CLAIM_MILESTONES

    async def _insert_claim(self, *, broadcaster_id: str, user_id: str, username: str, redeem_type: str, stream_id: str, redemption_id: str | None = None) -> None:
        query = """
        INSERT INTO redeem_claims (
            broadcaster_id,
            user_id,
            username,
            redeem_type,
            stream_id,
            redemption_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """

        async with self.db.acquire() as connection:
            await connection.execute(
                query,
                (
                    broadcaster_id,
                    user_id,
                    username,
                    redeem_type,
                    stream_id,
                    redemption_id
                )
            )

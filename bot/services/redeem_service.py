import logging
import random
import sqlite3
from dataclasses import dataclass

from bot.profiles import FeatureName, RedeemConfig, get_active_profile, render_profile_message

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class RedeemResult:
    handled: bool
    message: str | None = None


class RedeemService:
    DAILY_REDEEM_TYPE = "daily"
    FIRST_REDEEM_TYPE = "first"

    def __init__(self, bot, db, points_service):
        self.bot = bot
        self.db = db
        self.points = points_service

    async def setup(self) -> None:

        LOGGER.info("[Redeems] Preparing redeem claim storage.")

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

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query)

                columns = await connection.fetchall(
                    "PRAGMA table_info(redeem_claims)"
                )

                column_names = {
                    column["name"]
                    for column in columns
                }

                if "stream_id" not in column_names:
                    LOGGER.warning(
                        "[Redeems] Adding stream ID support to legacy redeem claim storage."
                    )

                    await connection.execute(
                        """
                        ALTER TABLE redeem_claims
                        ADD COLUMN stream_id TEXT NOT NULL DEFAULT 'legacy'
                        """
                    )

                await connection.execute(
                    "DROP INDEX IF EXISTS idx_redeem_claims_daily"
                )

                await connection.execute(
                    "DROP INDEX IF EXISTS idx_redeem_claims_first"
                )

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
        except Exception:
            LOGGER.exception("[Redeems] Failed to prepare redeem claim storage.")
            raise

        LOGGER.info("[Redeems] Redeem claim storage ready.")

    async def handle_redemption(self, *, broadcaster_id: str, user_id: str, username: str, reward_title: str,
                                redemption_id: str | None = None) -> RedeemResult:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        config = self.get_redeem_config(broadcaster_id)

        if config is None:
            return RedeemResult(handled=False)

        normalized_reward = reward_title.strip().lower()
        daily_title = config.daily_title.strip().lower()
        first_title = config.first_title.strip().lower()

        if normalized_reward not in {
            daily_title,
            first_title
        }:
            return RedeemResult(handled=False)

        LOGGER.info(
            "[Redeems] Processing %s redeem from %s for broadcaster %s.",
            normalized_reward,
            username,
            broadcaster_id
        )

        stream_id = await self.get_current_stream_id(broadcaster_id)

        if stream_id is None:
            LOGGER.info(
                "[Redeems] Rejected redeem from %s because broadcaster %s is offline.",
                username,
                broadcaster_id
            )

            message = render_profile_message(
                config.messages.stream_offline,
                username=username
            )

            return RedeemResult(
                handled=True,
                message=message
            )

        if normalized_reward == daily_title:
            return await self.claim_daily(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                stream_id=stream_id,
                config=config,
                redemption_id=redemption_id
            )

        if normalized_reward == first_title:
            return await self.claim_first(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                stream_id=stream_id,
                config=config,
                redemption_id=redemption_id
            )

        return RedeemResult(handled=False)

    async def claim_daily(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str,
                          config: RedeemConfig, redemption_id: str | None = None) -> RedeemResult:

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
            LOGGER.debug(
                "[Redeems] User %s already claimed the daily reward for stream %s.",
                username,
                stream_id
            )

            message = render_profile_message(
                config.messages.daily_already_claimed,
                username=username
            )

            return RedeemResult(
                handled=True,
                message=message
            )

        claim_count = await self.get_claim_count(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            redeem_type=self.DAILY_REDEEM_TYPE
        )

        is_double = self.is_daily_double(config)
        amount = config.daily_amount * 2 if is_double else config.daily_amount

        await self.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            amount=amount
        )

        LOGGER.info(
            "[Redeems] User %s claimed %d daily points for broadcaster %s%s.",
            username,
            amount,
            broadcaster_id,
            " with a double reward" if is_double else ""
        )

        template = (
            config.messages.daily_double
            if is_double
            else config.messages.daily_success
        )

        message = render_profile_message(
            template,
            username=username,
            amount=amount,
            claim_count=claim_count
        )

        if self.is_milestone(config, claim_count):
            LOGGER.info(
                "[Redeems] User %s reached daily claim milestone %d.",
                username,
                claim_count
            )

            milestone = render_profile_message(
                config.messages.daily_milestone,
                username=username,
                amount=amount,
                claim_count=claim_count
            )

            if milestone:
                message = f"{message or ''}{milestone}"

        return RedeemResult(
            handled=True,
            message=message
        )

    async def claim_first(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str,
                          config: RedeemConfig, redemption_id: str | None = None) -> RedeemResult:

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

            LOGGER.debug(
                "[Redeems] First reward for stream %s was already claimed by %s.",
                stream_id,
                winner or "an unknown viewer"
            )

            if winner:
                message = render_profile_message(
                    config.messages.first_already_claimed_by,
                    username=username,
                    winner=winner
                )
            else:
                message = render_profile_message(
                    config.messages.first_already_claimed,
                    username=username
                )

            return RedeemResult(
                handled=True,
                message=message
            )

        await self.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            amount=config.first_amount
        )

        claim_count = await self.get_claim_count(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            redeem_type=self.FIRST_REDEEM_TYPE
        )

        LOGGER.info(
            "[Redeems] User %s claimed first for stream %s and received %d points.",
            username,
            stream_id,
            config.first_amount
        )

        message = render_profile_message(
            config.messages.first_success,
            username=username,
            amount=config.first_amount,
            claim_count=claim_count
        )

        if self.is_milestone(config, claim_count):
            LOGGER.info(
                "[Redeems] User %s reached first-claim milestone %d.",
                username,
                claim_count
            )

            milestone = render_profile_message(
                config.messages.first_milestone,
                username=username,
                amount=config.first_amount,
                claim_count=claim_count
            )

            if milestone:
                message = f"{message or ''}{milestone}"

        return RedeemResult(
            handled=True,
            message=message
        )

    async def get_claim_count(self, *, broadcaster_id: str, user_id: str, redeem_type: str) -> int:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        SELECT COUNT(*) AS claim_count
        FROM redeem_claims
        WHERE broadcaster_id = ?
          AND user_id = ?
          AND redeem_type = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        broadcaster_id,
                        user_id,
                        redeem_type
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to load %s claim count for user %s in broadcaster %s.",
                redeem_type,
                user_id,
                broadcaster_id
            )
            raise

        if not row:
            return 0

        return int(row["claim_count"])

    async def get_first_winner(self, *, broadcaster_id: str, stream_id: str) -> str | None:

        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)

        query = """
        SELECT username
        FROM redeem_claims
        WHERE broadcaster_id = ?
          AND redeem_type = ?
          AND stream_id = ?
        LIMIT 1
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        broadcaster_id,
                        self.FIRST_REDEEM_TYPE,
                        stream_id
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to load first winner for stream %s.",
                stream_id
            )
            raise

        if not row:
            return None

        return row["username"]

    async def get_current_stream_id(self, broadcaster_id: str) -> str | None:

        broadcaster_id = str(broadcaster_id)

        try:
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            stream = await broadcaster.fetch_stream()
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to fetch current stream for broadcaster %s.",
                broadcaster_id
            )
            return None

        if stream is None:
            return None

        stream_id = getattr(stream, "id", None)

        if stream_id is None:
            stream_id = getattr(stream, "stream_id", None)

        if stream_id is None:
            LOGGER.warning(
                "[Redeems] Live stream object for broadcaster %s did not expose a stream ID: %r",
                broadcaster_id,
                stream
            )
            return None

        return str(stream_id)

    def get_redeem_config(self, broadcaster_id: str) -> RedeemConfig | None:

        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return None

        if not self.bot.services:
            return None

        if not self.bot.services.features.is_enabled(broadcaster_id, FeatureName.REDEEMS):
            return None

        return profile.redeems

    @staticmethod
    def is_daily_double(config: RedeemConfig) -> bool:

        return random.random() < config.daily_double_chance

    @staticmethod
    def is_milestone(config: RedeemConfig, claim_count: int) -> bool:

        return claim_count in config.claim_milestones

    async def _insert_claim(self, *, broadcaster_id: str, user_id: str, username: str, redeem_type: str, stream_id: str,
                            redemption_id: str | None = None) -> None:

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

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        str(broadcaster_id),
                        str(user_id),
                        username,
                        redeem_type,
                        str(stream_id),
                        redemption_id
                    )
                )
        except sqlite3.IntegrityError:
            raise
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to save %s claim for user %s in broadcaster %s.",
                redeem_type,
                username,
                broadcaster_id
            )
            raise

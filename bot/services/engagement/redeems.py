import asyncio
import logging
import random
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from bot.profiles import FeatureName, RedeemConfig, TargetTimeoutRedeemConfig, get_active_profile, render_profile_message

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class RedeemResult:
    handled: bool
    message: str | None = None


class RedeemService:
    DAILY_REDEEM_TYPE = "daily"
    FIRST_REDEEM_TYPE = "first"
    SECOND_REDEEM_TYPE = "second"
    MODERATOR_RESTORE_BUFFER_SECONDS = 2

    def __init__(self, bot, db, points_service, counter_service=None):
        self.bot = bot
        self.db = db
        self.points = points_service
        self.counters = counter_service
        self._moderator_restore_tasks: set[asyncio.Task] = set()

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

                columns = await connection.fetchall("PRAGMA table_info(redeem_claims)")
                column_names = {column["name"] for column in columns}

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

                await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_daily")
                await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_first")
                await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_second")

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
                    CREATE TABLE IF NOT EXISTS redemption_events (
                        redemption_id TEXT PRIMARY KEY,
                        broadcaster_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        reward_title TEXT NOT NULL,
                        user_input TEXT,
                        stream_id TEXT,
                        redeemed_at TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_redemption_events_stream
                    ON redemption_events (
                        broadcaster_id,
                        stream_id,
                        redeemed_at
                    )
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

                await connection.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_second
                    ON redeem_claims (
                        broadcaster_id,
                        redeem_type,
                        stream_id
                    )
                    WHERE redeem_type = 'second'
                    """
                )
        except Exception:
            LOGGER.exception("[Redeems] Failed to prepare redeem claim storage.")
            raise

        LOGGER.info("[Redeems] Redeem claim storage ready.")

    async def record_activity(self, *, redemption_id: str | None, broadcaster_id: str, user_id: str,
                              username: str, reward_title: str, user_input: str | None,
                              stream_id: str | None, redeemed_at=None) -> bool:
        if not redemption_id:
            LOGGER.warning(
                "[Redeems] Could not save redemption activity for %s because its ID was missing.",
                username
            )
            return False

        if isinstance(redeemed_at, datetime):
            if redeemed_at.tzinfo is None:
                redeemed_at_value = redeemed_at.replace(tzinfo=UTC).isoformat()
            else:
                redeemed_at_value = redeemed_at.astimezone(UTC).isoformat()
        elif redeemed_at:
            redeemed_at_value = str(redeemed_at)
        else:
            redeemed_at_value = datetime.now(UTC).isoformat()

        query = """
        INSERT OR IGNORE INTO redemption_events (
            redemption_id,
            broadcaster_id,
            user_id,
            username,
            reward_title,
            user_input,
            stream_id,
            redeemed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        values = (
            str(redemption_id),
            str(broadcaster_id),
            str(user_id),
            username,
            reward_title,
            user_input or None,
            str(stream_id) if stream_id is not None else None,
            redeemed_at_value
        )

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
                change_row = await connection.fetchone(
                    "SELECT changes() AS inserted"
                )
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to save redemption activity for %s in broadcaster %s.",
                username,
                broadcaster_id
            )
            raise

        return bool(change_row and change_row["inserted"])

    async def get_latest_stream_id(self, broadcaster_id: str) -> str | None:
        query = """
        SELECT stream_id
        FROM (
            SELECT stream_id, created_at AS activity_at
            FROM redemption_events
            WHERE broadcaster_id = ?
              AND stream_id IS NOT NULL

            UNION ALL

            SELECT stream_id, created_at AS activity_at
            FROM redeem_claims
            WHERE broadcaster_id = ?
              AND stream_id != 'legacy'
        )
        ORDER BY activity_at DESC
        LIMIT 1
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (str(broadcaster_id), str(broadcaster_id)))
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to find the latest redemption stream for broadcaster %s.",
                broadcaster_id
            )
            raise

        return str(row["stream_id"]) if row else None

    async def get_dashboard_activity(self, *, broadcaster_id: str, stream_id: str | None,
                                     limit: int = 100) -> dict[str, object]:
        if stream_id is None:
            return {"stream_id": None, "checkins": [], "redemptions": []}

        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)
        safe_limit = max(1, min(int(limit), 200))

        claims_query = """
        SELECT username, redeem_type, created_at
        FROM redeem_claims
        WHERE broadcaster_id = ?
          AND stream_id = ?
        ORDER BY created_at ASC, id ASC
        LIMIT ?
        """

        redemptions_query = """
        SELECT redemption_id, username, reward_title, user_input, redeemed_at
        FROM redemption_events
        WHERE broadcaster_id = ?
          AND stream_id = ?
        ORDER BY redeemed_at DESC
        LIMIT ?
        """

        try:
            async with self.db.acquire() as connection:
                claim_rows = await connection.fetchall(
                    claims_query,
                    (broadcaster_id, stream_id, safe_limit)
                )
                redemption_rows = await connection.fetchall(
                    redemptions_query,
                    (broadcaster_id, stream_id, safe_limit)
                )
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to load dashboard activity for broadcaster %s stream %s.",
                broadcaster_id,
                stream_id
            )
            raise

        config = self.get_redeem_config(broadcaster_id)
        excluded_titles: set[str] = set()

        if config is not None:
            excluded_titles = {
                title.strip().lower()
                for title in (config.daily_title, config.first_title, config.second_title)
                if title.strip()
            }

        checkins = [
            {
                "username": row["username"],
                "type": row["redeem_type"],
                "redeemed_at": row["created_at"]
            }
            for row in claim_rows
        ]

        redemptions = [
            {
                "id": row["redemption_id"],
                "username": row["username"],
                "reward_title": row["reward_title"],
                "user_input": row["user_input"],
                "redeemed_at": row["redeemed_at"]
            }
            for row in redemption_rows
            if row["reward_title"].strip().lower() not in excluded_titles
        ]

        return {
            "stream_id": stream_id,
            "checkins": checkins,
            "redemptions": redemptions
        }

    async def handle_redemption(self, *, broadcaster_id: str, user_id: str, username: str, reward_title: str,
                                redemption_id: str | None = None, stream_id: str | None = None) -> RedeemResult:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        config = self.get_redeem_config(broadcaster_id)

        if config is None:
            return RedeemResult(handled=False)

        normalized_reward = reward_title.strip().lower()
        daily_title = config.daily_title.strip().lower()
        first_title = config.first_title.strip().lower()
        second_title = config.second_title.strip().lower()
        timeout_title = config.timeout.title.strip().lower()
        target_timeout = next((timeout for timeout in config.target_timeouts if timeout.title.strip().lower() == normalized_reward), None)
        handled_titles = {title for title in (daily_title, first_title, second_title, timeout_title) if title}

        if normalized_reward not in handled_titles and target_timeout is None:
            return RedeemResult(handled=False)

        LOGGER.info(
            "[Redeems] Processing %s redeem from %s for broadcaster %s.",
            normalized_reward,
            username,
            broadcaster_id
        )

        if stream_id is None:
            stream_id = await self.get_current_stream_id(broadcaster_id)

        if stream_id is None:
            LOGGER.info(
                "[Redeems] Rejected redeem from %s because broadcaster %s is offline.",
                username,
                broadcaster_id
            )

            message = render_profile_message(config.messages.stream_offline, username=username)
            return RedeemResult(handled=True, message=message)

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

        if normalized_reward == second_title:
            return await self.claim_second(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                stream_id=stream_id,
                config=config,
                redemption_id=redemption_id
            )

        if normalized_reward == timeout_title:
            return await self.timeout_redeemer(broadcaster_id=broadcaster_id, user_id=user_id, username=username, config=config)

        if target_timeout is not None:
            return await self.timeout_target(broadcaster_id=broadcaster_id, redeemer_username=username, timeout=target_timeout)

        return RedeemResult(handled=False)

    async def claim_daily(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str, config: RedeemConfig, redemption_id: str | None = None) -> RedeemResult:
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

            message = render_profile_message(config.messages.daily_already_claimed, username=username)
            return RedeemResult(handled=True, message=message)

        claim_count = await self.get_claim_count(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            redeem_type=self.DAILY_REDEEM_TYPE
        )

        is_double = self.is_daily_double(config)

        if is_double:
            amount = config.daily_amount * 2
            template = config.messages.daily_double
        else:
            amount = config.daily_amount
            template = config.messages.daily_success

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

        return RedeemResult(handled=True, message=message)

    async def claim_first(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str, config: RedeemConfig, redemption_id: str | None = None) -> RedeemResult:
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
            winner = await self.get_first_winner(broadcaster_id=broadcaster_id, stream_id=stream_id)

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
                message = render_profile_message(config.messages.first_already_claimed, username=username)

            return RedeemResult(handled=True, message=message)

        if config.first_amount > 0:
            await self.points.add_points(broadcaster_id=broadcaster_id, user_id=user_id, username=username, amount=config.first_amount)

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

        return RedeemResult(handled=True, message=message)

    async def claim_second(self, *, broadcaster_id: str, user_id: str, username: str, stream_id: str, config: RedeemConfig, redemption_id: str | None = None) -> RedeemResult:
        try:
            await self._insert_claim(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                redeem_type=self.SECOND_REDEEM_TYPE,
                stream_id=stream_id,
                redemption_id=redemption_id
            )
        except sqlite3.IntegrityError:
            winner = await self.get_position_winner(broadcaster_id=broadcaster_id, stream_id=stream_id, redeem_type=self.SECOND_REDEEM_TYPE)
            LOGGER.debug("[Redeems] Second reward for stream %s was already claimed by %s.", stream_id, winner or "an unknown viewer")

            if winner:
                message = render_profile_message(config.messages.second_already_claimed_by, username=username, winner=winner)
            else:
                message = render_profile_message(config.messages.second_already_claimed, username=username)

            return RedeemResult(handled=True, message=message)

        if config.second_amount > 0:
            await self.points.add_points(broadcaster_id=broadcaster_id, user_id=user_id, username=username, amount=config.second_amount)

        claim_count = await self.get_claim_count(broadcaster_id=broadcaster_id, user_id=user_id, redeem_type=self.SECOND_REDEEM_TYPE)
        LOGGER.info("[Redeems] User %s claimed second for stream %s and received %d points.", username, stream_id, config.second_amount)
        message = render_profile_message(config.messages.second_success, username=username, amount=config.second_amount, claim_count=claim_count)

        if self.is_milestone(config, claim_count):
            milestone = render_profile_message(config.messages.second_milestone, username=username, amount=config.second_amount, claim_count=claim_count)

            if milestone:
                message = f"{message or ''}{milestone}"

        return RedeemResult(handled=True, message=message)

    async def timeout_redeemer(self, *, broadcaster_id: str, user_id: str, username: str, config: RedeemConfig) -> RedeemResult:
        timeout = config.timeout
        broadcaster = self.bot.create_partialuser(broadcaster_id)
        was_moderator = False

        if timeout.restore_moderator:
            was_moderator = await self.is_moderator(broadcaster, broadcaster_id, user_id, username)

        try:
            await broadcaster.timeout_user(moderator=broadcaster_id, user=user_id, duration=timeout.duration_seconds, reason=timeout.reason)
        except Exception:
            LOGGER.exception("[Redeems] Failed to time out user %s in broadcaster %s.", username, broadcaster_id)
            message = render_profile_message(config.messages.timeout_failed, username=username)
            return RedeemResult(handled=True, message=message)

        if was_moderator:
            self.schedule_moderator_restoration(
                broadcaster=broadcaster,
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                delay_seconds=timeout.duration_seconds + self.MODERATOR_RESTORE_BUFFER_SECONDS
            )

        minutes = timeout.duration_seconds // 60
        LOGGER.info("[Redeems] Timed out user %s for %d seconds in broadcaster %s.", username, timeout.duration_seconds, broadcaster_id)
        message = render_profile_message(config.messages.timeout_success, username=username, minutes=minutes, seconds=timeout.duration_seconds)
        return RedeemResult(handled=True, message=message)

    async def is_moderator(self, broadcaster, broadcaster_id: str, user_id: str, username: str) -> bool:
        try:
            moderators = broadcaster.fetch_moderators(user_ids=[user_id], max_results=1)

            async for moderator in moderators:
                if str(moderator.id) == str(user_id):
                    return True
        except Exception:
            LOGGER.exception("[Redeems] Failed to check moderator status for %s in broadcaster %s.", username, broadcaster_id)

        return False

    async def restore_moderator(self, *, broadcaster, broadcaster_id: str, user_id: str, username: str, delay_seconds: int) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            await broadcaster.add_moderator(user=user_id)
        except asyncio.CancelledError:
            LOGGER.debug("[Redeems] Moderator restoration was cancelled for %s in broadcaster %s.", username, broadcaster_id)
            raise
        except Exception:
            LOGGER.exception("[Redeems] Failed to restore moderator status for %s in broadcaster %s.", username, broadcaster_id)
            return

        LOGGER.info("[Redeems] Restored moderator status for %s in broadcaster %s.", username, broadcaster_id)

    def schedule_moderator_restoration(self, *, broadcaster, broadcaster_id: str, user_id: str, username: str, delay_seconds: int) -> None:
        task = asyncio.create_task(
            self.restore_moderator(
                broadcaster=broadcaster,
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                delay_seconds=delay_seconds
            ),
            name=f"restore-redeem-moderator-{broadcaster_id}-{user_id}"
        )
        self._moderator_restore_tasks.add(task)
        task.add_done_callback(self._moderator_restore_tasks.discard)

        LOGGER.info("[Redeems] Scheduled moderator restoration for %s in broadcaster %s after %d seconds.", username, broadcaster_id, delay_seconds)

    async def timeout_target(self, *, broadcaster_id: str, redeemer_username: str, timeout: TargetTimeoutRedeemConfig) -> RedeemResult:
        broadcaster = self.bot.create_partialuser(broadcaster_id)

        try:
            await broadcaster.timeout_user(moderator=broadcaster_id, user=timeout.target_user_id, duration=timeout.duration_seconds, reason=timeout.reason)
        except Exception:
            LOGGER.exception("[Redeems] Failed to time out target %s in broadcaster %s.", timeout.target_username, broadcaster_id)
            message = render_profile_message(timeout.failure_message, username=redeemer_username, target_username=timeout.target_username)
            return RedeemResult(handled=True, message=message)

        minutes = timeout.duration_seconds // 60
        hours = timeout.duration_seconds // 3600
        LOGGER.info("[Redeems] User %s redeemed a %d-second timeout for target %s in broadcaster %s.", redeemer_username, timeout.duration_seconds, timeout.target_username, broadcaster_id)
        message = render_profile_message(
            timeout.success_message,
            username=redeemer_username,
            target_username=timeout.target_username,
            minutes=minutes,
            hours=hours,
            seconds=timeout.duration_seconds
        )

        if timeout.counter_name and timeout.counter_message and self.counters is not None:
            counter_key = f"target_timeout:{broadcaster_id}:{timeout.counter_name}"

            try:
                counter_value = await self.counters.increment_counter(counter_key)
            except Exception:
                LOGGER.exception("[Redeems] Failed to increment target-timeout counter %s for broadcaster %s.", timeout.counter_name, broadcaster_id)
            else:
                counter_message = render_profile_message(
                    timeout.counter_message,
                    username=redeemer_username,
                    target_username=timeout.target_username,
                    count=counter_value,
                    count_word="time" if counter_value == 1 else "times"
                )

                if counter_message:
                    message = f"{message or ''} {counter_message}".strip()

        return RedeemResult(handled=True, message=message)

    async def get_claim_count(self, *, broadcaster_id: str, user_id: str, redeem_type: str) -> int:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM redeem_claims
                WHERE broadcaster_id = ?
                  AND user_id = ?
                  AND redeem_type = ?
            ) + (
                SELECT COALESCE(SUM(claim_count), 0)
                FROM imported_redeem_totals
                WHERE broadcaster_id = ?
                  AND user_id = ?
                  AND redeem_type = ?
            ) AS claim_count
        """

        values = (
            broadcaster_id,
            user_id,
            redeem_type,
            broadcaster_id,
            user_id,
            redeem_type
        )

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, values)
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
        return await self.get_position_winner(broadcaster_id=broadcaster_id, stream_id=stream_id, redeem_type=self.FIRST_REDEEM_TYPE)

    async def get_position_winner(self, *, broadcaster_id: str, stream_id: str, redeem_type: str) -> str | None:
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
                row = await connection.fetchone(query, (broadcaster_id, redeem_type, stream_id))
        except Exception:
            LOGGER.exception(
                "[Redeems] Failed to load %s winner for stream %s.",
                redeem_type,
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
        services = self.bot.services

        if profile is None:
            return None

        if services is None:
            return None

        if not services.features.is_enabled(broadcaster_id, FeatureName.REDEEMS):
            return None

        return profile.redeems

    @staticmethod
    def is_daily_double(config: RedeemConfig) -> bool:
        return random.random() < config.daily_double_chance

    @staticmethod
    def is_milestone(config: RedeemConfig, claim_count: int) -> bool:
        return claim_count in config.claim_milestones

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

        values = (
            str(broadcaster_id),
            str(user_id),
            username,
            redeem_type,
            str(stream_id),
            redemption_id
        )

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, values)
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

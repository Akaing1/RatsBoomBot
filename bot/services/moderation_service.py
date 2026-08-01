import logging
from dataclasses import dataclass
from enum import StrEnum

LOGGER = logging.getLogger("RatBoomBot")


class ModerationAction(StrEnum):

    ALLOW = "allow"
    FLAG = "flag"
    BAN = "ban"


@dataclass(frozen=True)
class ModerationResult:

    action: ModerationAction
    reason: str
    source: str = "moderation_service"

    @property
    def should_allow(self) -> bool:
        return self.action == ModerationAction.ALLOW

    @property
    def should_flag(self) -> bool:
        return self.action == ModerationAction.FLAG

    @property
    def should_ban(self) -> bool:
        return self.action == ModerationAction.BAN


class ModerationService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def setup(self) -> None:

        LOGGER.info("[Moderation] Preparing moderation storage.")

        known_bots_query = """
        CREATE TABLE IF NOT EXISTS known_bots (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        allowlist_query = """
        CREATE TABLE IF NOT EXISTS moderation_allowlist (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        actions_query = """
        CREATE TABLE IF NOT EXISTS moderation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT,
            successful INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(known_bots_query)
                await connection.execute(allowlist_query)
                await connection.execute(actions_query)
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to prepare moderation storage."
            )
            raise

        LOGGER.info("[Moderation] Moderation storage ready.")

    async def evaluate_message(self, payload) -> ModerationResult:

        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name

        if self.is_protected_user(
            broadcaster_id,
            user_id
        ):
            return ModerationResult(
                action=ModerationAction.ALLOW,
                reason="Protected broadcaster or bot account."
            )

        if await self.is_allowlisted(user_id):
            LOGGER.debug(
                "[Moderation] Allowlisted user %s (%s) was permitted in broadcaster %s.",
                username,
                user_id,
                broadcaster_id
            )

            return ModerationResult(
                action=ModerationAction.ALLOW,
                reason="User is present in the moderation allowlist.",
                source="allowlist"
            )

        known_bot = await self.get_known_bot(user_id)

        if known_bot is not None:
            reason = known_bot["reason"]
            source = known_bot["source"]

            LOGGER.warning(
                "[Moderation] Known bot %s (%s) detected in broadcaster %s. Source: %s. Reason: %s",
                username,
                user_id,
                broadcaster_id,
                source,
                reason
            )

            return ModerationResult(
                action=ModerationAction.BAN,
                reason=reason,
                source=source
            )

        return ModerationResult(
            action=ModerationAction.ALLOW,
            reason="No confirmed bot match was found."
        )

    async def ban_user(self, payload, result: ModerationResult) -> bool:

        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name
        message = payload.text

        if self.is_protected_user(
            broadcaster_id,
            user_id
        ):
            LOGGER.warning(
                "[Moderation] Refused to ban protected user %s (%s) in broadcaster %s.",
                username,
                user_id,
                broadcaster_id
            )

            await self.record_action(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                action=ModerationAction.ALLOW,
                reason="Ban prevented because the user is protected.",
                source="protected_user",
                message=message,
                successful=False
            )

            return False

        channel = self.bot.create_partialuser(
            broadcaster_id
        )

        try:
            await channel.ban_user(
                moderator=broadcaster_id,
                user=user_id,
                reason=f"Automated bot detection: {result.reason}"
            )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to ban detected bot %s (%s) in broadcaster %s.",
                username,
                user_id,
                broadcaster_id
            )

            await self.record_action(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                action=ModerationAction.BAN,
                reason=result.reason,
                source=result.source,
                message=message,
                successful=False
            )

            return False

        await self.record_action(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            action=ModerationAction.BAN,
            reason=result.reason,
            source=result.source,
            message=message,
            successful=True
        )

        LOGGER.warning(
            "[Moderation] Banned detected bot %s (%s) in broadcaster %s. Reason: %s",
            username,
            user_id,
            broadcaster_id,
            result.reason
        )

        return True

    async def flag_user(self, payload, result: ModerationResult) -> None:

        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name
        message = payload.text

        await self.record_action(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            action=ModerationAction.FLAG,
            reason=result.reason,
            source=result.source,
            message=message,
            successful=True
        )

        LOGGER.warning(
            "[Moderation] Flagged user %s (%s) in broadcaster %s. Reason: %s",
            username,
            user_id,
            broadcaster_id,
            result.reason
        )

    async def add_known_bot(self, user_id: str, username: str | None, reason: str, source: str = "manual") -> None:

        user_id = str(user_id)

        query = """
        INSERT INTO known_bots (
            user_id,
            username,
            reason,
            source
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            reason = excluded.reason,
            source = excluded.source
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        user_id,
                        username,
                        reason,
                        source
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to add known bot %s (%s).",
                username or "unknown",
                user_id
            )
            raise

        LOGGER.info(
            "[Moderation] Added known bot %s (%s). Source: %s. Reason: %s",
            username or "unknown",
            user_id,
            source,
            reason
        )

    async def remove_known_bot(self, user_id: str) -> bool:

        user_id = str(user_id)

        query = """
        DELETE FROM known_bots
        WHERE user_id = ?
        RETURNING user_id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (user_id,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to remove known bot %s.",
                user_id
            )
            raise

        if row is None:
            LOGGER.debug(
                "[Moderation] Known bot %s was not found.",
                user_id
            )
            return False

        LOGGER.info(
            "[Moderation] Removed user %s from the known bot list.",
            user_id
        )

        return True

    async def allow_user(self, user_id: str, username: str | None = None, reason: str | None = None) -> None:

        user_id = str(user_id)

        query = """
        INSERT INTO moderation_allowlist (
            user_id,
            username,
            reason
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            reason = excluded.reason
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        user_id,
                        username,
                        reason
                    )
                )

                await connection.execute(
                    """
                    DELETE FROM known_bots
                    WHERE user_id = ?
                    """,
                    (user_id,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to allowlist user %s (%s).",
                username or "unknown",
                user_id
            )
            raise

        LOGGER.info(
            "[Moderation] Allowlisted user %s (%s).",
            username or "unknown",
            user_id
        )

    async def remove_allowed_user(self, user_id: str) -> bool:

        user_id = str(user_id)

        query = """
        DELETE FROM moderation_allowlist
        WHERE user_id = ?
        RETURNING user_id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (user_id,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to remove allowlisted user %s.",
                user_id
            )
            raise

        if row is None:
            return False

        LOGGER.info(
            "[Moderation] Removed user %s from the moderation allowlist.",
            user_id
        )

        return True

    async def is_known_bot(self, user_id: str) -> bool:

        return await self.get_known_bot(
            str(user_id)
        ) is not None

    async def get_known_bot(self, user_id: str):

        user_id = str(user_id)

        query = """
        SELECT user_id, username, reason, source
        FROM known_bots
        WHERE user_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                return await connection.fetchone(
                    query,
                    (user_id,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to check known bot status for user %s.",
                user_id
            )
            raise

    async def is_allowlisted(self, user_id: str) -> bool:

        user_id = str(user_id)

        query = """
        SELECT 1
        FROM moderation_allowlist
        WHERE user_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (user_id,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to check allowlist status for user %s.",
                user_id
            )
            raise

        return row is not None

    async def record_action(self, broadcaster_id: str, user_id: str, username: str, action: ModerationAction, reason: str, source: str, message: str | None = None, successful: bool = True) -> None:

        query = """
        INSERT INTO moderation_actions (
            broadcaster_id,
            user_id,
            username,
            action,
            reason,
            source,
            message,
            successful
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        str(broadcaster_id),
                        str(user_id),
                        username,
                        action.value,
                        reason,
                        source,
                        message,
                        int(successful)
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to record %s action for user %s in broadcaster %s.",
                action.value,
                user_id,
                broadcaster_id
            )

    def is_protected_user(self, broadcaster_id: str, user_id: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        if broadcaster_id == user_id:
            return True

        bot_id = getattr(
            self.bot,
            "bot_id",
            None
        )

        if bot_id is None:
            bot_user = getattr(
                self.bot,
                "user",
                None
            )

            bot_id = getattr(
                bot_user,
                "id",
                None
            )

        if bot_id is None:
            return False

        return user_id == str(bot_id)

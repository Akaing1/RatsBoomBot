import hashlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

LOGGER = logging.getLogger("RatBoomBot")

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\u2060\uFEFF]")
WHITESPACE_PATTERN = re.compile(r"\s+")
NON_TEXT_PATTERN = re.compile(r"[^\w\s:/?&.=#@+\-]", re.UNICODE)

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term"
}


class ModerationAction(StrEnum):

    ALLOW = "allow"
    FLAG = "flag"
    BAN = "ban"


@dataclass(frozen=True)
class ModerationResult:

    action: ModerationAction
    reason: str
    source: str = "moderation_service"
    campaign_id: int | None = None
    fingerprint: str | None = None

    @property
    def should_allow(self) -> bool:
        return self.action == ModerationAction.ALLOW

    @property
    def should_flag(self) -> bool:
        return self.action == ModerationAction.FLAG

    @property
    def should_ban(self) -> bool:
        return self.action == ModerationAction.BAN


@dataclass
class RecentMessage:

    broadcaster_id: str
    user_id: str
    username: str
    message: str
    normalized_message: str
    fingerprint: str
    created_at: float


class ModerationService:

    RECENT_MESSAGE_TTL_SECONDS = 120
    REQUIRED_EXTERNAL_OBSERVATIONS = 2

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.recent_messages: dict[str, RecentMessage] = {}

    async def setup(self) -> None:

        LOGGER.info("[Moderation] Preparing moderation storage.")

        campaigns_query = """
        CREATE TABLE IF NOT EXISTS moderation_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL UNIQUE,
            normalized_message TEXT NOT NULL,
            example_message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            confidence INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            reason TEXT,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        observations_query = """
        CREATE TABLE IF NOT EXISTS moderation_campaign_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            moderator_id TEXT,
            moderator_name TEXT,
            observed_action TEXT NOT NULL,
            source TEXT NOT NULL,
            reason TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES moderation_campaigns(id),
            UNIQUE (
                campaign_id,
                broadcaster_id,
                observed_action,
                source
            )
        )
        """

        accounts_query = """
        CREATE TABLE IF NOT EXISTS moderation_campaign_accounts (
            campaign_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (campaign_id, user_id),
            FOREIGN KEY (campaign_id) REFERENCES moderation_campaigns(id)
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
            campaign_id INTEGER,
            fingerprint TEXT,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT,
            successful INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES moderation_campaigns(id)
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(campaigns_query)
                await connection.execute(observations_query)
                await connection.execute(accounts_query)
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
        message = payload.text

        recent_message = self.cache_message(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            message=message
        )

        if self.is_protected_user(broadcaster_id, user_id):
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

        campaign = await self.get_confirmed_campaign(
            recent_message.fingerprint
        )

        if campaign is None:
            return ModerationResult(
                action=ModerationAction.ALLOW,
                reason="No confirmed message campaign matched.",
                fingerprint=recent_message.fingerprint
            )

        campaign_id = int(campaign["id"])
        reason = campaign["reason"] or "Message matched a confirmed spam campaign."
        source = campaign["source"]

        await self.associate_campaign_account(
            campaign_id=campaign_id,
            user_id=user_id,
            username=username
        )

        LOGGER.warning(
            "[Moderation] Message from %s (%s) matched campaign %d in broadcaster %s.",
            username,
            user_id,
            campaign_id,
            broadcaster_id
        )

        return ModerationResult(
            action=ModerationAction.BAN,
            reason=reason,
            source=source,
            campaign_id=campaign_id,
            fingerprint=recent_message.fingerprint
        )

    def cache_message(self, broadcaster_id: str, user_id: str, username: str, message: str) -> RecentMessage:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        normalized_message = self.normalize_message(message)
        fingerprint = self.create_fingerprint(normalized_message)

        recent_message = RecentMessage(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            message=message,
            normalized_message=normalized_message,
            fingerprint=fingerprint,
            created_at=time.time()
        )

        self.recent_messages[self.get_recent_message_key(broadcaster_id, user_id)] = recent_message
        self.remove_expired_messages()

        return recent_message

    def get_recent_message(self, broadcaster_id: str, user_id: str) -> RecentMessage | None:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        key = self.get_recent_message_key(broadcaster_id, user_id)
        recent_message = self.recent_messages.get(key)

        if recent_message is None:
            return None

        if time.time() - recent_message.created_at > self.RECENT_MESSAGE_TTL_SECONDS:
            self.recent_messages.pop(key, None)
            return None

        return recent_message

    async def observe_external_ban(self, broadcaster_id: str, user_id: str, username: str, moderator_id: str, moderator_name: str, reason: str | None, source: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        moderator_id = str(moderator_id)

        recent_message = self.get_recent_message(
            broadcaster_id,
            user_id
        )

        if recent_message is None:
            LOGGER.warning(
                "[Moderation] Could not associate %s ban of %s (%s) with a recent message in broadcaster %s.",
                source,
                username,
                user_id,
                broadcaster_id
            )
            return False

        campaign_id = await self.upsert_campaign(
            fingerprint=recent_message.fingerprint,
            normalized_message=recent_message.normalized_message,
            example_message=recent_message.message,
            source=source,
            reason=reason
        )

        created = await self.record_campaign_observation(
            campaign_id=campaign_id,
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            moderator_id=moderator_id,
            moderator_name=moderator_name,
            observed_action="ban",
            source=source,
            reason=reason,
            message=recent_message.message
        )

        await self.associate_campaign_account(
            campaign_id=campaign_id,
            user_id=user_id,
            username=username
        )

        if not created:
            return False

        await self.update_campaign_confidence(
            campaign_id,
            source
        )

        return True

    async def upsert_campaign(self, fingerprint: str, normalized_message: str, example_message: str, source: str, reason: str | None) -> int:

        query = """
        INSERT INTO moderation_campaigns (
            fingerprint,
            normalized_message,
            example_message,
            status,
            confidence,
            source,
            reason
        )
        VALUES (?, ?, ?, 'pending', 75, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            example_message = excluded.example_message,
            last_seen_at = CURRENT_TIMESTAMP,
            reason = COALESCE(excluded.reason, moderation_campaigns.reason)
        RETURNING id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        fingerprint,
                        normalized_message,
                        example_message,
                        source,
                        reason
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to create or update campaign %s.",
                fingerprint
            )
            raise

        return int(row["id"])

    async def record_campaign_observation(self, campaign_id: int, broadcaster_id: str, user_id: str, username: str, moderator_id: str | None, moderator_name: str | None, observed_action: str, source: str, reason: str | None, message: str) -> bool:

        query = """
        INSERT INTO moderation_campaign_observations (
            campaign_id,
            broadcaster_id,
            user_id,
            username,
            moderator_id,
            moderator_name,
            observed_action,
            source,
            reason,
            message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (
            campaign_id,
            broadcaster_id,
            observed_action,
            source
        ) DO NOTHING
        RETURNING id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        campaign_id,
                        str(broadcaster_id),
                        str(user_id),
                        username,
                        str(moderator_id) if moderator_id is not None else None,
                        moderator_name,
                        observed_action,
                        source,
                        reason,
                        message
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to record campaign %d observation in broadcaster %s.",
                campaign_id,
                broadcaster_id
            )
            raise

        if row is None:
            LOGGER.debug(
                "[Moderation] Duplicate %s observation ignored for campaign %d in broadcaster %s.",
                source,
                campaign_id,
                broadcaster_id
            )
            return False

        LOGGER.warning(
            "[Moderation] Recorded %s observation for campaign %d in broadcaster %s.",
            source,
            campaign_id,
            broadcaster_id
        )

        return True

    async def update_campaign_confidence(self, campaign_id: int, source: str) -> None:

        observation_count = await self.count_campaign_observations(
            campaign_id,
            source
        )

        confirmed = observation_count >= self.REQUIRED_EXTERNAL_OBSERVATIONS
        confidence = 100 if confirmed else 75
        status = "confirmed" if confirmed else "pending"

        query = """
        UPDATE moderation_campaigns
        SET status = ?,
            confidence = ?,
            last_seen_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        status,
                        confidence,
                        campaign_id
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to update confidence for campaign %d.",
                campaign_id
            )
            raise

        if confirmed:
            LOGGER.warning(
                "[Moderation] Confirmed campaign %d after %d independent %s observations.",
                campaign_id,
                observation_count,
                source
            )
            return

        LOGGER.info(
            "[Moderation] Campaign %d has %d/%d required %s observations.",
            campaign_id,
            observation_count,
            self.REQUIRED_EXTERNAL_OBSERVATIONS,
            source
        )

    async def count_campaign_observations(self, campaign_id: int, source: str) -> int:

        query = """
        SELECT COUNT(DISTINCT broadcaster_id) AS observation_count
        FROM moderation_campaign_observations
        WHERE campaign_id = ?
          AND source = ?
          AND observed_action = 'ban'
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        campaign_id,
                        source
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to count observations for campaign %d.",
                campaign_id
            )
            raise

        return int(row["observation_count"]) if row else 0

    async def get_confirmed_campaign(self, fingerprint: str):

        query = """
        SELECT id, fingerprint, normalized_message, confidence, source, reason
        FROM moderation_campaigns
        WHERE fingerprint = ?
          AND status = 'confirmed'
        """

        try:
            async with self.db.acquire() as connection:
                return await connection.fetchone(
                    query,
                    (fingerprint,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to check campaign fingerprint %s.",
                fingerprint
            )
            raise

    async def associate_campaign_account(self, campaign_id: int, user_id: str, username: str) -> None:

        query = """
        INSERT INTO moderation_campaign_accounts (
            campaign_id,
            user_id,
            username
        )
        VALUES (?, ?, ?)
        ON CONFLICT(campaign_id, user_id) DO UPDATE SET
            username = excluded.username,
            last_seen_at = CURRENT_TIMESTAMP
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        campaign_id,
                        str(user_id),
                        username
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to associate user %s with campaign %d.",
                user_id,
                campaign_id
            )
            raise

    async def confirm_campaign(self, fingerprint: str, reason: str = "Manually confirmed spam campaign.", source: str = "manual") -> bool:

        query = """
        UPDATE moderation_campaigns
        SET status = 'confirmed',
            confidence = 100,
            reason = ?,
            source = ?,
            last_seen_at = CURRENT_TIMESTAMP
        WHERE fingerprint = ?
        RETURNING id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (
                        reason,
                        source,
                        fingerprint
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to confirm campaign %s.",
                fingerprint
            )
            raise

        return row is not None

    async def reject_campaign(self, fingerprint: str) -> bool:

        query = """
        UPDATE moderation_campaigns
        SET status = 'rejected',
            confidence = 0,
            last_seen_at = CURRENT_TIMESTAMP
        WHERE fingerprint = ?
        RETURNING id
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (fingerprint,)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to reject campaign %s.",
                fingerprint
            )
            raise

        return row is not None

    async def ban_user(self, payload, result: ModerationResult) -> bool:

        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = payload.chatter.name
        message = payload.text

        if self.is_protected_user(broadcaster_id, user_id):
            LOGGER.warning(
                "[Moderation] Refused to ban protected user %s (%s) in broadcaster %s.",
                username,
                user_id,
                broadcaster_id
            )
            return False

        channel = self.bot.create_partialuser(
            broadcaster_id
        )

        try:
            await channel.ban_user(
                moderator=broadcaster_id,
                user=user_id,
                reason=f"Matched confirmed spam campaign: {result.reason}"
            )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to ban campaign account %s (%s) in broadcaster %s.",
                username,
                user_id,
                broadcaster_id
            )

            await self.record_action(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                campaign_id=result.campaign_id,
                fingerprint=result.fingerprint,
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
            campaign_id=result.campaign_id,
            fingerprint=result.fingerprint,
            action=ModerationAction.BAN,
            reason=result.reason,
            source=result.source,
            message=message,
            successful=True
        )

        LOGGER.warning(
            "[Moderation] Banned %s (%s) for matching campaign %s in broadcaster %s.",
            username,
            user_id,
            result.campaign_id,
            broadcaster_id
        )

        return True

    async def allow_user(self, user_id: str, username: str | None = None, reason: str | None = None) -> None:

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
                        str(user_id),
                        username,
                        reason
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to allowlist user %s (%s).",
                username or "unknown",
                user_id
            )
            raise

    async def is_allowlisted(self, user_id: str) -> bool:

        query = """
        SELECT 1
        FROM moderation_allowlist
        WHERE user_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(
                    query,
                    (str(user_id),)
                )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to check allowlist status for user %s.",
                user_id
            )
            raise

        return row is not None

    async def record_action(self, broadcaster_id: str, user_id: str, username: str, campaign_id: int | None, fingerprint: str | None, action: ModerationAction, reason: str, source: str, message: str | None = None, successful: bool = True) -> None:

        query = """
        INSERT INTO moderation_actions (
            broadcaster_id,
            user_id,
            username,
            campaign_id,
            fingerprint,
            action,
            reason,
            source,
            message,
            successful
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        str(broadcaster_id),
                        str(user_id),
                        username,
                        campaign_id,
                        fingerprint,
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

    def remove_expired_messages(self) -> None:

        now = time.time()

        expired_keys = [
            key
            for key, message in self.recent_messages.items()
            if now - message.created_at > self.RECENT_MESSAGE_TTL_SECONDS
        ]

        for key in expired_keys:
            self.recent_messages.pop(key, None)

    def is_protected_user(self, broadcaster_id: str, user_id: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        if broadcaster_id == user_id:
            return True

        bot_id = getattr(self.bot, "bot_id", None)

        if bot_id is None:
            bot_user = getattr(self.bot, "user", None)
            bot_id = getattr(bot_user, "id", None)

        return bot_id is not None and user_id == str(bot_id)

    @staticmethod
    def normalize_message(message: str) -> str:

        normalized = unicodedata.normalize(
            "NFKC",
            str(message)
        )

        normalized = ZERO_WIDTH_PATTERN.sub(
            "",
            normalized
        )

        normalized = normalized.lower()

        normalized = URL_PATTERN.sub(
            lambda match: ModerationService.normalize_url(match.group(0)),
            normalized
        )

        normalized = NON_TEXT_PATTERN.sub(
            " ",
            normalized
        )

        normalized = WHITESPACE_PATTERN.sub(
            " ",
            normalized
        )

        return normalized.strip()

    @staticmethod
    def normalize_url(url: str) -> str:

        clean_url = url.rstrip(".,!?;:)]}'\"")

        try:
            parsed = urlsplit(clean_url)
        except ValueError:
            return clean_url.lower()

        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        ]

        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                urlencode(filtered_query),
                ""
            )
        )

    @staticmethod
    def create_fingerprint(normalized_message: str) -> str:

        return hashlib.sha256(
            normalized_message.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def get_recent_message_key(broadcaster_id: str, user_id: str) -> str:

        return f"{str(broadcaster_id)}:{str(user_id)}"

import logging
from dataclasses import dataclass

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class ChatIdentityState:
    broadcaster_id: str
    premium_enabled: bool = False
    bot_user_id: str | None = None
    bot_login: str | None = None
    bot_display_name: str | None = None
    connected_at: str | None = None
    token_available: bool = False

    @property
    def connected(self) -> bool:
        return self.premium_enabled and self.bot_user_id is not None and self.token_available


class ChatIdentityService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.identities: dict[str, ChatIdentityState] = {}

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                """
                SELECT identities.broadcaster_id, identities.premium_enabled, identities.bot_user_id,
                       identities.bot_login, identities.bot_display_name, identities.connected_at,
                       CASE WHEN tokens.user_id IS NULL THEN 0 ELSE 1 END AS token_available
                FROM channel_chat_identities AS identities
                LEFT JOIN tokens ON tokens.user_id = identities.bot_user_id
                """
            )

        self.identities = {
            str(row["broadcaster_id"]): ChatIdentityState(
                broadcaster_id=str(row["broadcaster_id"]),
                premium_enabled=bool(row["premium_enabled"]),
                bot_user_id=str(row["bot_user_id"]) if row["bot_user_id"] else None,
                bot_login=row["bot_login"],
                bot_display_name=row["bot_display_name"],
                connected_at=row["connected_at"],
                token_available=bool(row["token_available"])
            )
            for row in rows
        }
        LOGGER.info("[ChatIdentity] Loaded premium chat identity settings for %d channel(s).", len(self.identities))

    def get_state(self, broadcaster_id: str) -> ChatIdentityState:
        broadcaster_id = str(broadcaster_id)
        return self.identities.get(broadcaster_id, ChatIdentityState(broadcaster_id=broadcaster_id))

    def is_custom_bot(self, user_id: str) -> bool:
        user_id = str(user_id)
        return any(state.bot_user_id == user_id for state in self.identities.values())

    async def set_premium_enabled(self, broadcaster_id: str, enabled: bool) -> ChatIdentityState:
        broadcaster_id = str(broadcaster_id)

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO channel_chat_identities (broadcaster_id, premium_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id) DO UPDATE SET
                    premium_enabled = excluded.premium_enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (broadcaster_id, int(enabled))
            )

        await self.setup()
        LOGGER.info("[ChatIdentity] Premium custom identity %s for broadcaster %s.", "enabled" if enabled else "disabled", broadcaster_id)
        return self.get_state(broadcaster_id)

    async def connect(self, broadcaster_id: str, user_id: str, login: str, display_name: str) -> ChatIdentityState:
        broadcaster_id = str(broadcaster_id)
        state = self.get_state(broadcaster_id)

        if not state.premium_enabled:
            raise ValueError("Premium custom identity access is not enabled for this channel.")

        if str(user_id) in {broadcaster_id, str(self.bot.bot_id)}:
            raise ValueError("Choose a dedicated Twitch bot account, not the broadcaster or RatsBoomBot account.")

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                UPDATE channel_chat_identities
                SET bot_user_id = ?, bot_login = ?, bot_display_name = ?, connected_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE broadcaster_id = ? AND premium_enabled = 1
                """,
                (str(user_id), login.lower(), display_name, broadcaster_id)
            )

        await self.setup()
        LOGGER.info("[ChatIdentity] Connected custom bot %s (%s) to broadcaster %s.", login, user_id, broadcaster_id)
        return self.get_state(broadcaster_id)

    async def disconnect(self, broadcaster_id: str) -> str | None:
        broadcaster_id = str(broadcaster_id)
        previous_user_id = self.get_state(broadcaster_id).bot_user_id

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                UPDATE channel_chat_identities
                SET bot_user_id = NULL, bot_login = NULL, bot_display_name = NULL, connected_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE broadcaster_id = ?
                """,
                (broadcaster_id,)
            )

        await self.setup()
        LOGGER.info("[ChatIdentity] Disconnected custom bot from broadcaster %s.", broadcaster_id)
        return previous_user_id

    async def remove_channel(self, broadcaster_id: str) -> str | None:
        broadcaster_id = str(broadcaster_id)
        previous_user_id = self.get_state(broadcaster_id).bot_user_id

        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM channel_chat_identities WHERE broadcaster_id = ?", (broadcaster_id,))

        await self.setup()
        return previous_user_id

    def sender_id(self, broadcaster_id: str) -> str:
        state = self.get_state(broadcaster_id)
        return state.bot_user_id if state.connected and state.bot_user_id else str(self.bot.bot_id)

    async def send_message(self, broadcaster, message: str, *, reply_to_message_id: str | None = None, me: bool = False):
        broadcaster_id = str(broadcaster.id)
        sender_id = self.sender_id(broadcaster_id)
        content = (f"/me {message}" if me else message).strip()

        try:
            return await broadcaster.send_message(sender=sender_id, message=content, reply_to_message_id=reply_to_message_id)
        except Exception:
            if sender_id == str(self.bot.bot_id):
                raise

            LOGGER.exception("[ChatIdentity] Custom bot message failed for broadcaster %s; falling back to RatsBoomBot.", broadcaster_id, extra={"broadcaster_id": broadcaster_id, "category": "CHAT_IDENTITY"})
            return await broadcaster.send_message(sender=self.bot.bot_id, message=content, reply_to_message_id=reply_to_message_id)

    async def send_announcement(self, broadcaster, message: str, color: str | None = None) -> None:
        broadcaster_id = str(broadcaster.id)
        sender_id = self.sender_id(broadcaster_id)

        try:
            await broadcaster.send_announcement(moderator=sender_id, message=message, color=color)
        except Exception:
            if sender_id == str(self.bot.bot_id):
                raise

            LOGGER.exception("[ChatIdentity] Custom bot announcement failed for broadcaster %s; falling back to RatsBoomBot.", broadcaster_id, extra={"broadcaster_id": broadcaster_id, "category": "CHAT_IDENTITY"})
            await broadcaster.send_announcement(moderator=self.bot.bot_id, message=message, color=color)

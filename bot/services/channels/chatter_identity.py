import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class ChatterIdentity:
    user_id: str
    login: str
    display_name: str


class ChatterIdentityService:
    WRITE_INTERVAL = timedelta(hours=1)

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self._identities: dict[str, ChatterIdentity] = {}
        self._global_aliases: dict[str, set[str]] = {}
        self._channel_aliases: dict[str, dict[str, set[str]]] = {}
        self._user_channels: dict[str, set[str]] = {}
        self._last_persisted: dict[tuple[str, str], datetime] = {}

    async def setup(self) -> None:
        LOGGER.info("[Chatters] Loading saved chatter identities.")

        async with self.db.acquire() as connection:
            identity_rows = await connection.fetchall(
                """
                SELECT user_id, login, display_name
                FROM chatter_identities
                """
            )
            observation_rows = await connection.fetchall(
                """
                SELECT broadcaster_id, user_id, last_seen_at
                FROM chatter_channel_observations
                """
            )

        for row in identity_rows:
            identity = ChatterIdentity(
                user_id=str(row["user_id"]),
                login=row["login"],
                display_name=row["display_name"]
            )
            self._identities[identity.user_id] = identity
            self._add_aliases(self._global_aliases, identity)

        for row in observation_rows:
            broadcaster_id = str(row["broadcaster_id"])
            user_id = str(row["user_id"])
            identity = self._identities.get(user_id)

            if identity is None:
                continue

            aliases = self._channel_aliases.setdefault(broadcaster_id, {})
            self._add_aliases(aliases, identity)
            self._user_channels.setdefault(user_id, set()).add(broadcaster_id)
            self._last_persisted[(broadcaster_id, user_id)] = self._parse_timestamp(row["last_seen_at"])

        LOGGER.info(
            "[Chatters] Loaded %d identities observed across %d channels.",
            len(self._identities),
            len(self._channel_aliases)
        )

    async def observe(self, broadcaster_id: str, chatter) -> None:
        user_id = str(chatter.id)
        login = str(chatter.name)
        display_name = str(getattr(chatter, "display_name", None) or login)
        broadcaster_id = str(broadcaster_id)
        identity = ChatterIdentity(user_id=user_id, login=login, display_name=display_name)
        previous = self._identities.get(user_id)
        identity_changed = previous != identity

        if identity_changed and previous is not None:
            self._remove_identity_aliases(previous)

        if identity_changed:
            self._identities[user_id] = identity
            self._add_aliases(self._global_aliases, identity)

        channel_aliases = self._channel_aliases.setdefault(broadcaster_id, {})
        self._user_channels.setdefault(user_id, set()).add(broadcaster_id)

        if identity_changed:
            for observed_broadcaster_id in self._user_channels[user_id]:
                observed_aliases = self._channel_aliases.setdefault(observed_broadcaster_id, {})
                self._add_aliases(observed_aliases, identity)

        self._add_aliases(channel_aliases, identity)

        now = datetime.now(UTC)
        last_persisted = self._last_persisted.get((broadcaster_id, user_id))

        if not identity_changed and last_persisted is not None and now - last_persisted < self.WRITE_INTERVAL:
            return

        await self._persist(broadcaster_id, identity, now)
        self._last_persisted[(broadcaster_id, user_id)] = now

    async def resolve(self, broadcaster_id: str | None, argument: str):
        value = argument.strip().removeprefix("@").strip()

        if not value:
            return None

        if value.isascii() and value.isdecimal():
            user = await self.bot.fetch_user(id=value)
        else:
            user_id = self._resolve_alias(broadcaster_id, value)

            if user_id is not None:
                user = await self.bot.fetch_user(id=user_id)
            else:
                user = await self.bot.fetch_user(login=value)

        if user is not None and broadcaster_id is not None:
            await self.observe(broadcaster_id, user)

        return user

    def _resolve_alias(self, broadcaster_id: str | None, value: str) -> str | None:
        key = self.normalize(value)

        if broadcaster_id is not None:
            channel_matches = self._channel_aliases.get(str(broadcaster_id), {}).get(key, set())

            if len(channel_matches) == 1:
                return next(iter(channel_matches))

            if len(channel_matches) > 1:
                return None

        global_matches = self._global_aliases.get(key, set())

        if len(global_matches) == 1:
            return next(iter(global_matches))

        return None

    async def _persist(self, broadcaster_id: str, identity: ChatterIdentity, observed_at: datetime) -> None:
        observed_at_value = observed_at.isoformat()

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO chatter_identities (user_id, login, display_name, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    login = excluded.login,
                    display_name = excluded.display_name,
                    last_seen_at = excluded.last_seen_at
                """,
                (identity.user_id, identity.login, identity.display_name, observed_at_value, observed_at_value)
            )
            await connection.execute(
                """
                INSERT INTO chatter_channel_observations (broadcaster_id, user_id, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at
                """,
                (broadcaster_id, identity.user_id, observed_at_value, observed_at_value)
            )

    def _remove_identity_aliases(self, identity: ChatterIdentity) -> None:
        self._remove_aliases(self._global_aliases, identity)

        for aliases in self._channel_aliases.values():
            self._remove_aliases(aliases, identity)

    @classmethod
    def _add_aliases(cls, aliases: dict[str, set[str]], identity: ChatterIdentity) -> None:
        for value in (identity.login, identity.display_name):
            aliases.setdefault(cls.normalize(value), set()).add(identity.user_id)

    @classmethod
    def _remove_aliases(cls, aliases: dict[str, set[str]], identity: ChatterIdentity) -> None:
        for value in (identity.login, identity.display_name):
            key = cls.normalize(value)
            matches = aliases.get(key)

            if matches is None:
                continue

            matches.discard(identity.user_id)

            if not matches:
                aliases.pop(key, None)

    @staticmethod
    def normalize(value: str) -> str:
        return value.strip().removeprefix("@").strip().casefold()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return datetime.min.replace(tzinfo=UTC)

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

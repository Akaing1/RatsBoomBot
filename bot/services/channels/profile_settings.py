import json
import logging
from dataclasses import dataclass, fields, replace
from string import Formatter

from bot.profiles import ChannelProfile, PointsMessages
from bot.timer_messages import format_timers, parse_timers

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class ProfileSettingDefinition:
    key: str
    group: str
    label: str
    description: str
    value_type: str = "text"
    maximum_length: int = 500
    minimum: int | None = None
    maximum: int | None = None
    rows: int = 3


@dataclass(frozen=True)
class ProfileSettingState:
    definition: ProfileSettingDefinition
    default_value: str | int
    override_value: str | int | None
    effective_value: str | int

    @property
    def timer_entries(self):
        return parse_timers(str(self.effective_value))


@dataclass(frozen=True)
class ProtectedUser:
    user_id: str
    login: str
    display_name: str


PROFILE_SETTING_DEFINITIONS = (
    ProfileSettingDefinition("timer_messages", "Timers", "Timer messages", "Add, edit, or remove the automated messages that rotate in chat.", value_type="lines", maximum_length=10000, rows=6),
    ProfileSettingDefinition("lurk_message", "Commands", "Lurk message", "Sent when a viewer uses !lurk. Use {username} for the viewer name."),
    ProfileSettingDefinition("community_messages.follow", "Community messages", "Follow message", "Sent when a viewer follows. Leave empty to send nothing."),
    ProfileSettingDefinition("community_messages.subscription", "Community messages", "Subscription message", "Sent for a new subscription. Use {username} for the subscriber. Leave empty to send nothing."),
    ProfileSettingDefinition("community_messages.resubscription", "Community messages", "Resubscription message", "Sent for a returning subscription. Use {username} and {months}. Leave empty to send nothing."),
    ProfileSettingDefinition("community_messages.gifted_subscription", "Community messages", "Gifted subscription message", "Sent once per gift batch, without recipient names. Use {username}, {count}, and {subscription_word}. Leave empty to send nothing."),
    ProfileSettingDefinition("raid_messages.incoming", "Raid messages", "Incoming raid message", "Sent when another channel raids this channel."),
    ProfileSettingDefinition("raid_messages.outgoing", "Raid messages", "Outgoing raid message", "Sent when the broadcaster starts a raid."),
    ProfileSettingDefinition("raid_messages.outgoing_subscriber", "Raid messages", "Subscriber raid message", "Optional subscriber variation for outgoing raids."),
    ProfileSettingDefinition("shoutout_messages.with_game", "Shoutouts", "Shoutout with game", "Shoutout used when Twitch provides the target's last game."),
    ProfileSettingDefinition("shoutout_messages.without_game", "Shoutouts", "Shoutout without game", "Shoutout used when no game is available."),
    ProfileSettingDefinition("redeems.daily_title", "Redeems", "Daily redeem title", "Exact Twitch reward title used for the daily claim.", maximum_length=100, rows=1),
    ProfileSettingDefinition("redeems.first_title", "Redeems", "First redeem title", "Exact Twitch reward title used for first place.", maximum_length=100, rows=1),
    ProfileSettingDefinition("redeems.vip_title", "Redeems", "VIP redeem title", "Exact Twitch reward title that permanently grants VIP status.", maximum_length=100, rows=1),
    ProfileSettingDefinition("league.game_name", "League of Legends", "Riot game name", "The game-name portion of the broadcaster's Riot ID.", maximum_length=100, rows=1),
    ProfileSettingDefinition("league.tag_line", "League of Legends", "Riot tag line", "The tag-line portion of the broadcaster's Riot ID.", maximum_length=20, rows=1),
    ProfileSettingDefinition("league.region", "League of Legends", "Region", "The OP.GG region code, such as NA or EUW.", maximum_length=12, rows=1),
    ProfileSettingDefinition("league.display_name", "League of Legends", "League display name", "Name used when presenting broadcaster League statistics.", maximum_length=100, rows=1),
    ProfileSettingDefinition("overwatch.player_id", "Overwatch", "BattleTag", "The broadcaster's Overwatch BattleTag.", maximum_length=100, rows=1),
    ProfileSettingDefinition("overwatch.platform", "Overwatch", "Platform", "The OverFast platform code, such as pc.", maximum_length=20, rows=1),
    ProfileSettingDefinition("overwatch.display_name", "Overwatch", "Display name", "Name used in Overwatch command responses.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.potion", "Raid item names", "Power Potion name", "Custom display and purchase name for Power Potion.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.second_wind", "Raid item names", "Second Wind name", "Custom display and purchase name for Second Wind.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.berserk", "Raid item names", "Berserk name", "Custom display and purchase name for Berserk.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.lucky_dice", "Raid item names", "Lucky Dice name", "Custom display and purchase name for Lucky Dice.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.fools_card", "Raid item names", "Fool's Card name", "Custom display and purchase name for The Fool's Card.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.blessing", "Raid item names", "Blessing name", "Custom display and purchase name for Blessing of the Gods.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.ancient_pact", "Raid item names", "Ancient Pact name", "Custom display and purchase name for Ancient Pact.", maximum_length=100, rows=1),
    ProfileSettingDefinition("raid_bosses.item_names.flag_bearer", "Raid item names", "Flag Bearer name", "Custom display and purchase name for Flag Bearer's Will.", maximum_length=100, rows=1)
)

LOYALTY_GROUP = "Loyalty points"
LOYALTY_RESPONSE_LABELS = {"balance_self": "Points (user)", "balance_other": "Points (other)", "add_success": "Add Points", "give_success": "Give Points"}
LOYALTY_PLACEHOLDERS = {
    f"points.messages.{field.name}": {name for _, name, _, _ in Formatter().parse(field.default) if name is not None} | {"currency"}
    for field in fields(PointsMessages)
}
PROFILE_SETTING_DEFINITIONS += (
    ProfileSettingDefinition("points.display_name", LOYALTY_GROUP, "Loyalty Points Name", "Display name for your channel currency. Defaults to Points. Leave empty to use Points. Use {currency} in responses to insert this name. This name also becomes a chat command alias (for example, bombs gives !bombs).", maximum_length=60, rows=1),
) + tuple(
    ProfileSettingDefinition(f"points.messages.{field.name}", LOYALTY_GROUP, LOYALTY_RESPONSE_LABELS[field.name], "Available placeholders: " + ", ".join("{" + name + "}" for name in sorted(LOYALTY_PLACEHOLDERS[f"points.messages.{field.name}"])) + ". Leave empty to send nothing.")
    for field in fields(PointsMessages) if field.name in LOYALTY_RESPONSE_LABELS
)

PROFILE_SETTINGS_BY_KEY = {definition.key: definition for definition in PROFILE_SETTING_DEFINITIONS}
DEVELOPER_PROFILE_MIGRATION_VERSION = 2


class ProfileSettingsService:

    def __init__(self, db):
        self.db = db
        self.overrides: dict[str, dict[str, str | int]] = {}
        self.protected_users: dict[str, dict[str, ProtectedUser]] = {}
        self.base_profiles: dict[str, ChannelProfile] = {}

    async def setup(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS channel_profile_overrides (
            broadcaster_id TEXT NOT NULL,
            setting_name TEXT NOT NULL,
            setting_value TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, setting_name)
        )
        """
        migration_query = """
        CREATE TABLE IF NOT EXISTS channel_profile_migrations (
            broadcaster_id TEXT PRIMARY KEY,
            migration_version INTEGER NOT NULL,
            migrated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        protected_users_query = """
        CREATE TABLE IF NOT EXISTS channel_protected_users (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)
            await connection.execute(migration_query)
            await connection.execute(protected_users_query)

        await self.load_overrides()
        await self.load_protected_users()
        LOGGER.info("[Profiles] Loaded database profile overrides for %d broadcaster(s).", len(self.overrides))

    async def load_overrides(self) -> None:
        query = """
        SELECT broadcaster_id, setting_name, setting_value, updated_by
        FROM channel_profile_overrides
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query)

        loaded: dict[str, dict[str, str | int]] = {}

        for row in rows:
            # Seeded developer defaults should follow the current code; preserve user edits.
            if row["updated_by"] == "developer-profile-migration" and row["setting_name"] in {"points.display_name", *(f"points.messages.{name}" for name in LOYALTY_RESPONSE_LABELS)}:
                continue
            definition = PROFILE_SETTINGS_BY_KEY.get(row["setting_name"])

            if definition is None:
                LOGGER.warning("[Profiles] Ignoring unknown profile setting %s.", row["setting_name"])
                continue

            try:
                value = self.deserialize_value(definition, row["setting_value"])
            except (TypeError, ValueError):
                LOGGER.warning("[Profiles] Ignoring invalid profile setting %s for broadcaster %s.", row["setting_name"], row["broadcaster_id"])
                continue

            loaded.setdefault(str(row["broadcaster_id"]), {})[definition.key] = value

        self.overrides = loaded

    async def load_protected_users(self) -> None:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                """
                SELECT broadcaster_id, user_id, login, display_name
                FROM channel_protected_users
                ORDER BY display_name COLLATE NOCASE, user_id
                """
            )

        loaded: dict[str, dict[str, ProtectedUser]] = {}

        for row in rows:
            broadcaster_id = str(row["broadcaster_id"])
            user = ProtectedUser(
                user_id=str(row["user_id"]),
                login=str(row["login"]),
                display_name=str(row["display_name"])
            )
            loaded.setdefault(broadcaster_id, {})[user.user_id] = user

        self.protected_users = loaded

    def get_added_protected_users(self, broadcaster_id: str) -> tuple[ProtectedUser, ...]:
        users = self.protected_users.get(str(broadcaster_id), {}).values()
        return tuple(sorted(users, key=lambda user: (user.display_name.casefold(), user.user_id)))

    def get_default_protected_user_ids(self, broadcaster_id: str) -> tuple[str, ...]:
        profile = self.base_profiles.get(str(broadcaster_id))
        return profile.protected_user_ids if profile is not None else ()

    async def add_protected_user(self, broadcaster_id: str, user_id: str, login: str, display_name: str) -> ProtectedUser:
        broadcaster_id = str(broadcaster_id)
        user = ProtectedUser(str(user_id), login.casefold(), display_name)

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO channel_protected_users (broadcaster_id, user_id, login, display_name, added_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
                    login = excluded.login,
                    display_name = excluded.display_name
                """,
                (broadcaster_id, user.user_id, user.login, user.display_name)
            )

        self.protected_users.setdefault(broadcaster_id, {})[user.user_id] = user
        self.refresh_active_profile(broadcaster_id)
        LOGGER.info("[Profiles] Added protected user %s (%s) for broadcaster %s.", user.display_name, user.user_id, broadcaster_id)
        return user

    async def remove_protected_user(self, broadcaster_id: str, user_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        if user_id in self.get_default_protected_user_ids(broadcaster_id):
            raise ValueError("Channel-default protected users cannot be removed from the dashboard.")

        channel_users = self.protected_users.get(broadcaster_id, {})
        removed = user_id in channel_users

        if not removed:
            return False

        async with self.db.acquire() as connection:
            await connection.execute(
                "DELETE FROM channel_protected_users WHERE broadcaster_id = ? AND user_id = ?",
                (broadcaster_id, user_id)
            )

        channel_users.pop(user_id, None)
        self.refresh_active_profile(broadcaster_id)
        LOGGER.info("[Profiles] Removed protected user %s for broadcaster %s.", user_id, broadcaster_id)

        return True

    async def migrate_developer_profile(self, broadcaster_id: str, profile: ChannelProfile) -> bool:
        broadcaster_id = str(broadcaster_id)
        query = "SELECT migration_version FROM channel_profile_migrations WHERE broadcaster_id = ?"

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (broadcaster_id,))

            if row and int(row["migration_version"]) >= DEVELOPER_PROFILE_MIGRATION_VERSION:
                return False

            for definition in PROFILE_SETTING_DEFINITIONS:
                value = self.get_profile_value(profile, definition.key)
                await connection.execute(
                    """
                    INSERT INTO channel_profile_overrides (broadcaster_id, setting_name, setting_value, updated_by, updated_at)
                    VALUES (?, ?, ?, 'developer-profile-migration', CURRENT_TIMESTAMP)
                    ON CONFLICT(broadcaster_id, setting_name) DO NOTHING
                    """,
                    (broadcaster_id, definition.key, self.serialize_value(value))
                )

            await connection.execute(
                """
                INSERT INTO channel_profile_migrations (broadcaster_id, migration_version, migrated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(broadcaster_id) DO UPDATE SET
                    migration_version = excluded.migration_version,
                    migrated_at = CURRENT_TIMESTAMP
                """,
                (broadcaster_id, DEVELOPER_PROFILE_MIGRATION_VERSION)
            )

        await self.load_overrides()
        LOGGER.info("[Profiles] Migrated editable developer profile defaults for broadcaster %s.", broadcaster_id)
        return True

    async def set_override(self, broadcaster_id: str, setting_name: str, raw_value: str, updated_by: str) -> ProfileSettingState:
        broadcaster_id = str(broadcaster_id)
        definition = self.get_definition(setting_name)
        value = self.validate_value(definition, raw_value)
        query = """
        INSERT INTO channel_profile_overrides (broadcaster_id, setting_name, setting_value, updated_by, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(broadcaster_id, setting_name) DO UPDATE SET
            setting_value = excluded.setting_value,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, setting_name, self.serialize_value(value), updated_by))

        self.overrides.setdefault(broadcaster_id, {})[setting_name] = value
        self.refresh_active_profile(broadcaster_id)
        return self.get_setting_state(broadcaster_id, setting_name)

    async def clear_override(self, broadcaster_id: str, setting_name: str, updated_by: str) -> ProfileSettingState:
        broadcaster_id = str(broadcaster_id)
        self.get_definition(setting_name)

        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM channel_profile_overrides WHERE broadcaster_id = ? AND setting_name = ?", (broadcaster_id, setting_name))

        channel_overrides = self.overrides.get(broadcaster_id, {})
        channel_overrides.pop(setting_name, None)
        self.refresh_active_profile(broadcaster_id)
        LOGGER.info("[Profiles] Cleared profile setting %s for broadcaster %s by %s.", setting_name, broadcaster_id, updated_by)
        return self.get_setting_state(broadcaster_id, setting_name)

    def apply_overrides(self, broadcaster_id: str, profile: ChannelProfile) -> ChannelProfile:
        broadcaster_id = str(broadcaster_id)
        self.base_profiles[broadcaster_id] = profile
        default_messages = PointsMessages()
        fixed_messages = {field.name: getattr(default_messages, field.name) for field in fields(PointsMessages) if field.name not in LOYALTY_RESPONSE_LABELS}
        messages = replace(profile.points.messages, **fixed_messages)
        effective_profile = replace(profile, points=replace(profile.points, messages=messages))

        for setting_name, value in self.overrides.get(broadcaster_id, {}).items():
            if setting_name in PROFILE_SETTINGS_BY_KEY:
                effective_profile = self.replace_profile_value(effective_profile, setting_name, value)

        if not effective_profile.points.display_name.strip():
            effective_profile = replace(effective_profile, points=replace(effective_profile.points, display_name="Points"))

        protected_user_ids = tuple(dict.fromkeys((
            *effective_profile.protected_user_ids,
            *self.protected_users.get(broadcaster_id, {})
        )))
        effective_profile = replace(effective_profile, protected_user_ids=protected_user_ids)
        return effective_profile

    def get_setting_groups(self, broadcaster_id: str, available_integrations: set[str] | None = None) -> dict[str, list[ProfileSettingState]]:
        groups: dict[str, list[ProfileSettingState]] = {}
        available_integrations = available_integrations or set()

        for definition in PROFILE_SETTING_DEFINITIONS:
            if definition.group in {"League of Legends", "Overwatch"} and definition.group.lower().split()[0] not in available_integrations:
                continue

            groups.setdefault(definition.group, []).append(self.get_setting_state(broadcaster_id, definition.key))

        return groups

    def refresh_active_profile(self, broadcaster_id: str) -> ChannelProfile | None:
        from bot.profiles import activate_profile

        broadcaster_id = str(broadcaster_id)
        base_profile = self.base_profiles.get(broadcaster_id)

        if base_profile is None:
            return None

        effective_profile = self.apply_overrides(broadcaster_id, base_profile)
        activate_profile(broadcaster_id, effective_profile)
        return effective_profile

    def get_setting_state(self, broadcaster_id: str, setting_name: str) -> ProfileSettingState:
        from bot.profiles import get_active_profile

        definition = self.get_definition(setting_name)
        profile = get_active_profile(str(broadcaster_id))

        if profile is None:
            raise ValueError("No active profile exists for this broadcaster.")

        effective_value = self.get_profile_value(profile, setting_name)
        override_value = self.overrides.get(str(broadcaster_id), {}).get(setting_name)
        default_profile = self.base_profiles.get(str(broadcaster_id), profile)
        default_value = self.get_profile_value(default_profile, setting_name)
        return ProfileSettingState(definition, default_value, override_value, effective_value)

    @staticmethod
    def get_definition(setting_name: str) -> ProfileSettingDefinition:
        definition = PROFILE_SETTINGS_BY_KEY.get(setting_name)

        if definition is None:
            raise ValueError("Unknown profile setting.")

        return definition

    @staticmethod
    def get_profile_value(profile: ChannelProfile, setting_name: str):
        value = profile

        for part in setting_name.split("."):
            value = getattr(value, part)

        if setting_name == "timer_messages":
            return format_timers(value)

        if isinstance(value, tuple):
            return "\n".join(str(item) for item in value)

        return value if value is not None else ""

    @classmethod
    def replace_profile_value(cls, profile: ChannelProfile, setting_name: str, value) -> ChannelProfile:
        parts = setting_name.split(".")

        if setting_name == "timer_messages":
            value = parse_timers(str(value))

        def replace_nested(current, remaining: list[str]):
            field = remaining[0]

            if len(remaining) == 1:
                return replace(current, **{field: value})

            return replace(current, **{field: replace_nested(getattr(current, field), remaining[1:])})

        return replace_nested(profile, parts)

    @staticmethod
    def validate_value(definition: ProfileSettingDefinition, raw_value: str) -> str | int:
        if definition.value_type == "integer":
            value = int(raw_value)

            if definition.minimum is not None and value < definition.minimum:
                raise ValueError(f"{definition.label} must be at least {definition.minimum}.")

            if definition.maximum is not None and value > definition.maximum:
                raise ValueError(f"{definition.label} must be at most {definition.maximum}.")

            return value

        if definition.key == "timer_messages":
            entries = parse_timers(raw_value)
            for entry in entries:
                if not isinstance(entry.message, str) or len(entry.message) > 500:
                    raise ValueError("Each timer message must be 500 characters or fewer.")
                if "\n" in entry.message or "\r" in entry.message:
                    raise ValueError("Each timer must contain a single message.")
            value = format_timers(tuple(type(entry)(entry.message.strip(), entry.kind, entry.color) for entry in entries if entry.message.strip()))
            if len(value) > definition.maximum_length:
                raise ValueError("Timer messages are too long.")
            return value

        value = raw_value.strip()
        if definition.key == "points.display_name" and not value:
            value = "Points"

        if definition.value_type == "lines":
            messages = [line.strip() for line in value.splitlines() if line.strip()]

            if any(len(message) > 500 for message in messages):
                raise ValueError("Each timer message must be 500 characters or fewer.")

            value = "\n".join(messages)

        if len(value) > definition.maximum_length:
            raise ValueError(f"{definition.label} must be {definition.maximum_length} characters or fewer.")

        if definition.key in LOYALTY_PLACEHOLDERS:
            for _, name, spec, conversion in Formatter().parse(value):
                if name is not None and (name not in LOYALTY_PLACEHOLDERS[definition.key] or spec or conversion):
                    raise ValueError("Use only the listed placeholders without formatting modifiers.")
        if definition.group == LOYALTY_GROUP and ("\n" in value or "\r" in value):
            raise ValueError("Use a single line of text.")

        return value

    @staticmethod
    def serialize_value(value: str | int) -> str:
        return json.dumps(value)

    @staticmethod
    def deserialize_value(definition: ProfileSettingDefinition, stored_value: str) -> str | int:
        value = json.loads(stored_value)

        if definition.value_type == "integer" and not isinstance(value, int):
            raise TypeError("Expected an integer setting.")

        if definition.value_type in {"text", "lines"} and not isinstance(value, str):
            raise TypeError("Expected a text setting.")

        return value

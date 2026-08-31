import json
import logging
from dataclasses import dataclass, replace

from bot.profiles import ChannelProfile

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


PROFILE_SETTING_DEFINITIONS = (
    ProfileSettingDefinition("timer_messages", "Timers", "Timer messages", "One automated timer message per line.", value_type="lines", maximum_length=2000, rows=6),
    ProfileSettingDefinition("community_messages.follow", "Community messages", "Follow message", "Sent when a viewer follows. Leave empty to send nothing."),
    ProfileSettingDefinition("community_messages.subscription", "Community messages", "Subscription message", "Sent for a new subscription."),
    ProfileSettingDefinition("community_messages.resubscription", "Community messages", "Resubscription message", "Sent for a returning subscription."),
    ProfileSettingDefinition("raid_messages.incoming", "Raid messages", "Incoming raid message", "Sent when another channel raids this channel."),
    ProfileSettingDefinition("raid_messages.outgoing", "Raid messages", "Outgoing raid message", "Sent when the broadcaster starts a raid."),
    ProfileSettingDefinition("raid_messages.outgoing_subscriber", "Raid messages", "Subscriber raid message", "Optional subscriber variation for outgoing raids."),
    ProfileSettingDefinition("shoutout_messages.with_game", "Shoutouts", "Shoutout with game", "Shoutout used when Twitch provides the target's last game."),
    ProfileSettingDefinition("shoutout_messages.without_game", "Shoutouts", "Shoutout without game", "Shoutout used when no game is available."),
    ProfileSettingDefinition("redeems.daily_title", "Redeems", "Daily redeem title", "Exact Twitch reward title used for the daily claim.", maximum_length=100, rows=1),
    ProfileSettingDefinition("redeems.first_title", "Redeems", "First redeem title", "Exact Twitch reward title used for first place.", maximum_length=100, rows=1),
    ProfileSettingDefinition("redeems.daily_amount", "Redeems", "Daily point reward", "Points awarded for a daily claim.", value_type="integer", minimum=0, maximum=1000000, rows=1),
    ProfileSettingDefinition("redeems.first_amount", "Redeems", "First point reward", "Points awarded for first place.", value_type="integer", minimum=0, maximum=1000000, rows=1),
    ProfileSettingDefinition("league.game_name", "League of Legends", "Riot game name", "The game-name portion of the broadcaster's Riot ID.", maximum_length=100, rows=1),
    ProfileSettingDefinition("league.tag_line", "League of Legends", "Riot tag line", "The tag-line portion of the broadcaster's Riot ID.", maximum_length=20, rows=1),
    ProfileSettingDefinition("league.region", "League of Legends", "Region", "The OP.GG region code, such as NA or EUW.", maximum_length=12, rows=1),
    ProfileSettingDefinition("league.display_name", "League of Legends", "League display name", "Name used when presenting broadcaster League statistics.", maximum_length=100, rows=1),
    ProfileSettingDefinition("overwatch.player_id", "Overwatch", "BattleTag", "The broadcaster's Overwatch BattleTag.", maximum_length=100, rows=1),
    ProfileSettingDefinition("overwatch.platform", "Overwatch", "Platform", "The OverFast platform code, such as pc.", maximum_length=20, rows=1),
    ProfileSettingDefinition("overwatch.display_name", "Overwatch", "Display name", "Name used in Overwatch command responses.", maximum_length=100, rows=1)
)

PROFILE_SETTINGS_BY_KEY = {definition.key: definition for definition in PROFILE_SETTING_DEFINITIONS}
DEVELOPER_PROFILE_MIGRATION_VERSION = 1


class ProfileSettingsService:

    def __init__(self, db):
        self.db = db
        self.overrides: dict[str, dict[str, str | int]] = {}
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

        async with self.db.acquire() as connection:
            await connection.execute(query)
            await connection.execute(migration_query)

        await self.load_overrides()
        LOGGER.info("[Profiles] Loaded database profile overrides for %d broadcaster(s).", len(self.overrides))

    async def load_overrides(self) -> None:
        query = """
        SELECT broadcaster_id, setting_name, setting_value
        FROM channel_profile_overrides
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query)

        loaded: dict[str, dict[str, str | int]] = {}

        for row in rows:
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
        effective_profile = profile

        for setting_name, value in self.overrides.get(broadcaster_id, {}).items():
            effective_profile = self.replace_profile_value(effective_profile, setting_name, value)

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

        if isinstance(value, tuple):
            return "\n".join(str(item) for item in value)

        return value if value is not None else ""

    @classmethod
    def replace_profile_value(cls, profile: ChannelProfile, setting_name: str, value) -> ChannelProfile:
        parts = setting_name.split(".")

        if len(parts) == 1:
            stored_value = tuple(line.strip() for line in str(value).splitlines() if line.strip()) if setting_name == "timer_messages" else value
            return replace(profile, **{setting_name: stored_value})

        if len(parts) == 2:
            section = getattr(profile, parts[0])
            return replace(profile, **{parts[0]: replace(section, **{parts[1]: value})})

        raise ValueError(f"Unsupported profile setting path: {setting_name}")

    @staticmethod
    def validate_value(definition: ProfileSettingDefinition, raw_value: str) -> str | int:
        if definition.value_type == "integer":
            value = int(raw_value)

            if definition.minimum is not None and value < definition.minimum:
                raise ValueError(f"{definition.label} must be at least {definition.minimum}.")

            if definition.maximum is not None and value > definition.maximum:
                raise ValueError(f"{definition.label} must be at most {definition.maximum}.")

            return value

        value = raw_value.strip()

        if len(value) > definition.maximum_length:
            raise ValueError(f"{definition.label} must be {definition.maximum_length} characters or fewer.")

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

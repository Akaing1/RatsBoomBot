import logging
from dataclasses import dataclass

from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")

FEATURE_PREFIX = "feature:"
GLOBAL_GROUP_PREFIX = "global_group:"
GLOBAL_COMMAND_PREFIX = "global_command:"


@dataclass(frozen=True)
class FeatureState:
    feature: FeatureName
    default_enabled: bool
    override_enabled: bool | None
    effective_enabled: bool
    profile_enabled: bool
    blocked_by_profile: bool


@dataclass(frozen=True)
class GlobalGroupState:
    group: GlobalCommandGroup
    default_enabled: bool
    override_enabled: bool | None
    effective_enabled: bool
    profile_enabled: bool
    globals_enabled: bool
    blocked_by_profile: bool
    blocked_by_globals: bool


@dataclass(frozen=True)
class GlobalCommandState:
    command: GlobalCommandName
    default_enabled: bool
    override_enabled: bool | None
    effective_enabled: bool
    profile_enabled: bool
    globals_enabled: bool
    blocked_by_profile: bool
    blocked_by_globals: bool


class FeatureToggleService:

    def __init__(self, db):
        self.db = db
        self.overrides: dict[str, dict[str, bool]] = {}

    async def setup(self) -> None:
        LOGGER.info("[Features] Preparing channel toggle storage.")

        query = """
        CREATE TABLE IF NOT EXISTS channel_feature_overrides (
            broadcaster_id TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (
                broadcaster_id,
                feature_name
            )
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query)
        except Exception:
            LOGGER.exception("[Features] Failed to prepare channel toggle storage.")
            raise

        await self.migrate_legacy_overrides()
        await self.load_overrides()

        override_count = sum(len(channel_overrides) for channel_overrides in self.overrides.values())

        LOGGER.info(
            "[Features] Channel toggle storage ready with %d override(s) across %d broadcaster(s).",
            override_count,
            len(self.overrides)
        )

    async def migrate_legacy_overrides(self) -> None:
        feature_names = {
            FeatureName.CHANNEL.value,
            FeatureName.TIMERS.value,
            FeatureName.POINTS.value,
            FeatureName.REDEEMS.value,
            FeatureName.COMMUNITY_EVENTS.value,
            FeatureName.RAID_RESPONSES.value
        }

        group_names = {
            GlobalCommandGroup.VIEWER_QUEUE.value,
            GlobalCommandGroup.SHOUTOUTS.value,
            GlobalCommandGroup.SOCIALS.value
        }

        query = """
        SELECT broadcaster_id, feature_name, enabled, updated_by
        FROM channel_feature_overrides
        WHERE feature_name NOT LIKE 'feature:%'
          AND feature_name NOT LIKE 'global_group:%'
          AND feature_name NOT LIKE 'global_command:%'
        """

        try:
            async with self.db.acquire() as connection:
                rows = await connection.fetchall(query)

                for row in rows:
                    broadcaster_id = str(row["broadcaster_id"])
                    legacy_name = row["feature_name"]
                    enabled = bool(row["enabled"])
                    updated_by = row["updated_by"] or "legacy-migration"

                    if legacy_name in feature_names:
                        keys = [self.feature_key(FeatureName(legacy_name))]
                    elif legacy_name in group_names:
                        keys = [self.global_group_key(GlobalCommandGroup(legacy_name))]
                    elif legacy_name == "kamikaze":
                        keys = [self.global_command_key(GlobalCommandName.KAMIKAZE)]
                    elif legacy_name == "counters":
                        keys = [
                            self.global_command_key(GlobalCommandName.EXPLODE),
                            self.global_command_key(GlobalCommandName.REKLOP),
                            self.global_command_key(GlobalCommandName.RANDY),
                            self.global_command_key(GlobalCommandName.CAR)
                        ]
                    else:
                        LOGGER.warning(
                            "[Features] Leaving unknown legacy toggle %s unchanged for broadcaster %s.",
                            legacy_name,
                            broadcaster_id
                        )
                        continue

                    for key in keys:
                        await connection.execute(
                            """
                            INSERT INTO channel_feature_overrides (
                                broadcaster_id,
                                feature_name,
                                enabled,
                                updated_by,
                                updated_at
                            )
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(broadcaster_id, feature_name) DO NOTHING
                            """,
                            (broadcaster_id, key, int(enabled), updated_by)
                        )

                    await connection.execute(
                        """
                        DELETE FROM channel_feature_overrides
                        WHERE broadcaster_id = ?
                          AND feature_name = ?
                        """,
                        (broadcaster_id, legacy_name)
                    )

                    LOGGER.info(
                        "[Features] Migrated legacy toggle %s for broadcaster %s.",
                        legacy_name,
                        broadcaster_id
                    )
        except Exception:
            LOGGER.exception("[Features] Failed to migrate legacy channel toggles.")
            raise

    async def load_overrides(self) -> None:
        query = """
        SELECT broadcaster_id, feature_name, enabled
        FROM channel_feature_overrides
        """

        try:
            async with self.db.acquire() as connection:
                rows = await connection.fetchall(query)
        except Exception:
            LOGGER.exception("[Features] Failed to load channel toggle overrides.")
            raise

        loaded_overrides: dict[str, dict[str, bool]] = {}
        skipped_count = 0

        for row in rows:
            broadcaster_id = str(row["broadcaster_id"])
            key = row["feature_name"]

            if not self.is_valid_key(key):
                skipped_count += 1

                LOGGER.warning(
                    "[Features] Ignored unknown stored toggle %s for broadcaster %s.",
                    key,
                    broadcaster_id
                )
                continue

            channel_overrides = loaded_overrides.setdefault(broadcaster_id, {})
            channel_overrides[key] = bool(row["enabled"])

        self.overrides = loaded_overrides

        override_count = sum(len(channel_overrides) for channel_overrides in self.overrides.values())

        LOGGER.info(
            "[Features] Loaded %d toggle override(s) across %d broadcaster(s).",
            override_count,
            len(self.overrides)
        )

        if skipped_count:
            LOGGER.warning(
                "[Features] Skipped %d unknown stored toggle override(s).",
                skipped_count
            )

    async def set_enabled(self, broadcaster_id: str, feature: FeatureName, enabled: bool, updated_by: str) -> FeatureState:
        broadcaster_id = str(broadcaster_id)
        key = self.feature_key(feature)

        await self.set_override(broadcaster_id, key, enabled, updated_by)

        return self.get_feature_state(broadcaster_id, feature)

    async def set_global_group_enabled(self, broadcaster_id: str, group: GlobalCommandGroup, enabled: bool, updated_by: str) -> GlobalGroupState:
        broadcaster_id = str(broadcaster_id)
        key = self.global_group_key(group)

        await self.set_override(broadcaster_id, key, enabled, updated_by)

        return self.get_global_group_state(broadcaster_id, group)

    async def set_global_command_enabled(self, broadcaster_id: str, command: GlobalCommandName, enabled: bool, updated_by: str) -> GlobalCommandState:
        broadcaster_id = str(broadcaster_id)
        key = self.global_command_key(command)

        await self.set_override(broadcaster_id, key, enabled, updated_by)

        return self.get_global_command_state(broadcaster_id, command)

    async def clear_override(self, broadcaster_id: str, feature: FeatureName, updated_by: str) -> FeatureState:
        broadcaster_id = str(broadcaster_id)

        await self.clear_stored_override(broadcaster_id, self.feature_key(feature), updated_by)

        return self.get_feature_state(broadcaster_id, feature)

    async def clear_global_group_override(self, broadcaster_id: str, group: GlobalCommandGroup, updated_by: str) -> GlobalGroupState:
        broadcaster_id = str(broadcaster_id)

        await self.clear_stored_override(broadcaster_id, self.global_group_key(group), updated_by)

        return self.get_global_group_state(broadcaster_id, group)

    async def clear_global_command_override(self, broadcaster_id: str, command: GlobalCommandName, updated_by: str) -> GlobalCommandState:
        broadcaster_id = str(broadcaster_id)

        await self.clear_stored_override(broadcaster_id, self.global_command_key(command), updated_by)

        return self.get_global_command_state(broadcaster_id, command)

    async def set_override(self, broadcaster_id: str, key: str, enabled: bool, updated_by: str) -> None:
        query = """
        INSERT INTO channel_feature_overrides (
            broadcaster_id,
            feature_name,
            enabled,
            updated_by,
            updated_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (
            broadcaster_id,
            feature_name
        ) DO UPDATE SET
            enabled = excluded.enabled,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id, key, int(enabled), updated_by))
        except Exception:
            LOGGER.exception(
                "[Features] Failed to set toggle %s to %s for broadcaster %s.",
                key,
                enabled,
                broadcaster_id
            )
            raise

        channel_overrides = self.overrides.setdefault(broadcaster_id, {})
        channel_overrides[key] = enabled

        LOGGER.info(
            "[Features] Toggle %s was %s for broadcaster %s by %s.",
            key,
            "enabled" if enabled else "disabled",
            broadcaster_id,
            updated_by
        )

    async def clear_stored_override(self, broadcaster_id: str, key: str, updated_by: str) -> None:
        query = """
        DELETE FROM channel_feature_overrides
        WHERE broadcaster_id = ?
          AND feature_name = ?
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id, key))
        except Exception:
            LOGGER.exception(
                "[Features] Failed to clear toggle %s for broadcaster %s.",
                key,
                broadcaster_id
            )
            raise

        channel_overrides = self.overrides.get(broadcaster_id)

        if channel_overrides is not None:
            channel_overrides.pop(key, None)

            if not channel_overrides:
                self.overrides.pop(broadcaster_id, None)

        LOGGER.info(
            "[Features] Toggle %s override was cleared for broadcaster %s by %s.",
            key,
            broadcaster_id,
            updated_by
        )

    def is_enabled(self, broadcaster_id: str, feature: FeatureName) -> bool:
        return self.get_feature_state(broadcaster_id, feature).effective_enabled

    def is_global_group_enabled(self, broadcaster_id: str, group: GlobalCommandGroup) -> bool:
        return self.get_global_group_state(broadcaster_id, group).effective_enabled

    def is_global_command_enabled(self, broadcaster_id: str, command: GlobalCommandName) -> bool:
        return self.get_global_command_state(broadcaster_id, command).effective_enabled

    def get_feature_state(self, broadcaster_id: str, feature: FeatureName) -> FeatureState:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return FeatureState(
                feature=feature,
                default_enabled=False,
                override_enabled=None,
                effective_enabled=False,
                profile_enabled=False,
                blocked_by_profile=False
            )

        key = self.feature_key(feature)
        override_enabled = self.get_override(broadcaster_id, key)
        default_enabled = profile.features.is_enabled(feature)
        configured_enabled = override_enabled if override_enabled is not None else default_enabled
        profile_enabled = self.get_profile_enabled(broadcaster_id)

        if feature is FeatureName.CHANNEL:
            blocked_by_profile = False
            effective_enabled = configured_enabled
        else:
            blocked_by_profile = configured_enabled and not profile_enabled
            effective_enabled = configured_enabled and profile_enabled

        return FeatureState(
            feature=feature,
            default_enabled=default_enabled,
            override_enabled=override_enabled,
            effective_enabled=effective_enabled,
            profile_enabled=profile_enabled,
            blocked_by_profile=blocked_by_profile
        )

    def get_global_group_state(self, broadcaster_id: str, group: GlobalCommandGroup) -> GlobalGroupState:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return GlobalGroupState(
                group=group,
                default_enabled=False,
                override_enabled=None,
                effective_enabled=False,
                profile_enabled=False,
                globals_enabled=False,
                blocked_by_profile=False,
                blocked_by_globals=False
            )

        key = self.global_group_key(group)
        override_enabled = self.get_override(broadcaster_id, key)
        default_enabled = profile.globals.is_group_enabled(group)
        configured_enabled = override_enabled if override_enabled is not None else default_enabled
        profile_enabled = self.get_profile_enabled(broadcaster_id)

        if group is GlobalCommandGroup.GLOBALS:
            globals_enabled = configured_enabled
            blocked_by_globals = False
            effective_enabled = configured_enabled and profile_enabled
        else:
            globals_enabled = self.get_globals_enabled(broadcaster_id)
            blocked_by_globals = configured_enabled and not globals_enabled
            effective_enabled = configured_enabled and globals_enabled and profile_enabled

        blocked_by_profile = configured_enabled and not profile_enabled

        return GlobalGroupState(
            group=group,
            default_enabled=default_enabled,
            override_enabled=override_enabled,
            effective_enabled=effective_enabled,
            profile_enabled=profile_enabled,
            globals_enabled=globals_enabled,
            blocked_by_profile=blocked_by_profile,
            blocked_by_globals=blocked_by_globals
        )

    def get_global_command_state(self, broadcaster_id: str, command: GlobalCommandName) -> GlobalCommandState:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return GlobalCommandState(
                command=command,
                default_enabled=False,
                override_enabled=None,
                effective_enabled=False,
                profile_enabled=False,
                globals_enabled=False,
                blocked_by_profile=False,
                blocked_by_globals=False
            )

        key = self.global_command_key(command)
        override_enabled = self.get_override(broadcaster_id, key)
        default_enabled = profile.globals.is_command_enabled(command)
        configured_enabled = override_enabled if override_enabled is not None else default_enabled
        profile_enabled = self.get_profile_enabled(broadcaster_id)
        globals_enabled = self.get_globals_enabled(broadcaster_id)
        blocked_by_profile = configured_enabled and not profile_enabled
        blocked_by_globals = configured_enabled and not globals_enabled
        effective_enabled = configured_enabled and globals_enabled and profile_enabled

        return GlobalCommandState(
            command=command,
            default_enabled=default_enabled,
            override_enabled=override_enabled,
            effective_enabled=effective_enabled,
            profile_enabled=profile_enabled,
            globals_enabled=globals_enabled,
            blocked_by_profile=blocked_by_profile,
            blocked_by_globals=blocked_by_globals
        )

    def get_profile_enabled(self, broadcaster_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return False

        override_enabled = self.get_override(broadcaster_id, self.feature_key(FeatureName.CHANNEL))

        if override_enabled is not None:
            return override_enabled

        return profile.features.is_enabled(FeatureName.CHANNEL)

    def get_globals_enabled(self, broadcaster_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return False

        key = self.global_group_key(GlobalCommandGroup.GLOBALS)
        override_enabled = self.get_override(broadcaster_id, key)

        if override_enabled is not None:
            return override_enabled

        return profile.globals.is_group_enabled(GlobalCommandGroup.GLOBALS)

    def get_channel_features(self, broadcaster_id: str) -> dict[FeatureName, FeatureState]:
        return {feature: self.get_feature_state(broadcaster_id, feature) for feature in FeatureName}

    def get_global_groups(self, broadcaster_id: str) -> dict[GlobalCommandGroup, GlobalGroupState]:
        return {group: self.get_global_group_state(broadcaster_id, group) for group in GlobalCommandGroup}

    def get_global_commands(self, broadcaster_id: str) -> dict[GlobalCommandName, GlobalCommandState]:
        return {command: self.get_global_command_state(broadcaster_id, command) for command in GlobalCommandName}

    def get_override(self, broadcaster_id: str, key: str) -> bool | None:
        channel_overrides = self.overrides.get(str(broadcaster_id), {})
        return channel_overrides.get(key)

    @staticmethod
    def feature_key(feature: FeatureName) -> str:
        return f"{FEATURE_PREFIX}{feature.value}"

    @staticmethod
    def global_group_key(group: GlobalCommandGroup) -> str:
        return f"{GLOBAL_GROUP_PREFIX}{group.value}"

    @staticmethod
    def global_command_key(command: GlobalCommandName) -> str:
        return f"{GLOBAL_COMMAND_PREFIX}{command.value}"

    @staticmethod
    def is_valid_key(key: str) -> bool:
        try:
            if key.startswith(FEATURE_PREFIX):
                FeatureName(key.removeprefix(FEATURE_PREFIX))
                return True

            if key.startswith(GLOBAL_GROUP_PREFIX):
                GlobalCommandGroup(key.removeprefix(GLOBAL_GROUP_PREFIX))
                return True

            if key.startswith(GLOBAL_COMMAND_PREFIX):
                GlobalCommandName(key.removeprefix(GLOBAL_COMMAND_PREFIX))
                return True
        except ValueError:
            return False

        return False

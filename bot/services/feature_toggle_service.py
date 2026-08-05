import logging
from dataclasses import dataclass

from bot.profiles import (
    FeatureName,
    get_active_profile
)

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class FeatureState:
    feature: FeatureName
    default_enabled: bool
    override_enabled: bool | None
    effective_enabled: bool
    profile_enabled: bool
    blocked_by_profile: bool


class FeatureToggleService:

    def __init__(self, db):
        self.db = db
        self.overrides: dict[str, dict[FeatureName, bool]] = {}

    async def setup(self) -> None:

        LOGGER.info(
            "[Features] Preparing channel feature toggle storage."
        )

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
            LOGGER.exception(
                "[Features] Failed to prepare feature toggle storage."
            )
            raise

        await self.load_overrides()

        LOGGER.info(
            "[Features] Feature toggle storage ready with %d channel override set(s).",
            len(self.overrides)
        )

    async def load_overrides(self) -> None:

        query = """
        SELECT
            broadcaster_id,
            feature_name,
            enabled
        FROM channel_feature_overrides
        """

        try:
            async with self.db.acquire() as connection:
                rows = await connection.fetchall(query)
        except Exception:
            LOGGER.exception(
                "[Features] Failed to load channel feature overrides."
            )
            raise

        loaded_overrides: dict[
            str,
            dict[FeatureName, bool]
        ] = {}

        skipped_count = 0

        for row in rows:
            broadcaster_id = str(
                row["broadcaster_id"]
            )

            try:
                feature = FeatureName(
                    row["feature_name"]
                )
            except ValueError:
                skipped_count += 1

                LOGGER.warning(
                    "[Features] Ignored unknown stored feature %s for broadcaster %s.",
                    row["feature_name"],
                    broadcaster_id
                )
                continue

            channel_overrides = loaded_overrides.setdefault(
                broadcaster_id,
                {}
            )

            channel_overrides[feature] = bool(
                row["enabled"]
            )

        self.overrides = loaded_overrides

        LOGGER.info(
            "[Features] Loaded %d feature override(s) across %d broadcaster(s).",
            sum(
                len(channel_overrides)
                for channel_overrides in self.overrides.values()
            ),
            len(self.overrides)
        )

        if skipped_count:
            LOGGER.warning(
                "[Features] Skipped %d unknown stored feature override(s).",
                skipped_count
            )

    async def set_enabled(self, broadcaster_id: str, feature: FeatureName, enabled: bool,
                          updated_by: str) -> FeatureState:

        broadcaster_id = str(broadcaster_id)

        query = """
        INSERT INTO channel_feature_overrides (
            broadcaster_id,
            feature_name,
            enabled,
            updated_by,
            updated_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(
            broadcaster_id,
            feature_name
        ) DO UPDATE SET
            enabled = excluded.enabled,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        broadcaster_id,
                        feature.value,
                        int(enabled),
                        updated_by
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Features] Failed to set feature %s to %s for broadcaster %s.",
                feature.value,
                enabled,
                broadcaster_id
            )
            raise

        channel_overrides = self.overrides.setdefault(
            broadcaster_id,
            {}
        )

        channel_overrides[feature] = enabled

        LOGGER.info(
            "[Features] Feature %s was %s for broadcaster %s by %s.",
            feature.value,
            "enabled" if enabled else "disabled",
            broadcaster_id,
            updated_by
        )

        return self.get_feature_state(
            broadcaster_id,
            feature
        )

    async def clear_override(self, broadcaster_id: str, feature: FeatureName, updated_by: str) -> FeatureState:

        broadcaster_id = str(broadcaster_id)

        query = """
        DELETE FROM channel_feature_overrides
        WHERE broadcaster_id = ?
          AND feature_name = ?
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(
                    query,
                    (
                        broadcaster_id,
                        feature.value
                    )
                )
        except Exception:
            LOGGER.exception(
                "[Features] Failed to clear feature %s override for broadcaster %s.",
                feature.value,
                broadcaster_id
            )
            raise

        channel_overrides = self.overrides.get(broadcaster_id)

        if channel_overrides is not None:
            channel_overrides.pop(
                feature,
                None
            )

            if not channel_overrides:
                self.overrides.pop(
                    broadcaster_id,
                    None
                )

        LOGGER.info(
            "[Features] Feature %s override was cleared for broadcaster %s by %s.",
            feature.value,
            broadcaster_id,
            updated_by
        )

        return self.get_feature_state(
            broadcaster_id,
            feature
        )

    def is_enabled(self, broadcaster_id: str, feature: FeatureName) -> bool:

        return self.get_feature_state(broadcaster_id, feature).effective_enabled

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

        default_enabled = profile.features.is_enabled(feature)
        override_enabled = self.overrides.get(broadcaster_id, {}).get(feature)

        configured_enabled = (
            override_enabled
            if override_enabled is not None
            else default_enabled
        )

        profile_enabled = self.get_profile_enabled(broadcaster_id)

        blocked_by_profile = (
                feature is not FeatureName.PROFILE
                and configured_enabled
                and not profile_enabled
        )

        effective_enabled = (
            configured_enabled
            if feature is FeatureName.PROFILE
            else configured_enabled and profile_enabled
        )

        return FeatureState(
            feature=feature,
            default_enabled=default_enabled,
            override_enabled=override_enabled,
            effective_enabled=effective_enabled,
            profile_enabled=profile_enabled,
            blocked_by_profile=blocked_by_profile
        )

    def get_profile_enabled(self, broadcaster_id: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return False

        default_enabled = profile.features.is_enabled(FeatureName.PROFILE)
        override_enabled = self.overrides.get(broadcaster_id, {}).get(FeatureName.PROFILE)

        if override_enabled is not None:
            return override_enabled

        return default_enabled

    def get_channel_features(self, broadcaster_id: str) -> dict[FeatureName, FeatureState]:

        broadcaster_id = str(broadcaster_id)

        return {
            feature: self.get_feature_state(broadcaster_id, feature)
            for feature in FeatureName
        }

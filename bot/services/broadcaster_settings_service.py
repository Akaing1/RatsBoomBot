import logging
from dataclasses import dataclass

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class BroadcasterSettings:
    broadcaster_id: str
    discord_url: str | None = None
    youtube_url: str | None = None
    timers_enabled: bool = True


class BroadcasterSettingsService:

    def __init__(self, db):
        self.db = db

    async def setup(self) -> None:
        LOGGER.info("[Broadcaster Settings] Preparing broadcaster settings storage.")

        query = """
        CREATE TABLE IF NOT EXISTS broadcaster_settings (
            broadcaster_id TEXT PRIMARY KEY,
            discord_url TEXT,
            youtube_url TEXT,
            timers_enabled INTEGER NOT NULL DEFAULT 1
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query)
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to prepare broadcaster settings storage."
            )
            raise

        LOGGER.info("[Broadcaster Settings] Broadcaster settings storage ready.")

    async def get_settings(self, broadcaster_id: str) -> BroadcasterSettings:
        broadcaster_id = str(broadcaster_id)

        query = """
        SELECT broadcaster_id, discord_url, youtube_url, timers_enabled
        FROM broadcaster_settings
        WHERE broadcaster_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (broadcaster_id,))
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to load settings for broadcaster %s.",
                broadcaster_id
            )
            raise

        if not row:
            LOGGER.debug(
                "[Broadcaster Settings] No saved settings found for broadcaster %s. Using defaults.",
                broadcaster_id
            )
            return BroadcasterSettings(broadcaster_id=broadcaster_id)

        LOGGER.debug(
            "[Broadcaster Settings] Loaded settings for broadcaster %s.",
            broadcaster_id
        )

        return BroadcasterSettings(
            broadcaster_id=row["broadcaster_id"],
            discord_url=row["discord_url"],
            youtube_url=row["youtube_url"],
            timers_enabled=bool(row["timers_enabled"])
        )

    async def set_discord_url(self, broadcaster_id: str, discord_url: str) -> None:
        broadcaster_id = str(broadcaster_id)

        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, discord_url)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            discord_url = excluded.discord_url
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id, discord_url))
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to update Discord URL for broadcaster %s.",
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Broadcaster Settings] Updated Discord URL for broadcaster %s.",
            broadcaster_id
        )

    async def set_youtube_url(self, broadcaster_id: str, youtube_url: str) -> None:
        broadcaster_id = str(broadcaster_id)

        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, youtube_url)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            youtube_url = excluded.youtube_url
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id, youtube_url))
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to update YouTube URL for broadcaster %s.",
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Broadcaster Settings] Updated YouTube URL for broadcaster %s.",
            broadcaster_id
        )

    async def set_timers_enabled(self, broadcaster_id: str, enabled: bool) -> None:
        broadcaster_id = str(broadcaster_id)

        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, timers_enabled)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            timers_enabled = excluded.timers_enabled
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query, (broadcaster_id, int(enabled)))
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to update timer state for broadcaster %s.",
                broadcaster_id
            )
            raise

        LOGGER.info(
            "[Broadcaster Settings] Timers %s for broadcaster %s.",
            "enabled" if enabled else "disabled",
            broadcaster_id
        )

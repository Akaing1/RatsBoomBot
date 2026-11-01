import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class BroadcasterSettings:
    broadcaster_id: str
    discord_url: str | None = None
    youtube_url: str | None = None
    tiktok_url: str | None = None
    x_url: str | None = None
    kofi_url: str | None = None
    vgen_url: str | None = None
    timers_enabled: bool = True
    follow_raid: bool = True


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
            timers_enabled INTEGER NOT NULL DEFAULT 1,
            follow_raid INTEGER NOT NULL DEFAULT 1
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query)
                await connection.execute("""CREATE TABLE IF NOT EXISTS broadcaster_social_links (
                    broadcaster_id TEXT NOT NULL, platform TEXT NOT NULL, url TEXT NOT NULL,
                    PRIMARY KEY (broadcaster_id, platform))""")
        except Exception:
            LOGGER.exception(
                "[Broadcaster Settings] Failed to prepare broadcaster settings storage."
            )
            raise

        LOGGER.info("[Broadcaster Settings] Broadcaster settings storage ready.")

    async def get_settings(self, broadcaster_id: str) -> BroadcasterSettings:
        broadcaster_id = str(broadcaster_id)

        query = """
        SELECT broadcaster_id, discord_url, youtube_url, timers_enabled, follow_raid
        FROM broadcaster_settings
        WHERE broadcaster_id = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (broadcaster_id,))
                social_rows = await connection.fetchall("SELECT platform, url FROM broadcaster_social_links WHERE broadcaster_id = ?", (broadcaster_id,))
                socials = {f"{item['platform']}_url": item['url'] for item in social_rows if item['platform'] in {"tiktok", "x", "kofi", "vgen"}}
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
            return BroadcasterSettings(broadcaster_id=broadcaster_id, **socials)

        LOGGER.debug(
            "[Broadcaster Settings] Loaded settings for broadcaster %s.",
            broadcaster_id
        )

        return BroadcasterSettings(
            broadcaster_id=row["broadcaster_id"],
            discord_url=row["discord_url"],
            youtube_url=row["youtube_url"],
            timers_enabled=bool(row["timers_enabled"]),
            follow_raid=bool(row["follow_raid"]), **socials
        )

    async def set_social_url(self, broadcaster_id: str, platform: str, url: str) -> None:
        if platform not in {"tiktok", "x", "kofi", "vgen"}:
            raise ValueError("Unknown social platform.")
        url = url.strip()
        parsed = urlsplit(url)
        if url and (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or len(url) > 2000):
            raise ValueError("Enter a valid HTTP or HTTPS URL.")
        async with self.db.acquire() as connection:
            if url:
                await connection.execute("""INSERT INTO broadcaster_social_links (broadcaster_id, platform, url) VALUES (?, ?, ?)
                    ON CONFLICT(broadcaster_id, platform) DO UPDATE SET url = excluded.url""", (str(broadcaster_id), platform, url))
            else:
                await connection.execute("DELETE FROM broadcaster_social_links WHERE broadcaster_id = ? AND platform = ?", (str(broadcaster_id), platform))

    async def set_follow_raid(self, broadcaster_id: str, enabled: bool) -> None:
        async with self.db.acquire() as connection:
            await connection.execute("""INSERT INTO broadcaster_settings (broadcaster_id, follow_raid) VALUES (?, ?)
                ON CONFLICT(broadcaster_id) DO UPDATE SET follow_raid = excluded.follow_raid""",
                (str(broadcaster_id), int(enabled)))

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

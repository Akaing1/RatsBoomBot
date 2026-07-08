from dataclasses import dataclass


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
        query = """
        CREATE TABLE IF NOT EXISTS broadcaster_settings (
            broadcaster_id TEXT PRIMARY KEY,
            discord_url TEXT,
            youtube_url TEXT,
            timers_enabled INTEGER NOT NULL DEFAULT 1
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

    async def get_settings(self, broadcaster_id: str) -> BroadcasterSettings:
        query = """
        SELECT broadcaster_id, discord_url, youtube_url, timers_enabled
        FROM broadcaster_settings
        WHERE broadcaster_id = ?
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (broadcaster_id,))

        if not row:
            return BroadcasterSettings(broadcaster_id=broadcaster_id)

        return BroadcasterSettings(
            broadcaster_id=row["broadcaster_id"],
            discord_url=row["discord_url"],
            youtube_url=row["youtube_url"],
            timers_enabled=bool(row["timers_enabled"])
        )

    async def set_discord_url(self, broadcaster_id: str, discord_url: str) -> None:
        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, discord_url)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            discord_url = excluded.discord_url
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, discord_url))

    async def set_youtube_url(self, broadcaster_id: str, youtube_url: str) -> None:
        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, youtube_url)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            youtube_url = excluded.youtube_url
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, youtube_url))

    async def set_timers_enabled(self, broadcaster_id: str, enabled: bool) -> None:
        query = """
        INSERT INTO broadcaster_settings (broadcaster_id, timers_enabled)
        VALUES (?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            timers_enabled = excluded.timers_enabled
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, int(enabled)))

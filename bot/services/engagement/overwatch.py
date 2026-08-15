import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from bot.profiles import OverwatchConfig

LOGGER = logging.getLogger("RatBoomBot")
OVERFAST_BASE_URL = "https://overfast-api.tekrop.fr"


class OverwatchNotConfiguredError(ValueError):
    pass


@dataclass(frozen=True)
class OverwatchSession:
    wins: int = 0
    losses: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses


class OverwatchService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def setup(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS overwatch_sessions (
            broadcaster_id TEXT PRIMARY KEY,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

    async def is_allowed_game(self, broadcaster_id: str, config: OverwatchConfig) -> bool:
        try:
            broadcaster = self.bot.create_partialuser(str(broadcaster_id))
            stream = await broadcaster.fetch_stream()
        except Exception:
            LOGGER.exception("[Overwatch] Failed to fetch the current game for broadcaster %s.", broadcaster_id)
            return False

        if stream is None:
            return False

        game_name = str(getattr(stream, "game_name", "") or "").casefold()
        return game_name in {game.casefold() for game in config.allowed_games}

    async def get_session(self, broadcaster_id: str) -> OverwatchSession:
        query = "SELECT wins, losses FROM overwatch_sessions WHERE broadcaster_id = ?"

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(broadcaster_id),))

        if row is None:
            return OverwatchSession()

        return OverwatchSession(wins=int(row[0]), losses=int(row[1]))

    async def record_result(self, broadcaster_id: str, result: str) -> OverwatchSession:
        column = "wins" if result == "win" else "losses"
        query = f"""
        INSERT INTO overwatch_sessions (broadcaster_id, {column})
        VALUES (?, 1)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            {column} = {column} + 1,
            updated_at = CURRENT_TIMESTAMP
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (str(broadcaster_id),))

        return await self.get_session(broadcaster_id)

    async def reset_session(self, broadcaster_id: str) -> None:
        query = "DELETE FROM overwatch_sessions WHERE broadcaster_id = ?"

        async with self.db.acquire() as connection:
            await connection.execute(query, (str(broadcaster_id),))

    async def fetch_ranks(self, config: OverwatchConfig) -> dict[str, str | None]:
        if not config.player_id:
            raise OverwatchNotConfiguredError("Overwatch player ID is not configured.")

        player_id = quote(config.player_id.replace("#", "-"), safe="-")
        url = f"{OVERFAST_BASE_URL}/players/{player_id}/summary"

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        competitive = payload.get("competitive") or {}
        platform = competitive.get(config.platform) or {}
        ranks: dict[str, str | None] = {}

        for role in ("tank", "damage", "support", "open"):
            rank = platform.get(role)
            ranks[role] = self.format_rank(rank)

        return ranks

    @staticmethod
    def format_rank(rank: dict | None) -> str | None:
        if not rank:
            return None

        division = str(rank.get("division", "")).strip().title()
        tier = rank.get("tier")

        if not division or tier is None:
            return None

        return f"{division} {tier}"

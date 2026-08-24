import ast
import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations

import httpx

from bot.profiles import ACTIVE_CHANNEL_PROFILES, LeagueConfig

LOGGER = logging.getLogger("RatBoomBot")
OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"
OPGG_PROTOCOL_VERSION = "2025-06-18"
MATCH_REFRESH_SECONDS = 60 * 60 * 4
SEASON_REFRESH_SECONDS = 60 * 60 * 12
ITEM_REFRESH_SECONDS = 60 * 60 * 24
BUILD_RETENTION_DAYS = 14
COMMUNITY_RANK_REFRESH_SECONDS = 60 * 60 * 12
SUPPORTED_REGIONS = ("BR", "EUNE", "EUW", "JP", "KR", "LAN", "LAS", "NA", "OCE", "PH", "RU", "SG", "TH", "TR", "TW", "VN")
RANKED_QUEUES = ("SOLORANKED", "FLEXRANKED")
TIER_ORDER = {tier: index for index, tier in enumerate(("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"))}
DIVISION_ORDER = {"IV": 0, "III": 1, "II": 2, "I": 3}
NUMBER_DIVISIONS = {1: "I", 2: "II", 3: "III", 4: "IV"}


class LeagueProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class TypedValue:
    name: str
    values: tuple


@dataclass(frozen=True)
class SeasonalChampion:
    name: str
    games: int
    wins: int
    losses: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.games * 100 if self.games else 0.0


@dataclass(frozen=True)
class SeasonSummary:
    season_id: str
    game_type: str
    champions: tuple[SeasonalChampion, ...]


@dataclass(frozen=True)
class RecentMatch:
    match_id: str
    started_at: str
    game_type: str
    duration_seconds: int
    champion_name: str
    result: str
    item_ids: tuple[int, ...]
    role_bound_item: int | None


@dataclass(frozen=True)
class CoreBuild:
    champion_name: str
    item_names: tuple[str, str, str]
    games: int
    matching_games: int


@dataclass(frozen=True)
class RankEntry:
    queue_type: str
    tier: str | None
    division: str | None
    lp: int
    wins: int
    losses: int

    @property
    def games(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return self.wins / self.games * 100 if self.games else 0.0

    @property
    def score(self) -> int:
        if self.tier is None:
            return -1

        return TIER_ORDER.get(self.tier.upper(), -1) * 100000 + DIVISION_ORDER.get(self.division or "", 0) * 10000 + self.lp


@dataclass(frozen=True)
class RankProfile:
    game_name: str
    tag_line: str
    region: str
    ranks: tuple[RankEntry, ...]


@dataclass(frozen=True)
class LeagueRegistration:
    broadcaster_id: str
    user_id: str
    twitch_login: str
    twitch_display_name: str
    game_name: str
    tag_line: str
    region: str
    refreshed_at: str


@dataclass(frozen=True)
class CommunityRank:
    registration: LeagueRegistration
    rank: RankEntry | None


def _convert_ast_node(node):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name) and node.id in {"null", "true", "false"}:
        return {"null": None, "true": True, "false": False}[node.id]

    if isinstance(node, ast.List):
        return [_convert_ast_node(item) for item in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_convert_ast_node(item) for item in node.elts)

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        return TypedValue(node.func.id, tuple(_convert_ast_node(argument) for argument in node.args))

    raise LeagueProviderError(f"Unsupported OP.GG response node: {type(node).__name__}")


def parse_typed_response(text: str) -> TypedValue:
    expression = text.rsplit("\n\n", 1)[-1].strip()

    try:
        parsed = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as error:
        raise LeagueProviderError("OP.GG returned an unreadable typed response.") from error

    value = _convert_ast_node(parsed.body)

    if not isinstance(value, TypedValue):
        raise LeagueProviderError("OP.GG returned an unexpected response value.")

    return value


def unwrap_typed(value: TypedValue, expected_name: str) -> tuple:
    if not isinstance(value, TypedValue) or value.name != expected_name:
        actual_name = getattr(value, "name", type(value).__name__)
        raise LeagueProviderError(f"Expected {expected_name} from OP.GG, received {actual_name}.")

    return value.values


def normalize_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise LeagueProviderError(f"OP.GG returned an invalid match timestamp: {value}") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


class OpggMcpClient:

    def __init__(self, url: str = OPGG_MCP_URL, timeout_seconds: float = 30):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.client: httpx.AsyncClient | None = None
        self.session_id: str | None = None
        self.request_id = 0

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout_seconds)
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self.client is not None:
            await self.client.aclose()

        self.client = None
        self.session_id = None

    async def initialize(self) -> None:
        params = {
            "protocolVersion": OPGG_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "RatsBoomBot", "version": "1.0"}
        }
        response = await self._post("initialize", params, include_session=False)
        self.session_id = response.headers.get("mcp-session-id")

        if not self.session_id:
            raise LeagueProviderError("OP.GG did not provide an MCP session ID.")

        await self._post("notifications/initialized", {}, notification=True)

    async def call_tool(self, name: str, arguments: dict) -> str:
        response = await self._post("tools/call", {"name": name, "arguments": arguments})
        payload = response.json()

        if payload.get("error"):
            raise LeagueProviderError(str(payload["error"]))

        result = payload.get("result") or {}

        if result.get("isError"):
            raise LeagueProviderError(f"OP.GG tool {name} returned an error.")

        for content in result.get("content") or ():
            if content.get("type") == "text":
                return str(content.get("text") or "")

        raise LeagueProviderError(f"OP.GG tool {name} returned no text content.")

    async def _post(self, method: str, params: dict, *, include_session: bool = True, notification: bool = False) -> httpx.Response:
        if self.client is None:
            raise LeagueProviderError("The OP.GG MCP client has not been initialized.")

        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

        if include_session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {"jsonrpc": "2.0", "method": method, "params": params}

        if not notification:
            self.request_id += 1
            payload["id"] = self.request_id

        response = await self.client.post(self.url, headers=headers, json=payload)
        response.raise_for_status()
        return response

    async def fetch_season_summary(self, config: LeagueConfig) -> SeasonSummary:
        fields = (
            "data.summoner.ranked_most_champions.{game_type,season_id,play,win,lose}",
            "data.summoner.ranked_most_champions.my_champion_stats[].{champion_name,play,win,lose}"
        )
        text = await self.call_tool("lol_get_summoner_profile", {
            "game_name": config.game_name,
            "tag_line": config.tag_line,
            "region": config.region,
            "lang": "en_US",
            "desired_output_fields": list(fields)
        })
        root = parse_typed_response(text)
        data = unwrap_typed(root, "LolGetSummonerProfile")[0]
        summoner = unwrap_typed(unwrap_typed(data, "Data")[0], "Summoner")
        ranked = unwrap_typed(summoner[0], "RankedMostChampions")
        game_type, season_id, _play, _win, _lose, champion_values = ranked
        champions = []

        for champion_value in champion_values:
            play, win, lose, champion_name = unwrap_typed(champion_value, "MyChampionStat")
            champions.append(SeasonalChampion(str(champion_name), int(play), int(win), int(lose)))

        champions.sort(key=lambda champion: (-champion.games, champion.name.casefold()))
        return SeasonSummary(str(season_id), str(game_type), tuple(champions))

    async def fetch_recent_matches(self, config: LeagueConfig) -> tuple[RecentMatch, ...]:
        fields = (
            "data.game_history[].{id,created_at,game_type,game_length_second}",
            "data.game_history[].participants[].{champion_name,items[],role_bound_item}",
            "data.game_history[].participants[].stats.result"
        )
        text = await self.call_tool("lol_list_summoner_matches", {
            "game_name": config.game_name,
            "tag_line": config.tag_line,
            "region": config.region,
            "lang": "en_US",
            "limit": 20,
            "desired_output_fields": list(fields)
        })
        root = parse_typed_response(text)
        data = unwrap_typed(root, "LolListSummonerMatches")[0]
        history = unwrap_typed(data, "Data")[0]
        matches = []

        for match_value in history:
            match_id, started_at, game_type, duration_seconds, participants = unwrap_typed(match_value, "GameHistory")

            if not participants:
                continue

            champion_name, item_ids, stats_value, role_bound_item = unwrap_typed(participants[0], "Participant")
            result = unwrap_typed(stats_value, "Stats")[0]
            matches.append(RecentMatch(
                match_id=str(match_id),
                started_at=normalize_timestamp(str(started_at)),
                game_type=str(game_type),
                duration_seconds=int(duration_seconds),
                champion_name=str(champion_name),
                result=str(result),
                item_ids=tuple(int(item_id) for item_id in item_ids),
                role_bound_item=int(role_bound_item) if role_bound_item is not None else None
            ))

        return tuple(matches)

    async def fetch_rank_profile(self, game_name: str, tag_line: str, region: str) -> RankProfile:
        fields = (
            "data.summoner.{game_name,tagline}",
            "data.summoner.league_stats[].{game_type,win,lose}",
            "data.summoner.league_stats[].tier_info.{division,level,lp,tier}"
        )
        text = await self.call_tool("lol_get_summoner_profile", {
            "game_name": game_name,
            "tag_line": tag_line,
            "region": region,
            "lang": "en_US",
            "desired_output_fields": list(fields)
        })
        root = parse_typed_response(text)
        data = unwrap_typed(root, "LolGetSummonerProfile")[0]
        returned_game_name, returned_tag_line, league_stats = unwrap_typed(unwrap_typed(data, "Data")[0], "Summoner")
        ranks = []

        for league_stat in league_stats or ():
            queue_type, tier_value, wins, losses = unwrap_typed(league_stat, "LeagueStat")

            if str(queue_type) not in RANKED_QUEUES:
                continue

            if tier_value is None:
                ranks.append(RankEntry(str(queue_type), None, None, 0, int(wins or 0), int(losses or 0)))
                continue

            tier, division, lp, _level = unwrap_typed(tier_value, "TierInfo")
            division_name = NUMBER_DIVISIONS.get(int(division)) if division is not None else None
            ranks.append(RankEntry(
                queue_type=str(queue_type),
                tier=str(tier).upper() if tier else None,
                division=division_name,
                lp=int(lp or 0),
                wins=int(wins or 0),
                losses=int(losses or 0)
            ))

        return RankProfile(str(returned_game_name), str(returned_tag_line), region.upper(), tuple(ranks))

    async def fetch_items(self) -> tuple[dict, ...]:
        text = await self.call_tool("lol_list_items", {"lang": "en_US", "map": "SUMMONERS_RIFT"})

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise LeagueProviderError("OP.GG returned unreadable item data.") from error

        return tuple((payload.get("data") or {}).get("items") or ())


class LeagueService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def setup(self) -> None:
        queries = (
            """
            CREATE TABLE IF NOT EXISTS league_season_champions (
                broadcaster_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                season_id TEXT NOT NULL,
                game_type TEXT NOT NULL,
                champion_name TEXT NOT NULL,
                games INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                refreshed_at TEXT NOT NULL,
                PRIMARY KEY (broadcaster_id, season_id, game_type, champion_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_matches (
                broadcaster_id TEXT NOT NULL,
                match_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                game_type TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                champion_name TEXT NOT NULL,
                result TEXT NOT NULL,
                item_ids TEXT NOT NULL,
                role_bound_item INTEGER,
                PRIMARY KEY (broadcaster_id, match_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_items (
                item_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                from_items TEXT NOT NULL,
                into_items TEXT NOT NULL,
                gold_purchasable INTEGER NOT NULL,
                is_boot INTEGER NOT NULL DEFAULT 0,
                refreshed_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_refresh_state (
                refresh_key TEXT PRIMARY KEY,
                refreshed_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_registrations (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                twitch_login TEXT NOT NULL,
                twitch_display_name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                region TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,
                PRIMARY KEY (broadcaster_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_community_ranks (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                queue_type TEXT NOT NULL,
                tier TEXT,
                division TEXT,
                lp INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                rank_score INTEGER NOT NULL,
                refreshed_at TEXT NOT NULL,
                PRIMARY KEY (broadcaster_id, user_id, queue_type)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS league_rank_snapshots (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                queue_type TEXT NOT NULL,
                tier TEXT,
                division TEXT,
                lp INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                rank_score INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_league_community_ladder
            ON league_community_ranks (broadcaster_id, queue_type, rank_score DESC)
            """
        )

        async with self.db.acquire() as connection:
            for query in queries:
                await connection.execute(query)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._refresh_loop(), name="league-refresh")

    async def stop(self) -> None:
        self._stop_event.set()

        if self._task is None:
            return

        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _refresh_loop(self) -> None:
        await self.refresh_all(force_season=True)

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=MATCH_REFRESH_SECONDS)
            except TimeoutError:
                await self.refresh_all(force_season=False)

    @staticmethod
    def configured_profiles() -> tuple[tuple[str, LeagueConfig], ...]:
        profiles = []

        for broadcaster_id, profile in ACTIVE_CHANNEL_PROFILES.items():
            config = profile.league

            if config.enabled and config.game_name and config.tag_line:
                profiles.append((str(broadcaster_id), config))

        return tuple(profiles)

    async def refresh_all(self, *, force_season: bool = False) -> None:
        profiles = self.configured_profiles()

        if not profiles:
            LOGGER.info("[League] No active League profiles are configured.")
            return

        try:
            async with OpggMcpClient() as client:
                if await self.refresh_due("items", ITEM_REFRESH_SECONDS):
                    try:
                        await self.refresh_items(client)
                    except Exception:
                        LOGGER.exception("[League] Failed to refresh the OP.GG item catalog.")

                for index, (broadcaster_id, config) in enumerate(profiles):
                    if index:
                        await asyncio.sleep(2)

                    await self.refresh_profile(client, broadcaster_id, config, force_season=force_season)

                await self.refresh_registered_players(client, {broadcaster_id for broadcaster_id, _config in profiles})
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("[League] OP.GG refresh cycle failed.")

    async def refresh_profile(self, client: OpggMcpClient, broadcaster_id: str, config: LeagueConfig, *, force_season: bool) -> None:
        season_key = f"season:{broadcaster_id}"

        if force_season or await self.refresh_due(season_key, SEASON_REFRESH_SECONDS):
            try:
                summary = await client.fetch_season_summary(config)
                await self.save_season_summary(broadcaster_id, config.provider, summary)
                await self.mark_refreshed(season_key)
            except Exception:
                LOGGER.exception("[League] Failed to refresh seasonal champions for %s.", config.display_name)

        try:
            matches = await client.fetch_recent_matches(config)
            inserted = await self.save_matches(broadcaster_id, matches)
            await self.cleanup_matches(broadcaster_id)
            await self.mark_refreshed(f"matches:{broadcaster_id}")
            LOGGER.info("[League] Saved %d new matches for %s.", inserted, config.display_name)
        except Exception:
            LOGGER.exception("[League] Failed to refresh recent matches for %s.", config.display_name)

    async def refresh_registered_players(self, client: OpggMcpClient, active_broadcaster_ids: set[str]) -> None:
        if not active_broadcaster_ids:
            return

        placeholders = ", ".join("?" for _broadcaster_id in active_broadcaster_ids)
        query = f"""
        SELECT broadcaster_id, user_id, twitch_login, twitch_display_name, game_name, tag_line, region, refreshed_at
        FROM league_registrations
        WHERE broadcaster_id IN ({placeholders})
        ORDER BY refreshed_at
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, tuple(active_broadcaster_ids))

        for index, row in enumerate(rows):
            registration = self.registration_from_row(row)

            if not self.timestamp_is_stale(registration.refreshed_at, COMMUNITY_RANK_REFRESH_SECONDS):
                continue

            if index:
                await asyncio.sleep(2)

            try:
                profile = await client.fetch_rank_profile(registration.game_name, registration.tag_line, registration.region)
                await self.save_registration_ranks(registration.broadcaster_id, registration.user_id, profile)
            except Exception:
                LOGGER.exception("[League] Failed to refresh registered Riot ID %s#%s.", registration.game_name, registration.tag_line)

    async def refresh_due(self, refresh_key: str, interval_seconds: int) -> bool:
        query = "SELECT refreshed_at FROM league_refresh_state WHERE refresh_key = ?"

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (refresh_key,))

        if row is None:
            return True

        try:
            refreshed_at = datetime.fromisoformat(str(row[0]))
        except ValueError:
            return True

        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=UTC)

        return datetime.now(UTC) - refreshed_at >= timedelta(seconds=interval_seconds)

    async def mark_refreshed(self, refresh_key: str) -> None:
        query = """
        INSERT INTO league_refresh_state (refresh_key, refreshed_at)
        VALUES (?, ?)
        ON CONFLICT(refresh_key) DO UPDATE SET refreshed_at = excluded.refreshed_at
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (refresh_key, datetime.now(UTC).isoformat()))

    async def refresh_items(self, client: OpggMcpClient) -> None:
        items = await client.fetch_items()
        item_by_id = {int(item["item_id"]): item for item in items}
        boot_ids = self.find_boot_ids(item_by_id)
        refreshed_at = datetime.now(UTC).isoformat()
        query = """
        INSERT INTO league_items (item_id, name, from_items, into_items, gold_purchasable, is_boot, refreshed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            name = excluded.name,
            from_items = excluded.from_items,
            into_items = excluded.into_items,
            gold_purchasable = excluded.gold_purchasable,
            is_boot = excluded.is_boot,
            refreshed_at = excluded.refreshed_at
        """

        async with self.db.acquire() as connection:
            for item_id, item in item_by_id.items():
                values = (
                    item_id,
                    str(item.get("name") or item_id),
                    json.dumps(item.get("from_items") or []),
                    json.dumps(item.get("into_items") or []),
                    int(bool(item.get("gold_purchasable", True))),
                    int(item_id in boot_ids),
                    refreshed_at
                )
                await connection.execute(query, values)

        await self.mark_refreshed("items")
        LOGGER.info("[League] Refreshed %d League items from OP.GG.", len(items))

    @staticmethod
    def find_boot_ids(item_by_id: dict[int, dict]) -> set[int]:
        boot_ids = {1001}
        pending = [1001]

        while pending:
            item_id = pending.pop()

            for next_id in item_by_id.get(item_id, {}).get("into_items") or ():
                next_id = int(next_id)

                if next_id in item_by_id and next_id not in boot_ids:
                    boot_ids.add(next_id)
                    pending.append(next_id)

        return boot_ids

    async def save_season_summary(self, broadcaster_id: str, provider: str, summary: SeasonSummary) -> None:
        refreshed_at = datetime.now(UTC).isoformat()
        delete_query = "DELETE FROM league_season_champions WHERE broadcaster_id = ?"
        insert_query = """
        INSERT INTO league_season_champions (
            broadcaster_id, provider, season_id, game_type, champion_name,
            games, wins, losses, refreshed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        async with self.db.acquire() as connection:
            await connection.execute(delete_query, (str(broadcaster_id),))

            for champion in summary.champions:
                values = (
                    str(broadcaster_id), provider, summary.season_id, summary.game_type,
                    champion.name, champion.games, champion.wins, champion.losses, refreshed_at
                )
                await connection.execute(insert_query, values)

    async def save_matches(self, broadcaster_id: str, matches: tuple[RecentMatch, ...]) -> int:
        query = """
        INSERT OR IGNORE INTO league_matches (
            broadcaster_id, match_id, started_at, game_type, duration_seconds,
            champion_name, result, item_ids, role_bound_item
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        inserted = 0

        async with self.db.acquire() as connection:
            for match in matches:
                if match.game_type not in {"SOLORANKED", "FLEXRANKED"}:
                    continue

                values = (
                    str(broadcaster_id), match.match_id, match.started_at, match.game_type,
                    match.duration_seconds, match.champion_name, match.result,
                    json.dumps(match.item_ids), match.role_bound_item
                )
                await connection.execute(query, values)
                changes = await connection.fetchone("SELECT changes()")
                inserted += int(changes[0])

        return inserted

    async def cleanup_matches(self, broadcaster_id: str) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=BUILD_RETENTION_DAYS)).isoformat()
        query = "DELETE FROM league_matches WHERE broadcaster_id = ? AND started_at < ?"

        async with self.db.acquire() as connection:
            await connection.execute(query, (str(broadcaster_id), cutoff))

    async def get_top_champions(self, broadcaster_id: str, limit: int = 5) -> tuple[SeasonalChampion, ...]:
        query = """
        SELECT champion_name, games, wins, losses
        FROM league_season_champions
        WHERE broadcaster_id = ?
        ORDER BY games DESC, champion_name COLLATE NOCASE
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (str(broadcaster_id), int(limit)))

        return tuple(SeasonalChampion(str(row[0]), int(row[1]), int(row[2]), int(row[3])) for row in rows)

    async def get_core_build(self, broadcaster_id: str, champion_query: str, config: LeagueConfig) -> CoreBuild | None:
        champion_name = await self.resolve_champion_name(broadcaster_id, champion_query, config)

        if champion_name is None:
            return None

        cutoff = (datetime.now(UTC) - timedelta(days=BUILD_RETENTION_DAYS)).isoformat()
        match_query = """
        SELECT item_ids, role_bound_item
        FROM league_matches
        WHERE broadcaster_id = ?
          AND champion_name = ? COLLATE NOCASE
          AND started_at >= ?
          AND result IN ('WIN', 'LOSE')
        """
        item_query = "SELECT item_id, name, from_items, into_items, gold_purchasable, is_boot FROM league_items"

        async with self.db.acquire() as connection:
            matches = await connection.fetchall(match_query, (str(broadcaster_id), champion_name, cutoff))
            item_rows = await connection.fetchall(item_query)

        if len(matches) < 2:
            return None

        items = {int(row[0]): row for row in item_rows}
        core_counts: Counter[tuple[int, int, int]] = Counter()

        for match in matches:
            role_bound_item = int(match[1]) if match[1] is not None else None
            completed_items = []

            for item_id in json.loads(str(match[0])):
                item_id = int(item_id)
                item = items.get(item_id)

                if item is None or item_id == role_bound_item:
                    continue

                from_items = json.loads(str(item[2]))
                into_items = json.loads(str(item[3]))

                if from_items and not into_items and bool(item[4]) and not bool(item[5]):
                    completed_items.append(item_id)

            for combination in combinations(sorted(set(completed_items)), 3):
                core_counts[combination] += 1

        if not core_counts:
            return None

        item_frequency = Counter(item_id for core, count in core_counts.items() for item_id in core for _ in range(count))
        best_core, matching_games = max(
            core_counts.items(),
            key=lambda entry: (entry[1], sum(item_frequency[item_id] for item_id in entry[0]), tuple(-item_id for item_id in entry[0]))
        )

        if matching_games < 2:
            return None

        item_names = tuple(str(items[item_id][1]) for item_id in best_core)
        return CoreBuild(champion_name, item_names, len(matches), matching_games)

    async def register_player(self, broadcaster_id: str, user_id: str, twitch_login: str, twitch_display_name: str,
                              riot_id: str, default_region: str) -> CommunityRank:
        game_name, tag_line, region = self.parse_registration(riot_id, default_region)
        existing = await self.get_registration(broadcaster_id, user_id)

        if (
            existing is not None
            and existing.game_name.casefold() == game_name.casefold()
            and existing.tag_line.casefold() == tag_line.casefold()
            and existing.region == region
            and not self.timestamp_is_stale(existing.refreshed_at, COMMUNITY_RANK_REFRESH_SECONDS)
        ):
            async with self.db.acquire() as connection:
                await connection.execute(
                    "UPDATE league_registrations SET twitch_login = ?, twitch_display_name = ? WHERE broadcaster_id = ? AND user_id = ?",
                    (twitch_login, twitch_display_name, str(broadcaster_id), str(user_id))
                )

            refreshed_registration = await self.get_registration(broadcaster_id, user_id)
            return CommunityRank(refreshed_registration or existing, await self.get_player_rank(broadcaster_id, user_id))

        async with OpggMcpClient() as client:
            profile = await client.fetch_rank_profile(game_name, tag_line, region)

        now = datetime.now(UTC).isoformat()
        same_account = (
            existing is not None
            and existing.game_name.casefold() == profile.game_name.casefold()
            and existing.tag_line.casefold() == profile.tag_line.casefold()
            and existing.region == profile.region
        )
        query = """
        INSERT INTO league_registrations (
            broadcaster_id, user_id, twitch_login, twitch_display_name,
            game_name, tag_line, region, registered_at, refreshed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            twitch_login = excluded.twitch_login,
            twitch_display_name = excluded.twitch_display_name,
            game_name = excluded.game_name,
            tag_line = excluded.tag_line,
            region = excluded.region,
            refreshed_at = excluded.refreshed_at
        """
        values = (
            str(broadcaster_id), str(user_id), twitch_login, twitch_display_name,
            profile.game_name, profile.tag_line, profile.region, now, now
        )

        async with self.db.acquire() as connection:
            if existing is not None and not same_account:
                await connection.execute("DELETE FROM league_rank_snapshots WHERE broadcaster_id = ? AND user_id = ?", (str(broadcaster_id), str(user_id)))
                await connection.execute("DELETE FROM league_community_ranks WHERE broadcaster_id = ? AND user_id = ?", (str(broadcaster_id), str(user_id)))

            await connection.execute(query, values)

        await self.save_registration_ranks(str(broadcaster_id), str(user_id), profile)
        registration = await self.get_registration(broadcaster_id, user_id)

        if registration is None:
            raise LeagueProviderError("The League registration could not be saved.")

        LOGGER.info("[League] Registered Twitch user %s as %s#%s in %s.", user_id, profile.game_name, profile.tag_line, profile.region)
        return CommunityRank(registration, await self.get_player_rank(broadcaster_id, user_id))

    async def unregister_player(self, broadcaster_id: str, user_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        async with self.db.acquire() as connection:
            existing = await connection.fetchone(
                "SELECT 1 FROM league_registrations WHERE broadcaster_id = ? AND user_id = ?",
                (broadcaster_id, user_id)
            )

            if existing is None:
                return False

            await connection.execute("DELETE FROM league_rank_snapshots WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))
            await connection.execute("DELETE FROM league_community_ranks WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))
            await connection.execute("DELETE FROM league_registrations WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))

        LOGGER.info("[League] Removed League registration for Twitch user %s in broadcaster %s.", user_id, broadcaster_id)
        return True

    async def save_registration_ranks(self, broadcaster_id: str, user_id: str, profile: RankProfile) -> None:
        now = datetime.now(UTC).isoformat()
        rank_query = """
        INSERT INTO league_community_ranks (
            broadcaster_id, user_id, queue_type, tier, division, lp,
            wins, losses, rank_score, refreshed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(broadcaster_id, user_id, queue_type) DO UPDATE SET
            tier = excluded.tier,
            division = excluded.division,
            lp = excluded.lp,
            wins = excluded.wins,
            losses = excluded.losses,
            rank_score = excluded.rank_score,
            refreshed_at = excluded.refreshed_at
        """
        snapshot_query = """
        INSERT INTO league_rank_snapshots (
            broadcaster_id, user_id, queue_type, tier, division, lp,
            wins, losses, rank_score, recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        async with self.db.acquire() as connection:
            returned_queues = {rank.queue_type for rank in profile.ranks}

            for rank in profile.ranks:
                previous = await connection.fetchone(
                    """
                    SELECT tier, division, lp, wins, losses
                    FROM league_community_ranks
                    WHERE broadcaster_id = ? AND user_id = ? AND queue_type = ?
                    """,
                    (broadcaster_id, user_id, rank.queue_type)
                )
                values = (
                    broadcaster_id, user_id, rank.queue_type, rank.tier, rank.division,
                    rank.lp, rank.wins, rank.losses, rank.score, now
                )
                await connection.execute(rank_query, values)
                current_values = (rank.tier, rank.division, rank.lp, rank.wins, rank.losses)

                if previous is None or tuple(previous) != current_values:
                    await connection.execute(snapshot_query, values)

            for queue_type in set(RANKED_QUEUES) - returned_queues:
                await connection.execute(
                    "DELETE FROM league_community_ranks WHERE broadcaster_id = ? AND user_id = ? AND queue_type = ?",
                    (broadcaster_id, user_id, queue_type)
                )

            await connection.execute(
                "UPDATE league_registrations SET game_name = ?, tag_line = ?, region = ?, refreshed_at = ? WHERE broadcaster_id = ? AND user_id = ?",
                (profile.game_name, profile.tag_line, profile.region, now, broadcaster_id, user_id)
            )

    async def get_registration(self, broadcaster_id: str, user_id: str) -> LeagueRegistration | None:
        query = """
        SELECT broadcaster_id, user_id, twitch_login, twitch_display_name, game_name, tag_line, region, refreshed_at
        FROM league_registrations
        WHERE broadcaster_id = ? AND user_id = ?
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(broadcaster_id), str(user_id)))

        return self.registration_from_row(row) if row is not None else None

    async def get_player_rank(self, broadcaster_id: str, user_id: str, queue_type: str = "SOLORANKED") -> RankEntry | None:
        query = """
        SELECT queue_type, tier, division, lp, wins, losses
        FROM league_community_ranks
        WHERE broadcaster_id = ? AND user_id = ? AND queue_type = ?
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(broadcaster_id), str(user_id), queue_type))

        if row is None:
            return None

        return RankEntry(str(row[0]), str(row[1]) if row[1] else None, str(row[2]) if row[2] else None, int(row[3]), int(row[4]), int(row[5]))

    async def get_community_rank(self, broadcaster_id: str, user_id: str) -> CommunityRank | None:
        registration = await self.get_registration(broadcaster_id, user_id)

        if registration is None:
            return None

        return CommunityRank(registration, await self.get_player_rank(broadcaster_id, user_id))

    async def get_ladder(self, broadcaster_id: str, limit: int = 10) -> tuple[CommunityRank, ...]:
        query = """
        SELECT
            r.broadcaster_id, r.user_id, r.twitch_login, r.twitch_display_name,
            r.game_name, r.tag_line, r.region, r.refreshed_at,
            c.queue_type, c.tier, c.division, c.lp, c.wins, c.losses
        FROM league_registrations AS r
        LEFT JOIN league_community_ranks AS c
          ON c.broadcaster_id = r.broadcaster_id
         AND c.user_id = r.user_id
         AND c.queue_type = 'SOLORANKED'
        WHERE r.broadcaster_id = ?
        ORDER BY COALESCE(c.rank_score, -1) DESC, r.twitch_display_name COLLATE NOCASE
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (str(broadcaster_id), int(limit)))

        entries = []

        for row in rows:
            registration = self.registration_from_row(row[:8])
            rank = None if row[8] is None else RankEntry(str(row[8]), str(row[9]) if row[9] else None, str(row[10]) if row[10] else None, int(row[11]), int(row[12]), int(row[13]))
            entries.append(CommunityRank(registration, rank))

        return tuple(entries)

    @staticmethod
    def parse_registration(value: str, default_region: str) -> tuple[str, str, str]:
        parts = value.strip().rsplit(maxsplit=1)
        region = default_region.upper()
        riot_id = value.strip()

        if len(parts) == 2 and parts[1].upper() in SUPPORTED_REGIONS:
            riot_id, region = parts[0], parts[1].upper()
        elif len(parts) == 2 and "#" in parts[0]:
            raise ValueError(f"Unsupported League region: {parts[1].upper()}.")

        if "#" not in riot_id:
            raise ValueError("Include the complete Riot ID, such as PlayerName#TAG.")

        game_name, tag_line = (part.strip() for part in riot_id.rsplit("#", 1))

        if not game_name or not tag_line:
            raise ValueError("Include the complete Riot ID, such as PlayerName#TAG.")

        if region not in SUPPORTED_REGIONS:
            raise ValueError(f"Unsupported League region: {region}.")

        return game_name, tag_line, region

    @staticmethod
    def registration_from_row(row) -> LeagueRegistration:
        return LeagueRegistration(*(str(value) for value in row))

    @staticmethod
    def timestamp_is_stale(value: str, interval_seconds: int) -> bool:
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return True

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        return datetime.now(UTC) - timestamp >= timedelta(seconds=interval_seconds)

    async def resolve_champion_name(self, broadcaster_id: str, champion_query: str, config: LeagueConfig) -> str | None:
        normalized_query = self.normalize_champion_name(champion_query)
        aliases = {self.normalize_champion_name(alias): name for alias, name in config.champion_aliases}
        requested_name = aliases.get(normalized_query, champion_query.strip())
        normalized_requested_name = self.normalize_champion_name(requested_name)
        cutoff = (datetime.now(UTC) - timedelta(days=BUILD_RETENTION_DAYS)).isoformat()
        query = """
        SELECT DISTINCT champion_name
        FROM league_matches
        WHERE broadcaster_id = ? AND started_at >= ?
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (str(broadcaster_id), cutoff))

        for row in rows:
            champion_name = str(row[0])

            if self.normalize_champion_name(champion_name) == normalized_requested_name:
                return champion_name

        return None

    @staticmethod
    def normalize_champion_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.casefold())

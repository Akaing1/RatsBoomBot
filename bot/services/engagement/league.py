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


def _convert_ast_node(node):
    if isinstance(node, ast.Constant):
        return node.value

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

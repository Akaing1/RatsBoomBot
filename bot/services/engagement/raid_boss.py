import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from bot.profiles import RaidBossConfig

LOGGER = logging.getLogger("RatBoomBot")

WEAPON_TYPES = {
    "sword": "melee",
    "bow": "ranged",
    "spellbook": "magic"
}


@dataclass(frozen=True)
class RaidBossEvent:
    id: int
    boss_name: str
    boss_type: str
    max_hp: int
    current_hp: int
    reward_pool: int
    status: str
    stream_limit: int
    streams_used: int


@dataclass(frozen=True)
class RaidAttackResult:
    damage: int
    current_hp: int
    boss_name: str
    weapon: str | None
    potion_used: bool
    defeated: bool
    reward: int = 0
    error: str | None = None
    critical_hit: bool = False


class RaidBossService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def setup(self) -> None:
        LOGGER.info("[Raid Bosses] Preparing raid boss storage.")

        queries = (
            """
            CREATE TABLE IF NOT EXISTS raid_boss_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcaster_id TEXT NOT NULL,
                boss_name TEXT NOT NULL,
                boss_type TEXT NOT NULL,
                max_hp INTEGER NOT NULL,
                current_hp INTEGER NOT NULL,
                reward_pool INTEGER NOT NULL,
                final_hit_reward INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                spawned_at TEXT NOT NULL,
                stream_limit INTEGER NOT NULL,
                final_hitter_id TEXT,
                final_hitter_name TEXT,
                rewards_paid INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS raid_boss_streams (
                event_id INTEGER NOT NULL,
                stream_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                PRIMARY KEY (event_id, stream_id)
            )
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS raid_boss_one_active_event
            ON raid_boss_events (broadcaster_id)
            WHERE status = 'active'
            """,
            """
            CREATE TABLE IF NOT EXISTS raid_boss_attacks (
                event_id INTEGER NOT NULL,
                broadcaster_id TEXT NOT NULL,
                stream_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                damage INTEGER NOT NULL,
                attacked_at TEXT NOT NULL,
                PRIMARY KEY (event_id, stream_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS raid_boss_players (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                equipped_weapon TEXT,
                potion_attacks_remaining INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (broadcaster_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS raid_boss_inventory (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (broadcaster_id, user_id, item_id)
            )
            """
        )

        try:
            async with self.db.acquire() as connection:
                for query in queries:
                    await connection.execute(query)
        except Exception:
            LOGGER.exception("[Raid Bosses] Failed to prepare raid boss storage.")
            raise

        LOGGER.info("[Raid Bosses] Raid boss storage ready.")

    async def get_active_event(self, broadcaster_id: str) -> RaidBossEvent | None:
        query = """
        SELECT id, boss_name, boss_type, max_hp, current_hp, reward_pool, status,
               stream_limit,
               (SELECT COUNT(*) FROM raid_boss_streams WHERE event_id = raid_boss_events.id) AS streams_used
        FROM raid_boss_events
        WHERE broadcaster_id = ?
          AND status = 'active'
        LIMIT 1
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(broadcaster_id),))

        return self._event_from_row(row) if row else None

    async def spawn(self, broadcaster_id: str, boss_type: str, config: RaidBossConfig) -> RaidBossEvent | None:
        boss_type = boss_type.lower()
        active_event = await self.get_active_event(broadcaster_id)

        if boss_type not in WEAPON_TYPES.values() or active_event is not None:
            return None

        boss_name = getattr(config.names, boss_type)
        now = datetime.now(UTC)
        query = """
        INSERT INTO raid_boss_events (
            broadcaster_id, boss_name, boss_type, max_hp, current_hp,
            reward_pool, final_hit_reward, stream_limit, spawned_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, boss_name, boss_type, max_hp, current_hp, reward_pool, status,
                  stream_limit, 0 AS streams_used
        """
        values = (
            str(broadcaster_id), boss_name, boss_type, config.max_hp, config.max_hp,
            config.reward_pool, config.final_hit_reward, config.duration_streams, now.isoformat()
        )

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, values)

        LOGGER.info("[Raid Bosses] Spawned %s for broadcaster %s.", boss_name, broadcaster_id)
        return self._event_from_row(row)

    async def attack(self, broadcaster_id: str, stream_id: str, user_id: str, username: str, config: RaidBossConfig) -> RaidAttackResult:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return RaidAttackResult(0, 0, "", None, False, False, error="There is no active raid boss.")

        player = await self._get_player(broadcaster_id, user_id)
        weapon = player["equipped_weapon"] if player else None
        potion_attacks = int(player["potion_attacks_remaining"]) if player else 0
        damage = random.randint(config.base_damage_min, config.base_damage_max)

        if weapon and WEAPON_TYPES.get(weapon) == event.boss_type:
            damage = round(damage * config.weapon_multiplier)

        potion_used = potion_attacks > 0

        if potion_used:
            damage = round(damage * config.potion_multiplier)

        critical_hit = random.random() < config.critical_chance

        if critical_hit:
            damage = round(damage * config.critical_multiplier)

        damage = min(damage, event.current_hp)
        now = datetime.now(UTC).isoformat()

        async with self.db.acquire() as connection:
            attack_row = await connection.fetchone(
                """
                INSERT INTO raid_boss_attacks (
                    event_id, broadcaster_id, stream_id, user_id, username, damage, attacked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, stream_id, user_id) DO NOTHING
                RETURNING event_id
                """,
                (event.id, broadcaster_id, str(stream_id), user_id, username, damage, now)
            )

            if attack_row is None:
                return RaidAttackResult(0, event.current_hp, event.boss_name, weapon, False, False, error="You already attacked during this stream.")

            row = await connection.fetchone(
                """
                UPDATE raid_boss_events
                SET current_hp = MAX(current_hp - ?, 0)
                WHERE id = ?
                  AND status = 'active'
                RETURNING current_hp
                """,
                (damage, event.id)
            )

            if potion_used:
                await connection.execute(
                    """
                    UPDATE raid_boss_players
                    SET potion_attacks_remaining = MAX(potion_attacks_remaining - 1, 0)
                    WHERE broadcaster_id = ? AND user_id = ?
                    """,
                    (broadcaster_id, user_id)
                )

        if row is None:
            return RaidAttackResult(0, 0, event.boss_name, weapon, potion_used, False, error="The raid ended before your attack landed.")

        current_hp = int(row["current_hp"])
        reward = 0

        if current_hp == 0:
            reward = await self.resolve(broadcaster_id, defeated=True, final_hitter_id=user_id, final_hitter_name=username)

        LOGGER.info("[Raid Bosses] %s dealt %d damage to %s in broadcaster %s.", username, damage, event.boss_name, broadcaster_id)
        return RaidAttackResult(damage, current_hp, event.boss_name, weapon, potion_used, current_hp == 0, reward, critical_hit=critical_hit)

    async def register_stream(self, broadcaster_id: str, stream_id: str) -> tuple[RaidBossEvent | None, int]:
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return None, 0

        async with self.db.acquire() as connection:
            inserted = await connection.fetchone(
                """
                INSERT INTO raid_boss_streams (event_id, stream_id, started_at)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id, stream_id) DO NOTHING
                RETURNING event_id
                """,
                (event.id, str(stream_id), datetime.now(UTC).isoformat())
            )

            row = None

            if inserted is not None:
                row = await connection.fetchone(
                    "SELECT COUNT(*) AS streams_used FROM raid_boss_streams WHERE event_id = ?",
                    (event.id,)
                )

        if inserted is None:
            return await self.get_active_event(broadcaster_id), 0

        streams_used = int(row["streams_used"])

        if streams_used > event.stream_limit:
            reward = await self.resolve(broadcaster_id, defeated=False)
            return None, reward

        return await self.get_active_event(broadcaster_id), 0

    async def buy(self, broadcaster_id: str, user_id: str, username: str, item_id: str, config: RaidBossConfig) -> str | None:
        item_id = item_id.lower()
        cost = config.potion_cost if item_id == "potion" else config.weapon_cost

        if item_id not in (*WEAPON_TYPES, "potion"):
            return None

        async with self.db.acquire() as connection:
            if item_id in WEAPON_TYPES:
                owned = await connection.fetchone(
                    "SELECT quantity FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ? AND quantity > 0",
                    (str(broadcaster_id), str(user_id), item_id)
                )

                if owned is not None:
                    return "owned"

            balance = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

            if balance is None or int(balance["points"]) < cost:
                return "insufficient"

            await connection.execute(
                "UPDATE viewers SET points = points - ? WHERE broadcaster_id = ? AND user_id = ?",
                (cost, str(broadcaster_id), str(user_id))
            )
            await self._ensure_player(connection, broadcaster_id, user_id, username)

            if item_id == "potion":
                await connection.execute(
                    """
                    UPDATE raid_boss_players
                    SET potion_attacks_remaining = potion_attacks_remaining + ?
                    WHERE broadcaster_id = ? AND user_id = ?
                    """,
                    (config.potion_attacks, str(broadcaster_id), str(user_id))
                )
            else:
                await connection.execute(
                    """
                    INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = 1
                    """,
                    (str(broadcaster_id), str(user_id), item_id)
                )

        return "purchased"

    async def equip(self, broadcaster_id: str, user_id: str, username: str, weapon: str) -> bool:
        weapon = weapon.lower()

        if weapon not in WEAPON_TYPES:
            return False

        async with self.db.acquire() as connection:
            owned = await connection.fetchone(
                "SELECT quantity FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ? AND quantity > 0",
                (str(broadcaster_id), str(user_id), weapon)
            )

            if owned is None:
                return False

            await self._ensure_player(connection, broadcaster_id, user_id, username)
            await connection.execute(
                "UPDATE raid_boss_players SET equipped_weapon = ? WHERE broadcaster_id = ? AND user_id = ?",
                (weapon, str(broadcaster_id), str(user_id))
            )

        return True

    async def get_inventory(self, broadcaster_id: str, user_id: str) -> tuple[list[str], str | None, int]:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                "SELECT item_id FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND quantity > 0 ORDER BY item_id",
                (str(broadcaster_id), str(user_id))
            )
            player = await connection.fetchone(
                "SELECT equipped_weapon, potion_attacks_remaining FROM raid_boss_players WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

        weapons = [str(row["item_id"]) for row in rows]
        equipped = str(player["equipped_weapon"]) if player and player["equipped_weapon"] else None
        potions = int(player["potion_attacks_remaining"]) if player else 0
        return weapons, equipped, potions

    async def get_leaderboard(self, broadcaster_id: str, limit: int = 5) -> list[tuple[str, int]]:
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return []

        query = """
        SELECT username, SUM(damage) AS total_damage
        FROM raid_boss_attacks
        WHERE event_id = ?
        GROUP BY user_id, username
        ORDER BY total_damage DESC, username COLLATE NOCASE
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (event.id, max(1, limit)))

        return [(str(row["username"]), int(row["total_damage"])) for row in rows]

    async def resolve(self, broadcaster_id: str, defeated: bool, final_hitter_id: str | None = None, final_hitter_name: str | None = None) -> int:
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return 0

        damage_dealt = event.max_hp - event.current_hp
        remaining_ratio = event.current_hp / event.max_hp
        multiplier = 1.0 if defeated else (0.5 if remaining_ratio <= 0.25 else 0.25)
        payout_pool = round(event.reward_pool * multiplier)
        status = "defeated" if defeated else "failed"

        async with self.db.acquire() as connection:
            resolution = await connection.fetchone(
                """
                UPDATE raid_boss_events
                SET status = ?, final_hitter_id = ?, final_hitter_name = ?, rewards_paid = 1
                WHERE id = ? AND status = 'active' AND rewards_paid = 0
                RETURNING final_hit_reward
                """,
                (status, final_hitter_id, final_hitter_name, event.id)
            )

            if resolution is None:
                return 0

            contributions = await connection.fetchall(
                "SELECT user_id, username, SUM(damage) AS damage FROM raid_boss_attacks WHERE event_id = ? GROUP BY user_id, username",
                (event.id,)
            )

            if damage_dealt > 0:
                for contribution in contributions:
                    reward = payout_pool * int(contribution["damage"]) // damage_dealt
                    await self._add_points(connection, broadcaster_id, contribution["user_id"], contribution["username"], reward)

            if defeated and final_hitter_id and final_hitter_name:
                await self._add_points(connection, broadcaster_id, final_hitter_id, final_hitter_name, int(resolution["final_hit_reward"]))

        LOGGER.info("[Raid Bosses] Resolved %s as %s with a %d-point pool.", event.boss_name, status, payout_pool)
        return payout_pool

    async def _get_player(self, broadcaster_id: str, user_id: str):
        async with self.db.acquire() as connection:
            return await connection.fetchone(
                "SELECT equipped_weapon, potion_attacks_remaining FROM raid_boss_players WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

    @staticmethod
    async def _ensure_player(connection, broadcaster_id: str, user_id: str, username: str) -> None:
        await connection.execute(
            """
            INSERT INTO raid_boss_players (broadcaster_id, user_id, username)
            VALUES (?, ?, ?)
            ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET username = excluded.username
            """,
            (str(broadcaster_id), str(user_id), username)
        )

    @staticmethod
    async def _add_points(connection, broadcaster_id: str, user_id: str, username: str, amount: int) -> None:
        if amount <= 0:
            return

        await connection.execute(
            """
            INSERT INTO viewers (broadcaster_id, user_id, username, points, messages)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET username = excluded.username, points = points + excluded.points
            """,
            (str(broadcaster_id), str(user_id), username, amount)
        )

    @staticmethod
    def _event_from_row(row) -> RaidBossEvent:
        return RaidBossEvent(
            id=int(row["id"]),
            boss_name=str(row["boss_name"]),
            boss_type=str(row["boss_type"]),
            max_hp=int(row["max_hp"]),
            current_hp=int(row["current_hp"]),
            reward_pool=int(row["reward_pool"]),
            status=str(row["status"]),
            stream_limit=int(row["stream_limit"]),
            streams_used=int(row["streams_used"])
        )

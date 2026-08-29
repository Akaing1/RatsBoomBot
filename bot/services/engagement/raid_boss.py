import logging
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from bot.profiles import RaidBossConfig

LOGGER = logging.getLogger("RatBoomBot")

BASIC_WEAPON_TYPES = {
    "sword": "melee",
    "bow": "ranged",
    "spellbook": "magic"
}
UNIQUE_WEAPON_TYPES = {
    "mythical_blade": "melee",
    "mythical_longbow": "ranged",
    "mythical_grimoire": "magic"
}
WEAPON_TYPES = BASIC_WEAPON_TYPES | UNIQUE_WEAPON_TYPES


@dataclass(frozen=True)
class RaidBossEvent:
    id: int
    boss_name: str
    boss_type: str
    boss_tier: str
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
    broken_weapon: str | None = None
    drops: tuple[tuple[str, str], ...] = ()


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
                boss_tier TEXT NOT NULL DEFAULT 'main',
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
                weapon TEXT,
                potion_used INTEGER NOT NULL DEFAULT 0,
                critical_hit INTEGER NOT NULL DEFAULT 0,
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
                durability INTEGER NOT NULL DEFAULT 15,
                PRIMARY KEY (broadcaster_id, user_id, item_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS raid_boss_channel_state (
                broadcaster_id TEXT PRIMARY KEY,
                tutorial_completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        try:
            async with self.db.acquire() as connection:
                for query in queries:
                    await connection.execute(query)

                columns = await connection.fetchall("PRAGMA table_info(raid_boss_events)")

                if "boss_tier" not in {str(column["name"]) for column in columns}:
                    await connection.execute("ALTER TABLE raid_boss_events ADD COLUMN boss_tier TEXT NOT NULL DEFAULT 'main'")

                attack_columns = await connection.fetchall("PRAGMA table_info(raid_boss_attacks)")
                attack_column_names = {str(column["name"]) for column in attack_columns}

                if "weapon" not in attack_column_names:
                    await connection.execute("ALTER TABLE raid_boss_attacks ADD COLUMN weapon TEXT")

                if "potion_used" not in attack_column_names:
                    await connection.execute("ALTER TABLE raid_boss_attacks ADD COLUMN potion_used INTEGER NOT NULL DEFAULT 0")

                if "critical_hit" not in attack_column_names:
                    await connection.execute("ALTER TABLE raid_boss_attacks ADD COLUMN critical_hit INTEGER NOT NULL DEFAULT 0")

                inventory_columns = await connection.fetchall("PRAGMA table_info(raid_boss_inventory)")

                if "durability" not in {str(column["name"]) for column in inventory_columns}:
                    await connection.execute("ALTER TABLE raid_boss_inventory ADD COLUMN durability INTEGER NOT NULL DEFAULT 15")
        except Exception:
            LOGGER.exception("[Raid Bosses] Failed to prepare raid boss storage.")
            raise

        LOGGER.info("[Raid Bosses] Raid boss storage ready.")

    async def get_active_event(self, broadcaster_id: str) -> RaidBossEvent | None:
        query = """
        SELECT id, boss_name, boss_type, boss_tier, max_hp, current_hp, reward_pool, status,
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

    async def has_completed_tutorial(self, broadcaster_id: str) -> bool:
        async with self.db.acquire() as connection:
            row = await connection.fetchone("SELECT tutorial_completed FROM raid_boss_channel_state WHERE broadcaster_id = ?", (str(broadcaster_id),))

        return bool(row and row["tutorial_completed"])

    async def spawn(self, broadcaster_id: str, boss_type: str, config: RaidBossConfig, boss_tier: str = "main") -> RaidBossEvent | None:
        boss_type = boss_type.lower()
        boss_tier = boss_tier.lower()
        active_event = await self.get_active_event(broadcaster_id)

        if boss_type not in WEAPON_TYPES.values() or boss_tier not in {"mini", "main", "tutorial"} or active_event is not None:
            return None

        if boss_tier == "tutorial" and (not config.tutorial_enabled or await self.has_completed_tutorial(broadcaster_id)):
            return None

        if boss_tier == "tutorial":
            boss_name = getattr(config.mini_names, boss_type)
            max_hp = config.tutorial_hp
            final_hit_reward = config.mini_final_hit_reward
            stream_limit = config.tutorial_duration_streams
        elif boss_tier == "mini":
            boss_name = getattr(config.mini_names, boss_type)
            max_hp = random.randrange(config.mini_hp_min, config.mini_hp_max + 1, config.mini_hp_step)
            final_hit_reward = config.mini_final_hit_reward
            stream_limit = config.mini_duration_streams
        else:
            boss_name = getattr(config.names, boss_type)
            max_hp = config.max_hp
            final_hit_reward = config.final_hit_reward
            stream_limit = config.duration_streams

        reward_pool = round(max_hp * config.reward_points_per_hp)

        now = datetime.now(UTC)
        query = """
        INSERT INTO raid_boss_events (
            broadcaster_id, boss_name, boss_type, boss_tier, max_hp, current_hp,
            reward_pool, final_hit_reward, stream_limit, spawned_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, boss_name, boss_type, boss_tier, max_hp, current_hp, reward_pool, status,
                  stream_limit, 0 AS streams_used
        """
        values = (
            str(broadcaster_id), boss_name, boss_type, boss_tier, max_hp, max_hp,
            reward_pool, final_hit_reward, stream_limit, now.isoformat()
        )

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, values)

        LOGGER.info("[Raid Bosses] Spawned %s %s for broadcaster %s.", boss_tier, boss_name, broadcaster_id)
        return self._event_from_row(row)

    async def attack(self, broadcaster_id: str, stream_id: str, user_id: str, username: str, config: RaidBossConfig) -> RaidAttackResult:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return RaidAttackResult(0, 0, "", None, False, False, error="There is no active raid boss.")

        player = await self._get_player(broadcaster_id, user_id)
        weapon = player["equipped_weapon"] if player else None
        weapon_durability = int(player["weapon_durability"]) if player else 0
        weapon_used = weapon if weapon and weapon_durability > 0 else None
        potion_attacks = int(player["potion_attacks_remaining"]) if player else 0
        damage = random.randint(config.base_damage_min, config.base_damage_max)

        if weapon_used:
            weapon_attack = config.unique_weapon_attack if weapon_used in UNIQUE_WEAPON_TYPES else config.weapon_attack

            if WEAPON_TYPES.get(weapon_used) == event.boss_type:
                weapon_attack = round(weapon_attack * config.weapon_multiplier)

            damage += weapon_attack

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
                    event_id, broadcaster_id, stream_id, user_id, username, damage,
                    weapon, potion_used, critical_hit, attacked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, stream_id, user_id) DO NOTHING
                RETURNING event_id
                """,
                (event.id, broadcaster_id, str(stream_id), user_id, username, damage, weapon_used, int(potion_used), int(critical_hit), now)
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

            if weapon_used:
                await connection.execute(
                    "UPDATE raid_boss_inventory SET durability = MAX(durability - 1, 0) WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?",
                    (broadcaster_id, user_id, weapon_used)
                )

        if row is None:
            return RaidAttackResult(0, 0, event.boss_name, weapon, potion_used, False, error="The raid ended before your attack landed.")

        current_hp = int(row["current_hp"])
        reward = 0
        drops: tuple[tuple[str, str], ...] = ()

        if current_hp == 0:
            reward = await self.resolve(broadcaster_id, defeated=True, final_hitter_id=user_id, final_hitter_name=username)

            if reward > 0:
                drops = await self._award_victory_drops(broadcaster_id, user_id, username, event, config)

        LOGGER.info("[Raid Bosses] %s dealt %d damage to %s in broadcaster %s.", username, damage, event.boss_name, broadcaster_id)
        broken_weapon = weapon if weapon and not weapon_used else None
        return RaidAttackResult(damage, current_hp, event.boss_name, weapon_used, potion_used, current_hp == 0, reward, critical_hit=critical_hit, broken_weapon=broken_weapon, drops=drops)

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

        if item_id not in (*BASIC_WEAPON_TYPES, "potion"):
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
                    INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = 1, durability = excluded.durability
                    """,
                    (str(broadcaster_id), str(user_id), item_id, config.weapon_durability)
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

    async def get_inventory(self, broadcaster_id: str, user_id: str) -> tuple[list[str], str | None, int, int]:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                "SELECT item_id, durability FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND quantity > 0 ORDER BY item_id",
                (str(broadcaster_id), str(user_id))
            )
            player = await connection.fetchone(
                "SELECT equipped_weapon, potion_attacks_remaining FROM raid_boss_players WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

        weapons = [str(row["item_id"]) for row in rows]
        equipped = str(player["equipped_weapon"]) if player and player["equipped_weapon"] else None
        equipped_durability = next((int(row["durability"]) for row in rows if str(row["item_id"]) == equipped), 0)
        potions = int(player["potion_attacks_remaining"]) if player else 0
        return weapons, equipped, equipped_durability, potions

    async def repair(self, broadcaster_id: str, user_id: str, weapon: str, config: RaidBossConfig) -> str:
        weapon = weapon.lower()

        if weapon not in WEAPON_TYPES:
            return "invalid"

        async with self.db.acquire() as connection:
            owned = await connection.fetchone(
                "SELECT durability FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ? AND quantity > 0",
                (str(broadcaster_id), str(user_id), weapon)
            )

            if owned is None:
                return "not_owned"

            if int(owned["durability"]) >= config.weapon_durability:
                return "full"

            balance = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

            if balance is None or int(balance["points"]) < config.repair_cost:
                return "insufficient"

            await connection.execute(
                "UPDATE viewers SET points = points - ? WHERE broadcaster_id = ? AND user_id = ?",
                (config.repair_cost, str(broadcaster_id), str(user_id))
            )
            await connection.execute(
                "UPDATE raid_boss_inventory SET durability = ? WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?",
                (config.weapon_durability, str(broadcaster_id), str(user_id), weapon)
            )

        return "repaired"

    async def get_dashboard_metrics(self, broadcaster_id: str) -> dict[str, object] | None:
        query = """
        SELECT events.id, events.boss_name, events.boss_type, events.boss_tier,
               events.max_hp, events.current_hp, events.reward_pool, events.status,
               events.stream_limit,
               (SELECT COUNT(*) FROM raid_boss_streams WHERE event_id = events.id) AS streams_used,
               (SELECT COUNT(*) FROM raid_boss_attacks WHERE event_id = events.id) AS total_attacks,
               (SELECT COUNT(DISTINCT user_id) FROM raid_boss_attacks WHERE event_id = events.id) AS unique_attackers,
               (SELECT COALESCE(SUM(damage), 0) FROM raid_boss_attacks WHERE event_id = events.id) AS total_damage,
               (SELECT COALESCE(AVG(damage), 0) FROM raid_boss_attacks WHERE event_id = events.id) AS average_damage,
               (SELECT COUNT(*) FROM raid_boss_attacks WHERE event_id = events.id AND weapon IS NOT NULL) AS weapon_attacks,
               (SELECT COALESCE(SUM(potion_used), 0) FROM raid_boss_attacks WHERE event_id = events.id) AS potion_attacks,
               (SELECT COALESCE(SUM(critical_hit), 0) FROM raid_boss_attacks WHERE event_id = events.id) AS critical_hits
        FROM raid_boss_events AS events
        WHERE events.id = (
            SELECT id FROM raid_boss_events
            WHERE broadcaster_id = ?
            ORDER BY id DESC
            LIMIT 1
        )
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(broadcaster_id),))

        if row is None:
            return None

        max_hp = int(row["max_hp"])
        current_hp = int(row["current_hp"])
        return {
            "event_id": int(row["id"]),
            "boss_name": str(row["boss_name"]),
            "boss_type": str(row["boss_type"]),
            "boss_tier": str(row["boss_tier"]),
            "max_hp": max_hp,
            "current_hp": current_hp,
            "hp_percent": round(current_hp / max_hp * 100, 1),
            "reward_pool": int(row["reward_pool"]),
            "status": str(row["status"]),
            "stream_limit": int(row["stream_limit"]),
            "streams_used": int(row["streams_used"]),
            "total_attacks": int(row["total_attacks"]),
            "unique_attackers": int(row["unique_attackers"]),
            "total_damage": int(row["total_damage"]),
            "average_damage": round(float(row["average_damage"]), 1),
            "weapon_attacks": int(row["weapon_attacks"]),
            "potion_attacks": int(row["potion_attacks"]),
            "critical_hits": int(row["critical_hits"])
        }

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

            if defeated and event.boss_tier == "tutorial":
                await connection.execute(
                    """
                    INSERT INTO raid_boss_channel_state (broadcaster_id, tutorial_completed)
                    VALUES (?, 1)
                    ON CONFLICT(broadcaster_id) DO UPDATE SET tutorial_completed = 1
                    """,
                    (str(broadcaster_id),)
                )

        LOGGER.info("[Raid Bosses] Resolved %s as %s with a %d-point pool.", event.boss_name, status, payout_pool)
        return payout_pool

    async def _award_victory_drops(self, broadcaster_id: str, final_hitter_id: str, final_hitter_name: str, event: RaidBossEvent, config: RaidBossConfig) -> tuple[tuple[str, str], ...]:
        async with self.db.acquire() as connection:
            contributors = await connection.fetchall(
                """
                SELECT user_id, username, SUM(damage) AS total_damage
                FROM raid_boss_attacks
                WHERE event_id = ?
                GROUP BY user_id, username
                ORDER BY total_damage DESC, username COLLATE NOCASE
                """,
                (event.id,)
            )

            awards: list[tuple[str, str, str]] = []

            if event.boss_tier == "tutorial":
                starter_weapons = tuple(BASIC_WEAPON_TYPES)
                awards = [(str(contributor["user_id"]), str(contributor["username"]), random.choice(starter_weapons)) for contributor in contributors]
            else:
                mythical_weapon = next(item_id for item_id, weapon_type in UNIQUE_WEAPON_TYPES.items() if weapon_type == event.boss_type)

                if random.random() < config.final_hit_unique_drop_chance:
                    awards.append((str(final_hitter_id), final_hitter_name, mythical_weapon))

                contributor_count = len(contributors)
                top_count = max(1, math.ceil(contributor_count * config.top_contributor_percent)) if contributor_count else 0

                for contributor in contributors[:top_count]:
                    if random.random() < config.top_contributor_unique_drop_chance:
                        awards.append((str(contributor["user_id"]), str(contributor["username"]), mythical_weapon))

            for recipient_id, recipient_name, item_id in awards:
                await self._ensure_player(connection, broadcaster_id, recipient_id, recipient_name)
                await connection.execute(
                    """
                    INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = 1, durability = MAX(durability, excluded.durability)
                    """,
                    (str(broadcaster_id), recipient_id, item_id, config.weapon_durability)
                )
                LOGGER.info("[Raid Bosses] Awarded %s to %s for defeating %s.", item_id, recipient_name, event.boss_name)

        return tuple((recipient_name, item_id) for _, recipient_name, item_id in awards)

    async def _get_player(self, broadcaster_id: str, user_id: str):
        async with self.db.acquire() as connection:
            return await connection.fetchone(
                """
                SELECT players.equipped_weapon, players.potion_attacks_remaining,
                       COALESCE(inventory.durability, 0) AS weapon_durability
                FROM raid_boss_players AS players
                LEFT JOIN raid_boss_inventory AS inventory
                  ON inventory.broadcaster_id = players.broadcaster_id
                 AND inventory.user_id = players.user_id
                 AND inventory.item_id = players.equipped_weapon
                WHERE players.broadcaster_id = ? AND players.user_id = ?
                """,
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
            boss_tier=str(row["boss_tier"]),
            max_hp=int(row["max_hp"]),
            current_hp=int(row["current_hp"]),
            reward_pool=int(row["reward_pool"]),
            status=str(row["status"]),
            stream_limit=int(row["stream_limit"]),
            streams_used=int(row["streams_used"])
        )

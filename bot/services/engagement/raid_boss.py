import asyncio
import logging
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bot.profiles import RaidBossConfig

LOGGER = logging.getLogger("RatBoomBot")

BASIC_WEAPON_TYPES = {
    "basic_sword": "melee",
    "basic_bow": "ranged",
    "apprentice_tome": "magic"
}
REFINED_WEAPON_TYPES = {
    "refined_sword": "melee",
    "refined_bow": "ranged",
    "enchanted_tome": "magic"
}
MASTERWORK_WEAPON_TYPES = {
    "masterwork_sword": "melee",
    "masterwork_bow": "ranged",
    "archmage_grimoire": "magic"
}
UNIQUE_WEAPON_TYPES = {
    "mythical_blade": "melee",
    "mythical_longbow": "ranged",
    "mythical_grimoire": "magic"
}
STANDARD_WEAPON_TYPES = BASIC_WEAPON_TYPES | REFINED_WEAPON_TYPES | MASTERWORK_WEAPON_TYPES
WEAPON_TYPES = STANDARD_WEAPON_TYPES | UNIQUE_WEAPON_TYPES
ITEM_ALIASES = {"sword": "basic_sword", "bow": "basic_bow", "tome": "apprentice_tome", "spellbook": "apprentice_tome", "power": "potion", "power_potion": "potion", "secondwind": "second_wind", "blessing_of_the_gods": "blessing", "archmage's_grimoire": "archmage_grimoire", "archmage’s_grimoire": "archmage_grimoire"}
BUFF_ITEMS = frozenset({"potion", "second_wind", "berserk", "blessing"})
CRAFTING_RECIPES = {
    "refined_sword": "basic_sword", "refined_bow": "basic_bow", "enchanted_tome": "apprentice_tome",
    "masterwork_sword": "refined_sword", "masterwork_bow": "refined_bow", "archmage_grimoire": "enchanted_tome"
}
CRAFTING_FAMILIES = {
    "sword": (("masterwork_sword", "refined_sword"), ("refined_sword", "basic_sword")),
    "bow": (("masterwork_bow", "refined_bow"), ("refined_bow", "basic_bow")),
    "tome": (("archmage_grimoire", "enchanted_tome"), ("enchanted_tome", "apprentice_tome")),
    "magic": (("archmage_grimoire", "enchanted_tome"), ("enchanted_tome", "apprentice_tome"))
}


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
    buff_used: str | None = None
    blessing_active: bool = False
    shattered_weapon: str | None = None


class RaidBossService:

    PRE_SPAWN_SECONDS = 10 * 60
    AUTOMATIC_WARNING_SECONDS = 20 * 60
    FIRST_REMINDER_SECONDS = 45 * 60
    REPEAT_REMINDER_SECONDS = 60 * 60
    REQUIRED_REMINDER_MESSAGES = 20

    def __init__(self, bot, db, chatter_stats=None):
        self.bot = bot
        self.db = db
        self.chatter_stats = chatter_stats
        self.spawn_tasks: dict[str, asyncio.Task] = {}
        self.reminder_tasks: dict[str, asyncio.Task] = {}
        self.reminder_message_counts: dict[str, int] = {}
        self.reminder_activity_events: dict[str, asyncio.Event] = {}

    async def setup(self) -> None:
        LOGGER.info("[Raid Bosses] Raid boss storage is managed by database migrations.")

    @staticmethod
    def is_buff(item_id: str) -> bool:
        return item_id in BUFF_ITEMS

    @staticmethod
    def contribution_reward_multiplier(rank: int, contributor_count: int) -> float:
        if rank <= max(1, math.ceil(contributor_count * 0.10)):
            return 2.0

        if rank <= math.ceil(contributor_count * 0.20):
            return 1.5

        if rank <= math.ceil(contributor_count * 0.50):
            return 1.25

        return 1.0

    async def stop(self) -> None:
        tasks = tuple(self.spawn_tasks.values()) + tuple(self.reminder_tasks.values())
        self.spawn_tasks.clear()
        self.reminder_tasks.clear()
        self.reminder_message_counts.clear()
        self.reminder_activity_events.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def schedule_spawn(self, broadcaster_id: str, config: RaidBossConfig, boss_tier: str | None = None, boss_type: str | None = None, stream_id: str | None = None) -> bool:
        broadcaster_id = str(broadcaster_id)

        if broadcaster_id in self.spawn_tasks or await self.get_active_event(broadcaster_id) is not None:
            return False

        automatic = boss_tier is None or boss_type is None
        stream_id = str(stream_id or self._active_stream_id(broadcaster_id) or "manual")
        now = datetime.now(UTC)
        warning_at = now + timedelta(seconds=self.AUTOMATIC_WARNING_SECONDS if automatic else 0)
        spawn_at = warning_at + timedelta(seconds=self.PRE_SPAWN_SECONDS)
        await self._save_spawn_schedule(broadcaster_id, stream_id, boss_tier, boss_type, warning_at, spawn_at)
        task = asyncio.create_task(self._spawn_after_warning(broadcaster_id, config, boss_tier, boss_type, warning_at, spawn_at, False), name=f"raid-spawn-{broadcaster_id}")
        self.spawn_tasks[broadcaster_id] = task
        return True

    async def restore_session(self, broadcaster_id: str, stream_id: str, config: RaidBossConfig) -> None:
        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)
        active_event = await self.get_active_event(broadcaster_id)

        if active_event is not None:
            await self.register_stream(broadcaster_id, stream_id)
            await self.start_reminders(broadcaster_id, stream_id)
            return

        schedule = await self._get_schedule(broadcaster_id)

        if schedule is None or str(schedule["stream_id"]) != stream_id or schedule["spawn_at"] is None:
            await self.schedule_spawn(broadcaster_id, config, stream_id=stream_id)
            return

        warning_at = datetime.fromisoformat(str(schedule["warning_at"]))
        spawn_at = datetime.fromisoformat(str(schedule["spawn_at"]))
        boss_tier = str(schedule["boss_tier"]) if schedule["boss_tier"] is not None else None
        boss_type = str(schedule["boss_type"]) if schedule["boss_type"] is not None else None
        self.spawn_tasks[broadcaster_id] = asyncio.create_task(self._spawn_after_warning(broadcaster_id, config, boss_tier, boss_type, warning_at, spawn_at, bool(schedule["warning_sent"])), name=f"raid-spawn-{broadcaster_id}")

    async def cancel_announcements(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        self.reminder_message_counts.pop(broadcaster_id, None)
        self.reminder_activity_events.pop(broadcaster_id, None)

        for tasks in (self.spawn_tasks, self.reminder_tasks):
            task = tasks.pop(broadcaster_id, None)

            if task is not None:
                task.cancel()

        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM raid_boss_schedules WHERE broadcaster_id = ?", (broadcaster_id,))

    async def start_reminders(self, broadcaster_id: str, stream_id: str | None = None) -> None:
        broadcaster_id = str(broadcaster_id)
        existing = self.reminder_tasks.pop(broadcaster_id, None)

        if existing is not None:
            existing.cancel()

        schedule = await self._get_schedule(broadcaster_id)
        message_count = int(schedule["reminder_message_count"]) if schedule is not None else 0
        next_reminder_at = datetime.fromisoformat(str(schedule["next_reminder_at"])) if schedule is not None and schedule["next_reminder_at"] else datetime.now(UTC) + timedelta(seconds=self.FIRST_REMINDER_SECONDS)
        stream_id = str(stream_id or (schedule["stream_id"] if schedule is not None else self._active_stream_id(broadcaster_id) or "unknown"))
        await self._save_reminder_schedule(broadcaster_id, stream_id, next_reminder_at, message_count)
        self.reminder_message_counts[broadcaster_id] = message_count
        self.reminder_activity_events[broadcaster_id] = asyncio.Event()

        if message_count >= self.REQUIRED_REMINDER_MESSAGES:
            self.reminder_activity_events[broadcaster_id].set()

        self.reminder_tasks[broadcaster_id] = asyncio.create_task(self._reminder_loop(broadcaster_id), name=f"raid-reminders-{broadcaster_id}")

    async def track_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)

        if broadcaster_id not in self.reminder_tasks:
            return

        current_count = self.reminder_message_counts.get(broadcaster_id, 0)

        if current_count >= self.REQUIRED_REMINDER_MESSAGES:
            return

        message_count = current_count + 1
        self.reminder_message_counts[broadcaster_id] = message_count

        async with self.db.acquire() as connection:
            await connection.execute("UPDATE raid_boss_schedules SET reminder_message_count = ? WHERE broadcaster_id = ?", (message_count, broadcaster_id))

        if message_count >= self.REQUIRED_REMINDER_MESSAGES:
            activity_event = self.reminder_activity_events.get(broadcaster_id)

            if activity_event is not None:
                activity_event.set()

    async def _spawn_after_warning(self, broadcaster_id: str, config: RaidBossConfig, boss_tier: str | None, boss_type: str | None, warning_at: datetime, spawn_at: datetime, warning_sent: bool) -> None:
        try:
            warning_delay = max(0.0, (warning_at - datetime.now(UTC)).total_seconds())

            if warning_delay:
                await self._sleep_until(warning_at)

            if not warning_sent and datetime.now(UTC) < spawn_at:
                await self._send_message(broadcaster_id, "A dangerous presence is approaching... Prepare yourselves for the raid in 10 minutes!")

                async with self.db.acquire() as connection:
                    await connection.execute("UPDATE raid_boss_schedules SET warning_sent = 1 WHERE broadcaster_id = ?", (broadcaster_id,))

            await self._sleep_until(spawn_at)

            automatic = boss_tier is None or boss_type is None
            event = await self.spawn_automatic(broadcaster_id, config) if automatic else await self.spawn(broadcaster_id, str(boss_type), config, str(boss_tier))

            if event is None:
                return

            active_session = self.bot.services.stream_logs.active_sessions.get(broadcaster_id)

            if active_session is not None:
                await self.register_stream(broadcaster_id, str(active_session.stream_id))

            stream_id = str(active_session.stream_id) if active_session is not None else str(self._active_stream_id(broadcaster_id) or "manual")
            await self._save_reminder_schedule(broadcaster_id, stream_id, datetime.now(UTC) + timedelta(seconds=self.FIRST_REMINDER_SECONDS), 0)
            await self.send_announcement(broadcaster_id, self._spawn_message(event), "orange")
            await self.start_reminders(broadcaster_id, stream_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("[Raid Bosses] Scheduled spawn failed for broadcaster %s.", broadcaster_id)
        finally:
            if self.spawn_tasks.get(broadcaster_id) is asyncio.current_task():
                self.spawn_tasks.pop(broadcaster_id, None)

    async def _reminder_loop(self, broadcaster_id: str) -> None:
        try:
            while True:
                event = await self.get_active_event(broadcaster_id)

                if event is None:
                    return

                schedule = await self._get_schedule(broadcaster_id)
                next_reminder_at = datetime.fromisoformat(str(schedule["next_reminder_at"])) if schedule is not None and schedule["next_reminder_at"] else datetime.now(UTC)
                await self._sleep_until(next_reminder_at)
                await self._wait_for_reminder_activity(broadcaster_id)
                event = await self.get_active_event(broadcaster_id)

                if event is None:
                    return

                await self._send_message(broadcaster_id, self._reminder_message(event))
                self.reminder_message_counts[broadcaster_id] = 0
                self.reminder_activity_events[broadcaster_id].clear()
                next_reminder_at = datetime.now(UTC) + timedelta(seconds=self.REPEAT_REMINDER_SECONDS)
                stream_id = str(schedule["stream_id"]) if schedule is not None else str(self._active_stream_id(broadcaster_id) or "unknown")
                await self._save_reminder_schedule(broadcaster_id, stream_id, next_reminder_at, 0)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("[Raid Bosses] Reminder loop failed for broadcaster %s.", broadcaster_id)
        finally:
            if self.reminder_tasks.get(broadcaster_id) is asyncio.current_task():
                self.reminder_tasks.pop(broadcaster_id, None)
                self.reminder_message_counts.pop(broadcaster_id, None)
                self.reminder_activity_events.pop(broadcaster_id, None)

    async def _wait_for_reminder_activity(self, broadcaster_id: str) -> None:
        if self.reminder_message_counts.get(broadcaster_id, 0) >= self.REQUIRED_REMINDER_MESSAGES:
            return

        activity_event = self.reminder_activity_events.get(broadcaster_id)

        if activity_event is None:
            activity_event = asyncio.Event()
            self.reminder_activity_events[broadcaster_id] = activity_event

        await activity_event.wait()

    @staticmethod
    async def _sleep_until(target: datetime) -> None:
        await asyncio.sleep(max(0.0, (target - datetime.now(UTC)).total_seconds()))

    def _active_stream_id(self, broadcaster_id: str) -> str | None:
        services = getattr(self.bot, "services", None)
        stream_logs = getattr(services, "stream_logs", None)
        active_sessions = getattr(stream_logs, "active_sessions", {})
        session = active_sessions.get(str(broadcaster_id))
        return str(session.stream_id) if session is not None else None

    async def _get_schedule(self, broadcaster_id: str):
        async with self.db.acquire() as connection:
            return await connection.fetchone("SELECT * FROM raid_boss_schedules WHERE broadcaster_id = ?", (str(broadcaster_id),))

    async def _save_spawn_schedule(self, broadcaster_id: str, stream_id: str, boss_tier: str | None, boss_type: str | None, warning_at: datetime, spawn_at: datetime) -> None:
        query = """
        INSERT INTO raid_boss_schedules (broadcaster_id, stream_id, boss_tier, boss_type, warning_at, warning_sent, spawn_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            stream_id = excluded.stream_id,
            boss_tier = excluded.boss_tier,
            boss_type = excluded.boss_type,
            warning_at = excluded.warning_at,
            warning_sent = 0,
            spawn_at = excluded.spawn_at,
            next_reminder_at = NULL,
            reminder_message_count = 0
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, stream_id, boss_tier, boss_type, warning_at.isoformat(), spawn_at.isoformat()))

    async def _save_reminder_schedule(self, broadcaster_id: str, stream_id: str, next_reminder_at: datetime, message_count: int) -> None:
        query = """
        INSERT INTO raid_boss_schedules (broadcaster_id, stream_id, next_reminder_at, reminder_message_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(broadcaster_id) DO UPDATE SET
            stream_id = excluded.stream_id,
            warning_at = NULL,
            spawn_at = NULL,
            next_reminder_at = excluded.next_reminder_at,
            reminder_message_count = excluded.reminder_message_count
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, stream_id, next_reminder_at.isoformat(), message_count))

    async def _send_message(self, broadcaster_id: str, message: str) -> None:
        channel = self.bot.create_partialuser(str(broadcaster_id))
        await self.bot.services.chat_identity.send_message(channel, message)

    async def send_announcement(self, broadcaster_id: str, message: str, color: str) -> None:
        channel = self.bot.create_partialuser(str(broadcaster_id))

        try:
            await self.bot.services.chat_identity.send_announcement(channel, message, color)
        except Exception:
            LOGGER.warning("[Raid Bosses] Could not send a raid announcement for broadcaster %s. Falling back to a chat message.", broadcaster_id, exc_info=True, extra={"broadcaster_id": str(broadcaster_id)})
            await self.bot.services.chat_identity.send_message(channel, message)

    @staticmethod
    def _spawn_message(event: RaidBossEvent) -> str:
        return f"{event.boss_name} [{event.boss_tier.title()} Boss / {event.boss_type.title()}] has appeared with {event.max_hp:,} HP for {event.stream_limit} streams! Everyone gets one !raid attack per stream."

    @staticmethod
    def _reminder_message(event: RaidBossEvent) -> str:
        percent = event.current_hp / event.max_hp * 100
        return f"Raid reminder: {event.boss_name} has {event.current_hp:,}/{event.max_hp:,} HP remaining ({percent:.1f}%). Use !raid attack before the stream ends!"

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

    async def spawn_automatic(self, broadcaster_id: str, config: RaidBossConfig) -> RaidBossEvent | None:
        if not config.automatic_spawning_enabled or not await self.has_completed_tutorial(broadcaster_id):
            return None

        if await self.get_active_event(broadcaster_id) is not None:
            return None

        async with self.db.acquire() as connection:
            row = await connection.fetchone("SELECT consecutive_mini_bosses FROM raid_boss_channel_state WHERE broadcaster_id = ?", (str(broadcaster_id),))

        consecutive_minis = int(row["consecutive_mini_bosses"]) if row else 0
        main_chance = 0.0

        main_boss_guaranteed = consecutive_minis >= config.main_boss_guaranteed_after_minis

        if main_boss_guaranteed:
            main_chance = 1.0
        elif consecutive_minis == 4:
            main_chance = config.main_boss_chance_after_four_minis
        elif consecutive_minis == 3:
            main_chance = config.main_boss_chance_after_three_minis

        boss_tier = "main" if main_boss_guaranteed or random.random() < main_chance else "mini"
        event = await self.spawn(broadcaster_id, random.choice(tuple(BASIC_WEAPON_TYPES.values())), config, boss_tier)

        if event is None:
            return None

        next_mini_count = 0 if boss_tier == "main" else consecutive_minis + 1

        async with self.db.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO raid_boss_channel_state (broadcaster_id, consecutive_mini_bosses)
                VALUES (?, ?)
                ON CONFLICT(broadcaster_id) DO UPDATE SET consecutive_mini_bosses = excluded.consecutive_mini_bosses
                """,
                (str(broadcaster_id), next_mini_count)
            )

        LOGGER.info("[Raid Bosses] Automatic cycle selected a %s boss for broadcaster %s after %d consecutive mini bosses.", boss_tier, broadcaster_id, consecutive_minis)
        return event

    async def spawn(self, broadcaster_id: str, boss_type: str, config: RaidBossConfig, boss_tier: str = "main") -> RaidBossEvent | None:
        boss_type = boss_type.lower()
        boss_tier = boss_tier.lower()
        active_event = await self.get_active_event(broadcaster_id)

        if boss_type not in WEAPON_TYPES.values() or boss_tier not in {"mini", "main", "tutorial"} or active_event is not None:
            return None

        if boss_tier == "tutorial" and (not config.tutorial_enabled or await self.has_completed_tutorial(broadcaster_id)):
            return None

        if boss_tier == "tutorial":
            boss_name = config.tutorial_name
            max_hp = config.tutorial_hp
            final_hit_reward = config.mini_final_hit_reward
            stream_limit = config.tutorial_duration_streams
        elif boss_tier == "mini":
            boss_name = random.choice(config.mini_names.choices_for(boss_type))
            max_hp = random.randrange(config.mini_hp_min, config.mini_hp_max + 1, config.mini_hp_step)
            final_hit_reward = config.mini_final_hit_reward
            stream_limit = config.mini_duration_streams
        else:
            boss_name = random.choice(config.names.choices_for(boss_type))
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

        stream_id = str(stream_id)
        player = await self._get_player(broadcaster_id, user_id)
        weapon = player["equipped_weapon"] if player else None
        weapon_durability = int(player["weapon_durability"]) if player else 0
        weapon_used = weapon if weapon and weapon_durability > 0 else None
        potion_attacks = int(player["potion_attacks_remaining"]) if player else 0
        second_wind_charges = int(player["second_wind_charges"]) if player and "second_wind_charges" in player.keys() else 0
        berserk_charges = int(player["berserk_charges"]) if player and "berserk_charges" in player.keys() else 0

        async with self.db.acquire() as connection:
            prior = await connection.fetchone(
                "SELECT COUNT(*) AS attacks, COALESCE(SUM(CASE WHEN buff_used = 'berserk' THEN 1 ELSE 0 END), 0) AS berserks FROM raid_boss_attacks WHERE event_id = ? AND stream_id = ? AND user_id = ?",
                (event.id, stream_id, user_id)
            )
            blessing = await connection.fetchone("SELECT blessing_username FROM raid_boss_stream_effects WHERE broadcaster_id = ? AND stream_id = ?", (broadcaster_id, stream_id))

        attack_number = int(prior["attacks"]) + 1

        if attack_number > 2 or (attack_number == 2 and second_wind_charges <= 0):
            return RaidAttackResult(0, event.current_hp, event.boss_name, weapon, False, False, error="You already attacked during this stream.")

        berserk_used = berserk_charges > 0 and int(prior["berserks"]) == 0

        if berserk_used and (weapon_used is None or weapon_durability < config.berserk_durability_cost):
            return RaidAttackResult(0, event.current_hp, event.boss_name, weapon, False, False, error=f"Berserk requires an equipped weapon with at least {config.berserk_durability_cost} durability.")

        damage = random.randint(config.base_damage_min, config.base_damage_max)

        if weapon_used:
            if weapon_used in UNIQUE_WEAPON_TYPES:
                weapon_attack = config.unique_weapon_attack
            elif weapon_used in MASTERWORK_WEAPON_TYPES:
                weapon_attack = config.masterwork_weapon_attack
            elif weapon_used in REFINED_WEAPON_TYPES:
                weapon_attack = config.refined_weapon_attack
            else:
                weapon_attack = config.weapon_attack

            if WEAPON_TYPES.get(weapon_used) == event.boss_type:
                weapon_attack = round(weapon_attack * config.weapon_multiplier)

            damage += weapon_attack

        potion_used = potion_attacks > 0 and not berserk_used

        if berserk_used:
            damage = round(damage * config.berserk_multiplier)
        elif potion_used:
            damage = round(damage * config.potion_multiplier)

        blessing_active = blessing is not None

        if blessing_active:
            damage = round(damage * config.blessing_multiplier)

        critical_hit = not berserk_used and random.random() < config.critical_chance

        if critical_hit:
            damage = round(damage * config.critical_multiplier)

        damage = min(damage, event.current_hp)
        now = datetime.now(UTC).isoformat()

        shattered_weapon = weapon_used if berserk_used and weapon_used in STANDARD_WEAPON_TYPES and random.random() < config.berserk_shatter_chance else None
        buff_used = "berserk" if berserk_used else "power_potion" if potion_used else None

        async with self.db.acquire() as connection:
            attack_row = await connection.fetchone(
                """
                INSERT INTO raid_boss_attacks (
                    event_id, broadcaster_id, stream_id, user_id, username, damage,
                    attack_number, weapon, potion_used, critical_hit, buff_used, blessing_active, weapon_shattered, attacked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, stream_id, user_id, attack_number) DO NOTHING
                RETURNING event_id
                """,
                (event.id, broadcaster_id, stream_id, user_id, username, damage, attack_number, weapon_used, int(potion_used), int(critical_hit), buff_used, int(blessing_active), int(shattered_weapon is not None), now)
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

            if berserk_used:
                await connection.execute("UPDATE raid_boss_players SET berserk_charges = MAX(berserk_charges - 1, 0) WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))

            if attack_number == 2:
                await connection.execute("UPDATE raid_boss_players SET second_wind_charges = MAX(second_wind_charges - 1, 0) WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))

            if weapon_used:
                durability_cost = config.berserk_durability_cost if berserk_used else 1

                if shattered_weapon:
                    await connection.execute("UPDATE raid_boss_inventory SET quantity = MAX(quantity - 1, 0), durability = ? WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?", (config.weapon_durability, broadcaster_id, user_id, weapon_used))
                    await connection.execute("UPDATE raid_boss_players SET equipped_weapon = NULL WHERE broadcaster_id = ? AND user_id = ? AND NOT EXISTS (SELECT 1 FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ? AND quantity > 0)", (broadcaster_id, user_id, broadcaster_id, user_id, weapon_used))
                else:
                    await connection.execute("UPDATE raid_boss_inventory SET durability = MAX(durability - ?, 0) WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?", (durability_cost, broadcaster_id, user_id, weapon_used))

        if row is None:
            return RaidAttackResult(0, 0, event.boss_name, weapon, potion_used, False, error="The raid ended before your attack landed.")

        current_hp = int(row["current_hp"])
        reward = 0
        drops: tuple[tuple[str, str], ...] = ()

        if current_hp == 0:
            reward = await self.resolve(broadcaster_id, defeated=True, final_hitter_id=user_id, final_hitter_name=username)

            if reward > 0:
                drops = await self._award_victory_drops(broadcaster_id, event, config)

        LOGGER.info("[Raid Bosses] %s dealt %d damage to %s in broadcaster %s.", username, damage, event.boss_name, broadcaster_id)
        broken_weapon = weapon if weapon and not weapon_used else None
        return RaidAttackResult(damage, current_hp, event.boss_name, weapon_used, potion_used, current_hp == 0, reward, critical_hit=critical_hit, broken_weapon=broken_weapon, drops=drops, buff_used=buff_used, blessing_active=blessing_active, shattered_weapon=shattered_weapon)

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

    async def buy(self, broadcaster_id: str, user_id: str, username: str, item_id: str, config: RaidBossConfig, stream_id: str | None = None) -> str | None:
        item_id = self.normalize_item(item_id)
        costs = {"potion": config.potion_cost, "second_wind": config.second_wind_cost, "berserk": config.berserk_cost, "blessing": config.blessing_cost}
        cost = costs.get(item_id, config.weapon_cost)

        if item_id not in (*BASIC_WEAPON_TYPES, *costs):
            return None

        if self.is_buff(item_id) and stream_id is None:
            return "stream_required"

        async with self.db.acquire() as connection:
            if item_id == "blessing":
                existing = await connection.fetchone("SELECT blessing_username FROM raid_boss_stream_effects WHERE broadcaster_id = ? AND stream_id = ?", (str(broadcaster_id), str(stream_id)))

                if existing is not None:
                    return f"out_of_stock:{existing['blessing_username']}"

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

            if item_id in {"potion", "second_wind", "berserk"}:
                column = {"potion": "potion_attacks_remaining", "second_wind": "second_wind_charges", "berserk": "berserk_charges"}[item_id]
                amount = config.potion_attacks if item_id == "potion" else 1
                await connection.execute(
                    f"UPDATE raid_boss_players SET {column} = {column} + ? WHERE broadcaster_id = ? AND user_id = ?",
                    (amount, str(broadcaster_id), str(user_id))
                )
            elif item_id == "blessing":
                inserted = await connection.fetchone(
                    "INSERT INTO raid_boss_stream_effects (broadcaster_id, stream_id, blessing_user_id, blessing_username, purchased_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(broadcaster_id, stream_id) DO NOTHING RETURNING blessing_username",
                    (str(broadcaster_id), str(stream_id), str(user_id), username, datetime.now(UTC).isoformat())
                )

                if inserted is None:
                    existing = await connection.fetchone("SELECT blessing_username FROM raid_boss_stream_effects WHERE broadcaster_id = ? AND stream_id = ?", (str(broadcaster_id), str(stream_id)))
                    await connection.execute("UPDATE viewers SET points = points + ? WHERE broadcaster_id = ? AND user_id = ?", (cost, str(broadcaster_id), str(user_id)))
                    return f"out_of_stock:{existing['blessing_username']}"
            else:
                await connection.execute(
                    """
                    INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = quantity + 1
                    """,
                    (str(broadcaster_id), str(user_id), item_id, config.weapon_durability)
                )

        return "purchased"

    async def craft(self, broadcaster_id: str, user_id: str, username: str, item_id: str, config: RaidBossConfig) -> str:
        requested_item = "_".join(item_id.lower().strip().split())
        family = CRAFTING_FAMILIES.get(requested_item)
        item_id = self.normalize_item(item_id) if family is None else ""
        ingredient = CRAFTING_RECIPES.get(item_id)

        if family is None and ingredient is None:
            return "invalid"

        async with self.db.acquire() as connection:
            owned = None

            if family is not None:
                for output, required_item in family:
                    candidate = await connection.fetchone("SELECT quantity FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?", (str(broadcaster_id), str(user_id), required_item))

                    if candidate is not None and int(candidate["quantity"]) >= 2:
                        item_id, ingredient, owned = output, required_item, candidate
                        break
            else:
                owned = await connection.fetchone("SELECT quantity FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?", (str(broadcaster_id), str(user_id), ingredient))

            if owned is None or int(owned["quantity"]) < 2:
                return "materials"

            cost = config.masterwork_crafting_cost if item_id in MASTERWORK_WEAPON_TYPES else config.refined_crafting_cost
            balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?", (str(broadcaster_id), str(user_id)))

            if balance is None or int(balance["points"]) < cost:
                return "insufficient"

            await self._ensure_player(connection, broadcaster_id, user_id, username)
            player = await connection.fetchone("SELECT equipped_weapon FROM raid_boss_players WHERE broadcaster_id = ? AND user_id = ?", (str(broadcaster_id), str(user_id)))
            await connection.execute("UPDATE viewers SET points = points - ? WHERE broadcaster_id = ? AND user_id = ?", (cost, str(broadcaster_id), str(user_id)))
            await connection.execute("UPDATE raid_boss_inventory SET quantity = quantity - 2 WHERE broadcaster_id = ? AND user_id = ? AND item_id = ?", (str(broadcaster_id), str(user_id), ingredient))
            await connection.execute("INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability) VALUES (?, ?, ?, 1, ?) ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = quantity + 1", (str(broadcaster_id), str(user_id), item_id, config.weapon_durability))

            if player and player["equipped_weapon"] == ingredient and int(owned["quantity"]) == 2:
                await connection.execute("UPDATE raid_boss_players SET equipped_weapon = ? WHERE broadcaster_id = ? AND user_id = ?", (item_id, str(broadcaster_id), str(user_id)))

        return f"crafted:{item_id}"

    @staticmethod
    def normalize_item(item_id: str) -> str:
        normalized = "_".join(item_id.lower().strip().split())
        return ITEM_ALIASES.get(normalized, normalized)

    async def equip(self, broadcaster_id: str, user_id: str, username: str, weapon: str) -> bool:
        weapon = self.normalize_item(weapon)

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

    async def unequip(self, broadcaster_id: str, user_id: str) -> bool:
        async with self.db.acquire() as connection:
            row = await connection.fetchone(
                "UPDATE raid_boss_players SET equipped_weapon = NULL WHERE broadcaster_id = ? AND user_id = ? AND equipped_weapon IS NOT NULL RETURNING user_id",
                (str(broadcaster_id), str(user_id))
            )

        return row is not None

    async def get_inventory(self, broadcaster_id: str, user_id: str) -> tuple[list[tuple[str, int]], str | None, int, dict[str, int]]:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                "SELECT item_id, quantity, durability FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND quantity > 0 ORDER BY item_id",
                (str(broadcaster_id), str(user_id))
            )
            player = await connection.fetchone(
                "SELECT equipped_weapon, potion_attacks_remaining, second_wind_charges, berserk_charges FROM raid_boss_players WHERE broadcaster_id = ? AND user_id = ?",
                (str(broadcaster_id), str(user_id))
            )

        weapons = [(str(row["item_id"]), int(row["quantity"])) for row in rows]
        equipped = str(player["equipped_weapon"]) if player and player["equipped_weapon"] else None
        equipped_durability = next((int(row["durability"]) for row in rows if str(row["item_id"]) == equipped), 0)
        potions = {
            "power": int(player["potion_attacks_remaining"]) if player else 0,
            "second_wind": int(player["second_wind_charges"]) if player else 0,
            "berserk": int(player["berserk_charges"]) if player else 0
        }
        return weapons, equipped, equipped_durability, potions

    async def repair(self, broadcaster_id: str, user_id: str, weapon: str, config: RaidBossConfig) -> str:
        weapon = self.normalize_item(weapon)

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

    async def get_recent_events(self, broadcaster_id: str, limit: int = 5) -> list[dict[str, object]]:
        query = """
        SELECT events.boss_name, events.boss_type, events.boss_tier, events.status,
               events.max_hp, events.current_hp, events.reward_pool, events.spawned_at,
               (SELECT COUNT(DISTINCT user_id) FROM raid_boss_attacks WHERE event_id = events.id) AS unique_attackers,
               (SELECT COALESCE(SUM(damage), 0) FROM raid_boss_attacks WHERE event_id = events.id) AS total_damage
        FROM raid_boss_events AS events
        WHERE events.broadcaster_id = ?
          AND events.status IN ('defeated', 'failed')
        ORDER BY events.id DESC
        LIMIT ?
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (str(broadcaster_id), max(1, limit)))

        return [
            {
                "boss_name": str(row["boss_name"]),
                "boss_type": str(row["boss_type"]),
                "boss_tier": str(row["boss_tier"]),
                "status": str(row["status"]),
                "max_hp": int(row["max_hp"]),
                "current_hp": int(row["current_hp"]),
                "reward_pool": int(row["reward_pool"]),
                "spawned_at": str(row["spawned_at"]),
                "unique_attackers": int(row["unique_attackers"]),
                "total_damage": int(row["total_damage"])
            }
            for row in rows
        ]

    async def get_contributors(self, broadcaster_id: str) -> list[tuple[str, int]]:
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return []

        query = """
        SELECT username, SUM(damage) AS total_damage
        FROM raid_boss_attacks
        WHERE event_id = ?
        GROUP BY user_id, username
        ORDER BY total_damage DESC, username COLLATE NOCASE
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query, (event.id,))

        return [(str(row["username"]), int(row["total_damage"])) for row in rows]

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

    async def get_latest_loot(self, broadcaster_id: str, user_id: str) -> dict[str, object] | None:
        query = """
        SELECT events.id, events.boss_name, summaries.contribution_points, summaries.final_hit_points, summaries.bonus_points
        FROM raid_boss_events AS events
        LEFT JOIN raid_boss_reward_summaries AS summaries
          ON summaries.event_id = events.id
         AND summaries.user_id = ?
        WHERE events.broadcaster_id = ?
          AND events.status IN ('defeated', 'failed')
        ORDER BY events.id DESC
        LIMIT 1
        """

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (str(user_id), str(broadcaster_id)))

            if row is None:
                return None

            items = await connection.fetchall(
                "SELECT item_id FROM raid_boss_reward_items WHERE event_id = ? AND user_id = ? ORDER BY item_id",
                (int(row["id"]), str(user_id))
            )

        contribution_points = int(row["contribution_points"] or 0)
        final_hit_points = int(row["final_hit_points"] or 0)
        bonus_points = int(row["bonus_points"] or 0)
        return {
            "boss_name": str(row["boss_name"]),
            "contribution_points": contribution_points,
            "final_hit_points": final_hit_points,
            "bonus_points": bonus_points,
            "total_points": contribution_points + final_hit_points + bonus_points,
            "items": tuple(str(item["item_id"]) for item in items)
        }

    async def resolve(self, broadcaster_id: str, defeated: bool, final_hitter_id: str | None = None, final_hitter_name: str | None = None) -> int:
        event = await self.get_active_event(broadcaster_id)

        if event is None:
            return 0

        damage_dealt = event.max_hp - event.current_hp
        remaining_ratio = event.current_hp / event.max_hp
        multiplier = 1.0 if defeated else (0.5 if remaining_ratio <= 0.25 else 0.25)
        payout_pool = event.max_hp if defeated else round(event.reward_pool * multiplier)
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
                "SELECT user_id, username, SUM(damage) AS damage FROM raid_boss_attacks WHERE event_id = ? GROUP BY user_id, username ORDER BY damage DESC, username COLLATE NOCASE",
                (event.id,)
            )

            total_contribution_rewards = 0

            if damage_dealt > 0:
                base_reward = event.max_hp // len(contributions) if defeated and contributions else 0

                for rank, contribution in enumerate(contributions, start=1):
                    reward = int(base_reward * self.contribution_reward_multiplier(rank, len(contributions))) if defeated else payout_pool * int(contribution["damage"]) // damage_dealt
                    await self._add_points(connection, broadcaster_id, contribution["user_id"], contribution["username"], reward)
                    await connection.execute(
                        """
                        INSERT INTO raid_boss_reward_summaries (event_id, broadcaster_id, user_id, username, contribution_points)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(event_id, user_id) DO UPDATE SET contribution_points = excluded.contribution_points, username = excluded.username
                        """,
                        (event.id, str(broadcaster_id), str(contribution["user_id"]), str(contribution["username"]), reward)
                    )

            if defeated and final_hitter_id and final_hitter_name:
                final_hit_reward = int(resolution["final_hit_reward"])
                await self._add_points(connection, broadcaster_id, final_hitter_id, final_hitter_name, final_hit_reward)
                await connection.execute(
                    """
                    INSERT INTO raid_boss_reward_summaries (event_id, broadcaster_id, user_id, username, final_hit_points)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET final_hit_points = excluded.final_hit_points, username = excluded.username
                    """,
                    (event.id, str(broadcaster_id), str(final_hitter_id), str(final_hitter_name), final_hit_reward)
                )

            if defeated and event.boss_tier == "tutorial":
                await connection.execute(
                    """
                    INSERT INTO raid_boss_channel_state (broadcaster_id, tutorial_completed)
                    VALUES (?, 1)
                    ON CONFLICT(broadcaster_id) DO UPDATE SET tutorial_completed = 1
                    """,
                    (str(broadcaster_id),)
                )

        awarded_points = total_contribution_rewards if defeated else payout_pool
        LOGGER.info("[Raid Bosses] Resolved %s as %s with %d contribution points awarded.", event.boss_name, status, awarded_points)
        reminder_task = self.reminder_tasks.pop(str(broadcaster_id), None)

        if reminder_task is not None:
            reminder_task.cancel()

        self.reminder_message_counts.pop(str(broadcaster_id), None)
        self.reminder_activity_events.pop(str(broadcaster_id), None)

        async with self.db.acquire() as connection:
            await connection.execute("DELETE FROM raid_boss_schedules WHERE broadcaster_id = ?", (str(broadcaster_id),))

        return awarded_points

    async def _award_victory_drops(self, broadcaster_id: str, event: RaidBossEvent, config: RaidBossConfig) -> tuple[tuple[str, str], ...]:
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

                for contributor in contributors:
                    recipient_id = str(contributor["user_id"])
                    recipient_name = str(contributor["username"])
                    owned_rows = await connection.fetchall(
                        "SELECT item_id FROM raid_boss_inventory WHERE broadcaster_id = ? AND user_id = ? AND quantity > 0",
                        (str(broadcaster_id), recipient_id)
                    )
                    owned_weapons = {str(row["item_id"]) for row in owned_rows}
                    available_weapons = tuple(weapon for weapon in starter_weapons if weapon not in owned_weapons)

                    if available_weapons:
                        awards.append((recipient_id, recipient_name, random.choice(available_weapons)))
                    else:
                        await self._ensure_player(connection, broadcaster_id, recipient_id, recipient_name)
                        await self._add_points(connection, broadcaster_id, recipient_id, recipient_name, config.tutorial_complete_collection_points)
                        awards.append((recipient_id, recipient_name, f"{config.tutorial_complete_collection_points}_points"))
            else:
                mythical_weapon = next(item_id for item_id, weapon_type in UNIQUE_WEAPON_TYPES.items() if weapon_type == event.boss_type)

                contributor_count = len(contributors)
                top_count = max(1, math.ceil(contributor_count * config.top_contributor_percent)) if contributor_count else 0

                for contributor in contributors[:top_count]:
                    if random.random() < config.top_contributor_unique_drop_chance:
                        awards.append((str(contributor["user_id"]), str(contributor["username"]), mythical_weapon))

            for recipient_id, recipient_name, item_id in awards:
                if item_id.endswith("_points"):
                    bonus_points = int(item_id.removesuffix("_points"))
                    await connection.execute(
                        """
                        INSERT INTO raid_boss_reward_summaries (event_id, broadcaster_id, user_id, username, bonus_points)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(event_id, user_id) DO UPDATE SET bonus_points = bonus_points + excluded.bonus_points, username = excluded.username
                        """,
                        (event.id, str(broadcaster_id), recipient_id, recipient_name, bonus_points)
                    )
                    LOGGER.info("[Raid Bosses] Awarded %s to %s for already owning every starter weapon.", item_id, recipient_name)
                    continue

                await self._ensure_player(connection, broadcaster_id, recipient_id, recipient_name)
                await connection.execute(
                    """
                    INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = 1, durability = MAX(durability, excluded.durability)
                    """,
                    (str(broadcaster_id), recipient_id, item_id, config.weapon_durability)
                )
                await connection.execute(
                    "INSERT OR IGNORE INTO raid_boss_reward_items (event_id, broadcaster_id, user_id, item_id) VALUES (?, ?, ?, ?)",
                    (event.id, str(broadcaster_id), recipient_id, item_id)
                )
                LOGGER.info("[Raid Bosses] Awarded %s to %s for defeating %s.", item_id, recipient_name, event.boss_name)

        return tuple((recipient_name, item_id) for _, recipient_name, item_id in awards)

    async def _get_player(self, broadcaster_id: str, user_id: str):
        async with self.db.acquire() as connection:
            return await connection.fetchone(
                """
                SELECT players.equipped_weapon, players.potion_attacks_remaining,
                       players.second_wind_charges, players.berserk_charges,
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

    async def _add_points(self, connection, broadcaster_id: str, user_id: str, username: str, amount: int) -> None:
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

        if self.chatter_stats is not None:
            await self.chatter_stats.record_points_earned(broadcaster_id, user_id, amount, connection)

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

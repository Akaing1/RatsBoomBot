import asqlite
import pytest

from bot.profiles import RaidBossConfig, RaidBossNames
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService


@pytest.fixture(autouse=True)
def disable_random_critical_hits(monkeypatch):
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 1.0)


def build_config(**overrides) -> RaidBossConfig:
    values = {
        "enabled": True,
        "names": RaidBossNames(melee="Baron Nashor", ranged="Elder Dragon", magic="Atakhan"),
        "max_hp": 1000,
        "reward_pool": 1000,
        "final_hit_reward": 100,
        "base_damage_min": 100,
        "base_damage_max": 100,
        "weapon_cost": 200,
        "potion_cost": 300,
        "tutorial_enabled": False,
        "reward_points_per_hp": 1.0
    }
    values.update(overrides)
    return RaidBossConfig(**values)


def test_default_damage_is_balanced_for_larger_chats() -> None:
    config = RaidBossConfig()

    assert config.max_hp == 150000
    assert config.duration_streams == 5
    assert config.base_damage_min == 390
    assert config.base_damage_max == 430
    assert config.weapon_attack == 40
    assert config.weapon_durability == 15
    assert config.repair_cost == 1500
    assert config.weapon_cost == 25000
    assert config.potion_cost == 10000
    assert config.potion_multiplier == 2.0
    assert config.critical_chance == 0.05
    assert config.critical_multiplier == 1.5


def test_default_mini_boss_balance_is_separate_from_main_bosses() -> None:
    config = RaidBossConfig()

    assert config.mini_hp_min == 20000
    assert config.mini_hp_max == 50000
    assert config.mini_hp_step == 15000
    assert config.mini_duration_streams == 3
    assert config.mini_reward_pool == 25000
    assert config.mini_final_hit_reward == 1000
    assert config.main_boss_chance_after_three_minis == 0.25
    assert config.main_boss_chance_after_four_minis == 0.50
    assert config.main_boss_guaranteed_after_minis == 5


@pytest.mark.asyncio
async def test_automatic_cycle_waits_for_tutorial_completion(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        service = RaidBossService(bot=None, db=database)
        await service.setup()

        event = await service.spawn_automatic("channel-1", build_config())

        assert event is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("consecutive_minis", "roll", "expected_tier", "next_count"), (
    (0, 0.0, "mini", 1),
    (2, 0.0, "mini", 3),
    (3, 0.24, "main", 0),
    (3, 0.25, "mini", 4),
    (4, 0.49, "main", 0),
    (4, 0.50, "mini", 5),
    (5, 1.0, "main", 0)
))
async def test_automatic_cycle_uses_main_boss_pity_chances(tmp_path, monkeypatch, consecutive_minis, roll, expected_tier, next_count) -> None:
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: roll)
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.choice", lambda values: "melee")

    async with asqlite.create_pool(str(tmp_path / f"raid-{consecutive_minis}-{roll}.db")) as database:
        service = RaidBossService(bot=None, db=database)
        await service.setup()
        async with database.acquire() as connection:
            await connection.execute("INSERT INTO raid_boss_channel_state (broadcaster_id, tutorial_completed, consecutive_mini_bosses) VALUES (?, 1, ?)", ("channel-1", consecutive_minis))

        event = await service.spawn_automatic("channel-1", build_config())

        async with database.acquire() as connection:
            state = await connection.fetchone("SELECT consecutive_mini_bosses FROM raid_boss_channel_state WHERE broadcaster_id = ?", ("channel-1",))

        assert event is not None
        assert event.boss_tier == expected_tier
        assert state["consecutive_mini_bosses"] == next_count


def test_common_matching_weapon_supports_three_stream_mini_boss_clear() -> None:
    config = RaidBossConfig()
    minimum_matching_damage = config.base_damage_min + round(config.weapon_attack * config.weapon_multiplier)

    assert minimum_matching_damage * 20 * 3 >= 20000
    assert (config.base_damage_max + round(config.weapon_attack * config.weapon_multiplier)) * 50 * config.duration_streams < config.max_hp


@pytest.mark.asyncio
async def test_critical_hit_adds_fifty_percent_damage(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 0.0)

    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        service = RaidBossService(bot=None, db=database)
        await service.setup()
        config = build_config(max_hp=1000)
        await service.spawn("channel-1", "melee", config)

        result = await service.attack("channel-1", "stream-1", "user-1", "alice", config)

        assert result.damage == 150
        assert result.critical_hit is True


@pytest.mark.asyncio
async def test_mini_boss_uses_tier_specific_name_balance_and_persisted_tier(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.randrange", lambda start, stop, step: 55000)

    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        service = RaidBossService(bot=None, db=database)
        await service.setup()
        config = build_config(
            mini_names=RaidBossNames(melee="Behemoth", ranged="Magitek Gunship", magic="Ahriman"),
            mini_hp_min=35000,
            mini_hp_max=70000,
            mini_duration_streams=3,
            mini_reward_pool=25000,
            mini_final_hit_reward=1000
        )

        event = await service.spawn("channel-1", "melee", config, "mini")

        assert event is not None
        assert event.boss_name == "Behemoth"
        assert event.boss_tier == "mini"
        assert event.max_hp == 55000
        assert event.stream_limit == 3
        assert event.reward_pool == 55000


@pytest.mark.asyncio
async def test_main_boss_remains_the_default_spawn_tier(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        service = RaidBossService(bot=None, db=database)
        await service.setup()
        config = build_config(max_hp=150000, duration_streams=5, reward_pool=100000)

        event = await service.spawn("channel-1", "magic", config)

        assert event is not None
        assert event.boss_name == "Atakhan"
        assert event.boss_tier == "main"
        assert event.max_hp == 150000
        assert event.stream_limit == 5
        assert event.reward_pool == 150000


@pytest.mark.asyncio
async def test_attack_is_limited_once_per_viewer_per_stream(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config()
        await service.spawn("channel-1", "melee", config)

        first = await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        duplicate = await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        next_stream = await service.attack("channel-1", "stream-2", "user-1", "alice", config)

        assert first.damage == 100
        assert duplicate.error == "You already attacked during this stream."
        assert next_stream.damage == 100


@pytest.mark.asyncio
async def test_matching_weapon_and_power_potion_stack(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=5000)
        await points.add_points("channel-1", "user-1", "alice", 1000)
        await service.spawn("channel-1", "melee", config)

        assert await service.buy("channel-1", "user-1", "alice", "sword", config) == "purchased"
        assert await service.equip("channel-1", "user-1", "alice", "sword") is True
        assert await service.buy("channel-1", "user-1", "alice", "potion", config) == "purchased"

        result = await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        weapons, equipped, durability, potion_attacks = await service.get_inventory("channel-1", "user-1")

        async with database.acquire() as connection:
            saved_attack = await connection.fetchone("SELECT weapon, potion_used, critical_hit FROM raid_boss_attacks WHERE user_id = ?", ("user-1",))

        assert result.damage == 360
        assert result.weapon == "sword"
        assert result.potion_used is True
        assert weapons == ["sword"]
        assert equipped == "sword"
        assert durability == config.weapon_durability - 1
        assert potion_attacks == 2
        assert saved_attack["weapon"] == "sword"
        assert saved_attack["potion_used"] == 1
        assert saved_attack["critical_hit"] == 0
        assert await points.get_points("channel-1", "user-1") == 500


@pytest.mark.asyncio
async def test_weapon_durability_disables_bonus_until_repaired(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=5000, weapon_cost=200, weapon_durability=1, repair_cost=150)
        await points.add_points("channel-1", "user-1", "alice", 1000)
        await service.spawn("channel-1", "melee", config)
        await service.buy("channel-1", "user-1", "alice", "sword", config)
        await service.equip("channel-1", "user-1", "alice", "sword")

        armed = await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        broken = await service.attack("channel-1", "stream-2", "user-1", "alice", config)
        repair = await service.repair("channel-1", "user-1", "sword", config)
        repaired = await service.attack("channel-1", "stream-3", "user-1", "alice", config)

        assert armed.damage == 180
        assert armed.weapon == "sword"
        assert broken.damage == 100
        assert broken.weapon is None
        assert broken.broken_weapon == "sword"
        assert repair == "repaired"
        assert repaired.damage == 180
        assert await points.get_points("channel-1", "user-1") == 650


@pytest.mark.asyncio
async def test_dashboard_metrics_summarize_latest_encounter(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 0.0)

    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=5000, weapon_cost=200, potion_cost=300)
        await points.add_points("channel-1", "user-1", "alice", 1000)
        await service.spawn("channel-1", "melee", config, "main")
        await service.register_stream("channel-1", "stream-1")
        await service.buy("channel-1", "user-1", "alice", "sword", config)
        await service.equip("channel-1", "user-1", "alice", "sword")
        await service.buy("channel-1", "user-1", "alice", "potion", config)
        await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        await service.attack("channel-1", "stream-1", "user-2", "bob", config)

        metrics = await service.get_dashboard_metrics("channel-1")

        assert metrics is not None
        assert metrics["boss_name"] == "Baron Nashor"
        assert metrics["boss_tier"] == "main"
        assert metrics["streams_used"] == 1
        assert metrics["unique_attackers"] == 2
        assert metrics["total_attacks"] == 2
        assert metrics["total_damage"] == 690
        assert metrics["average_damage"] == 345.0
        assert metrics["weapon_attacks"] == 1
        assert metrics["potion_attacks"] == 1
        assert metrics["critical_hits"] == 2


@pytest.mark.asyncio
async def test_failed_subjugation_uses_half_or_quarter_reward_pool(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()

        quarter_config = build_config(base_damage_min=100, base_damage_max=100)
        await service.spawn("channel-1", "melee", quarter_config)
        await service.attack("channel-1", "stream-1", "user-1", "alice", quarter_config)
        quarter_pool = await service.resolve("channel-1", defeated=False)

        half_config = build_config(base_damage_min=800, base_damage_max=800)
        await service.spawn("channel-1", "ranged", half_config)
        await service.attack("channel-1", "stream-2", "user-2", "bob", half_config)
        half_pool = await service.resolve("channel-1", defeated=False)

        assert quarter_pool == 250
        assert half_pool == 500
        assert await points.get_points("channel-1", "user-1") == 250
        assert await points.get_points("channel-1", "user-2") == 500


@pytest.mark.asyncio
async def test_final_hit_distributes_full_pool_and_finisher_reward(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=100)
        await service.spawn("channel-1", "magic", config)

        result = await service.attack("channel-1", "stream-1", "user-1", "alice", config)

        assert result.defeated is True
        assert result.reward == 100
        assert await points.get_points("channel-1", "user-1") == 200
        assert await service.get_active_event("channel-1") is None


@pytest.mark.asyncio
async def test_first_encounter_gives_every_participant_a_random_starter_weapon(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(tutorial_enabled=True, tutorial_name="Striking Dummy", tutorial_hp=10000, tutorial_duration_streams=2, base_damage_min=5000, base_damage_max=5000, reward_points_per_hp=0.5)

        event = await service.spawn("channel-1", "melee", config, "tutorial")
        await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        result = await service.attack("channel-1", "stream-1", "user-2", "bob", config)
        alice_weapons, _, _, _ = await service.get_inventory("channel-1", "user-1")
        bob_weapons, _, _, _ = await service.get_inventory("channel-1", "user-2")

        assert event is not None
        assert event.boss_tier == "tutorial"
        assert event.boss_name == "Striking Dummy"
        assert event.max_hp == 10000
        assert event.stream_limit == 2
        assert event.reward_pool == 5000
        assert {username for username, _ in result.drops} == {"alice", "bob"}
        assert len(alice_weapons) == 1
        assert len(bob_weapons) == 1
        assert set(alice_weapons + bob_weapons) <= {"sword", "bow", "spellbook"}
        assert await service.has_completed_tutorial("channel-1") is True
        assert await service.spawn("channel-1", "melee", config, "tutorial") is None


@pytest.mark.asyncio
async def test_previous_pilot_does_not_prevent_manual_tutorial_spawn(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(tutorial_enabled=True)
        await service.spawn("channel-1", "magic", config, "mini")
        await service.resolve("channel-1", defeated=False)

        tutorial = await service.spawn("channel-1", "magic", config, "tutorial")

        assert tutorial is not None
        assert tutorial.boss_tier == "tutorial"
        assert tutorial.max_hp == config.tutorial_hp


@pytest.mark.asyncio
async def test_defeated_boss_can_drop_type_matching_unique_weapon(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=100, final_hit_unique_drop_chance=1.1)
        await service.spawn("channel-1", "magic", config)

        result = await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        weapons, _, _, _ = await service.get_inventory("channel-1", "user-1")

        assert result.drops == (("alice", "mythical_grimoire"),)
        assert weapons == ["mythical_grimoire"]


@pytest.mark.asyncio
async def test_top_contributor_gets_separate_unique_drop_roll(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=200, final_hit_unique_drop_chance=0.0, top_contributor_unique_drop_chance=1.1)
        await service.spawn("channel-1", "ranged", config)
        await service.attack("channel-1", "stream-1", "user-1", "alice", config)

        result = await service.attack("channel-1", "stream-1", "user-2", "bob", config)
        weapons, _, _, _ = await service.get_inventory("channel-1", "user-1")

        assert result.drops == (("alice", "mythical_longbow"),)
        assert weapons == ["mythical_longbow"]


@pytest.mark.asyncio
async def test_top_ten_percent_each_receive_an_independent_unique_drop_roll(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(max_hp=2000, final_hit_unique_drop_chance=0.0, top_contributor_unique_drop_chance=1.1, top_contributor_percent=0.10)
        await service.spawn("channel-1", "melee", config)

        result = None

        for index in range(20):
            result = await service.attack("channel-1", "stream-1", f"user-{index:02d}", f"viewer{index:02d}", config)

        assert result is not None
        assert result.drops == (("viewer00", "mythical_blade"), ("viewer01", "mythical_blade"))


@pytest.mark.asyncio
async def test_boss_expires_after_configured_number_of_unique_streams(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await service.setup()
        config = build_config(duration_streams=2)
        await service.spawn("channel-1", "melee", config)
        await service.attack("channel-1", "stream-1", "user-1", "alice", config)

        first_stream, first_reward = await service.register_stream("channel-1", "stream-1")
        duplicate_stream, duplicate_reward = await service.register_stream("channel-1", "stream-1")
        second_stream, second_reward = await service.register_stream("channel-1", "stream-2")
        expired_event, failed_reward = await service.register_stream("channel-1", "stream-3")

        assert first_stream is not None
        assert first_stream.streams_used == 1
        assert duplicate_stream is not None
        assert duplicate_stream.streams_used == 1
        assert second_stream is not None
        assert second_stream.streams_used == 2
        assert first_reward == duplicate_reward == second_reward == 0
        assert expired_event is None
        assert failed_reward == 250
        assert await points.get_points("channel-1", "user-1") == 250
        assert await service.get_active_event("channel-1") is None

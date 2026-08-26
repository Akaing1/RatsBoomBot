import asqlite
import pytest

from bot.profiles import RaidBossConfig, RaidBossNames
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService


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
        "potion_cost": 300
    }
    values.update(overrides)
    return RaidBossConfig(**values)


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
        weapons, equipped, potion_attacks = await service.get_inventory("channel-1", "user-1")

        assert result.damage == 1000
        assert result.weapon == "sword"
        assert result.potion_used is True
        assert weapons == ["sword"]
        assert equipped == "sword"
        assert potion_attacks == 2
        assert await points.get_points("channel-1", "user-1") == 500


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
        assert result.reward == 1000
        assert await points.get_points("channel-1", "user-1") == 1100
        assert await service.get_active_event("channel-1") is None


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

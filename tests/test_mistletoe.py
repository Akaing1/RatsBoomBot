import pytest

from rpg_minigame.mistletoe import FinaleReward, Hit, apply_hit, finale_reward


def test_crossings_and_overkill():
    assert apply_hit(800_001, 1) == Hit(800_000, 1, 10_000)
    assert apply_hit(800_000, 1) == Hit(799_999, 1, 0)
    assert apply_hit(201_000, 300_000) == Hit(0, 201_000, 20_000)
    with pytest.raises(ValueError):
        apply_hit(0, 1)


@pytest.mark.parametrize(("hp", "rank", "expected"), [
    (1_000_000, 1, FinaleReward(0, 2, 0, 0)),
    (1, 1, FinaleReward(80_000, 2, 0, 0)),
    (0, 10, FinaleReward(120_000, 3, 1, 0.05)),
    (0, 11, FinaleReward(100_000, 2, 1, 0)),
])
def test_finale(hp, rank, expected):
    assert finale_reward(hp, rank) == expected


@pytest.mark.asyncio
async def test_first_contribution_unlocks_one_global_badge(tmp_path):
    import asqlite
    from bot.services.channels.achievements import AchievementService
    from storage.migration_runner import run_migrations

    async with asqlite.create_pool(str(tmp_path / "christmas.db")) as db:
        await run_migrations(db)
        async with db.acquire() as connection:
            for channel in ("first", "second"):
                await connection.execute("INSERT INTO mistletoe_2026_contributions VALUES (?, 'viewer', 1)", (channel,))
            rows = await connection.fetchall("SELECT * FROM achievement_unlocks WHERE achievement_id='gift_inspector_2026'")
            assert len(rows) == 1 and rows[0]["broadcaster_id"] == ""
        collection = await AchievementService(db).get_collection("viewer", lambda channel: None)
        card = next(card for card in collection["cards"] if card["title"] == "Gift Inspector 2026")
        assert (card["scope"], card["category"], card["percent"]) == ("global", "raids", 100)

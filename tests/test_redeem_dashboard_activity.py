import asqlite
import pytest

from bot.profiles import RedeemConfig
from bot.services.redeem_service import RedeemService


@pytest.mark.asyncio
async def test_dashboard_activity_separates_checkins_and_other_redeems(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "redeem-activity.db"

    async with asqlite.create_pool(str(database_path)) as database:
        service = RedeemService(bot=None, db=database, points_service=None)
        await service.setup()

        monkeypatch.setattr(
            service,
            "get_redeem_config",
            lambda broadcaster_id: RedeemConfig(
                daily_title="Daily Check-in",
                first_title="FIRST"
            )
        )

        async with database.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO redeem_claims (
                    broadcaster_id,
                    user_id,
                    username,
                    redeem_type,
                    stream_id,
                    redemption_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("channel-1", "user-1", "alice", "daily", "stream-1", "daily-1")
            )

        await service.record_activity(
            redemption_id="daily-1",
            broadcaster_id="channel-1",
            user_id="user-1",
            username="alice",
            reward_title="Daily Check-in",
            user_input=None,
            stream_id="stream-1"
        )
        await service.record_activity(
            redemption_id="other-1",
            broadcaster_id="channel-1",
            user_id="user-2",
            username="bob",
            reward_title="Choose a Game",
            user_input="Outer Wilds",
            stream_id="stream-1"
        )

        activity = await service.get_dashboard_activity(
            broadcaster_id="channel-1",
            stream_id="stream-1"
        )

    assert activity["stream_id"] == "stream-1"
    assert activity["checkins"] == [
        {
            "username": "alice",
            "type": "daily",
            "redeemed_at": activity["checkins"][0]["redeemed_at"]
        }
    ]
    assert activity["redemptions"] == [
        {
            "id": "other-1",
            "username": "bob",
            "reward_title": "Choose a Game",
            "user_input": "Outer Wilds",
            "redeemed_at": activity["redemptions"][0]["redeemed_at"]
        }
    ]


@pytest.mark.asyncio
async def test_duplicate_redemption_activity_is_ignored(tmp_path) -> None:
    database_path = tmp_path / "redeem-activity.db"

    async with asqlite.create_pool(str(database_path)) as database:
        service = RedeemService(bot=None, db=database, points_service=None)
        await service.setup()

        values = {
            "redemption_id": "redeem-1",
            "broadcaster_id": "channel-1",
            "user_id": "user-1",
            "username": "alice",
            "reward_title": "Hydrate",
            "user_input": None,
            "stream_id": "stream-1"
        }

        first_inserted = await service.record_activity(**values)
        second_inserted = await service.record_activity(**values)

        async with database.acquire() as connection:
            row = await connection.fetchone(
                "SELECT COUNT(*) AS count FROM redemption_events WHERE redemption_id = ?",
                ("redeem-1",)
            )

    assert first_inserted is True
    assert second_inserted is False
    assert row["count"] == 1

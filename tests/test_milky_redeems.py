from types import SimpleNamespace

import asqlite
import pytest

from bot.channels.milky_galaxyvt.profile_details import MILKY_GALAXYVT_REDEEMS
from bot.services.engagement.counter import CounterService
from bot.services.engagement.redeems import RedeemService
from storage.migration_runner import run_migrations


class FakePointsService:

    def __init__(self):
        self.awards = []

    async def add_points(self, **values) -> None:
        self.awards.append(values)


class FakeBroadcaster:

    def __init__(self):
        self.timeouts = []

    async def timeout_user(self, **values) -> None:
        self.timeouts.append(values)


class FakeBot:

    def __init__(self):
        self.broadcaster = FakeBroadcaster()

    def create_partialuser(self, broadcaster_id: str):
        return self.broadcaster


@pytest.mark.asyncio
async def test_milky_first_and_second_redeems_keep_separate_counts(tmp_path) -> None:
    database_path = tmp_path / "milky-redeems.db"
    bot = FakeBot()
    points = FakePointsService()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)
        service = RedeemService(bot=bot, db=database, points_service=points)
        await service.setup()
        service.get_redeem_config = lambda broadcaster_id: MILKY_GALAXYVT_REDEEMS

        first_one = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="First", stream_id="stream-1")
        first_two = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="First", stream_id="stream-2")
        second_one = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="Second", stream_id="stream-1")
        duplicate_second = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-2", username="bob", reward_title="Second", stream_id="stream-1")

    assert first_one.message == "Welcome in @alice, you have been first 1 times!"
    assert first_two.message == "Welcome in @alice, you have been first 2 times!"
    assert second_one.message == "Welcome in @alice, you have been second 1 times!"
    assert duplicate_second.message == "@bob, Second was already claimed by @alice this stream."


@pytest.mark.asyncio
async def test_milky_timeout_redeem_times_out_the_redeemer(tmp_path) -> None:
    database_path = tmp_path / "milky-timeout.db"
    bot = FakeBot()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)
        service = RedeemService(bot=bot, db=database, points_service=FakePointsService())
        await service.setup()
        service.get_redeem_config = lambda broadcaster_id: MILKY_GALAXYVT_REDEEMS
        result = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="3 Minute Timeout", stream_id="stream-1")

    assert bot.broadcaster.timeouts == [{
        "moderator": "channel-1",
        "user": "user-1",
        "duration": 180,
        "reason": "Redeemed 3 Minute Timeout."
    }]
    assert result.message == "@alice has timed themselves out for 3 minutes!"


@pytest.mark.asyncio
async def test_milky_slime_mason_redeem_times_out_configured_target(tmp_path) -> None:
    database_path = tmp_path / "milky-target-timeout.db"
    bot = FakeBot()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)
        counters = CounterService(bot=bot, db=database)
        await counters.setup()
        service = RedeemService(bot=bot, db=database, points_service=FakePointsService(), counter_service=counters)
        await service.setup()
        service.get_redeem_config = lambda broadcaster_id: MILKY_GALAXYVT_REDEEMS
        first_result = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="Slime Mason", stream_id="stream-1")
        second_result = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-2", username="bob", reward_title="Slime Mason", stream_id="stream-1")

    assert bot.broadcaster.timeouts == [{
        "moderator": "channel-1",
        "user": "208244235",
        "duration": 86400,
        "reason": "You've been slimed out."
    }, {
        "moderator": "channel-1",
        "user": "208244235",
        "duration": 86400,
        "reason": "You've been slimed out."
    }]
    assert first_result.message == "@unfitend has been slimed out for 24 hours! Mason has been slimed out 1 time!"
    assert second_result.message == "@unfitend has been slimed out for 24 hours! Mason has been slimed out 2 times!"

import asyncio
from types import SimpleNamespace

import asqlite
import pytest

from bot.channels.milky_galaxyvt.profile_details import MILKY_GALAXYVT_REDEEMS
from bot.profiles import RedeemConfig
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
        self.moderator_ids = set()
        self.added_moderators = []
        self.vip_ids = set()
        self.added_vips = []

    async def timeout_user(self, **values) -> None:
        self.timeouts.append(values)

    async def fetch_moderators(self, user_ids, max_results):
        for user_id in user_ids:
            if str(user_id) in self.moderator_ids:
                yield SimpleNamespace(id=str(user_id))

    async def add_moderator(self, *, user) -> None:
        self.added_moderators.append(str(user))

    async def fetch_vips(self, user_ids, max_results):
        for user_id in user_ids:
            if str(user_id) in self.vip_ids:
                yield SimpleNamespace(id=str(user_id))

    async def add_vip(self, *, user) -> None:
        self.vip_ids.add(str(user))
        self.added_vips.append(str(user))


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
async def test_milky_timeout_redeem_times_out_and_restores_moderator(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "milky-timeout.db"
    bot = FakeBot()
    bot.broadcaster.moderator_ids.add("user-1")

    async def skip_sleep(delay_seconds: int) -> None:
        return None

    monkeypatch.setattr("bot.services.engagement.redeems.asyncio.sleep", skip_sleep)

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)
        service = RedeemService(bot=bot, db=database, points_service=FakePointsService())
        await service.setup()
        service.get_redeem_config = lambda broadcaster_id: MILKY_GALAXYVT_REDEEMS
        result = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="3 Minute Timeout", stream_id="stream-1")
        restore_tasks = tuple(service._moderator_restore_tasks)
        await asyncio.gather(*restore_tasks)

    assert bot.broadcaster.timeouts == [{
        "moderator": "channel-1",
        "user": "user-1",
        "duration": 180,
        "reason": "Redeemed 3 Minute Timeout."
    }]
    assert result.message == "@alice has timed themselves out for 3 minutes!"
    assert bot.broadcaster.added_moderators == ["user-1"]


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


@pytest.mark.asyncio
async def test_vip_redeem_grants_permanent_vip_once(tmp_path) -> None:
    database_path = tmp_path / "vip-redeem.db"
    bot = FakeBot()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)
        service = RedeemService(bot=bot, db=database, points_service=FakePointsService())
        await service.setup()
        service.get_redeem_config = lambda broadcaster_id: RedeemConfig(vip_title="VIP")

        granted = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="VIP", stream_id="stream-1")
        duplicate = await service.handle_redemption(broadcaster_id="channel-1", user_id="user-1", username="alice", reward_title="VIP", stream_id="stream-1")

    assert bot.broadcaster.added_vips == ["user-1"]
    assert granted.message == "@alice is now a VIP! Welcome to the very important rat club!"
    assert duplicate.message == "@alice, you are already a VIP in this channel."

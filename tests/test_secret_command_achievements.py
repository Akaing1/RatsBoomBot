import asqlite
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.profiles import ChannelAchievementNames
from bot.services.channels.achievements import AchievementService
from bot.services.engagement.points import PointsService
from bot.shared.commands.utility import UtilityCommands
from bot.shared.commands.points import PointsCommandHandler
from bot.profiles import PointsConfig
from storage.migrations import MIGRATIONS
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_roll_credits_measured_user_once_and_no_backfill(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "rolls.db")) as db:
        async with db.acquire() as connection:
            for migration in MIGRATIONS[:33]:
                await migration.run(connection)
            await connection.execute("INSERT INTO viewers (broadcaster_id,user_id,username,points,messages) VALUES ('channel','measured','measured',100,0)")
            for migration in MIGRATIONS[33:]:
                await migration.run(connection)
            assert not await connection.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='shower'")

        service = AchievementService(db)
        await service.record_command_roll("channel", "normal-roll", "stinky", "measured", 45)
        await service.record_command_roll("channel", "message-1", "stinky", "measured", 100)
        await service.record_command_roll("channel", "message-1", "stinky", "measured", 100)
        await service.record_command_roll("channel", "message-2", "stinky", "measured", 100)
        await service.record_command_roll("channel", "message-3", "smart", "measured", 100)
        await service.record_command_roll("channel", "message-4", "height", "measured", 12)

        async with db.acquire() as connection:
            balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel' AND user_id='measured'")
            rewards = await connection.fetchone("SELECT COUNT(*) AS total FROM channel_achievement_rewards WHERE broadcaster_id='channel' AND user_id='measured'")
            assert balance["points"] == 75100
            assert rewards["total"] == 3
            assert not await connection.fetchone("SELECT 1 FROM command_achievement_rolls WHERE message_id='normal-roll'")
            assert not await connection.fetchone("SELECT 1 FROM achievement_unlocks WHERE broadcaster_id='' AND achievement_id='shower'")
        channel = await service.get_channel_collection('measured','channel',ChannelAchievementNames(),lambda _: {'display_name':'Channel'},'bread')
        assert any(card['title'] == 'You Need a Shower' and card['tier'] == 'Platinum' for card in channel['cards'])
        assert 'Squeaky Clean' not in str(channel)


@pytest.mark.asyncio
async def test_stream_roll_is_limited_per_viewer_command_and_stream(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "stream-rolls.db")) as db:
        await run_migrations(db)
        service = AchievementService(db)

        assert await service.record_stream_command_roll("channel", "stream-1", "message-1", "stinky", "viewer", 45) is True
        assert await service.record_stream_command_roll("channel", "stream-1", "message-2", "stinky", "viewer", 100) is False
        assert await service.record_stream_command_roll("channel", "stream-1", "message-3", "smart", "viewer", 50) is True
        assert await service.record_stream_command_roll("channel", "stream-1", "message-4", "stinky", "other", 50) is True
        assert await service.record_stream_command_roll("channel", "stream-2", "message-5", "stinky", "viewer", 100) is True

        async with db.acquire() as connection:
            rolls = await connection.fetchall("SELECT stream_id,command,user_id,value FROM command_stream_rolls ORDER BY message_id")
            achievement_rolls = await connection.fetchall("SELECT message_id FROM command_achievement_rolls ORDER BY message_id")

        assert len(rolls) == 4
        assert [row["message_id"] for row in achievement_rolls] == ["message-3", "message-4", "message-5"]


@pytest.mark.asyncio
async def test_offline_measurement_responds_normally_without_achievement_tracking(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "offline-roll.db")) as db:
        await run_migrations(db)
        stream_logs = SimpleNamespace(get_active_session=lambda broadcaster_id: None)
        bot = SimpleNamespace(services=SimpleNamespace(achievements=AchievementService(db),stream_logs=stream_logs))
        commands = UtilityCommands(bot)
        monkeypatch.setattr(commands, "command_enabled", lambda ctx, name: True)
        monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: 100)
        replies = []

        async def reply(message):
            replies.append(message)

        ctx = SimpleNamespace(
            broadcaster=SimpleNamespace(id="channel"),
            chatter=SimpleNamespace(id="viewer",name="viewer"),
            payload=SimpleNamespace(id="offline-message"),reply=reply
        )
        await commands.lucky.callback(commands,ctx)

        assert len(replies) == 1 and "100% lucky" in replies[0]

        async with db.acquire() as connection:
            assert not await connection.fetchone("SELECT 1 FROM command_stream_rolls")


@pytest.mark.asyncio
async def test_failed_kamikaze_unlocks_global_and_channel_without_double_payment(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "misses.db")) as db:
        await run_migrations(db)
        service = AchievementService(db)
        await service.record_kamikaze_failure('a','message-1','user')
        await service.record_kamikaze_failure('a','message-1','user')
        await service.record_kamikaze_failure('b','message-2','user')
        async with db.acquire() as connection:
            rows = await connection.fetchall("SELECT broadcaster_id,achievement_id FROM achievement_unlocks WHERE user_id='user' AND achievement_id LIKE 'nice_try%' ORDER BY broadcaster_id")
            rewards = await connection.fetchall("SELECT broadcaster_id,points FROM channel_achievement_rewards WHERE user_id='user' AND achievement_id='nice_try'")
        assert {(row['broadcaster_id'],row['achievement_id']) for row in rows} == {('', 'nice_try_global'), ('a','nice_try'), ('b','nice_try')}
        assert len(rewards) == 2 and all(row['points'] == 500 for row in rewards)


@pytest.mark.asyncio
async def test_ten_settled_gamble_losses_save_origin_and_pay_channel_once(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "gamble-streak.db")) as db:
        await run_migrations(db)
        points = PointsService(None,db)
        await points.add_points('a','user','user',100000,earned=False)
        for _ in range(10):
            assert await points.settle_wager('a','user','user',1,0,game='gamble',channel_name='MeinyaYozakura') is not None
        global_cards = await AchievementService(db).get_collection('user',lambda channel: {'display_name':channel})
        card = next(card for card in global_cards['cards'] if card['title']=="Can't End on a Loss")
        assert 'MeinyaYozakura' in card['description']
        assert card['tier']=='Platinum' and card['steps'][0]['reward'] is None
        assert await points.get_points('a','user') == 124990

        # Roulette and an insufficient bet must not move the !gamble streak.
        await points.settle_wager('a','user','user',1,0)
        assert await points.settle_wager('a','user','user',9999999,0,game='gamble') is None
        await points.settle_wager('a','user','user',1,0,game='gamble',channel_name='MeinyaYozakura')
        await points.add_points('b','user','user',100000,earned=False)
        for _ in range(10):
            await points.settle_wager('b','user','user',1,0,game='gamble',channel_name='Milky_GalaxyVT')
        async with db.acquire() as connection:
            rewards = await connection.fetchall("SELECT broadcaster_id,points FROM channel_achievement_rewards WHERE user_id='user' AND achievement_id='loss_streak'")
            global_unlocks = await connection.fetchall("SELECT * FROM achievement_unlocks WHERE user_id='user' AND achievement_id='loss_streak_global'")
        assert len(rewards)==2 and len(global_unlocks)==1
        assert await points.get_points('a','user')==124988
        assert await points.get_points('b','user')==124990


@pytest.mark.asyncio
async def test_win_streak_requires_ten_consecutive_wins(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "wins.db")) as db:
        await run_migrations(db)
        points = PointsService(None,db)
        await points.add_points('channel','user','user',100,earned=False)
        for _ in range(9):
            await points.settle_wager('channel','user','user',1,2,game='gamble',channel_name='Rat')
        await points.settle_wager('channel','user','user',1,0,game='gamble',channel_name='Rat')
        for _ in range(10):
            await points.settle_wager('channel','user','user',1,2,game='gamble',channel_name='Rat')
        async with db.acquire() as connection:
            unlock = await connection.fetchone("SELECT 1 FROM achievement_unlocks WHERE user_id='user' AND achievement_id='win_streak_global'")
            reward = await connection.fetchone("SELECT points FROM channel_achievement_rewards WHERE user_id='user' AND achievement_id='win_streak'")
        assert unlock is not None and reward['points']==25000


@pytest.mark.asyncio
async def test_measurement_command_awards_target_not_caller(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "measured.db")) as db:
        await run_migrations(db)
        stream_logs = SimpleNamespace(get_active_session=lambda broadcaster_id: SimpleNamespace(stream_id="stream-1"))
        bot = SimpleNamespace(services=SimpleNamespace(achievements=AchievementService(db),stream_logs=stream_logs))
        commands = UtilityCommands(bot)
        monkeypatch.setattr(commands, "command_enabled", lambda ctx, name: True)
        monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: 12)
        replies = []

        async def reply(message):
            replies.append(message)

        ctx = SimpleNamespace(
            broadcaster=SimpleNamespace(id="channel"),
            chatter=SimpleNamespace(id="caller",name="caller"),
            payload=SimpleNamespace(id="height-message"),reply=reply
        )
        target = SimpleNamespace(id="measured",name="measured")
        await commands.height.callback(commands,ctx,target)
        ctx.payload.id = "second-height-message"
        await commands.height.callback(commands,ctx,target)
        assert len(replies) == 2 and all("measured" in message for message in replies)
        async with db.acquire() as connection:
            unlock = await connection.fetchone("SELECT user_id FROM achievement_unlocks WHERE broadcaster_id='channel' AND achievement_id='tiny'")
            paid = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel' AND user_id='measured'")
            caller = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel' AND user_id='caller'")
            rolls = await connection.fetchone("SELECT COUNT(*) AS total FROM command_stream_rolls WHERE user_id='measured' AND command='height'")
            achievement_rolls = await connection.fetchone("SELECT COUNT(*) AS total FROM command_achievement_rolls WHERE user_id='measured' AND command='height'")
        assert unlock['user_id']=='measured' and paid['points']==25000 and caller is None and rolls['total']==1 and achievement_rolls['total']==1


@pytest.mark.asyncio
async def test_gamble_loss_reply_uses_balance_including_achievement_reward(monkeypatch):
    points = SimpleNamespace(get_points=AsyncMock(return_value=100),settle_wager=AsyncMock(return_value=25090))
    handler = PointsCommandHandler(SimpleNamespace(services=SimpleNamespace(points=points)))
    monkeypatch.setattr(handler,"get_context",AsyncMock(return_value=('channel',PointsConfig())))
    monkeypatch.setattr(handler,"send_message",AsyncMock())
    monkeypatch.setattr('bot.shared.commands.points.random.random',lambda: 1.0)
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='channel',login='rat'),chatter=SimpleNamespace(id='user',name='viewer'))
    await handler.gamble(ctx,'10','points')
    assert handler.send_message.await_args.kwargs['new_balance']==25090
    assert points.settle_wager.await_args.kwargs['game']=='gamble'

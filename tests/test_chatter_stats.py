from types import SimpleNamespace

import asqlite
import pytest

from bot.services.channels.chatter_stats import ChatterStatsService
from bot.services.engagement.points import PointsService
from bot.shared.commands.stats import StatsCommands
from storage.migrations import MIGRATIONS
from storage.migration_runner import run_migrations
from web.shared.common import templates


class FakeBroadcasters:

    def __init__(self):
        self.items = {
            "channel-1": SimpleNamespace(id="channel-1", login="testchannel", display_name="TestChannel", profile_image_url="https://example.com/channel.png")
        }

    def get_broadcasters(self):
        return self.items


class FakeChatIdentity:

    @staticmethod
    def is_custom_bot(user_id: str) -> bool:
        return False


async def seed_identity(database) -> None:
    async with database.acquire() as connection:
        await connection.execute("INSERT INTO chatter_identities (user_id, login, display_name) VALUES ('user-1', 'alice', 'Alice')")
        await connection.execute("INSERT INTO chatter_channel_observations (broadcaster_id, user_id) VALUES ('channel-1', 'user-1')")


@pytest.mark.asyncio
async def test_chatter_profile_migration_seeds_existing_activity(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "upgrade.db")) as database:
        async with database.acquire() as connection:
            for migration in MIGRATIONS[:12]:
                await migration.run(connection)

            await connection.execute("INSERT INTO chatter_identities (user_id, login, display_name) VALUES ('user-1', 'alice', 'Alice')")
            await connection.execute("INSERT INTO chatter_channel_observations (broadcaster_id, user_id) VALUES ('channel-1', 'user-1')")
            await connection.execute("INSERT INTO viewers (broadcaster_id, user_id, username, points, messages) VALUES ('channel-1', 'user-1', 'alice', 725, 18)")
            await MIGRATIONS[12].run(connection)
            row = await connection.fetchone("SELECT messages_sent, lifetime_points_earned FROM chatter_channel_stats WHERE broadcaster_id = 'channel-1' AND user_id = 'user-1'")

        assert int(row["messages_sent"]) == 18
        assert int(row["lifetime_points_earned"]) == 725


@pytest.mark.asyncio
async def test_chatter_stats_count_every_message_and_only_bot_earned_points(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "stats.db")) as database:
        await run_migrations(database)
        await seed_identity(database)
        bot = SimpleNamespace(bot_id="main-bot")
        service = ChatterStatsService(bot, database, FakeBroadcasters())
        bot.services = SimpleNamespace(chat_identity=FakeChatIdentity())
        payload = SimpleNamespace(broadcaster=SimpleNamespace(id="channel-1"), chatter=SimpleNamespace(id="user-1", name="alice"))

        await service.track_message(payload)
        await service.track_message(payload)

        points = PointsService(bot=None, db=database, chatter_stats=service)
        await points.add_points("channel-1", "user-1", "alice", 100)
        await points.add_points("channel-1", "user-1", "alice", 50, earned=False)

        async with database.acquire() as connection:
            row = await connection.fetchone("SELECT messages_sent, lifetime_points_earned FROM chatter_channel_stats WHERE broadcaster_id = 'channel-1' AND user_id = 'user-1'")

        assert int(row["messages_sent"]) == 2
        assert int(row["lifetime_points_earned"]) == 100


@pytest.mark.asyncio
async def test_chatter_profiles_aggregate_global_and_channel_activity(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "stats.db")) as database:
        await run_migrations(database)
        await seed_identity(database)

        async with database.acquire() as connection:
            await connection.execute("INSERT INTO chatter_channel_stats (broadcaster_id, user_id, messages_sent, lifetime_points_earned) VALUES ('channel-1', 'user-1', 42, 900)")
            await connection.execute("INSERT INTO viewers (broadcaster_id, user_id, username, points, messages) VALUES ('channel-1', 'user-1', 'alice', 350, 20)")
            await connection.execute("INSERT INTO redeem_claims (broadcaster_id, user_id, username, redeem_type, stream_id) VALUES ('channel-1', 'user-1', 'alice', 'daily', 'stream-1')")
            await connection.execute("INSERT INTO imported_redeem_totals (broadcaster_id, user_id, username, redeem_type, claim_count) VALUES ('channel-1', 'user-1', 'alice', 'daily', 3)")
            await connection.execute("INSERT INTO imported_redeem_totals (broadcaster_id, user_id, username, redeem_type, claim_count) VALUES ('channel-1', 'user-1', 'alice', 'first', 2)")
            await connection.execute("INSERT INTO raid_boss_events (id, broadcaster_id, boss_name, boss_type, boss_tier, max_hp, current_hp, reward_pool, final_hit_reward, status, spawned_at, stream_limit, final_hitter_id, final_hitter_name) VALUES (1, 'channel-1', 'Test Boss', 'melee', 'main', 1000, 0, 500, 100, 'defeated', '2026-09-01T00:00:00+00:00', 3, 'user-1', 'alice')")
            await connection.execute("INSERT INTO raid_boss_attacks (event_id, broadcaster_id, stream_id, user_id, username, damage, attacked_at) VALUES (1, 'channel-1', 'stream-1', 'user-1', 'alice', 275, '2026-09-01T00:01:00+00:00')")
            await connection.execute("INSERT INTO raid_boss_players (broadcaster_id, user_id, username, equipped_weapon) VALUES ('channel-1', 'user-1', 'alice', 'sword')")
            await connection.execute("INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability) VALUES ('channel-1', 'user-1', 'sword', 1, 12)")
            await connection.execute("INSERT INTO raid_boss_reward_summaries (event_id, broadcaster_id, user_id, username, contribution_points, final_hit_points) VALUES (1, 'channel-1', 'user-1', 'alice', 140, 100)")

        service = ChatterStatsService(SimpleNamespace(bot_id="main-bot"), database, FakeBroadcasters())
        global_profile = await service.get_global_profile("alice")
        channel_profile = await service.get_channel_profile("alice", "testchannel")

        assert global_profile["messages_sent"] == 42
        assert global_profile["damage_dealt"] == 275
        assert global_profile["highest_contribution"] == 275
        assert global_profile["bosses_defeated"] == 1
        assert global_profile["daily_check_ins"] == 4
        assert global_profile["favorite_channel"]["display_name"] == "TestChannel"
        assert global_profile["raid_reward_points"] == 240
        assert global_profile["top_contributor_finishes"] == 1
        assert global_profile["recent_raids"][0]["boss_name"] == "Test Boss"
        assert global_profile["recent_raids"][0]["top_contributor"] is True
        assert channel_profile["current_points"] == 350
        assert channel_profile["daily_check_ins"] == 4
        assert channel_profile["firsts"] == 2
        assert channel_profile["raid_reward_points"] == 240
        assert channel_profile["top_contributor_finishes"] == 1
        assert channel_profile["recent_raids"][0]["reward_points"] == 240
        assert channel_profile["inventory"][0]["equipped"] == 1


@pytest.mark.asyncio
async def test_stats_command_links_to_public_profile(monkeypatch) -> None:
    replies = []
    identity = {"login": "alice", "display_name": "Alice"}
    services = SimpleNamespace(
        features=SimpleNamespace(is_global_command_enabled=lambda broadcaster_id, command: True),
        chatter_stats=SimpleNamespace(resolve_identity=lambda value: None)
    )

    async def resolve_identity(value: str):
        return identity

    services.chatter_stats.resolve_identity = resolve_identity
    bot = SimpleNamespace(services=services)
    context = SimpleNamespace(chatter=SimpleNamespace(id="user-1", name="alice"), broadcaster=SimpleNamespace(id="channel-1"), reply=lambda message: None)

    async def reply(message: str) -> None:
        replies.append(message)

    context.reply = reply
    monkeypatch.setattr("bot.shared.commands.stats.settings.PUBLIC_BASE_URL", "https://ratsboombot.com")
    component = StatsCommands(bot)

    await component.stats.callback(component, context, "")

    assert replies == ["View Alice's RatsBoomBot profile: https://ratsboombot.com/chatters/alice"]


def test_chatter_profile_templates_compile() -> None:
    for template_name in ("public/chatter_profile.html", "public/chatter_channel_profile.html", "public/chatter_not_found.html"):
        assert templates.env.get_template(template_name) is not None

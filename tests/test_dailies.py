from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.command_registry import CommandSlowmode, UTILITY_COMMANDS
from bot.profiles import GlobalCommandName
from bot.services.channels.achievements import AchievementService
from bot.shared.commands.utility import UtilityCommands
from storage.migration_runner import run_migrations


def make_command(achievements=None, *, live=True, disabled=()):
    services = SimpleNamespace(
        features=SimpleNamespace(is_global_command_enabled=lambda channel, command: command.value not in disabled),
        achievements=achievements,
        stream_logs=SimpleNamespace(get_active_session=lambda channel: SimpleNamespace(stream_id="stream-1") if live else None),
    )
    ctx = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel"),
        chatter=SimpleNamespace(id="caller", name="caller"),
        payload=SimpleNamespace(id="message-1"), reply=AsyncMock(),
    )
    return UtilityCommands(SimpleNamespace(services=services)), ctx


@pytest.mark.asyncio
@pytest.mark.parametrize("targeted", [False, True])
async def test_dailies_records_all_rolls_and_shares_individual_limits(tmp_path, monkeypatch, targeted):
    async with asqlite.create_pool(str(tmp_path / "dailies.db")) as db:
        await run_migrations(db)
        component, ctx = make_command(AchievementService(db))
        target = SimpleNamespace(id="target", name="target") if targeted else None
        user_id = "target" if targeted else "caller"
        # The first individual stinky attempt must remain authoritative.
        await component.bot.services.achievements.record_stream_command_roll(
            "channel", "stream-1", "earlier", "stinky", user_id, 45)
        values = iter((100, 100, 100, 12))
        monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: next(values))
        await component.dailies.callback(component, ctx, target)
        ctx.reply.assert_awaited_once()
        message = ctx.reply.await_args.args[0]
        assert all(text in message for text in ("stinky: 100%", "lucky: 100%", "smart: 100%", 'height: 1\' 0"'))
        # A later individual roll and another combined invocation cannot add attempts.
        ctx.payload.id = "message-2"
        monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: high)
        await component.height.callback(component, ctx, target)
        ctx.payload.id = "message-3"
        await component.dailies.callback(component, ctx, target)
        async with db.acquire() as connection:
            rows = await connection.fetchall("SELECT command,user_id,value FROM command_stream_rolls ORDER BY command")
            unlock = await connection.fetchone("SELECT user_id FROM achievement_unlocks WHERE broadcaster_id='channel' AND achievement_id='tiny'")
            shower = await connection.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='shower'")
        assert {row["command"]: row["value"] for row in rows} == {"stinky": 45, "lucky": 100, "smart": 100, "height": 12}
        assert {row["user_id"] for row in rows} == {user_id}
        assert unlock["user_id"] == user_id
        assert shower is None


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [("dailies",), ("smart", "height"), ("stinky", "lucky", "smart", "height")])
async def test_dailies_honors_command_toggles(monkeypatch, disabled):
    achievements = SimpleNamespace(record_stream_command_roll=AsyncMock())
    component, ctx = make_command(achievements, disabled=disabled)
    monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: low)
    await component.dailies.callback(component, ctx)
    recorded = {call.args[3] for call in achievements.record_stream_command_roll.await_args_list}
    if "dailies" in disabled:
        assert recorded == set()
        ctx.reply.assert_not_awaited()
    else:
        assert recorded == {"stinky", "lucky", "smart", "height"} - set(disabled)
        ctx.reply.assert_awaited_once()
        if not recorded:
            assert ctx.reply.await_args.args[0] == "No achievement roll commands are enabled in this channel."
        else:
            assert "smart" not in ctx.reply.await_args.args[0]
            assert "height" not in ctx.reply.await_args.args[0]


@pytest.mark.asyncio
async def test_offline_dailies_replies_without_recording(monkeypatch):
    achievements = SimpleNamespace(record_stream_command_roll=AsyncMock())
    component, ctx = make_command(achievements, live=False)
    monkeypatch.setattr("bot.shared.commands.utility.random.randint", lambda low, high: high)
    await component.dailies.callback(component, ctx)
    ctx.reply.assert_awaited_once()
    achievements.record_stream_command_roll.assert_not_awaited()


def test_dailies_registration_help_and_shared_slowmode():
    entry = next(command for command in UTILITY_COMMANDS.commands if command.name == "dailies")
    assert entry.global_command is GlobalCommandName.DAILIES
    assert entry.slowmode is CommandSlowmode.SHARED
    assert UtilityCommands.dailies.name == "dailies"

    assert UtilityCommands.dailies.aliases == ["rollall"]
    assert entry.aliases == ("rollall",)

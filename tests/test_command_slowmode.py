from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.bot import TwitchBot
from bot.services.channels.command_slowmode import CommandSlowmodeService, SlowmodeBlocked
from bot.shared.commands.settings import SettingsCommands
from storage.migration_runner import run_migrations


def context(command="gamble", user="viewer", channel="channel", moderator=False):
    return SimpleNamespace(command=SimpleNamespace(name=command), chatter=SimpleNamespace(id=user, name=user, moderator=moderator), broadcaster=SimpleNamespace(id=channel), reply=AsyncMock())


def test_shared_cooldown_and_exemptions(monkeypatch):
    clock = [1000]
    monkeypatch.setattr("bot.services.channels.command_slowmode.time.monotonic", lambda: clock[0])
    service = CommandSlowmodeService(None)
    service.enabled_channels.update({"channel", "other"})
    first = context()
    assert service.allow(first)
    assert service.allow(first)  # Group and subcommand guards share an invocation.
    assert not service.allow(context("smart"))
    assert service.allow(context(user="another"))
    assert service.allow(context(channel="other"))
    assert service.allow(context(moderator=True))
    assert service.allow(context(user="channel"))
    assert service.allow(context("kamikaze"))
    clock[0] = 1119
    assert not service.allow(context("raid"))
    clock[0] = 1120
    assert service.allow(context("smart"))


@pytest.mark.asyncio
async def test_toggle_persistence_and_permissions(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "slowmode.db")) as db:
        await run_migrations(db)
        service = CommandSlowmodeService(db)
        await service.setup()
        assert service.allow(context())
        command = SettingsCommands(SimpleNamespace(services=SimpleNamespace(command_slowmode=service)))
        monkeypatch.setattr(command, "get_context", lambda *args: "channel")
        await command.set_slowmode.callback(command, context(), status="on")
        assert not service.enabled_channels
        await command.set_slowmode.callback(command, context(moderator=True), status="on")
        restarted = CommandSlowmodeService(db)
        await restarted.setup()
        assert restarted.enabled_channels == {"channel"}
        assert service.allow(context())
        assert not service.allow(context("smart"))
        await command.set_slowmode.callback(command, context(moderator=True), status="off")
        assert service.allow(context())
        assert service.allow(context())


@pytest.mark.asyncio
async def test_guard_blocks_before_callback_and_error_is_silent():
    service = CommandSlowmodeService(None)
    service.enabled_channels.add("channel")
    bot = SimpleNamespace(services=SimpleNamespace(command_slowmode=service))
    assert await TwitchBot.global_guard(bot, context())
    with pytest.raises(SlowmodeBlocked) as error:
        await TwitchBot.global_guard(bot, context("smart"))
    await TwitchBot.event_command_error(bot, SimpleNamespace(exception=error.value))

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.channels.custom_commands import CustomCommandService
from bot.services.channels.command_slowmode import CommandSlowmodeService
from bot.services.container import ServiceContainer


def test_custom_cleanup_removes_only_expired_timestamps():
    service = CustomCommandService(None)
    for name in ('deadlines', 'next_send', 'backoff'):
        setattr(service, name, {'old': 9, 'boundary': 10, 'active': 11})
    service.delivering.add('old')
    service.commands['old'] = {'hello': {'enabled': True}}
    service.prune_expired(10)
    for name in ('deadlines', 'next_send', 'backoff'):
        assert getattr(service, name) == {'active': 11}
    assert service.delivering == {'old'}
    assert 'old' in service.commands


def test_slowmode_cleanup_preserves_active_viewer_limits():
    service = CommandSlowmodeService(None)
    service.enabled_channels.add('channel')
    service.deadlines = {('channel', str(i)): 10 for i in range(10000)}
    service.deadlines[('channel', 'active')] = 20
    service.prune_expired(10)
    assert service.deadlines == {('channel', 'active'): 20}
    assert service.enabled_channels == {'channel'}


@pytest.mark.asyncio
async def test_empty_reload_removes_definition_cache_but_preserves_active_limits(monkeypatch):
    service = CustomCommandService(None)
    service.commands = {'channel': {'old': {}}, 'other': {'keep': {}}}
    service.backoff['channel'] = 999
    monkeypatch.setattr('bot.services.channels.custom_commands.list_commands', AsyncMock(return_value=[]))
    await service.reload('channel')
    assert service.commands == {'other': {'keep': {}}}
    assert service.backoff['channel'] == 999


@pytest.mark.asyncio
async def test_periodic_cleanup_runs_while_idle_and_stops_cleanly(monkeypatch):
    container = ServiceContainer.__new__(ServiceContainer)
    container._command_cleanup_task = None
    container.custom_commands = CustomCommandService(None)
    container.command_slowmode = CommandSlowmodeService(None)
    clock = SimpleNamespace(monotonic=lambda: 100)
    monkeypatch.setattr('bot.services.channels.custom_commands.time', clock)
    monkeypatch.setattr('bot.services.channels.command_slowmode.time', clock)
    container.custom_commands.next_send['idle'] = 101
    container.command_slowmode.deadlines[('idle', 'viewer')] = 101
    tick = asyncio.Event()
    sleeping = asyncio.Event()
    waits = []
    async def sleep(seconds):
        waits.append(seconds)
        sleeping.set()
        await tick.wait()
        tick.clear()
    monkeypatch.setattr('bot.services.container.asyncio', SimpleNamespace(
        create_task=asyncio.create_task, gather=asyncio.gather, sleep=sleep))
    container._start_command_cleanup()
    task = container._command_cleanup_task
    container._start_command_cleanup()
    assert container._command_cleanup_task is task
    try:
        await asyncio.wait_for(sleeping.wait(), 1)
        assert container.custom_commands.next_send == {'idle': 101}
        sleeping.clear()
        clock.monotonic = lambda: 102
        tick.set()
        await asyncio.wait_for(sleeping.wait(), 1)
        assert container.custom_commands.next_send == {}
        assert container.command_slowmode.deadlines == {}
        assert waits == [60, 60]
    finally:
        await container._stop_command_cleanup()
    assert task.done()
    assert container._command_cleanup_task is None
    await container._stop_command_cleanup()

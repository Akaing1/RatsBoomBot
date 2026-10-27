import asyncio
from types import SimpleNamespace

import pytest

from app.connection_watchdog import watch_connection


class Finished(Exception):
    pass


class Bot:
    def __init__(self):
        self.conduit_info = SimpleNamespace(shard_count=2, websockets={
            "0": SimpleNamespace(connected=True), "1": SimpleNamespace(connected=True)})
        self.ready = asyncio.Event()

    async def wait_until_ready(self):
        await self.ready.wait()


async def exercise(states, grace=30):
    bot = Bot()
    bot.ready.set()
    now = 0
    armed = []
    iterator = iter(states)

    async def sleep(interval):
        nonlocal now
        try:
            count = next(iterator)
        except StopIteration:
            raise Finished
        now += interval
        for i, socket in enumerate(bot.conduit_info.websockets.values()):
            socket.connected = i < count

    try:
        await watch_connection(bot, interval=15, grace=grace, clock=lambda: now,
                               sleep=sleep, arm_exit=lambda: armed.append(now))
    except Finished:
        pass
    except RuntimeError as error:
        assert "recovery deadline" in str(error)
    return armed


@pytest.mark.asyncio
async def test_quiet_healthy_bot_never_restarts():
    assert await exercise([2] * 50) == []


@pytest.mark.asyncio
async def test_persistent_partial_disconnect_restarts_once_after_grace():
    assert await exercise([1] * 10) == [45]


@pytest.mark.asyncio
async def test_recovery_resets_continuous_failure_timer():
    assert await exercise([0, 0, 2, 0, 0, 2]) == []


@pytest.mark.asyncio
async def test_missing_shards_detected():
    assert await exercise([0] * 10) == [45]


@pytest.mark.asyncio
async def test_watchdog_waits_for_startup_and_cancels_cleanly():
    bot = Bot()
    armed = []
    task = asyncio.create_task(watch_connection(bot, arm_exit=lambda: armed.append(True)))
    await asyncio.sleep(0)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not armed


@pytest.mark.asyncio
async def test_runtime_stops_watchdog_when_dashboard_exits(monkeypatch):
    from app import runtime
    stopped = asyncio.Event()
    cancelled = asyncio.Event()

    async def start(**kwargs):
        await stopped.wait()

    async def close():
        stopped.set()

    async def serve():
        await asyncio.sleep(0.01)

    async def watch(bot):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(runtime, "watch_connection", watch)
    monkeypatch.setattr(runtime, "record_performance", watch)
    await asyncio.wait_for(runtime.run_services(SimpleNamespace(start=start, close=close),
                            SimpleNamespace(serve=serve, should_exit=False)), timeout=1)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_runtime_propagates_watchdog_failure_and_closes_bot(monkeypatch):
    from app import runtime
    stopped = asyncio.Event()
    server = SimpleNamespace(should_exit=False)

    async def start(**kwargs):
        await stopped.wait()

    async def close():
        stopped.set()

    async def serve():
        while not server.should_exit:
            await asyncio.sleep(0)

    async def watch(bot):
        raise RuntimeError("recovery deadline exceeded")

    async def record(bot):
        await asyncio.Event().wait()

    server.serve = serve
    monkeypatch.setattr(runtime, "watch_connection", watch)
    monkeypatch.setattr(runtime, "record_performance", record)
    with pytest.raises(RuntimeError, match="recovery deadline"):
        await asyncio.wait_for(runtime.run_services(SimpleNamespace(start=start, close=close), server), timeout=1)
    assert stopped.is_set()

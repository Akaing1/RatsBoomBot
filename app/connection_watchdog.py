"""Observe local Twitch shards without adding network requests or using chat activity."""
import asyncio
import logging
import os
import threading
import time
from pathlib import Path

LOGGER = logging.getLogger("RatBoomBot")


def snapshot(bot, *, stacks=False):
    info = bot.conduit_info
    sockets = info.websockets
    connected = sum(bool(socket.connected) for socket in sockets.values())
    expected = info.shard_count or 0
    tasks = asyncio.all_tasks()
    resources = {}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith(("VmRSS:", "Threads:")):
                key, value = line.split(":", 1)
                resources[key] = value.strip()
        resources["fds"] = len(list(Path("/proc/self/fd").iterdir()))
    except OSError:
        pass
    LOGGER.info("[ConnectionWatchdog] shards=%d/%d tasks=%d resources=%s",
                connected, expected, len(tasks), resources)
    if stacks:
        # Only locations; never log frame locals, tokens, or coroutine arguments.
        for task in sorted(tasks, key=lambda t: t.get_name())[:30]:
            frames = task.get_stack(limit=3)
            LOGGER.warning("[ConnectionWatchdog] task=%s stack=%s", task.get_name(),
                           [(f.f_code.co_filename, f.f_lineno, f.f_code.co_name) for f in frames])
    return connected, expected


def arm_exit_deadline(seconds=20):
    # asyncio cancellation cannot stop a blocked event loop or uncooperative cleanup.
    # Only arm this after a confirmed prolonged disconnection, never at startup.
    timer = threading.Timer(seconds, os._exit, args=(75,))
    timer.daemon = True
    timer.start()


async def watch_connection(bot, *, interval=15, grace=300, clock=time.monotonic,
                           sleep=asyncio.sleep, arm_exit=arm_exit_deadline):
    # Initial setup may legitimately take a while. This patch monitors established
    # sessions only; it does not introduce a startup timeout.
    await bot.wait_until_ready()
    unhealthy_since = None
    next_report = 0.0
    previous = clock()
    while True:
        await sleep(interval)
        now = clock()
        lag = max(0.0, now - previous - interval)
        previous = now
        info = bot.conduit_info
        expected = info.shard_count or 0
        connected = sum(bool(s.connected) for s in info.websockets.values())
        if now >= next_report:
            snapshot(bot)
            LOGGER.info("[ConnectionWatchdog] event_loop_lag_seconds=%.3f", lag)
            next_report = now + 300
        if expected > 0 and connected >= expected:
            if unhealthy_since is not None:
                LOGGER.info("[ConnectionWatchdog] Twitch connection recovered after %.1fs",
                            now - unhealthy_since)
            unhealthy_since = None
            continue
        if unhealthy_since is None:
            unhealthy_since = now
            LOGGER.warning("[ConnectionWatchdog] Twitch connection degraded: %d/%d shards; allowing %ds recovery",
                           connected, expected, grace)
        if now - unhealthy_since >= grace:
            snapshot(bot, stacks=True)
            LOGGER.error("[ConnectionWatchdog] Twitch connection unavailable for %.1fs; restarting runtime",
                         now - unhealthy_since)
            arm_exit()
            raise RuntimeError("Twitch connection recovery deadline exceeded")

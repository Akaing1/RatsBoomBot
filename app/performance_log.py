"""Bounded, unattended performance history; no chat content or credentials."""
import asyncio
import json
import logging
import os
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import settings
from config.version import APP_VERSION
from web.shared.system_metrics import SystemMetricsCollector

LOGGER = logging.getLogger("RatBoomBot")


def read_diagnostics() -> dict:
    result = {"swap_used_bytes": None, "throttled_flags": None}
    try:
        values = {line.split(":")[0]: int(line.split()[1]) * 1024
                  for line in Path("/proc/meminfo").read_text().splitlines()}
        result["swap_used_bytes"] = values["SwapTotal"] - values["SwapFree"]
    except (OSError, ValueError, KeyError, IndexError):
        pass
    try:
        process = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                 text=True, timeout=2, check=True)
        result["throttled_flags"] = hex(int(process.stdout.strip().split("=", 1)[1], 16))
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return result


class PerformanceLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.collector = SystemMetricsCollector()
        self.handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024,
                                           backupCount=3, encoding="utf-8")
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def write(self, context: dict) -> None:
        sample = self.collector.collect()
        sample.update(read_diagnostics())
        sample.update(context)
        sample.update(pid=os.getpid(), version=APP_VERSION)
        record = logging.LogRecord("performance", logging.INFO, "", 0,
                                   json.dumps(sample), (), None)
        self.handler.handle(record)

    def close(self) -> None:
        self.handler.close()


async def record_performance(bot, interval: float = 60) -> None:
    path = Path(settings.DATABASE_PATH).resolve().parent / "performance.jsonl"
    recorder = None
    try:
        recorder = PerformanceLog(path)
        LOGGER.info("[Performance] Recording every %s seconds to %s (8 MiB rotation limit).", interval, path)
        while True:
            services = getattr(bot, "services", None)
            stream_logs = getattr(services, "stream_logs", None)
            context = {
                "active_stream_sessions": len(stream_logs.active_sessions) if stream_logs else None,
                "async_task_count": len(asyncio.all_tasks()),
            }
            try:
                # Slow filesystem or firmware reads must not block chat handling.
                write_task = asyncio.create_task(asyncio.to_thread(recorder.write, context))
                try:
                    await asyncio.shield(write_task)
                except asyncio.CancelledError:
                    await write_task
                    raise
            except Exception:
                LOGGER.warning("[Performance] Could not record sample.", exc_info=True)
            await asyncio.sleep(interval)
    except OSError:
        LOGGER.warning("[Performance] Could not open performance history at %s.", path, exc_info=True)
    finally:
        if recorder:
            recorder.close()

import asyncio
import json
from types import SimpleNamespace

from app import performance_log


def test_history_survives_reopen_and_rotates(tmp_path, monkeypatch):
    monkeypatch.setattr(performance_log, "read_diagnostics", lambda: {"swap_used_bytes": 0})
    path = tmp_path / "performance.jsonl"
    for _ in range(2):
        recorder = performance_log.PerformanceLog(path)
        monkeypatch.setattr(recorder.collector, "collect", lambda: {"process_memory_bytes": 123})
        recorder.write({"active_stream_sessions": 4})
        recorder.close()
    samples = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(samples) == 2
    assert samples[0]["process_memory_bytes"] == 123
    assert samples[0]["active_stream_sessions"] == 4
    recorder = performance_log.PerformanceLog(path)
    recorder.handler.maxBytes = 200
    for _ in range(20):
        recorder.write({})
    recorder.close()
    assert len(list(tmp_path.iterdir())) == 4


def test_unavailable_diagnostics(monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError
    monkeypatch.setattr(performance_log.Path, "read_text", unavailable)
    monkeypatch.setattr(performance_log.subprocess, "run", unavailable)
    assert performance_log.read_diagnostics() == {"swap_used_bytes": None, "throttled_flags": None}


def test_monitor_records_without_dashboard_and_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(performance_log.settings, "DATABASE_PATH", str(tmp_path / "bot.db"))
    monkeypatch.setattr(performance_log, "read_diagnostics", lambda: {})
    async def exercise():
        bot = SimpleNamespace(services=SimpleNamespace(stream_logs=SimpleNamespace(active_sessions={"a": 1})))
        task = asyncio.create_task(performance_log.record_performance(bot, interval=0.01))
        for _ in range(100):
            await asyncio.sleep(0.01)
            path = tmp_path / "performance.jsonl"
            if path.exists() and path.stat().st_size:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return json.loads(path.read_text().splitlines()[0])
    assert asyncio.run(exercise())["active_stream_sessions"] == 1

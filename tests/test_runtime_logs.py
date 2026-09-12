import logging

from app.runtime_logs import RuntimeLogBuffer


def create_record(message: str, broadcaster_id: str | None = None) -> logging.LogRecord:
    record = logging.LogRecord("RatBoomBot", logging.INFO, "", 0, message, (), None)

    if broadcaster_id is not None:
        record.broadcaster_id = broadcaster_id

    return record


def test_runtime_log_buffer_keeps_bot_health_records() -> None:
    buffer = RuntimeLogBuffer()

    buffer.emit(create_record("[Startup] RatBoomBot is starting."))
    buffer.emit(create_record("[Database] Database migrations are up to date."))

    assert [entry["message"] for entry in buffer.get_entries()] == [
        "[Startup] RatBoomBot is starting.",
        "[Database] Database migrations are up to date."
    ]


def test_runtime_log_buffer_excludes_channel_activity() -> None:
    buffer = RuntimeLogBuffer()

    buffer.emit(create_record("[Viewer Queue] User alice joined broadcaster 123.", broadcaster_id="123"))
    buffer.emit(create_record("[Redeems] User alice claimed Daily Check-in."))

    assert buffer.get_entries() == []


def test_runtime_logs_keep_channel_failures_and_tracebacks() -> None:
    buffer = RuntimeLogBuffer()
    try:
        raise ValueError("provider unavailable")
    except ValueError as error:
        record = logging.LogRecord("RatBoomBot", logging.ERROR, "", 0, "[League] Failed in UAT", (), (type(error), error, error.__traceback__))
    record.broadcaster_id = "123"
    buffer.emit(record)
    warning = logging.LogRecord("RatBoomBot", logging.WARNING, "", 0, "[League] Request timed out", (), None)
    buffer.emit(warning)
    entries = buffer.get_entries()
    assert len(entries) == 2
    assert "ValueError: provider unavailable" in entries[0]["message"]
    assert entries[1]["level"] == "WARNING"

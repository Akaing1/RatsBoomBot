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

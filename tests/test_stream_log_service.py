import logging
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from bot.services.stream.stream_logs import StreamLogService


@dataclass
class FakeBroadcaster:
    id: str
    name: str


class FakeBroadcasterService:
    def __init__(self) -> None:
        self.items = {
            "123": FakeBroadcaster(id="123", name="Test Channel")
        }

    def get_broadcasters(self) -> dict[str, FakeBroadcaster]:
        return self.items.copy()


class FakeBot:
    pass


@pytest.mark.asyncio
async def test_start_write_and_end_session(tmp_path) -> None:
    service = StreamLogService(
        bot=FakeBot(),
        broadcaster_service=FakeBroadcasterService(),
        logs_path=str(tmp_path)
    )

    session = await service.start_session(
        broadcaster_id="123",
        stream_id="stream-1",
        channel_name="Test Channel"
    )

    assert service.is_active("123") is True

    written = service.write("123", "CHAT", "Rat: hello")

    assert written is True
    await service.end_session("123")
    assert service.is_active("123") is False

    content = session.log_path.read_text(encoding="utf-8")

    assert "Stream session started" in content
    assert "Rat: hello" in content
    assert "Stream session ended" in content


@pytest.mark.asyncio
async def test_same_stream_reuses_active_session(tmp_path) -> None:
    service = StreamLogService(
        bot=FakeBot(),
        broadcaster_service=FakeBroadcasterService(),
        logs_path=str(tmp_path)
    )

    first_session = await service.start_session(
        broadcaster_id="123",
        stream_id="stream-1",
        channel_name="Test Channel"
    )

    second_session = await service.start_session(
        broadcaster_id="123",
        stream_id="stream-1",
        channel_name="Test Channel"
    )

    assert first_session is second_session
    assert len(service.active_sessions) == 1


@pytest.mark.asyncio
async def test_existing_stream_directory_is_resumed(tmp_path) -> None:
    service = StreamLogService(
        bot=FakeBot(),
        broadcaster_service=FakeBroadcasterService(),
        logs_path=str(tmp_path)
    )

    existing_directory = (tmp_path / "test_channel" / "2026-07-11_143210_stream-stream-1")
    existing_directory.mkdir(parents=True)

    log_file = (existing_directory / "log.txt")
    log_file.write_text("existing line\n", encoding="utf-8")

    session = await service.start_session(
        broadcaster_id="123",
        stream_id="stream-1",
        channel_name="Test Channel"
    )

    assert session.log_path == log_file

    content = log_file.read_text(encoding="utf-8")

    assert "existing line" in content
    assert "resumed logging" in content


def test_write_ignores_inactive_channel(tmp_path) -> None:
    service = StreamLogService(
        bot=FakeBot(),
        broadcaster_service=FakeBroadcasterService(),
        logs_path=str(tmp_path)
    )

    written = service.write("missing", "CHAT", "hello")

    assert written is False


def test_sanitize_and_clean_message(tmp_path) -> None:
    service = StreamLogService(
        bot=FakeBot(),
        broadcaster_service=FakeBroadcasterService(),
        logs_path=str(tmp_path)
    )

    assert service.sanitize_path_part(" Test Channel! ") == "test_channel"
    assert service.clean_message("one\ntwo\r\nthree") == "one two three"


def test_log_handler_only_writes_to_matching_broadcaster(tmp_path) -> None:
    service = StreamLogService(bot=FakeBot(), broadcaster_service=FakeBroadcasterService(), logs_path=str(tmp_path))
    first_log = tmp_path / "first" / "session" / "log.txt"
    second_log = tmp_path / "second" / "session" / "log.txt"
    first_log.parent.mkdir(parents=True)
    second_log.parent.mkdir(parents=True)
    service.active_sessions["123"] = SimpleNamespace(log_path=first_log)
    service.active_sessions["456"] = SimpleNamespace(log_path=second_log)
    record = logging.LogRecord("RatBoomBot", logging.INFO, "", 0, "Channel event", (), None)
    record.broadcaster_id = "123"

    service.log_handler.emit(record)

    assert "Channel event" in first_log.read_text(encoding="utf-8")
    assert not second_log.exists()


def test_log_handler_ignores_records_without_broadcaster(tmp_path) -> None:
    service = StreamLogService(bot=FakeBot(), broadcaster_service=FakeBroadcasterService(), logs_path=str(tmp_path))
    log_file = tmp_path / "channel" / "session" / "log.txt"
    service.active_sessions["123"] = SimpleNamespace(log_path=log_file)
    record = logging.LogRecord("RatBoomBot", logging.ERROR, "", 0, "Application error", (), None)

    service.log_handler.emit(record)

    assert not log_file.exists()

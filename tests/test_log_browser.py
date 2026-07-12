from config.settings import settings
from web.log_browser import (
    format_file_size,
    get_logs_directory,
    parse_session_directory_name,
    resolve_log_file
)


def test_format_file_size() -> None:
    assert format_file_size(12) == "12 B"

    assert format_file_size(2048) == "2.0 KB"

    assert format_file_size(2 * 1024 * 1024) == "2.0 MB"


def test_parse_session_directory_name() -> None:
    started_at, stream_id = parse_session_directory_name("2026-07-11_143210_stream-123456789")

    assert started_at == "July 11, 2026 at 02:32:10 PM"
    assert stream_id == "123456789"


def test_parse_unknown_session_directory_name() -> None:
    started_at, stream_id = parse_session_directory_name("legacy-folder")

    assert started_at == "legacy-folder"
    assert stream_id == "Unknown"


def test_resolve_log_file_accepts_valid_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STREAM_LOGS_PATH", str(tmp_path))

    log_file = (tmp_path / "channel" / "session" / "log.txt")
    log_file.parent.mkdir(parents=True)
    log_file.write_text("hello", encoding="utf-8")

    assert get_logs_directory() == tmp_path.resolve()

    assert resolve_log_file("channel", "session") == log_file.resolve()


def test_resolve_log_file_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STREAM_LOGS_PATH", str(tmp_path))

    outside_file = (tmp_path.parent / "secret" / "session" / "log.txt")
    outside_file.parent.mkdir(parents=True, exist_ok=True)
    outside_file.write_text("secret", encoding="utf-8")

    assert resolve_log_file("..", "secret/session") is None

from datetime import datetime
from pathlib import Path

from config.settings import settings


def get_logs_directory() -> Path:
    logs_directory = Path(settings.STREAM_LOGS_PATH).resolve()

    logs_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    return logs_directory


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"

    return f"{size_bytes / (1024 * 1024):.1f} MB"


def parse_session_directory_name(directory_name: str) -> tuple[str, str]:
    marker = "_stream-"

    if marker not in directory_name:
        return directory_name, "Unknown"

    timestamp_value, stream_id = directory_name.rsplit(marker, 1)

    try:
        started_at = datetime.strptime(timestamp_value, "%Y-%m-%d_%H%M%S").strftime("%B %d, %Y at %I:%M:%S %p")
    except ValueError:
        started_at = timestamp_value

    return started_at, stream_id


def resolve_log_file(channel_name: str, session_name: str) -> Path | None:
    logs_directory = get_logs_directory()

    requested_file = (
            logs_directory
            / channel_name
            / session_name
            / "log.txt"
    ).resolve()

    try:
        requested_file.relative_to(logs_directory)
    except ValueError:
        return None

    if not requested_file.is_file():
        return None

    return requested_file

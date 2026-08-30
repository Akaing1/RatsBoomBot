import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime

RUNTIME_HEALTH_CATEGORIES = frozenset({
    "Broadcasters",
    "Components",
    "Dashboard",
    "Database",
    "EventSub",
    "OAuth",
    "Profiles",
    "Runtime",
    "Services",
    "Shutdown",
    "Startup",
    "Stream Logs"
})


def is_runtime_health_record(record: logging.LogRecord) -> bool:
    if getattr(record, "broadcaster_id", None) is not None:
        return False

    message = record.getMessage().lstrip()

    if not message.startswith("["):
        return True

    category, separator, _ = message[1:].partition("]")
    return bool(separator) and category in RUNTIME_HEALTH_CATEGORIES


@dataclass(frozen=True)
class RuntimeLogEntry:
    id: int
    timestamp: str
    level: str
    message: str


class RuntimeLogBuffer(logging.Handler):

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__(level=logging.INFO)
        self.entries: deque[RuntimeLogEntry] = deque(maxlen=capacity)
        self.next_id = 1
        self.entries_lock = threading.Lock()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        if not is_runtime_health_record(record):
            return

        try:
            message = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds")

            with self.entries_lock:
                entry = RuntimeLogEntry(id=self.next_id, timestamp=timestamp, level=record.levelname, message=message)
                self.entries.append(entry)
                self.next_id += 1
        except Exception:
            self.handleError(record)

    def get_entries(self, after_id: int = 0, limit: int = 500) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), 1000))

        with self.entries_lock:
            matching_entries = [entry for entry in self.entries if entry.id > after_id]

        return [asdict(entry) for entry in matching_entries[-safe_limit:]]


runtime_log_buffer = RuntimeLogBuffer()

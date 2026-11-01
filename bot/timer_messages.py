import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TimerMessage:
    message: str
    kind: str = "message"
    color: str = "primary"
    enabled: bool = True
    interval_minutes: int = 30
    require_active_chat: bool = True
    minimum_messages: int = 20

    def __post_init__(self):
        if type(self.interval_minutes) is not int or not 1 <= self.interval_minutes <= 1440:
            raise ValueError("Timer interval must be between 1 and 1440 minutes.")
        if not isinstance(self.require_active_chat, bool):
            raise ValueError("Timer active chat requirement must be a boolean.")
        if type(self.minimum_messages) is not int or not 1 <= self.minimum_messages <= 100000:
            raise ValueError("Timer minimum messages must be between 1 and 100000.")
        if not isinstance(self.enabled, bool):
            raise ValueError("Timer enabled state must be a boolean.")
        if not isinstance(self.message, str):
            raise ValueError("Timer message must be text.")
        if self.kind not in ("message", "announcement"):
            raise ValueError("Timer type must be message or announcement.")
        if self.color not in ("primary", "blue", "green", "orange", "purple"):
            raise ValueError("Invalid announcement color.")


def normalize_timer(value) -> TimerMessage:
    if isinstance(value, TimerMessage):
        return value
    if isinstance(value, str):
        return TimerMessage(value)
    if isinstance(value, (tuple, list)) and 2 <= len(value) <= 7:
        return TimerMessage(*value)
    raise ValueError("Invalid timer entry.")


def parse_timers(value: str) -> tuple[TimerMessage, ...]:
    if value.lstrip().startswith("[[") or value.strip() == "[]":
        entries = json.loads(value)
        if not isinstance(entries, list):
            raise ValueError("Expected a list of timers.")
        return tuple(normalize_timer(entry) for entry in entries)
    return tuple(TimerMessage(line.strip()) for line in value.splitlines() if line.strip())


def format_timers(entries) -> str:
    timers = tuple(normalize_timer(entry) for entry in entries)
    if all(entry.kind == "message" and entry.enabled and entry.interval_minutes == 30 and entry.require_active_chat and entry.minimum_messages == 20 for entry in timers) and not any(entry.message.lstrip().startswith("[") for entry in timers):
        return "\n".join(entry.message for entry in timers)
    return json.dumps([[entry.message, entry.kind, entry.color, entry.enabled, entry.interval_minutes, entry.require_active_chat, entry.minimum_messages] for entry in timers], ensure_ascii=False)

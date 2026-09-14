import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TimerMessage:
    message: str
    kind: str = "message"
    color: str = "primary"

    def __post_init__(self):
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
    if isinstance(value, (tuple, list)) and 2 <= len(value) <= 3:
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
    if all(entry.kind == "message" for entry in timers) and not any(entry.message.lstrip().startswith("[") for entry in timers):
        return "\n".join(entry.message for entry in timers)
    return json.dumps([[entry.message, entry.kind, entry.color] for entry in timers], ensure_ascii=False)

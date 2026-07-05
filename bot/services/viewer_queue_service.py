from collections import deque
from dataclasses import dataclass, field


@dataclass
class ViewerQueueState:
    queue: deque[str] = field(default_factory=deque)
    users: set[str] = field(default_factory=set)
    is_open: bool = False


class ViewerQueueService:
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[str, ViewerQueueState] = {}

    def _get_queue_state(self, broadcaster_id: str) -> ViewerQueueState:
        if broadcaster_id not in self.queues:
            self.queues[broadcaster_id] = ViewerQueueState()

        return self.queues[broadcaster_id]

    def open_queue(self, broadcaster_id: str) -> str:
        state = self._get_queue_state(broadcaster_id)

        if state.is_open:
            return "The viewer queue is already open."

        state.is_open = True
        return "Queue is now open! Viewers can join the queue using !join."

    def close_queue(self, broadcaster_id: str) -> str:
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            return "The viewer queue is already closed."

        state.is_open = False
        return "The viewer queue is now closed."

    def is_queue_open(self, broadcaster_id: str) -> bool:
        state = self._get_queue_state(broadcaster_id)
        return state.is_open

    def join(self, broadcaster_id: str, username: str) -> tuple[bool, str]:
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username in state.users:
            return False, f"@{username}, you are already in the queue."

        state.queue.append(username)
        state.users.add(username)

        position = len(state.queue)
        return True, f"@{username}, you joined the queue! Position: {position}"

    def leave(self, broadcaster_id: str, username: str) -> tuple[bool, str]:
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username not in state.users:
            return False, f"@{username}, you are not in the queue."

        state.queue.remove(username)
        state.users.remove(username)

        return True, f"@{username}, you left the queue."

    def next_viewer(self, broadcaster_id: str) -> tuple[bool, str]:
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            return False, "The viewer queue is currently closed."

        if not state.queue:
            return False, "The queue is empty."

        username = state.queue.popleft()
        state.users.remove(username)

        return True, f"Next up: @{username}!"

    def clear(self, broadcaster_id: str) -> str:
        state = self._get_queue_state(broadcaster_id)

        state.queue.clear()
        state.users.clear()

        return "Viewer queue cleared."

    def list_queue(self, broadcaster_id: str) -> list[str]:
        state = self._get_queue_state(broadcaster_id)
        return list(state.queue)

    def size(self, broadcaster_id: str) -> int:
        state = self._get_queue_state(broadcaster_id)
        return len(state.queue)
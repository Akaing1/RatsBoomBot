import logging
from collections import deque
from dataclasses import dataclass, field

LOGGER = logging.getLogger("RatBoomBot")


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

        broadcaster_id = str(broadcaster_id)
        state = self.queues.get(broadcaster_id)

        if state is None:
            state = ViewerQueueState()
            self.queues[broadcaster_id] = state

            LOGGER.debug(
                "[Viewer Queue] Created queue state for broadcaster %s.",
                broadcaster_id
            )

        return state

    def open_queue(self, broadcaster_id: str) -> str:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if state.is_open:
            LOGGER.debug(
                "[Viewer Queue] Queue for broadcaster %s is already open.",
                broadcaster_id
            )
            return "The viewer queue is already open."

        state.is_open = True

        LOGGER.info(
            "[Viewer Queue] Opened queue for broadcaster %s.",
            broadcaster_id
        )

        return "Queue is now open! Viewers can join the queue using !join."

    def close_queue(self, broadcaster_id: str) -> str:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            LOGGER.debug(
                "[Viewer Queue] Queue for broadcaster %s is already closed.",
                broadcaster_id
            )
            return "The viewer queue is already closed."

        state.is_open = False

        LOGGER.info(
            "[Viewer Queue] Closed queue for broadcaster %s with %d viewers remaining.",
            broadcaster_id,
            len(state.queue)
        )

        return "The viewer queue is now closed."

    def is_queue_open(self, broadcaster_id: str) -> bool:

        state = self._get_queue_state(str(broadcaster_id))

        return state.is_open

    def join(self, broadcaster_id: str, username: str) -> tuple[bool, str]:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            LOGGER.debug(
                "[Viewer Queue] User %s could not join closed queue for broadcaster %s.",
                username,
                broadcaster_id
            )
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username in state.users:
            LOGGER.debug(
                "[Viewer Queue] User %s is already queued for broadcaster %s.",
                username,
                broadcaster_id
            )
            return False, f"@{username}, you are already in the queue."

        state.queue.append(username)
        state.users.add(username)

        position = len(state.queue)

        LOGGER.info(
            "[Viewer Queue] User %s joined broadcaster %s at position %d.",
            username,
            broadcaster_id,
            position
        )

        return True, f"@{username}, you joined the queue! Position: {position}"

    def leave(self, broadcaster_id: str, username: str) -> tuple[bool, str]:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            LOGGER.debug(
                "[Viewer Queue] User %s could not leave closed queue for broadcaster %s.",
                username,
                broadcaster_id
            )
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username not in state.users:
            LOGGER.debug(
                "[Viewer Queue] User %s is not queued for broadcaster %s.",
                username,
                broadcaster_id
            )
            return False, f"@{username}, you are not in the queue."

        state.queue.remove(username)
        state.users.remove(username)

        LOGGER.info(
            "[Viewer Queue] User %s left broadcaster %s. %d viewers remain.",
            username,
            broadcaster_id,
            len(state.queue)
        )

        return True, f"@{username}, you left the queue."

    def next_viewer(self, broadcaster_id: str) -> tuple[bool, str]:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            LOGGER.debug(
                "[Viewer Queue] Next viewer requested for closed queue in broadcaster %s.",
                broadcaster_id
            )
            return False, "The viewer queue is currently closed."

        if not state.queue:
            LOGGER.debug(
                "[Viewer Queue] Next viewer requested for empty queue in broadcaster %s.",
                broadcaster_id
            )
            return False, "The queue is empty."

        username = state.queue.popleft()
        state.users.remove(username)

        LOGGER.info(
            "[Viewer Queue] Selected user %s next for broadcaster %s. %d viewers remain.",
            username,
            broadcaster_id,
            len(state.queue)
        )

        return True, f"Next up: @{username}!"

    def clear(self, broadcaster_id: str) -> str:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        removed_count = len(state.queue)

        state.queue.clear()
        state.users.clear()

        LOGGER.info(
            "[Viewer Queue] Cleared %d viewers from broadcaster %s.",
            removed_count,
            broadcaster_id
        )

        return "Viewer queue cleared."

    def list_queue(self, broadcaster_id: str) -> list[str]:

        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        LOGGER.debug(
            "[Viewer Queue] Returning %d queued viewers for broadcaster %s.",
            len(state.queue),
            broadcaster_id
        )

        return list(state.queue)

    def size(self, broadcaster_id: str) -> int:

        state = self._get_queue_state(str(broadcaster_id))

        return len(state.queue)

    def remove_queue(self, broadcaster_id: str) -> None:

        broadcaster_id = str(broadcaster_id)
        state = self.queues.pop(broadcaster_id, None)

        if state is None:
            LOGGER.debug(
                "[Viewer Queue] No queue state found for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Viewer Queue] Removed queue state for broadcaster %s with %d viewers.",
            broadcaster_id,
            len(state.queue)
        )

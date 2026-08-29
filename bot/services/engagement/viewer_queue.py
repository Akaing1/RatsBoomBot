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

    def next_viewers(self, broadcaster_id: str, count: int = 1) -> tuple[bool, list[str], str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if count < 1:
            LOGGER.debug(
                "[Viewer Queue] Invalid next-viewer count %d requested in broadcaster %s.",
                count,
                broadcaster_id
            )
            return False, [], "The number of viewers must be at least 1."

        if not state.queue:
            LOGGER.debug(
                "[Viewer Queue] Next viewers requested for empty queue in broadcaster %s.",
                broadcaster_id
            )
            return False, [], "The queue is empty."

        selected_count = min(count, len(state.queue))
        selected_viewers: list[str] = []

        for _ in range(selected_count):
            username = state.queue.popleft()
            state.users.remove(username)
            selected_viewers.append(username)

        LOGGER.info(
            "[Viewer Queue] Selected %d viewer(s) for broadcaster %s: %s. %d viewers remain.",
            selected_count,
            broadcaster_id,
            ", ".join(selected_viewers),
            len(state.queue)
        )

        viewers_text = ", ".join(selected_viewers)

        if selected_count == 1:
            message = f"Next up: {viewers_text}!"
        else:
            message = f"Next group: {viewers_text}!"

        return True, selected_viewers, message

    def swap(self, broadcaster_id: str, first_position: int, second_position: int) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        queue_size = len(state.queue)

        if first_position < 1 or second_position < 1 or first_position > queue_size or second_position > queue_size:
            return False, f"Choose two positions between 1 and {queue_size}." if queue_size else "The queue is empty."

        queue_list = list(state.queue)
        queue_list[first_position - 1], queue_list[second_position - 1] = queue_list[second_position - 1], queue_list[first_position - 1]
        state.queue = deque(queue_list)
        LOGGER.info("[Viewer Queue] Swapped positions %d and %d in broadcaster %s.", first_position, second_position, broadcaster_id)
        return True, f"Swapped {queue_list[second_position - 1]} and {queue_list[first_position - 1]}."

    def requeue(self, broadcaster_id: str, current_position: int, new_position: int) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        queue_size = len(state.queue)

        if current_position < 1 or new_position < 1 or current_position > queue_size or new_position > queue_size:
            return False, f"Choose positions between 1 and {queue_size}." if queue_size else "The queue is empty."

        queue_list = list(state.queue)
        username = queue_list.pop(current_position - 1)
        queue_list.insert(new_position - 1, username)
        state.queue = deque(queue_list)
        LOGGER.info("[Viewer Queue] Moved %s from position %d to %d in broadcaster %s.", username, current_position, new_position, broadcaster_id)
        return True, f"Moved {username} to position {new_position}."

    def remove_position(self, broadcaster_id: str, position: int) -> tuple[bool, str | None, str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if position < 1:
            LOGGER.debug(
                "[Viewer Queue] Invalid removal position %d requested in broadcaster %s.",
                position,
                broadcaster_id
            )
            return False, None, "The queue position must be at least 1."

        queue_size = len(state.queue)

        if queue_size == 0:
            LOGGER.debug(
                "[Viewer Queue] Position removal requested for empty queue in broadcaster %s.",
                broadcaster_id
            )
            return False, None, "The queue is empty."

        if position > queue_size:
            LOGGER.debug(
                "[Viewer Queue] Position %d requested for broadcaster %s queue with %d viewers.",
                position,
                broadcaster_id,
                queue_size
            )
            return False, None, f"The queue only has {queue_size} viewer(s)."

        queue_list = list(state.queue)
        removed_username = queue_list.pop(position - 1)

        state.queue = deque(queue_list)
        state.users.remove(removed_username)

        LOGGER.info(
            "[Viewer Queue] Removed user %s from position %d in broadcaster %s. %d viewers remain.",
            removed_username,
            position,
            broadcaster_id,
            len(state.queue)
        )

        return True, removed_username, f"Removed @{removed_username} from position {position}."

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

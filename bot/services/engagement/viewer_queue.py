import logging
from asyncio import Lock
from collections import deque
from dataclasses import dataclass, field

import asqlite

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class ViewerQueueState:
    queue: deque[str] = field(default_factory=deque)
    users: set[str] = field(default_factory=set)
    is_open: bool = False
    blacklist: set[str] = field(default_factory=set)
    display_names: dict[str, str] = field(default_factory=dict)


class ViewerQueueService:

    def __init__(self, bot, db: asqlite.Pool):
        self.bot = bot
        self.db = db
        self.queues: dict[str, ViewerQueueState] = {}
        self.persistence_lock = Lock()

    async def setup(self) -> None:
        query = """
        SELECT states.broadcaster_id, states.is_open, entries.username, entries.display_name, entries.position
        FROM viewer_queue_states AS states
        LEFT JOIN viewer_queue_entries AS entries ON entries.broadcaster_id = states.broadcaster_id
        ORDER BY states.broadcaster_id, entries.position
        """

        async with self.db.acquire() as connection:
            rows = await connection.fetchall(query)
            blacklist_rows = await connection.fetchall(
                "SELECT broadcaster_id, username FROM viewer_queue_blacklist ORDER BY broadcaster_id, username"
            )

        self.queues.clear()

        for row in rows:
            broadcaster_id = str(row["broadcaster_id"])
            state = self.queues.setdefault(broadcaster_id, ViewerQueueState(is_open=bool(row["is_open"])))
            username = row["username"]

            if username is not None:
                state.queue.append(username)
                state.users.add(username)
                if row["display_name"]:
                    state.display_names[username] = str(row["display_name"])

        for row in blacklist_rows:
            state = self.queues.setdefault(str(row["broadcaster_id"]), ViewerQueueState())
            state.blacklist.add(str(row["username"]).lower())

        LOGGER.info("[Viewer Queue] Restored %d queue(s) with %d total viewer(s).", len(self.queues), sum(len(state.queue) for state in self.queues.values()))

    async def _persist(self, broadcaster_id: str, state: ViewerQueueState) -> None:
        state_query = """
        INSERT INTO viewer_queue_states (broadcaster_id, is_open, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(broadcaster_id)
        DO UPDATE SET
            is_open = excluded.is_open,
            updated_at = CURRENT_TIMESTAMP
        """
        entry_query = """
        INSERT INTO viewer_queue_entries (broadcaster_id, username, display_name, position)
        VALUES (?, ?, ?, ?)
        """
        entries = [
            (broadcaster_id, username, state.display_names.get(username), position)
            for position, username in enumerate(state.queue, start=1)
        ]

        async with self.persistence_lock:
            async with self.db.acquire() as connection:
                await connection.execute("BEGIN")

                try:
                    await connection.execute(state_query, (broadcaster_id, int(state.is_open)))
                    await connection.execute("DELETE FROM viewer_queue_entries WHERE broadcaster_id = ?", (broadcaster_id,))

                    if entries:
                        await connection.executemany(entry_query, entries)

                    await connection.commit()
                except Exception:
                    await connection.rollback()
                    raise

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

    async def open_queue(self, broadcaster_id: str) -> str:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if state.is_open:
            LOGGER.debug(
                "[Viewer Queue] Queue for broadcaster %s is already open.",
                broadcaster_id
            )
            return "The viewer queue is already open."

        state.is_open = True
        await self._persist(broadcaster_id, state)

        LOGGER.info(
            "[Viewer Queue] Opened queue for broadcaster %s.",
            broadcaster_id,
            extra={"broadcaster_id": broadcaster_id}
        )

        return "Queue is now open! Viewers can join the queue using !join."

    async def close_queue(self, broadcaster_id: str) -> str:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if not state.is_open:
            LOGGER.debug(
                "[Viewer Queue] Queue for broadcaster %s is already closed.",
                broadcaster_id
            )
            return "The viewer queue is already closed."

        state.is_open = False
        await self._persist(broadcaster_id, state)

        LOGGER.info(
            "[Viewer Queue] Closed queue for broadcaster %s with %d viewers remaining.",
            broadcaster_id,
            len(state.queue),
            extra={"broadcaster_id": broadcaster_id}
        )

        return "The viewer queue is now closed."

    def is_queue_open(self, broadcaster_id: str) -> bool:
        state = self._get_queue_state(str(broadcaster_id))
        return state.is_open

    @staticmethod
    def _member_label(state: ViewerQueueState, username: str) -> str:
        display_name = state.display_names.get(username, username)
        return f"{display_name} ({username})" if display_name.casefold() != username.casefold() else username

    async def join(self, broadcaster_id: str, username: str, display_name: str | None = None) -> tuple[bool, str]:
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

        if username in state.blacklist:
            LOGGER.info("[Viewer Queue] Blocked blacklisted user %s from joining broadcaster %s.", username, broadcaster_id)
            return False, f"{username}, you are not allowed to join this queue."

        if username in state.users:
            LOGGER.debug(
                "[Viewer Queue] User %s is already queued for broadcaster %s.",
                username,
                broadcaster_id
            )
            return False, f"{self._member_label(state, username)}, you are already in the queue."

        state.queue.append(username)
        state.users.add(username)
        if display_name and display_name.strip():
            state.display_names[username] = display_name.strip()
        await self._persist(broadcaster_id, state)

        position = len(state.queue)

        LOGGER.info(
            "[Viewer Queue] User %s joined broadcaster %s at position %d.",
            username,
            broadcaster_id,
            position,
            extra={"broadcaster_id": broadcaster_id}
        )

        return True, f"{self._member_label(state, username)}, you joined the queue! Position: {position}"

    async def leave(self, broadcaster_id: str, username: str) -> tuple[bool, str]:
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
            return False, f"{username}, you are not in the queue."

        label = self._member_label(state, username)
        state.queue.remove(username)
        state.users.remove(username)
        state.display_names.pop(username, None)
        await self._persist(broadcaster_id, state)

        LOGGER.info(
            "[Viewer Queue] User %s left broadcaster %s. %d viewers remain.",
            username,
            broadcaster_id,
            len(state.queue),
            extra={"broadcaster_id": broadcaster_id}
        )

        return True, f"{label}, you left the queue."

    async def next_viewers(self, broadcaster_id: str, count: int = 1) -> tuple[bool, list[str], str]:
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

        selected_members = await self.take_queue_members(broadcaster_id, count)
        selected_count = len(selected_members)
        selected_viewers = [member["username"] for member in selected_members]
        selected_labels = [member["label"] for member in selected_members]

        LOGGER.info(
            "[Viewer Queue] Selected %d viewer(s) for broadcaster %s: %s. %d viewers remain.",
            selected_count,
            broadcaster_id,
            ", ".join(selected_viewers),
            len(state.queue),
            extra={"broadcaster_id": broadcaster_id}
        )

        viewers_text = ", ".join(selected_labels)

        if selected_count == 1:
            message = f"Next up: {viewers_text}!"
        else:
            message = f"Next group: {viewers_text}!"

        return True, selected_viewers, message

    async def take_queue_members(self, broadcaster_id: str, count: int, *, exclude: set[str] | None = None) -> list[dict[str, str]]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)

        if count < 1 or not state.queue:
            return []

        excluded = {username.casefold() for username in (exclude or set())}
        selected = []
        remaining = deque()

        while state.queue:
            username = state.queue.popleft()

            if len(selected) < count and username.casefold() not in excluded:
                selected.append({
                    "username": username,
                    "display_name": state.display_names.get(username, username),
                    "label": self._member_label(state, username)
                })
                state.users.remove(username)
                state.display_names.pop(username, None)
            else:
                remaining.append(username)

        state.queue = remaining

        if selected:
            await self._persist(broadcaster_id, state)

        return selected

    async def swap(self, broadcaster_id: str, first_position: int, second_position: int) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        queue_size = len(state.queue)

        if first_position < 1 or second_position < 1 or first_position > queue_size or second_position > queue_size:
            return False, f"Choose two positions between 1 and {queue_size}." if queue_size else "The queue is empty."

        queue_list = list(state.queue)
        queue_list[first_position - 1], queue_list[second_position - 1] = queue_list[second_position - 1], queue_list[first_position - 1]
        state.queue = deque(queue_list)
        await self._persist(broadcaster_id, state)
        LOGGER.info("[Viewer Queue] Swapped positions %d and %d in broadcaster %s.", first_position, second_position, broadcaster_id, extra={"broadcaster_id": broadcaster_id})
        return True, (
            f"Swapped {self._member_label(state, queue_list[second_position - 1])} "
            f"and {self._member_label(state, queue_list[first_position - 1])}."
        )

    async def requeue(self, broadcaster_id: str, current_position: int, new_position: int) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        queue_size = len(state.queue)

        if current_position < 1 or new_position < 1 or current_position > queue_size or new_position > queue_size:
            return False, f"Choose positions between 1 and {queue_size}." if queue_size else "The queue is empty."

        queue_list = list(state.queue)
        username = queue_list.pop(current_position - 1)
        queue_list.insert(new_position - 1, username)
        state.queue = deque(queue_list)
        await self._persist(broadcaster_id, state)
        LOGGER.info("[Viewer Queue] Moved %s from position %d to %d in broadcaster %s.", username, current_position, new_position, broadcaster_id, extra={"broadcaster_id": broadcaster_id})
        return True, f"Moved {self._member_label(state, username)} to position {new_position}."

    async def remove_position(self, broadcaster_id: str, position: int) -> tuple[bool, str | None, str]:
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

        label = self._member_label(state, removed_username)
        state.queue = deque(queue_list)
        state.users.remove(removed_username)
        state.display_names.pop(removed_username, None)
        await self._persist(broadcaster_id, state)

        LOGGER.info(
            "[Viewer Queue] Removed user %s from position %d in broadcaster %s. %d viewers remain.",
            removed_username,
            position,
            broadcaster_id,
            len(state.queue),
            extra={"broadcaster_id": broadcaster_id}
        )

        return True, removed_username, f"Removed {label} from position {position}."

    async def clear(self, broadcaster_id: str) -> str:
        broadcaster_id = str(broadcaster_id)
        state = self._get_queue_state(broadcaster_id)
        removed_count = len(state.queue)

        state.queue.clear()
        state.users.clear()
        state.display_names.clear()
        await self._persist(broadcaster_id, state)

        LOGGER.info(
            "[Viewer Queue] Cleared %d viewers from broadcaster %s.",
            removed_count,
            broadcaster_id,
            extra={"broadcaster_id": broadcaster_id}
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

    def list_queue_members(self, broadcaster_id: str) -> list[dict[str, str]]:
        state = self._get_queue_state(str(broadcaster_id))
        return [
            {
                "username": username,
                "display_name": state.display_names.get(username, username),
                "label": self._member_label(state, username)
            }
            for username in state.queue
        ]

    def size(self, broadcaster_id: str) -> int:
        state = self._get_queue_state(str(broadcaster_id))
        return len(state.queue)

    def list_blacklist(self, broadcaster_id: str) -> list[str]:
        return sorted(self._get_queue_state(str(broadcaster_id)).blacklist)

    async def add_to_blacklist(self, broadcaster_id: str, username: str) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        username = username.strip().lstrip("@").lower()
        if not username:
            return False, "Enter a Twitch username."
        state = self._get_queue_state(broadcaster_id)
        if username in state.blacklist:
            return False, f"{username} is already blacklisted."

        state.blacklist.add(username)
        if username in state.users:
            state.queue.remove(username)
            state.users.remove(username)
            state.display_names.pop(username, None)
            await self._persist(broadcaster_id, state)

        async with self.db.acquire() as connection:
            await connection.execute(
                "INSERT OR IGNORE INTO viewer_queue_blacklist (broadcaster_id, username) VALUES (?, ?)",
                (broadcaster_id, username)
            )
            await connection.commit()
        return True, f"{username} was added to the queue blacklist."

    async def remove_from_blacklist(self, broadcaster_id: str, username: str) -> tuple[bool, str]:
        broadcaster_id = str(broadcaster_id)
        username = username.strip().lstrip("@").lower()
        state = self._get_queue_state(broadcaster_id)
        if username not in state.blacklist:
            return False, f"{username} is not blacklisted."
        state.blacklist.remove(username)
        async with self.db.acquire() as connection:
            await connection.execute(
                "DELETE FROM viewer_queue_blacklist WHERE broadcaster_id = ? AND username = ?",
                (broadcaster_id, username)
            )
            await connection.commit()
        return True, f"{username} was removed from the queue blacklist."

    async def remove_queue(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        state = self.queues.pop(broadcaster_id, None)

        async with self.persistence_lock:
            async with self.db.acquire() as connection:
                await connection.execute("DELETE FROM viewer_queue_entries WHERE broadcaster_id = ?", (broadcaster_id,))
                await connection.execute("DELETE FROM viewer_queue_states WHERE broadcaster_id = ?", (broadcaster_id,))
                await connection.execute("DELETE FROM viewer_queue_blacklist WHERE broadcaster_id = ?", (broadcaster_id,))
                await connection.commit()

        if state is None:
            LOGGER.debug(
                "[Viewer Queue] No queue state found for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Viewer Queue] Removed queue state for broadcaster %s with %d viewers.",
            broadcaster_id,
            len(state.queue),
            extra={"broadcaster_id": broadcaster_id}
        )

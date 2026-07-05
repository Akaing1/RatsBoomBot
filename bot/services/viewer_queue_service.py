from collections import deque


class ViewerQueueService:
    def __init__(self, bot):
        self.bot = bot

        self.queue = deque()
        self.users = set()

        self.is_open = False

    def open_queue(self) -> str:
        if self.is_open:
            return "The viewer queue is already open."
        self.is_open = True
        return "queue is now open! Viewers can join the queue using !join."

    def close_queue(self) -> str:
        if not self.is_open:
            return "The viewer queue is already closed."
        self.is_open = False
        return "The viewer queue is now closed."

    def is_queue_open(self) -> bool:
        return self.is_open

    def join(self, username: str) -> tuple[bool, str]:
        if not self.is_open:
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username in self.users:
            return False, f"@{username}, you are already in the queue."

        self.queue.append(username)
        self.users.add(username)

        position = len(self.queue)
        return True, f"@{username}, you joined the queue! Position: {position}"

    def leave(self, username: str) -> tuple[bool, str]:
        if not self.is_open:
            return False, "The viewer queue is currently closed."

        username = username.lower()

        if username not in self.users:
            return False, f"@{username}, you are not in the queue."

        self.queue.remove(username)
        self.users.remove(username)

        return True, f"@{username}, you left the queue."

    def next_viewer(self) -> str | None:
        if not self.is_open:
            return "The viewer queue is currently closed."

        if not self.queue:
            return None

        username = self.queue.popleft()
        self.users.remove(username)
        return username

    def clear(self):
        self.queue.clear()
        self.users.clear()

    def list_queue(self) -> list[str]:
        return list(self.queue)

    def size(self) -> int:
        return len(self.queue)

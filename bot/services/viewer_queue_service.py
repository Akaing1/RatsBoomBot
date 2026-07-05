from collections import deque


class ViewerQueueService:
    def __init__(self, bot):
        self.bot = bot

        self.queue = deque()
        self.users = set()

    def join(self, username: str) -> tuple[bool, str]:
        username = username.lower()

        if username in self.users:
            return False, f"@{username}, you are already in the queue."

        self.queue.append(username)
        self.users.add(username)

        position = len(self.queue)
        return True, f"@{username}, you joined the queue! Position: {position}"

    def leave(self, username: str) -> tuple[bool, str]:
        username = username.lower()

        if username not in self.users:
            return False, f"@{username}, you are not in the queue."

        self.queue.remove(username)
        self.users.remove(username)

        return True, f"@{username}, you left the queue."

    def next_viewer(self) -> str | None:
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

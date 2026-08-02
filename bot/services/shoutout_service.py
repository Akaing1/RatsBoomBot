import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class QueuedShoutout:

    user_id: str
    username: str
    requested_by: str
    queued_at: datetime


class ShoutoutService:

    GLOBAL_COOLDOWN = timedelta(minutes=2)
    TARGET_COOLDOWN = timedelta(hours=1)
    CHECK_INTERVAL_SECONDS = 10

    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[str, deque[QueuedShoutout]] = defaultdict(deque)
        self.queued_user_ids: dict[str, set[str]] = defaultdict(set)
        self.last_shoutout_at: dict[str, datetime] = {}
        self.target_last_shoutout_at: dict[str, dict[str, datetime]] = defaultdict(dict)
        self.worker_task: asyncio.Task | None = None
        self.running = False

    async def start(self) -> None:

        if self.running:
            return

        self.running = True
        self.worker_task = asyncio.create_task(
            self.run_worker()
        )

        LOGGER.info(
            "[Shoutouts] Shoutout queue worker started."
        )

    async def stop(self) -> None:

        self.running = False

        if self.worker_task is not None:
            self.worker_task.cancel()

            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

            self.worker_task = None

        LOGGER.info(
            "[Shoutouts] Shoutout queue worker stopped."
        )

    def enqueue(self, broadcaster_id: str, user_id: str, username: str, requested_by: str) -> tuple[bool, str, int | None]:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        if user_id in self.queued_user_ids[broadcaster_id]:
            return (
                False,
                f"@{username} is already in the shoutout queue.",
                None
            )

        cooldown_until = self.get_target_cooldown_until(
            broadcaster_id,
            user_id
        )

        if cooldown_until is not None:
            remaining = cooldown_until - datetime.now(UTC)
            minutes = max(1, int(remaining.total_seconds() // 60) + 1)

            return (
                False,
                (
                    f"@{username} was already shouted out recently. "
                    f"Try again in about {minutes} minutes."
                ),
                None
            )

        queued_shoutout = QueuedShoutout(
            user_id=user_id,
            username=username,
            requested_by=requested_by,
            queued_at=datetime.now(UTC)
        )

        self.queues[broadcaster_id].append(
            queued_shoutout
        )

        self.queued_user_ids[broadcaster_id].add(
            user_id
        )

        position = len(
            self.queues[broadcaster_id]
        )

        LOGGER.info(
            "[Shoutouts] Queued %s (%s) in broadcaster %s at position %d.",
            username,
            user_id,
            broadcaster_id,
            position
        )

        return (
            True,
            f"@{username} was added to the shoutout queue at position {position}.",
            position
        )

    async def run_worker(self) -> None:

        while self.running:
            try:
                await self.process_queues()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception(
                    "[Shoutouts] Shoutout queue worker failed during processing."
                )

            await asyncio.sleep(
                self.CHECK_INTERVAL_SECONDS
            )

    async def process_queues(self) -> None:

        for broadcaster_id in list(self.queues.keys()):
            await self.process_broadcaster_queue(
                broadcaster_id
            )

    async def process_broadcaster_queue(self, broadcaster_id: str) -> None:

        broadcaster_id = str(broadcaster_id)
        queue = self.queues[broadcaster_id]

        if not queue:
            return

        if self.is_global_cooldown_active(broadcaster_id):
            return

        queued_shoutout = queue[0]

        cooldown_until = self.get_target_cooldown_until(
            broadcaster_id,
            queued_shoutout.user_id
        )

        if cooldown_until is not None:
            queue.popleft()
            self.queued_user_ids[broadcaster_id].discard(
                queued_shoutout.user_id
            )

            LOGGER.info(
                "[Shoutouts] Removed %s (%s) from broadcaster %s queue because the target cooldown became active.",
                queued_shoutout.username,
                queued_shoutout.user_id,
                broadcaster_id
            )
            return

        success = await self.send_native_shoutout(
            broadcaster_id=broadcaster_id,
            target_id=queued_shoutout.user_id,
            username=queued_shoutout.username
        )

        if not success:
            return

        queue.popleft()

        self.queued_user_ids[broadcaster_id].discard(
            queued_shoutout.user_id
        )

        now = datetime.now(UTC)

        self.last_shoutout_at[broadcaster_id] = now
        self.target_last_shoutout_at[broadcaster_id][queued_shoutout.user_id] = now

        LOGGER.info(
            "[Shoutouts] Completed queued shoutout for %s (%s) in broadcaster %s.",
            queued_shoutout.username,
            queued_shoutout.user_id,
            broadcaster_id
        )

    async def send_native_shoutout(self, broadcaster_id: str, target_id: str, username: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        target_id = str(target_id)
        channel = self.bot.create_partialuser(
            broadcaster_id
        )

        try:
            await channel.send_shoutout(
                to_broadcaster=target_id,
                moderator=broadcaster_id
            )
        except Exception:
            LOGGER.exception(
                "[Shoutouts] Failed to send native Twitch shoutout for %s (%s) in broadcaster %s.",
                username,
                target_id,
                broadcaster_id
            )
            return False

        LOGGER.info(
            "[Shoutouts] Sent native Twitch shoutout for %s (%s) in broadcaster %s.",
            username,
            target_id,
            broadcaster_id
        )

        return True

    def is_global_cooldown_active(self, broadcaster_id: str) -> bool:

        broadcaster_id = str(broadcaster_id)
        last_shoutout = self.last_shoutout_at.get(
            broadcaster_id
        )

        if last_shoutout is None:
            return False

        return datetime.now(UTC) < last_shoutout + self.GLOBAL_COOLDOWN

    def get_target_cooldown_until(self, broadcaster_id: str, user_id: str) -> datetime | None:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        last_shoutout = self.target_last_shoutout_at[broadcaster_id].get(
            user_id
        )

        if last_shoutout is None:
            return None

        cooldown_until = last_shoutout + self.TARGET_COOLDOWN

        if datetime.now(UTC) >= cooldown_until:
            self.target_last_shoutout_at[broadcaster_id].pop(
                user_id,
                None
            )
            return None

        return cooldown_until

    def get_queue_position(self, broadcaster_id: str, user_id: str) -> int | None:

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        for index, queued_shoutout in enumerate(
            self.queues[broadcaster_id],
            start=1
        ):
            if queued_shoutout.user_id == user_id:
                return index

        return None

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from twitchio import HTTPException

from bot.profiles import ShoutoutMessages, get_active_profile, render_profile_message

LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class QueuedShoutout:
    user_id: str
    username: str
    requested_by: str
    queued_at: datetime
    attempts: int = 0


class ShoutoutService:
    GLOBAL_COOLDOWN = timedelta(minutes=2)
    TARGET_COOLDOWN = timedelta(hours=1)
    CHECK_INTERVAL_SECONDS = 10
    MAX_ATTEMPTS = 3

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
        self.worker_task = asyncio.create_task(self.run_worker())

        LOGGER.info("[Shoutouts] Shoutout queue worker started.")

    async def stop(self) -> None:
        self.running = False

        if self.worker_task is not None:
            self.worker_task.cancel()

            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

            self.worker_task = None

        LOGGER.info("[Shoutouts] Shoutout queue worker stopped.")

    def enqueue(self, broadcaster_id: str, user_id: str, username: str, requested_by: str) -> tuple[bool, str, int | None]:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        queued_user_ids = self.queued_user_ids[broadcaster_id]

        if user_id in queued_user_ids:
            return False, f"@{username} is already in the shoutout queue.", None

        cooldown_until = self.get_target_cooldown_until(broadcaster_id, user_id)

        if cooldown_until is not None:
            remaining = cooldown_until - datetime.now(UTC)
            minutes = max(1, int(remaining.total_seconds() // 60) + 1)
            message = f"@{username} was already shouted out recently. Try again in about {minutes} minutes."

            return False, message, None

        queued_shoutout = QueuedShoutout(
            user_id=user_id,
            username=username,
            requested_by=requested_by,
            queued_at=datetime.now(UTC)
        )

        queue = self.queues[broadcaster_id]
        queue.append(queued_shoutout)
        queued_user_ids.add(user_id)

        position = len(queue)

        LOGGER.info(
            "[Shoutouts] Queued %s (%s) in broadcaster %s at position %d.",
            username,
            user_id,
            broadcaster_id,
            position
        )

        return True, f"@{username} was added to the shoutout queue at position {position}.", position

    async def send_chat_message(self, broadcaster_id: str, username: str, template: str | None = None) -> bool:
        broadcaster_id = str(broadcaster_id)

        try:
            target = await self.bot.fetch_user(login=username)
            channel_info = await target.fetch_channel_info() if target is not None else None
        except Exception:
            LOGGER.exception("[Shoutouts] Failed to fetch channel information for %s.", username)
            channel_info = None

        game_name = getattr(channel_info, "game_name", None) or ""
        profile = get_active_profile(broadcaster_id)
        messages = profile.shoutout_messages if profile is not None else ShoutoutMessages()
        selected_template = template or (messages.with_game if game_name else messages.without_game)
        message = render_profile_message(
            selected_template,
            username=username,
            game_name=game_name,
            channel_url=f"https://twitch.tv/{username}"
        )

        if not message:
            LOGGER.warning("[Shoutouts] Shoutout message was empty or invalid for broadcaster %s.", broadcaster_id)
            return False

        try:
            channel = self.bot.create_partialuser(broadcaster_id)
            await channel.send_message(sender=self.bot.user, message=message)
        except Exception:
            LOGGER.exception("[Shoutouts] Failed to send shoutout message for %s in broadcaster %s.", username, broadcaster_id)
            return False

        LOGGER.info("[Shoutouts] Sent shoutout message for %s in broadcaster %s.", username, broadcaster_id)
        return True

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

            await asyncio.sleep(self.CHECK_INTERVAL_SECONDS)

    async def process_queues(self) -> None:
        for broadcaster_id in list(self.queues):
            await self.process_broadcaster_queue(broadcaster_id)

    async def process_broadcaster_queue(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        queue = self.queues[broadcaster_id]

        if not queue:
            return

        if self.is_global_cooldown_active(broadcaster_id):
            return

        queued_shoutout = queue[0]
        cooldown_until = self.get_target_cooldown_until(broadcaster_id, queued_shoutout.user_id)

        if cooldown_until is not None:
            queue.popleft()
            self.queued_user_ids[broadcaster_id].discard(queued_shoutout.user_id)

            LOGGER.info(
                "[Shoutouts] Removed %s (%s) from broadcaster %s queue because the target cooldown became active.",
                queued_shoutout.username,
                queued_shoutout.user_id,
                broadcaster_id
            )
            return

        result = await self.send_native_shoutout(
            broadcaster_id=broadcaster_id,
            target_id=queued_shoutout.user_id,
            username=queued_shoutout.username
        )

        if result == "global_cooldown":
            return

        if result == "failed":
            attempts = queued_shoutout.attempts + 1

            if attempts < self.MAX_ATTEMPTS:
                queue[0] = replace(queued_shoutout, attempts=attempts)

                LOGGER.warning(
                    "[Shoutouts] Native shoutout attempt %d of %d failed for %s (%s) in broadcaster %s. The shoutout will be retried.",
                    attempts,
                    self.MAX_ATTEMPTS,
                    queued_shoutout.username,
                    queued_shoutout.user_id,
                    broadcaster_id
                )
                return

            queue.popleft()
            self.queued_user_ids[broadcaster_id].discard(queued_shoutout.user_id)

            LOGGER.error(
                "[Shoutouts] Removed %s (%s) from broadcaster %s queue after %d failed native shoutout attempts.",
                queued_shoutout.username,
                queued_shoutout.user_id,
                broadcaster_id,
                attempts
            )
            return

        queue.popleft()
        self.queued_user_ids[broadcaster_id].discard(queued_shoutout.user_id)

        if result == "target_cooldown":
            LOGGER.info(
                "[Shoutouts] Removed %s (%s) from broadcaster %s queue because Twitch reported an active target cooldown.",
                queued_shoutout.username,
                queued_shoutout.user_id,
                broadcaster_id
            )
            return

        now = datetime.now(UTC)
        self.last_shoutout_at[broadcaster_id] = now
        self.target_last_shoutout_at[broadcaster_id][queued_shoutout.user_id] = now

        LOGGER.info(
            "[Shoutouts] Completed queued shoutout for %s (%s) in broadcaster %s.",
            queued_shoutout.username,
            queued_shoutout.user_id,
            broadcaster_id
        )

    async def send_native_shoutout(self, broadcaster_id: str, target_id: str, username: str) -> str:
        broadcaster_id = str(broadcaster_id)
        target_id = str(target_id)
        channel = self.bot.create_partialuser(broadcaster_id)

        try:
            await channel.send_shoutout(to_broadcaster=target_id, moderator=broadcaster_id)
        except HTTPException as error:
            message = str(error.extra.get("message", "")).lower()

            if error.status == 429 and "specified streamer" in message:
                self.target_last_shoutout_at[broadcaster_id][target_id] = datetime.now(UTC)

                LOGGER.info(
                    "[Shoutouts] Twitch reported that %s (%s) is already under the target cooldown in broadcaster %s.",
                    username,
                    target_id,
                    broadcaster_id
                )

                return "target_cooldown"

            if error.status == 429:
                self.last_shoutout_at[broadcaster_id] = datetime.now(UTC)

                LOGGER.info(
                    "[Shoutouts] Twitch reported that broadcaster %s is under the global shoutout cooldown.",
                    broadcaster_id
                )

                return "global_cooldown"

            LOGGER.exception(
                "[Shoutouts] Failed to send native Twitch shoutout for %s (%s) in broadcaster %s.",
                username,
                target_id,
                broadcaster_id
            )

            return "failed"
        except Exception:
            LOGGER.exception(
                "[Shoutouts] Failed to send native Twitch shoutout for %s (%s) in broadcaster %s.",
                username,
                target_id,
                broadcaster_id
            )

            return "failed"

        LOGGER.info(
            "[Shoutouts] Sent native Twitch shoutout for %s (%s) in broadcaster %s.",
            username,
            target_id,
            broadcaster_id
        )

        return "success"

    def is_global_cooldown_active(self, broadcaster_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        last_shoutout = self.last_shoutout_at.get(broadcaster_id)

        if last_shoutout is None:
            return False

        return datetime.now(UTC) < last_shoutout + self.GLOBAL_COOLDOWN

    def get_target_cooldown_until(self, broadcaster_id: str, user_id: str) -> datetime | None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        target_cooldowns = self.target_last_shoutout_at[broadcaster_id]
        last_shoutout = target_cooldowns.get(user_id)

        if last_shoutout is None:
            return None

        cooldown_until = last_shoutout + self.TARGET_COOLDOWN

        if datetime.now(UTC) >= cooldown_until:
            target_cooldowns.pop(user_id, None)
            return None

        return cooldown_until

    def get_queue_position(self, broadcaster_id: str, user_id: str) -> int | None:
        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        for index, queued_shoutout in enumerate(self.queues[broadcaster_id], start=1):
            if queued_shoutout.user_id == user_id:
                return index

        return None

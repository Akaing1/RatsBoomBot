import asyncio
import logging
import time

from bot.profiles import FeatureName, get_active_profile
from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")


class PassivePointsService:
    POINTS_PER_INTERVAL = 10
    INTERVAL_SECONDS = 120

    def __init__(self, bot, db, points, chat_identity, features):
        self.bot = bot
        self.db = db
        self.points = points
        self.chat_identity = chat_identity
        self.features = features
        self.tasks: dict[str, asyncio.Task] = {}

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS passive_point_payouts (
                    broadcaster_id TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    interval_started_at INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    awarded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (broadcaster_id, stream_id, interval_started_at, user_id)
                )
                """
            )

        LOGGER.info("[Passive Points] Passive earning storage is ready.")

    async def start_for_stream(self, broadcaster_id: str, stream_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        await self.stop_for_stream(broadcaster_id)
        self.tasks[broadcaster_id] = asyncio.create_task(
            self._run(broadcaster_id, str(stream_id)),
            name=f"passive-points-{broadcaster_id}"
        )
        LOGGER.info(
            "[Passive Points] Started passive earnings for broadcaster %s.",
            broadcaster_id,
            extra={"broadcaster_id": broadcaster_id, "category": "POINTS"}
        )

    async def stop_for_stream(self, broadcaster_id: str) -> None:
        task = self.tasks.pop(str(broadcaster_id), None)

        if task is None:
            return

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def stop(self) -> None:
        tasks = tuple(self.tasks.values())
        self.tasks.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, broadcaster_id: str, stream_id: str) -> None:
        while True:
            await asyncio.sleep(self.INTERVAL_SECONDS)

            try:
                await self.award_interval(broadcaster_id, stream_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception(
                    "[Passive Points] Failed to award a passive interval for broadcaster %s.",
                    broadcaster_id,
                    extra={"broadcaster_id": broadcaster_id, "category": "POINTS"}
                )

    async def award_interval(
        self,
        broadcaster_id: str,
        stream_id: str,
        *,
        interval_started_at: int | None = None
    ) -> int:
        broadcaster_id = str(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None or not self.features.is_enabled(broadcaster_id, FeatureName.POINTS):
            return 0

        moderator_id = str(self.chat_identity.sender_id(broadcaster_id))
        broadcaster = self.bot.create_partialuser(broadcaster_id)
        response = await broadcaster.fetch_chatters(
            moderator=moderator_id,
            first=1000,
            max_results=None
        )
        excluded_ids = {broadcaster_id, str(self.bot.bot_id)}
        eligible = []

        for chatter in getattr(response, "users", ()):
            user_id = str(chatter.id)
            username = str(chatter.name)

            if (
                user_id in excluded_ids
                or self.chat_identity.is_custom_bot(user_id)
                or username.lower() in settings.IGNORED_USERS
            ):
                continue

            eligible.append((user_id, username))

        if not eligible:
            return 0

        window = interval_started_at
        if window is None:
            window = int(time.time()) // self.INTERVAL_SECONDS * self.INTERVAL_SECONDS

        awarded = 0

        async with self.db.acquire() as connection:
            for user_id, username in eligible:
                await connection.execute(
                    """
                    INSERT OR IGNORE INTO passive_point_payouts (
                        broadcaster_id, stream_id, interval_started_at, user_id, points
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (broadcaster_id, str(stream_id), int(window), user_id, self.POINTS_PER_INTERVAL)
                )
                inserted = await connection.fetchone("SELECT changes() AS count")

                if not inserted or int(inserted["count"]) == 0:
                    continue

                await connection.execute(
                    """
                    INSERT INTO viewers (broadcaster_id, user_id, username, points, messages)
                    VALUES (?, ?, ?, ?, 0)
                    ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
                        username = excluded.username,
                        points = points + excluded.points
                    """,
                    (broadcaster_id, user_id, username, self.POINTS_PER_INTERVAL)
                )

                if self.points.chatter_stats is not None:
                    await self.points.chatter_stats.record_points_earned(
                        broadcaster_id,
                        user_id,
                        self.POINTS_PER_INTERVAL,
                        connection
                    )

                awarded += 1

        if awarded:
            LOGGER.info(
                "[Passive Points] Awarded %d points to %d connected chatter(s).",
                self.POINTS_PER_INTERVAL,
                awarded,
                extra={"broadcaster_id": broadcaster_id, "category": "POINTS"}
            )

        return awarded

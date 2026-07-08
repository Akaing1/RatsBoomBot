import asyncio
import itertools
import logging
import time

LOGGER = logging.getLogger("Bot")


class TimerService:
    INTERVAL_SECONDS = 30 * 60
    REQUIRED_MESSAGES = 20
    CHECK_EVERY_SECONDS = 5

    def __init__(self, bot, broadcasters, broadcaster_settings):
        self.bot = bot
        self.broadcasters = broadcasters
        self.broadcaster_settings = broadcaster_settings
        self._task: asyncio.Task | None = None

        self.message_counts: dict[str, int] = {}
        self.last_announcements: dict[str, float] = {}
        self.message_indexes: dict[str, int] = {}
        self.last_check = 0

    async def start(self) -> None:
        if self._task is not None:
            return

        LOGGER.info("Timer service started.")
        self._task = asyncio.create_task(self.announcement_loop())

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        self._task = None

    def track_message(self, payload) -> None:
        broadcaster_id = payload.broadcaster.id
        broadcaster_name = payload.broadcaster.name

        self.message_counts[broadcaster_id] = (self.message_counts.get(broadcaster_id, 0) + 1)

        self.last_announcements.setdefault(broadcaster_id, time.time())

        LOGGER.info(
            "[%s] Tracked message. Count: %s/%s",
            broadcaster_name,
            self.message_counts[broadcaster_id],
            self.REQUIRED_MESSAGES
        )

    async def announcement_loop(self) -> None:
        await self.bot.wait_until_ready()

        LOGGER.info("Announcement loop started.")

        while True:
            await asyncio.sleep(self.CHECK_EVERY_SECONDS)

            live_broadcasters = await self.broadcasters.get_live_broadcasters()

            if not live_broadcasters:
                if time.time() - self.last_check >= 600:
                    LOGGER.warning("No live broadcasters available for timer announcement.")
                    self.last_check = time.time()
                continue

            now = time.time()

            for broadcaster_id, broadcaster_name in live_broadcasters.items():
                broadcaster_settings = await self.broadcaster_settings.get_settings(broadcaster_id)

                if not broadcaster_settings.timers_enabled:
                    continue

                last_announcement = self.last_announcements.get(broadcaster_id, now)
                message_count = self.message_counts.get(broadcaster_id, 0)
                elapsed = now - last_announcement

                if elapsed < self.INTERVAL_SECONDS:
                    continue

                if message_count < self.REQUIRED_MESSAGES:
                    continue

                await self.send_next_announcement(
                    broadcaster_id,
                    broadcaster_name
                )

                self.message_counts[broadcaster_id] = 0
                self.last_announcements[broadcaster_id] = now

    async def send_next_announcement(self, broadcaster_id: str, broadcaster_name: str, ) -> None:
        settings = await self.broadcaster_settings.get_settings(broadcaster_id)
        messages = self.get_messages(settings)

        if not messages:
            LOGGER.info("No timer messages available for %s.", broadcaster_name)
            return

        index = self.message_indexes.get(broadcaster_id, 0)
        message = messages[index % len(messages)]
        self.message_indexes[broadcaster_id] = index + 1

        try:
            channel = self.bot.create_partialuser(broadcaster_id)

            await channel.send_message(
                sender=self.bot.user,
                message=message
            )

            LOGGER.info(
                "Announcement sent to %s: %s",
                broadcaster_name,
                message
            )

        except Exception as error:
            LOGGER.error(
                "Failed to send announcement to %s: %r",
                broadcaster_name,
                error
            )

    @staticmethod
    def get_messages(settings) -> list[str]:
        messages = []

        if settings.discord_url:
            messages.append(f"Lost something? Maybe you left it in the basement: {settings.discord_url}")

        if settings.youtube_url:
            messages.append(f"Missed something? Go check out Rat's youtube! {settings.youtube_url}")

        messages.append("Ready to gamble? Use !help to get a list of commands you can use!")

        return messages

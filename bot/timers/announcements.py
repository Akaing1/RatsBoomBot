import asyncio
import itertools
import logging
import time

from twitchio.ext import commands

LOGGER = logging.getLogger("Bot")


class AnnouncementTimers(commands.Component):
    INTERVAL_SECONDS = 30
    REQUIRED_MESSAGES = 2
    CHECK_EVERY_SECONDS = 3

    def __init__(self, bot):
        self.bot = bot
        self._task: asyncio.Task | None = None

        self.message_count = 0
        self.last_announcement = time.time()
        self.channels = {}

        self.messages = [
            "Join the Discord: discord.gg/...",
            "Follow me on YouTube: youtube.com/...",
        ]

        self.message_cycle = itertools.cycle(self.messages)

    async def component_load(self) -> None:
        LOGGER.info("Announcement timer component loaded.")
        self._task = asyncio.create_task(self.announcement_loop())

    async def component_teardown(self) -> None:
        if self._task:
            self._task.cancel()

    def track_message(self, payload) -> None:
        self.message_count += 1
        self.channels[payload.broadcaster.id] = payload.broadcaster

        LOGGER.info(
            "Tracked chat message. Count: %s/%s",
            self.message_count,
            self.REQUIRED_MESSAGES,
        )

    async def announcement_loop(self) -> None:
        await self.bot.wait_until_ready()

        LOGGER.info("Announcement timer loop started.")

        while True:
            await asyncio.sleep(self.CHECK_EVERY_SECONDS)

            elapsed = time.time() - self.last_announcement

            LOGGER.info(
                "Timer check: elapsed=%ss, messages=%s/%s, channels=%s",
                int(elapsed),
                self.message_count,
                self.REQUIRED_MESSAGES,
                len(self.channels),
            )

            if elapsed < self.INTERVAL_SECONDS:
                continue

            if self.message_count < self.REQUIRED_MESSAGES:
                continue

            if not self.channels:
                LOGGER.warning("No channels available for announcement.")
                continue

            await self.send_next_announcement()

            self.message_count = 0
            self.last_announcement = time.time()

    async def send_next_announcement(self) -> None:
        message = next(self.message_cycle)

        for broadcaster_id in self.channels.keys():
            try:
                channel = self.bot.create_partialuser(id=broadcaster_id)

                await channel.send_message(sender=self.bot.user, message=message, )

                LOGGER.info("Announcement sent to %s: %s", broadcaster_id, message)

            except Exception as error:
                LOGGER.error(
                    "Failed to send announcement to %s: %r",
                    broadcaster_id,
                    error,
                )

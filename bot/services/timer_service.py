import asyncio
import itertools
import logging
import time

LOGGER = logging.getLogger("Bot")


class TimerService:
    INTERVAL_SECONDS = 30 * 60
    REQUIRED_MESSAGES = 20
    CHECK_EVERY_SECONDS = 5

    def __init__(self, bot, channels):
        self.bot = bot
        self._task: asyncio.Task | None = None

        self.message_count = 0
        self.last_announcement = time.time()
        self.channels = channels

        self.messages = [
            "Lost something? Maybe you left it in the basement: https://discord.gg/RnwtqhpPa4",
            "Missed something? Go check out Rat's youtube! https://www.youtube.com/@Ninjakaing",
            "Ready to gamble? using !help to get a list of commands you can use!"
        ]

        self.message_cycle = itertools.cycle(self.messages)

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
        self.message_count += 1
        self.channels.track_channel(payload)

        LOGGER.info(
            "Tracked message. Count: %s/%s",
            self.message_count,
            self.REQUIRED_MESSAGES,
        )

    async def announcement_loop(self) -> None:
        await self.bot.wait_until_ready()

        LOGGER.info("Announcement loop started.")

        while True:
            await asyncio.sleep(self.CHECK_EVERY_SECONDS)

            elapsed = time.time() - self.last_announcement

            # LOGGER.info(
            #     "Timer check: elapsed=%ss, messages=%s/%s, channels=%s",
            #     int(elapsed),
            #     self.message_count,
            #     self.REQUIRED_MESSAGES,
            #     len(self.channels),
            # )

            if elapsed < self.INTERVAL_SECONDS:
                continue

            if self.message_count < self.REQUIRED_MESSAGES:
                continue

            if not self.channels:
                LOGGER.warning("No channels available for timer announcement.")
                continue

            await self.send_next_announcement()

            self.message_count = 0
            self.last_announcement = time.time()

    async def send_next_announcement(self, active_channels: dict[str, str]) -> None:
        message = next(self.message_cycle)

        for broadcaster_id, broadcaster_name in active_channels.items():
            try:
                channel = self.bot.create_partialuser(broadcaster_id)

                await channel.send_message(
                    sender=self.bot.user,
                    message=message,
                )

                LOGGER.info(
                    "Announcement sent to %s: %s",
                    broadcaster_name,
                    message,
                )

            except Exception as error:
                LOGGER.error(
                    "Failed to send announcement to %s: %r",
                    broadcaster_name,
                    error,
                )
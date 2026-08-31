import asyncio
import logging
import time

from bot.profiles import FeatureName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


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
            LOGGER.debug("[Timers] Timer service is already running.")
            return

        LOGGER.info("[Timers] Starting timer service.")

        self._task = asyncio.create_task(self.announcement_loop(), name="timer-announcement-loop")

        LOGGER.info("[Timers] Timer service started.")

    async def stop(self) -> None:
        if self._task is None:
            LOGGER.debug("[Timers] Timer service is not running.")
            return

        LOGGER.info("[Timers] Stopping timer service.")

        task = self._task
        self._task = None
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            LOGGER.exception(
                "[Timers] Timer announcement task failed during shutdown."
            )

        LOGGER.info("[Timers] Timer service stopped.")

    def track_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name

        if not self.bot.services:
            return

        if not self.bot.services.features.is_enabled(broadcaster_id, FeatureName.TIMERS):
            return

        self.message_counts[broadcaster_id] = self.message_counts.get(broadcaster_id, 0) + 1
        self.last_announcements.setdefault(broadcaster_id, time.time())

        LOGGER.debug(
            "[Timers] Tracked message for %s (%s). Count: %d/%d.",
            broadcaster_name,
            broadcaster_id,
            self.message_counts[broadcaster_id],
            self.REQUIRED_MESSAGES
        )

    async def announcement_loop(self) -> None:
        try:
            await self.bot.wait_until_ready()

            LOGGER.info("[Timers] Announcement loop started.")

            while True:
                await asyncio.sleep(self.CHECK_EVERY_SECONDS)

                try:
                    await self.check_announcements()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception(
                        "[Timers] Announcement check failed."
                    )
        except asyncio.CancelledError:
            LOGGER.debug("[Timers] Announcement loop cancelled.")
            raise
        except Exception:
            LOGGER.exception(
                "[Timers] Announcement loop terminated unexpectedly."
            )
            raise

    async def check_announcements(self) -> None:
        live_broadcasters = await self.broadcasters.get_live_broadcasters()

        if not live_broadcasters:
            now = time.time()

            if now - self.last_check >= 600:
                LOGGER.info(
                    "[Timers] No live broadcasters are available for announcements."
                )
                self.last_check = now

            return

        now = time.time()

        for broadcaster_id, broadcaster_name in live_broadcasters.items():
            if not self.bot.services.features.is_enabled(broadcaster_id, FeatureName.TIMERS):
                LOGGER.debug(
                    "[Timers] Timer feature is disabled for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                continue

            settings = await self.broadcaster_settings.get_settings(broadcaster_id)

            if not settings.timers_enabled:
                LOGGER.debug(
                    "[Timers] Announcements are disabled for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                continue

            last_announcement = self.last_announcements.get(broadcaster_id, now)
            message_count = self.message_counts.get(broadcaster_id, 0)
            elapsed = now - last_announcement

            if elapsed < self.INTERVAL_SECONDS:
                continue

            if message_count < self.REQUIRED_MESSAGES:
                LOGGER.debug(
                    "[Timers] %s has %d/%d required messages for an announcement.",
                    broadcaster_name,
                    message_count,
                    self.REQUIRED_MESSAGES
                )
                continue

            sent = await self.send_next_announcement(broadcaster_id, broadcaster_name)

            if not sent:
                continue

            self.message_counts[broadcaster_id] = 0
            self.last_announcements[broadcaster_id] = now

    async def send_next_announcement(self, broadcaster_id: str, broadcaster_name: str) -> bool:
        broadcaster_id = str(broadcaster_id)

        if not self.bot.services.features.is_enabled(broadcaster_id, FeatureName.TIMERS):
            LOGGER.debug(
                "[Timers] Skipped announcement because timers are disabled for %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return False

        settings = await self.broadcaster_settings.get_settings(broadcaster_id)
        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.warning(
                "[Timers] No active channel profile is available for %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return False

        messages = self.get_messages(profile.timer_messages, settings)

        if not messages:
            LOGGER.debug(
                "[Timers] No timer messages are available for %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return False

        index = self.message_indexes.get(broadcaster_id, 0)
        message = messages[index % len(messages)]

        try:
            channel = self.bot.create_partialuser(broadcaster_id)
            await self.bot.services.chat_identity.send_message(channel, message)
        except Exception:
            LOGGER.exception(
                "[Timers] Failed to send announcement to %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return False

        self.message_indexes[broadcaster_id] = index + 1

        LOGGER.info(
            "[Timers] Sent announcement to %s (%s): %s",
            broadcaster_name,
            broadcaster_id,
            message
        )

        return True

    @staticmethod
    def get_messages(templates: tuple[str, ...], settings) -> list[str]:
        messages: list[str] = []
        values = {"discord_url": settings.discord_url or "", "youtube_url": settings.youtube_url or ""}

        for template in templates:
            if "{discord_url}" in template and not settings.discord_url:
                continue

            if "{youtube_url}" in template and not settings.youtube_url:
                continue

            try:
                message = template.format_map(values).strip()
            except KeyError as error:
                LOGGER.warning(
                    "[Timers] Unknown placeholder %s in timer message: %s",
                    error,
                    template
                )
                continue

            if message:
                messages.append(message)

        return messages

import asyncio
import logging
import time
from dataclasses import replace

from bot.profiles import FeatureName, get_active_profile
from bot.timer_messages import TimerMessage, normalize_timer

LOGGER = logging.getLogger("RatBoomBot")


class TimerService:
    CHECK_EVERY_SECONDS = 5

    def __init__(self, bot, broadcasters, broadcaster_settings):
        self.bot = bot
        self.broadcasters = broadcasters
        self.broadcaster_settings = broadcaster_settings
        self._task: asyncio.Task | None = None

        self.message_counts: dict[str, int] = {}
        self.timer_progress: dict[str, dict[tuple[TimerMessage, int], tuple[float, int]]] = {}
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
        LOGGER.debug(
            "[Timers] Tracked message for %s (%s). Count: %d.",
            broadcaster_name,
            broadcaster_id,
            self.message_counts[broadcaster_id]
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

            profile = get_active_profile(broadcaster_id)
            if profile is None:
                continue
            count = self.message_counts.get(broadcaster_id, 0)
            progress = self.timer_progress.setdefault(broadcaster_id, {})
            occurrences: dict[TimerMessage, int] = {}
            active = set()
            for entry in profile.timer_messages:
                timer = normalize_timer(entry)
                messages = self.get_messages((timer,), settings)
                if not messages:
                    continue
                occurrence = occurrences.get(timer, 0)
                occurrences[timer] = occurrence + 1
                key = (timer, occurrence)
                active.add(key)
                last_sent, last_count = progress.setdefault(key, (now, count))
                if now - last_sent < timer.interval_minutes * 60:
                    continue
                if timer.require_active_chat and count - last_count < timer.minimum_messages:
                    continue
                if await self.send_announcement(broadcaster_id, broadcaster_name, messages[0]):
                    progress[key] = (now, count)
            for key in progress.keys() - active:
                del progress[key]

    async def send_announcement(self, broadcaster_id: str, broadcaster_name: str, message: TimerMessage) -> bool:
        if not self.bot.services.features.is_enabled(broadcaster_id, FeatureName.TIMERS):
            return False
        try:
            channel = self.bot.create_partialuser(broadcaster_id)
            delivery = message.kind
            if message.kind == "announcement":
                try:
                    await self.bot.services.chat_identity.send_announcement(channel, message.message, message.color)
                except Exception:
                    LOGGER.warning("[Timers] Announcement failed for %s; falling back to chat.", broadcaster_id, exc_info=True)
                    await self.bot.services.chat_identity.send_message(channel, message.message)
                    delivery = "message (announcement fallback)"
            else:
                await self.bot.services.chat_identity.send_message(channel, message.message)
        except Exception:
            LOGGER.exception(
                "[Timers] Failed to send announcement to %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return False

        LOGGER.info(
            "[Timers] Sent announcement to %s (%s): %s",
            broadcaster_name,
            broadcaster_id,
            message
        )
        self.bot.services.stream_logs.write(broadcaster_id, "TIMER", f"Sent timer {delivery}: {message.message}")

        return True

    @staticmethod
    def get_messages(templates, settings) -> list[TimerMessage]:
        messages: list[TimerMessage] = []
        values = {"discord_url": settings.discord_url or "", "youtube_url": settings.youtube_url or ""}

        for entry in templates:
            timer = normalize_timer(entry)
            if not timer.enabled:
                continue
            template = timer.message
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
                messages.append(replace(timer, message=message))

        return messages

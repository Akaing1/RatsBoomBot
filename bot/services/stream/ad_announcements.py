import asyncio
import logging
from datetime import datetime, timezone

from bot.profiles import DEFAULT_AD_ANNOUNCEMENT_MESSAGE, FeatureName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


class AdAnnouncementService:
    CHECK_EVERY_SECONDS = 30
    WARNING_SECONDS = 120

    def __init__(self, bot, broadcasters):
        self.bot = bot
        self.broadcasters = broadcasters
        self._task: asyncio.Task | None = None
        self.warned_ads: set[str] = set()

    async def start(self) -> None:
        if self._task is not None:
            LOGGER.debug("[Ads] Ad announcement service is already running.")
            return

        LOGGER.info("[Ads] Starting ad announcement service.")

        self._task = asyncio.create_task(self.ad_loop(), name="ad-announcement-loop")

        LOGGER.info("[Ads] Ad announcement service started.")

    async def stop(self) -> None:
        if self._task is None:
            LOGGER.debug("[Ads] Ad announcement service is not running.")
            return

        LOGGER.info("[Ads] Stopping ad announcement service.")

        task = self._task
        self._task = None
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            LOGGER.exception(
                "[Ads] Ad announcement task failed during shutdown."
            )

        self.warned_ads.clear()

        LOGGER.info("[Ads] Ad announcement service stopped.")

    async def ad_loop(self) -> None:
        try:
            await self.bot.wait_until_ready()

            LOGGER.info("[Ads] Ad announcement loop started.")

            while True:
                await asyncio.sleep(self.CHECK_EVERY_SECONDS)

                try:
                    await self.check_ad_schedules()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception("[Ads] Ad schedule check failed.")
        except asyncio.CancelledError:
            LOGGER.debug("[Ads] Ad announcement loop cancelled.")
            raise
        except Exception:
            LOGGER.exception(
                "[Ads] Ad announcement loop terminated unexpectedly."
            )
            raise

    async def check_ad_schedules(self) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.debug(
                "[Ads] Skipping ad schedule check because services are unavailable."
            )
            return

        active_channels = await self.broadcasters.get_live_broadcasters()

        if not active_channels:
            LOGGER.debug(
                "[Ads] No live broadcasters are available for ad schedule checks."
            )
            return

        now = datetime.now(timezone.utc)
        active_ad_keys: set[str] = set()

        for broadcaster_id, broadcaster_name in active_channels.items():
            if not services.features.is_enabled(broadcaster_id, FeatureName.AD_ANNOUNCEMENTS):
                LOGGER.debug(
                    "[Ads] Skipping ad schedule check because ad announcements are disabled for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                continue

            try:
                broadcaster = self.bot.create_partialuser(broadcaster_id)
                schedule = await broadcaster.fetch_ad_schedule()
            except Exception:
                LOGGER.exception(
                    "[Ads] Failed to fetch ad schedule for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                continue

            next_ad_at = schedule.next_ad_at

            if next_ad_at is None:
                LOGGER.debug(
                    "[Ads] No upcoming ad is scheduled for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                continue

            seconds_until_ad = int((next_ad_at - now).total_seconds())
            ad_key = f"{broadcaster_id}:{next_ad_at.isoformat()}"

            active_ad_keys.add(ad_key)

            if seconds_until_ad <= 0:
                continue

            if seconds_until_ad > self.WARNING_SECONDS:
                LOGGER.debug(
                    "[Ads] Next ad for %s begins in %d seconds.",
                    broadcaster_name,
                    seconds_until_ad
                )
                continue

            if ad_key in self.warned_ads:
                continue

            profile = get_active_profile(broadcaster_id)
            template = profile.ad_announcement_message if profile is not None else DEFAULT_AD_ANNOUNCEMENT_MESSAGE
            minutes, seconds = divmod(seconds_until_ad, 60)

            try:
                message = template.format(time=f"{minutes}:{seconds:02d}")
            except (KeyError, ValueError):
                LOGGER.warning("[Ads] Invalid ad announcement template for %s (%s). Using the default message.", broadcaster_name, broadcaster_id)
                message = DEFAULT_AD_ANNOUNCEMENT_MESSAGE.format(time=f"{minutes}:{seconds:02d}")

            try:
                await broadcaster.send_announcement(moderator=str(self.bot.user.id), message=message, color="purple")
            except Exception:
                LOGGER.warning(
                    "[Ads] Could not send an announcement to %s (%s). Falling back to a chat message.",
                    broadcaster_name,
                    broadcaster_id,
                    exc_info=True
                )

                try:
                    await broadcaster.send_message(sender=self.bot.user, message=message)
                except Exception:
                    LOGGER.exception(
                        "[Ads] Failed to send fallback ad warning to %s (%s).",
                        broadcaster_name,
                        broadcaster_id
                    )
                    continue

            self.warned_ads.add(ad_key)

            LOGGER.info(
                "[Ads] Sent ad announcement to %s (%s) for an ad starting in %d seconds.",
                broadcaster_name,
                broadcaster_id,
                seconds_until_ad
            )

        self.warned_ads.intersection_update(active_ad_keys)

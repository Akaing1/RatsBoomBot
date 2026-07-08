import asyncio
import logging
from datetime import datetime, timezone

LOGGER = logging.getLogger("Bot")


class AdAnnouncementService:
    CHECK_EVERY_SECONDS = 30
    WARNING_SECONDS = 60

    def __init__(self, bot, broadcasters):
        self.bot = bot
        self._task: asyncio.Task | None = None
        self.warned_ads: set[str] = set()
        self.broadcasters = broadcasters

    async def start(self) -> None:
        if self._task is not None:
            return

        LOGGER.info("Ad announcement service started.")
        self._task = asyncio.create_task(self.ad_loop())

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        self._task = None

    async def ad_loop(self) -> None:
        await self.bot.wait_until_ready()

        while True:
            await asyncio.sleep(self.CHECK_EVERY_SECONDS)

            if not self.bot.services:
                continue

            active_channels = await self.broadcasters.get_live_broadcasters()

            for broadcaster_id, broadcaster_name in active_channels.items():
                try:
                    broadcaster = self.bot.create_partialuser(broadcaster_id)
                    schedule = await broadcaster.fetch_ad_schedule()

                    next_ad_at = schedule.next_ad_at
                    if next_ad_at is None:
                        continue

                    now = datetime.now(timezone.utc)
                    seconds_until_ad = int((next_ad_at - now).total_seconds())

                    ad_key = f"{broadcaster_id}:{next_ad_at.isoformat()}"

                    if 0 < seconds_until_ad <= self.WARNING_SECONDS:
                        if ad_key in self.warned_ads:
                            continue

                        await broadcaster.send_message(
                            sender=self.bot.user,
                            message=f"Hide! The humans are coming! Ads starting in ~{seconds_until_ad} seconds!"
                        )

                        self.warned_ads.add(ad_key)
                        LOGGER.info("Ad warning sent to %s", broadcaster_name)

                except Exception as error:
                    LOGGER.error(
                        "Failed checking ad schedule for %s: %r",
                        broadcaster_name,
                        error
                    )

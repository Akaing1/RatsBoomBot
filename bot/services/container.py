import logging

from config.settings import settings

from bot.services.channels import BroadcasterService, BroadcasterSettingsService, FeatureToggleService
from bot.services.engagement import ClipService, CounterService, OverwatchService, PointsService, RedeemService, ViewerQueueService
from bot.services.stream import AdAnnouncementService, ShoutoutService, StreamLogService, TimerService
from bot.services.support import HelpService, ModerationService

LOGGER = logging.getLogger("RatBoomBot")


class ServiceContainer:

    def __init__(self, bot, db, broadcaster_ids):
        self.bot = bot
        self.db = db

        LOGGER.info("[Services] Creating service container.")

        self.broadcasters = BroadcasterService(bot, broadcaster_ids)
        self.broadcaster_settings = BroadcasterSettingsService(db)
        self.features = FeatureToggleService(db)
        self.stream_logs = StreamLogService(bot, self.broadcasters, settings.STREAM_LOGS_PATH)
        self.help = HelpService(bot)
        self.timers = TimerService(bot, self.broadcasters, self.broadcaster_settings)
        self.points = PointsService(bot, db)
        self.counters = CounterService(bot, db)
        self.ads = AdAnnouncementService(bot, self.broadcasters)
        self.viewer_queue = ViewerQueueService(bot)
        self.redeems = RedeemService(bot, db, self.points)
        self.overwatch = OverwatchService(bot, db)
        self.moderation = ModerationService(bot, db)
        self.shoutouts = ShoutoutService(bot)
        self.clips = ClipService(bot)

        LOGGER.info("[Services] Service container created.")

    async def setup(self) -> None:
        LOGGER.info("[Services] Beginning service setup.")

        services = (
            ("BroadcasterService", self.broadcasters),
            ("BroadcasterSettingsService", self.broadcaster_settings),
            ("FeatureToggleService", self.features),
            ("PointsService", self.points),
            ("CounterService", self.counters),
            ("RedeemService", self.redeems),
            ("OverwatchService", self.overwatch),
            ("ModerationService", self.moderation),
            ("StreamLogService", self.stream_logs)
        )

        for name, service in services:
            LOGGER.info("[Services] Setting up %s.", name)

            try:
                await service.setup()
            except Exception:
                LOGGER.exception("[Services] Failed to set up %s.", name)
                raise

            LOGGER.info("[Services] %s setup complete.", name)

        LOGGER.info("[Services] Service setup completed.")

    async def start(self) -> None:
        LOGGER.info("[Services] Starting background services.")

        services = (
            ("TimerService", self.timers),
            ("AdAnnouncementService", self.ads),
            ("ShoutoutService", self.shoutouts)
        )

        for name, service in services:
            LOGGER.info("[Services] Starting %s.", name)

            try:
                await service.start()
            except Exception:
                LOGGER.exception("[Services] Failed to start %s.", name)
                raise

            LOGGER.info("[Services] %s started.", name)

        LOGGER.info("[Services] Background services started.")

    async def stop(self) -> None:
        LOGGER.info("[Shutdown] Stopping services.")

        services = (
            ("TimerService", self.timers),
            ("AdAnnouncementService", self.ads),
            ("ShoutoutService", self.shoutouts),
            ("StreamLogService", self.stream_logs)
        )

        for name, service in services:
            LOGGER.info("[Shutdown] Stopping %s.", name)

            try:
                await service.stop()
            except Exception:
                LOGGER.exception("[Shutdown] Failed while stopping %s.", name)

        LOGGER.info("[Shutdown] All services stopped.")

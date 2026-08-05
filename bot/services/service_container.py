import logging

from config.settings import settings

from bot.services.ad_announcement_service import AdAnnouncementService
from bot.services.broadcaster_service import BroadcasterService
from bot.services.broadcaster_settings_service import BroadcasterSettingsService
from bot.services.counter_service import CounterService
from bot.services.help_service import HelpService
from bot.services.moderation_service import ModerationService
from bot.services.points_service import PointsService
from bot.services.redeem_service import RedeemService
from bot.services.stream_log_service import StreamLogService
from bot.services.timer_service import TimerService
from bot.services.viewer_queue_service import ViewerQueueService
from bot.services.shoutout_service import ShoutoutService
from bot.services.feature_toggle_service import FeatureToggleService

LOGGER = logging.getLogger("RatBoomBot")


class ServiceContainer:

    def __init__(self, bot, db, broadcaster_ids):
        self.bot = bot
        self.db = db

        LOGGER.info("[Services] Creating service container.")

        self.broadcasters = BroadcasterService(bot, broadcaster_ids)
        self.broadcaster_settings = BroadcasterSettingsService(db)

        self.stream_logs = StreamLogService(
            bot,
            self.broadcasters,
            settings.STREAM_LOGS_PATH
        )

        self.help = HelpService(bot)
        self.timers = TimerService(bot, self.broadcasters, self.broadcaster_settings)
        self.broadcaster_settings = BroadcasterSettingsService(db)
        self.features = FeatureToggleService(db)
        self.points = PointsService(bot, db)
        self.counters = CounterService(bot, db)
        self.ads = AdAnnouncementService(bot, self.broadcasters)
        self.viewer_queue = ViewerQueueService(bot)
        self.redeems = RedeemService(bot, db, self.points)
        self.moderation = ModerationService(bot, db)
        self.shoutouts = ShoutoutService(bot)

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

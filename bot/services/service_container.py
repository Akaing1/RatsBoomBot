from config.settings import settings
from bot.services.stream_log_service import StreamLogService
from bot.services.broadcaster_service import BroadcasterService
from bot.services.ad_announcement_service import AdAnnouncementService
from bot.services.broadcaster_settings_service import BroadcasterSettingsService
from bot.services.counter_service import CounterService
from bot.services.help_service import HelpService
from bot.services.points_service import PointsService
from bot.services.redeem_service import RedeemService
from bot.services.timer_service import TimerService
from bot.services.viewer_queue_service import ViewerQueueService


class ServiceContainer:
    def __init__(self, bot, db, broadcaster_ids):
        self.bot = bot
        self.db = db

        self.broadcasters = BroadcasterService(bot, broadcaster_ids)
        self.broadcaster_settings = BroadcasterSettingsService(db)

        self.stream_logs = StreamLogService(
            bot,
            self.broadcasters,
            settings.STREAM_LOGS_PATH
        )

        self.help = HelpService(bot)
        self.timers = TimerService(bot, self.broadcasters, self.broadcaster_settings)
        self.points = PointsService(bot, db)
        self.counters = CounterService(bot, db)
        self.ads = AdAnnouncementService(bot, self.broadcasters)
        self.viewer_queue = ViewerQueueService(bot)
        self.redeems = RedeemService(bot, db, self.points)

    async def setup(self) -> None:
        await self.broadcasters.setup()
        await self.broadcaster_settings.setup()
        await self.points.setup()
        await self.counters.setup()
        await self.redeems.setup()
        await self.stream_logs.setup()

    async def start(self) -> None:
        await self.timers.start()
        await self.ads.start()

    async def stop(self) -> None:
        await self.timers.stop()
        await self.ads.stop()
        await self.stream_logs.stop()

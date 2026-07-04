from bot.services.broadcaster_service import BroadcasterService
from bot.services.ad_announcement_service import AdAnnouncementService
from bot.services.counter_service import CounterService
from bot.services.help_service import HelpService
from bot.services.points_service import PointsService
from bot.services.timer_service import TimerService


class ServiceContainer:
    def __init__(self, bot, db, broadcaster_ids):
        self.bot = bot
        self.db = db

        self.broadcasters = BroadcasterService(bot, broadcaster_ids)

        self.help = HelpService(bot)
        self.timers = TimerService(bot, self.broadcasters)
        self.points = PointsService(bot, db)
        self.counters = CounterService(bot, db)
        self.ads = AdAnnouncementService(bot, self.broadcasters)

    async def setup(self) -> None:
        await self.broadcasters.setup()
        await self.points.setup()
        await self.counters.setup()

    async def start(self) -> None:
        await self.timers.start()
        await self.ads.start()

    async def stop(self) -> None:
        await self.timers.stop()
        await self.ads.stop()

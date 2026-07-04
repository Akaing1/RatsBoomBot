from bot.services.ad_announcement_service import AdAnnouncementService
from bot.services.counter_service import CounterService
from bot.services.help_service import HelpService
from bot.services.points_service import PointsService
from bot.services.timer_service import TimerService


class ServiceContainer:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

        self.help = HelpService(bot)
        self.timers = TimerService(bot)
        self.points = PointsService(bot, db)
        self.counters = CounterService(bot, db)
        self.ads = AdAnnouncementService(bot)

    async def setup(self) -> None:
        await self.points.setup()
        await self.counters.setup()

    async def start(self) -> None:
        await self.timers.start()
        await self.ads.start()

        await self.bot.announce_start_up()

    async def stop(self) -> None:
        await self.timers.stop()

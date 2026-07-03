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

    async def setup(self) -> None:
        await self.points.setup()

    async def start(self) -> None:
        await self.timers.start()

    async def stop(self) -> None:
        await self.timers.stop()
from bot.services.timer_service import TimerService


class ServiceContainer:
    def __init__(self, bot):
        self.bot = bot
        self.timers = TimerService(bot)

    async def start(self) -> None:
        await self.timers.start()

    async def stop(self) -> None:
        await self.timers.stop()
from time import perf_counter

from twitchio.ext import commands

from bot.command_timing import log_command_timing
from bot.profiles import get_active_profile


class ChannelContext(commands.Context):

    def _get_command(self, reset: bool = False) -> None:
        super()._get_command(reset=reset)
        if self.command is not None or not self.prefix or not self.invoked_with:
            return
        profile = get_active_profile(str(self.broadcaster.id))
        if profile is not None and self.invoked_with.casefold() == profile.points.command_alias:
            self._command = self.bot.get_command("points")

    async def _send_with_timing(self, content: str, *, me: bool, reply: bool):
        started = perf_counter()
        log_command_timing(self, "send_start")
        try:
            services = getattr(self.bot, "services", None)
            if services is None or (reply and self.message is None):
                result = await super().reply(content, me=me) if reply else await super().send(content, me=me)
            elif reply:
                result = await services.chat_identity.send_message(self.broadcaster, content, reply_to_message_id=self.message.id, me=me)
            else:
                result = await services.chat_identity.send_message(self.broadcaster, content, me=me)
        except Exception:
            log_command_timing(self, "send_failed", send_ms=(perf_counter() - started) * 1000)
            raise
        log_command_timing(self, "send_complete", send_ms=(perf_counter() - started) * 1000, result=result)
        return result

    async def send(self, content: str, *, me: bool = False):
        return await self._send_with_timing(content, me=me, reply=False)

    async def reply(self, content: str, *, me: bool = False):
        return await self._send_with_timing(content, me=me, reply=True)

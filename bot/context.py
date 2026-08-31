from twitchio.ext import commands


class ChannelContext(commands.Context):

    async def send(self, content: str, *, me: bool = False):
        services = getattr(self.bot, "services", None)

        if services is None:
            return await super().send(content, me=me)

        return await services.chat_identity.send_message(self.broadcaster, content, me=me)

    async def reply(self, content: str, *, me: bool = False):
        services = getattr(self.bot, "services", None)

        if services is None or self.message is None:
            return await super().reply(content, me=me)

        return await services.chat_identity.send_message(self.broadcaster, content, reply_to_message_id=self.message.id, me=me)

from twitchio import User
from twitchio.ext import commands

from bot.shared.commands.helpers import get_context_broadcaster_id


class LocalizedUser(commands.Converter[User]):

    async def convert(self, ctx: commands.Context, argument: str) -> User:
        services = ctx.bot.services

        if services is None:
            raise commands.BadArgument("User lookup is unavailable.", value=argument)

        broadcaster_id = get_context_broadcaster_id(ctx)
        user = await services.chatters.resolve(broadcaster_id, argument)

        if user is None:
            raise commands.BadArgument(f'Could not find a Twitch user matching "{argument}".', value=argument)

        return user

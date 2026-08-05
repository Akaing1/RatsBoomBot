from typing import Any

from twitchio.ext import commands

from bot.profiles import ChannelProfile, FeatureName


class ChannelComponent(commands.Component):
    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        self.bot = bot
        self.profile = profile
        self.broadcaster_id = str(broadcaster_id)

    @staticmethod
    def get_context_broadcaster_id(ctx: Any) -> str | None:
        broadcaster = getattr(ctx, "broadcaster", None)
        broadcaster_id = getattr(broadcaster, "id", None)

        if broadcaster_id is not None:
            return str(broadcaster_id)

        channel = getattr(ctx, "channel", None)
        channel_id = getattr(channel, "id", None)

        if channel_id is not None:
            return str(channel_id)

        message = getattr(ctx, "message", None)
        message_broadcaster = getattr(message, "broadcaster", None)
        message_broadcaster_id = getattr(
            message_broadcaster,
            "id",
            None
        )

        if message_broadcaster_id is not None:
            return str(message_broadcaster_id)

        return None

    def is_profile_channel(self, ctx: Any) -> bool:
        context_broadcaster_id = self.get_context_broadcaster_id(ctx)
        return context_broadcaster_id == self.broadcaster_id

    async def require_profile_channel(self, ctx: commands.Context) -> bool:
        if not self.is_profile_channel(ctx):
            return False

        if not self.bot.services:
            return False

        return self.bot.services.features.is_enabled(self.broadcaster_id, FeatureName.CHANNEL)

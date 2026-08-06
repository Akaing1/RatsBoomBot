from typing import Any

from twitchio.ext import commands

from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName


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
    message_broadcaster_id = getattr(message_broadcaster, "id", None)

    if message_broadcaster_id is not None:
        return str(message_broadcaster_id)

    return None


def is_feature_enabled(bot, ctx: commands.Context, feature: FeatureName) -> bool:
    broadcaster_id = get_context_broadcaster_id(ctx)
    services = bot.services

    if broadcaster_id is None or services is None:
        return False

    return services.features.is_enabled(broadcaster_id, feature)


def is_global_group_enabled(bot, ctx: commands.Context, group: GlobalCommandGroup) -> bool:
    broadcaster_id = get_context_broadcaster_id(ctx)
    services = bot.services

    if broadcaster_id is None or services is None:
        return False

    return services.features.is_global_group_enabled(broadcaster_id, group)


def is_global_command_enabled(bot, ctx: commands.Context, command: GlobalCommandName) -> bool:
    broadcaster_id = get_context_broadcaster_id(ctx)
    services = bot.services

    if broadcaster_id is None or services is None:
        return False

    return services.features.is_global_command_enabled(broadcaster_id, command)

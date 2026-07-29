import logging

from twitchio.ext import commands

from bot.channels import register_channel_profiles
from bot.shared.commands.counters import CounterCommands
from bot.shared.commands.moderation import ModerationCommands
from bot.shared.commands.points import PointsCommands
from bot.shared.commands.settings import SettingsCommands
from bot.shared.commands.shoutout import ShoutoutCommands
from bot.shared.commands.socials import SocialCommands
from bot.shared.commands.utility import UtilityCommands
from bot.shared.commands.viewer_queue import ViewerQueueCommands
from bot.shared.events.chat import ChatEvents
from bot.shared.events.community import CommunityEvents
from bot.shared.events.raids import RaidEvents
from bot.shared.events.redeems import RedeemEvents
from bot.shared.events.streams import StreamEvents
from bot.profiles import CHANNEL_PROFILES

LOGGER = logging.getLogger("Bot")

GLOBAL_COMPONENTS: tuple[type[commands.Component], ...] = (
    UtilityCommands,
    SocialCommands,
    PointsCommands,
    ModerationCommands,
    CounterCommands,
    ViewerQueueCommands,
    ShoutoutCommands,
    SettingsCommands,
    ChatEvents,
    CommunityEvents,
    RedeemEvents,
    RaidEvents,
    StreamEvents
)


async def load_global_components(bot) -> None:
    for component_class in GLOBAL_COMPONENTS:
        await bot.add_component(component_class(bot))


async def load_channel_components(bot) -> None:
    register_channel_profiles()

    active_broadcaster_ids = {
        str(broadcaster_id)
        for broadcaster_id in bot.broadcaster_ids
    }

    for broadcaster_id, profile in CHANNEL_PROFILES.items():
        if broadcaster_id not in active_broadcaster_ids:
            LOGGER.info(
                "Skipping inactive channel profile: %s (%s)",
                profile.channel_name,
                broadcaster_id
            )
            continue

        LOGGER.info(
            "Loading channel profile: %s (%s)",
            profile.channel_name,
            broadcaster_id
        )

        for component_class in profile.components:
            await bot.add_component(component_class(bot, profile))


async def load_components(bot) -> None:
    await load_global_components(bot)
    await load_channel_components(bot)

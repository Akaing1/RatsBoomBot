from twitchio.ext import commands

from bot.channels import register_channel_profiles
from bot.global.commands.counters import CounterCommands
from bot.global.commands.moderation import ModerationCommands
from bot.global.commands.points import PointsCommands
from bot.global.commands.settings import SettingsCommands
from bot.global.commands.shoutout import ShoutoutCommands
from bot.global.commands.socials import SocialCommands
from bot.global.commands.utility import UtilityCommands
from bot.global.commands.viewer_queue import ViewerQueueCommands
from bot.global.events.chat import ChatEvents
from bot.global.events.community import CommunityEvents
from bot.global.events.raids import RaidEvents
from bot.global.events.redeems import RedeemEvents
from bot.global.events.streams import StreamEvents
from bot.profiles import CHANNEL_PROFILES


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


async def load_components(bot) -> None:
    for component_class in GLOBAL_COMPONENTS:
        await bot.add_component(component_class(bot))

    register_channel_profiles()

    active_broadcaster_ids = {str(broadcaster_id) for broadcaster_id in bot.broadcaster_ids}

    for broadcaster_id, profile in CHANNEL_PROFILES.items():
        if broadcaster_id not in active_broadcaster_ids:
            continue

        for component_class in profile.components:
            await bot.add_component(component_class(bot, profile))

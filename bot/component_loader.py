import logging

from twitchio.ext import commands

from bot.channels import register_channel_profiles
from bot.profiles import CHANNEL_PROFILES
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


async def resolve_profile_users(bot) -> dict[str, object]:
    channel_names = list(CHANNEL_PROFILES.keys())

    if not channel_names:
        return {}

    users = await bot.fetch_users(logins=channel_names)

    return {
        user.name.lower(): user
        for user in users
    }


async def load_channel_components(bot) -> None:
    register_channel_profiles()

    active_broadcaster_ids = {
        str(broadcaster_id)
        for broadcaster_id in bot.broadcaster_ids
    }

    try:
        users_by_login = await resolve_profile_users(bot)
    except Exception:
        LOGGER.exception("Could not resolve channel profile usernames through Twitch.")
        return

    for channel_name, profile in CHANNEL_PROFILES.items():
        user = users_by_login.get(channel_name)

        if user is None:
            LOGGER.warning(
                "Could not find Twitch user for channel profile: %s",
                channel_name
            )
            continue

        broadcaster_id = str(user.id)

        if broadcaster_id not in active_broadcaster_ids:
            LOGGER.info(
                "Skipping unauthorized channel profile: %s (%s)",
                channel_name,
                broadcaster_id
            )
            continue

        LOGGER.info(
            "Loading channel profile: %s (%s)",
            channel_name,
            broadcaster_id
        )

        for component_class in profile.components:
            await bot.add_component(
                component_class(
                    bot,
                    profile,
                    broadcaster_id
                )
            )


async def load_components(bot) -> None:
    await load_global_components(bot)
    await load_channel_components(bot)

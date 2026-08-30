import logging

from twitchio import User
from twitchio.ext import commands

from bot.channels import register_channel_profiles
from bot.profiles import ACTIVE_CHANNEL_PROFILES, CHANNEL_PROFILES, activate_profile, create_generic_profile
from bot.shared.commands.counters import CounterCommands
from bot.shared.commands.league import LeagueCommands
from bot.shared.commands.clips import ClipCommands
from bot.shared.commands.mod_actions import ModActionCommands
from bot.shared.commands.overwatch import OverwatchCommands
from bot.shared.commands.points import PointsCommands
from bot.shared.commands.raid_boss import RaidBossCommands
from bot.shared.commands.raids import RaidCommands
from bot.shared.commands.settings import SettingsCommands
from bot.shared.commands.shoutout import ShoutoutCommands
from bot.shared.commands.socials import SocialCommands
from bot.shared.commands.utility import UtilityCommands
from bot.shared.commands.viewer_queue import ViewerQueueCommands
from bot.shared.events.chat import ChatEvents
from bot.shared.events.community import CommunityEvents
from bot.shared.events.moderation import ModerationEvents
from bot.shared.events.raids import RaidEvents
from bot.shared.events.redeems import RedeemEvents
from bot.shared.events.streams import StreamEvents

LOGGER = logging.getLogger("RatBoomBot")

GLOBAL_COMPONENTS: tuple[type[commands.Component], ...] = (
    UtilityCommands,
    ClipCommands,
    SocialCommands,
    PointsCommands,
    RaidBossCommands,
    RaidCommands,
    ModActionCommands,
    OverwatchCommands,
    CounterCommands,
    LeagueCommands,
    ViewerQueueCommands,
    ShoutoutCommands,
    SettingsCommands,
    ChatEvents,
    CommunityEvents,
    ModerationEvents,
    RedeemEvents,
    RaidEvents,
    StreamEvents
)


async def load_global_components(bot) -> None:
    LOGGER.info(
        "[Components] Loading %d global components.",
        len(GLOBAL_COMPONENTS)
    )

    loaded_count = 0

    for component_class in GLOBAL_COMPONENTS:
        component_name = component_class.__name__

        try:
            await bot.add_component(component_class(bot))
        except Exception:
            LOGGER.exception(
                "[Components] Failed to load global component %s.",
                component_name
            )
            raise

        loaded_count += 1

        LOGGER.debug(
            "[Components] Loaded global component %s.",
            component_name
        )

    LOGGER.info(
        "[Components] Loaded %d global components.",
        loaded_count
    )


async def resolve_profile_users(bot) -> dict[str, User]:
    channel_names = list(CHANNEL_PROFILES)

    if not channel_names:
        LOGGER.info("[Profiles] No channel profiles are registered.")
        return {}

    LOGGER.info(
        "[Profiles] Resolving %d channel profiles through Twitch.",
        len(channel_names)
    )

    users = await bot.fetch_users(logins=channel_names)
    users_by_login = {user.name.lower(): user for user in users}

    LOGGER.info(
        "[Profiles] Resolved %d of %d configured channel profiles.",
        len(users_by_login),
        len(channel_names)
    )

    return users_by_login


async def load_channel_components(bot) -> None:
    LOGGER.info("[Profiles] Registering channel profiles.")

    register_channel_profiles()

    LOGGER.info(
        "[Profiles] Registered %d channel profiles.",
        len(CHANNEL_PROFILES)
    )

    active_broadcaster_ids = {str(broadcaster_id) for broadcaster_id in bot.broadcaster_ids}

    LOGGER.info(
        "[Profiles] Found %d authorized broadcaster accounts.",
        len(active_broadcaster_ids)
    )

    try:
        users_by_login = await resolve_profile_users(bot)
    except Exception:
        LOGGER.exception(
            "[Profiles] Could not resolve channel profile usernames through Twitch."
        )
        raise

    activated_profiles = 0
    loaded_components = 0

    for channel_name, profile in CHANNEL_PROFILES.items():
        user = users_by_login.get(channel_name)

        if user is None:
            LOGGER.warning(
                "[Profiles] Twitch user could not be resolved for profile %s.",
                channel_name
            )
            continue

        broadcaster_id = str(user.id)

        if broadcaster_id not in active_broadcaster_ids:
            LOGGER.info(
                "[Profiles] Skipping unauthorized profile %s for broadcaster %s.",
                channel_name,
                broadcaster_id
            )
            continue

        if channel_name == "developer_ninjakaing":
            await bot.services.profile_settings.migrate_developer_profile(broadcaster_id, profile)

        profile = bot.services.profile_settings.apply_overrides(broadcaster_id, profile)

        LOGGER.info(
            "[Profiles] Activating profile %s for broadcaster %s.",
            channel_name,
            broadcaster_id
        )

        activate_profile(broadcaster_id, profile)
        activated_profiles += 1

        for component_class in profile.components:
            component_name = component_class.__name__

            try:
                await bot.add_component(component_class(bot, profile, broadcaster_id))
            except Exception:
                LOGGER.exception(
                    "[Components] Failed to load profile component %s for %s.",
                    component_name,
                    channel_name
                )
                raise

            loaded_components += 1

            LOGGER.debug(
                "[Components] Loaded profile component %s for %s.",
                component_name,
                channel_name
            )

        LOGGER.info(
            "[Profiles] Activated profile %s with %d components.",
            channel_name,
            len(profile.components)
        )

    for broadcaster_id in sorted(active_broadcaster_ids - set(ACTIVE_CHANNEL_PROFILES)):
        broadcaster = bot.services.broadcasters.get_broadcasters().get(broadcaster_id)
        channel_name = broadcaster.login if broadcaster is not None and broadcaster.login else f"channel_{broadcaster_id}"
        profile = bot.services.profile_settings.apply_overrides(broadcaster_id, create_generic_profile(channel_name))
        activate_profile(broadcaster_id, profile)
        activated_profiles += 1
        LOGGER.info("[Profiles] Activated generic profile %s for broadcaster %s.", channel_name, broadcaster_id)

    LOGGER.info(
        "[Profiles] Activated %d channel profiles and loaded %d profile components.",
        activated_profiles,
        loaded_components
    )


async def load_components(bot) -> None:
    LOGGER.info("[Components] Beginning component loading.")

    await load_global_components(bot)
    await load_channel_components(bot)

    LOGGER.info("[Components] Component loading completed.")

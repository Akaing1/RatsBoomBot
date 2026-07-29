import logging
from dataclasses import dataclass

from twitchio.ext import commands


LOGGER = logging.getLogger("Bot")


@dataclass(frozen=True)
class CommunityMessages:
    follow: str | None = None
    subscription: str | None = None
    resubscription: str | None = None


@dataclass(frozen=True)
class RaidMessages:
    incoming: str | None = None


@dataclass(frozen=True)
class RedeemMessages:
    stream_offline: str = "@{username}, this redeem only works while the stream is live."
    daily_already_claimed: str = "@{username}, you already claimed your stream daily reward."
    daily_success: str = (
        "@{username} claimed their stream daily reward and received "
        "{amount} points! They have collected their daily reward "
        "{claim_count} times!"
    )
    daily_double: str = (
        "Lucky day! @{username} received a double daily reward of "
        "{amount} points! They have collected their daily reward "
        "{claim_count} times!"
    )
    daily_milestone: str = (
        " Milestone! @{username} has collected their daily reward "
        "{claim_count} times!"
    )
    first_already_claimed_by: str = (
        "@{username}, this stream's first redeem was already "
        "claimed by @{winner}."
    )
    first_already_claimed: str = "@{username}, this stream's first redeem was already claimed."
    first_success: str = (
        "@{username} was first this stream and received "
        "{amount} points! They have claimed first "
        "{claim_count} times!"
    )
    first_milestone: str = (
        " Milestone! @{username} has claimed first "
        "{claim_count} times!"
    )


@dataclass(frozen=True)
class RedeemConfig:
    enabled: bool = False
    daily_title: str = ""
    first_title: str = ""
    daily_amount: int = 0
    first_amount: int = 0
    daily_double_chance: float = 0.05
    claim_milestones: tuple[int, ...] = (
        10,
        25,
        50,
        100,
        250,
        500,
        1000,
    )
    messages: RedeemMessages = RedeemMessages()


@dataclass(frozen=True)
class ChannelProfile:
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()
    timer_messages: tuple[str, ...] = ()
    community_messages: CommunityMessages = CommunityMessages()
    raid_messages: RaidMessages = RaidMessages()
    redeems: RedeemConfig = RedeemConfig()


CHANNEL_PROFILES: dict[str, ChannelProfile] = {}
ACTIVE_CHANNEL_PROFILES: dict[str, ChannelProfile] = {}


def register_profile(profile: ChannelProfile) -> None:
    channel_name = profile.channel_name.lower()

    if channel_name in CHANNEL_PROFILES:
        raise ValueError(
            f"A channel profile is already registered for {channel_name}."
        )

    CHANNEL_PROFILES[channel_name] = profile


def activate_profile(broadcaster_id: str, profile: ChannelProfile) -> None:
    ACTIVE_CHANNEL_PROFILES[str(broadcaster_id)] = profile


def get_active_profile(broadcaster_id: str) -> ChannelProfile | None:
    return ACTIVE_CHANNEL_PROFILES.get(str(broadcaster_id))


def render_profile_message(template: str | None, **values) -> str | None:
    if not template:
        return None

    try:
        return template.format_map(values).strip()
    except KeyError as error:
        LOGGER.warning(
            "Unknown channel-profile placeholder %s in message: %s",
            error,
            template,
        )
        return None


def clear_profiles() -> None:
    CHANNEL_PROFILES.clear()
    ACTIVE_CHANNEL_PROFILES.clear()

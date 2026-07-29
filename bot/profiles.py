from dataclasses import dataclass

from twitchio.ext import commands


@dataclass(frozen=True)
class ChannelProfile:
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()
    timer_messages: tuple[str, ...] = ()


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


def clear_profiles() -> None:
    CHANNEL_PROFILES.clear()
    ACTIVE_CHANNEL_PROFILES.clear()

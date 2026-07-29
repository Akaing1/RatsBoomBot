from dataclasses import dataclass

from twitchio.ext import commands


@dataclass(frozen=True)
class ChannelProfile:
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()


CHANNEL_PROFILES: dict[str, ChannelProfile] = {}


def register_profile(profile: ChannelProfile) -> None:
    channel_name = profile.channel_name.lower()

    if channel_name in CHANNEL_PROFILES:
        raise ValueError(
            f"A channel profile is already registered for {channel_name}."
        )

    CHANNEL_PROFILES[channel_name] = profile


def get_profile(channel_name: str) -> ChannelProfile | None:
    return CHANNEL_PROFILES.get(channel_name.lower())


def clear_profiles() -> None:
    CHANNEL_PROFILES.clear()

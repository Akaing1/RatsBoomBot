from dataclasses import dataclass

from twitchio.ext import commands


@dataclass(frozen=True)
class ChannelProfile:
    broadcaster_id: str
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()


CHANNEL_PROFILES: dict[str, ChannelProfile] = {}


def register_profile(profile: ChannelProfile) -> None:
    CHANNEL_PROFILES[profile.broadcaster_id] = profile


def get_profile(broadcaster_id: str) -> ChannelProfile | None:
    return CHANNEL_PROFILES.get(str(broadcaster_id))

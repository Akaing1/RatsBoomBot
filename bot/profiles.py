from dataclasses import dataclass

from twitchio.ext import commands


@dataclass(frozen=True)
class ChannelProfile:
    broadcaster_id: str
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()


CHANNEL_PROFILES: dict[str, ChannelProfile] = {}


def register_profile(profile: ChannelProfile) -> None:
    broadcaster_id = str(profile.broadcaster_id)

    if broadcaster_id in CHANNEL_PROFILES:
        raise ValueError(
            f"A channel profile is already registered for broadcaster {broadcaster_id}."
        )

    CHANNEL_PROFILES[broadcaster_id] = profile


def get_profile(broadcaster_id: str) -> ChannelProfile | None:
    return CHANNEL_PROFILES.get(str(broadcaster_id))


def clear_profiles() -> None:
    CHANNEL_PROFILES.clear()

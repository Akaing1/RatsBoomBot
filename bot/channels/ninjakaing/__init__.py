from bot.channels.ninjakaing.profile import NINJAKAING_PROFILE
from bot.profiles import register_profile


def register_channel_profiles() -> None:
    register_profile(NINJAKAING_PROFILE)

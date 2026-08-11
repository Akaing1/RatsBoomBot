from bot.channels.developer_ninjakaing.profile import DEVELOPER_NINJAKAING_PROFILE
from bot.channels.ninjakaing.profile import NINJAKAING_PROFILE
from bot.channels.meinya_yozakura.profile import MEINYA_PROFILE
from bot.profiles import clear_profiles, register_profile


def register_channel_profiles() -> None:
    clear_profiles()

    register_profile(NINJAKAING_PROFILE)
    register_profile(DEVELOPER_NINJAKAING_PROFILE)
    register_profile(MEINYA_PROFILE)
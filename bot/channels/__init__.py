from bot.channels.barbatos2upusr3x.profile import BARBATOS2UPUSR3X_PROFILE
from bot.channels.developer_ninjakaing.profile import DEVELOPER_NINJAKAING_PROFILE
from bot.channels.lunaaratv.profile import LUNAARATV_PROFILE
from bot.channels.meinya_yozakura.profile import MEINYA_PROFILE
from bot.channels.milky_galaxyvt.profile import MILKY_GALAXYVT_PROFILE
from bot.channels.ninjakaing.profile import NINJAKAING_PROFILE
from bot.channels.okkayay.profile import OKKAYAY_PROFILE
from bot.channels.onedaybread.profile import ONEDAYBREAD_PROFILE
from bot.channels.pikalulz.profile import PIKALULZ_PROFILE
from bot.channels.steohanyy.profile import STEOHANYY_PROFILE
from bot.channels.xxemares.profile import XXEMARES_PROFILE
from bot.profiles import clear_profiles, register_profile


def register_channel_profiles() -> None:
    clear_profiles()

    register_profile(NINJAKAING_PROFILE)
    register_profile(DEVELOPER_NINJAKAING_PROFILE)
    register_profile(MEINYA_PROFILE)
    register_profile(MILKY_GALAXYVT_PROFILE)
    register_profile(STEOHANYY_PROFILE)
    register_profile(ONEDAYBREAD_PROFILE)
    register_profile(LUNAARATV_PROFILE)
    register_profile(BARBATOS2UPUSR3X_PROFILE)
    register_profile(XXEMARES_PROFILE)
    register_profile(OKKAYAY_PROFILE)
    register_profile(PIKALULZ_PROFILE)

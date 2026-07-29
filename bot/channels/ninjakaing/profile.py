from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.profiles import ChannelProfile
from config.settings import settings

NINJAKAING_PROFILE = ChannelProfile(
    broadcaster_id=str(settings.OWNER_ID),
    channel_name="ninjakaing",
    components=(
        NinjakaingCommands,
    )
)

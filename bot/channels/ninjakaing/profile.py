from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.profiles import ChannelProfile


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(
        NinjakaingCommands,
    )
)

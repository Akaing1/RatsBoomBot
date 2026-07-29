from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.profiles import ChannelProfile

NINJAKAING_PROFILE = ChannelProfile(
    broadcaster_id="YOUR_TWITCH_BROADCASTER_ID",
    channel_name="ninjakaing",
    components=(NinjakaingCommands,)
)

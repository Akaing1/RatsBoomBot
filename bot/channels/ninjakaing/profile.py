from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.profiles import ChannelProfile


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(
        NinjakaingCommands,
    ),
    timer_messages=(
        "Lost something? Maybe you left it in the basement: {discord_url}",
        "Missed something? Go check out Rat's YouTube! {youtube_url}",
        "Ready to gamble? Use !help to get a list of commands you can use!",
    )
)
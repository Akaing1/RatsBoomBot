from bot.channels.developer_ninjakaing.commands.general import DeveloperNinjakaingCommands
from bot.profiles import ChannelProfile


DEVELOPER_NINJAKAING_PROFILE = ChannelProfile(
    channel_name="developer_ninjakaing",
    components=(
        DeveloperNinjakaingCommands,
    ),
    timer_messages=(
        "Developer timer test message one.",
        "Developer timer test message two.",
    )
)

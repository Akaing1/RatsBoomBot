from bot.channels.developer_ninjakaing.commands.general import DeveloperNinjakaingCommands
from bot.channels.developer_ninjakaing.commands.points import DeveloperPointsCommands
from bot.channels.developer_ninjakaing.profile_details import (
    DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES,
    DEVELOPER_NINJAKAING_POINTS,
    DEVELOPER_NINJAKAING_TIMER_MESSAGES
)
from bot.profiles import (
    ChannelProfile,
    FeatureDefaults
)


DEVELOPER_NINJAKAING_PROFILE = ChannelProfile(
    channel_name="developer_ninjakaing",
    components=(
        DeveloperNinjakaingCommands,
        DeveloperPointsCommands
    ),
    features=FeatureDefaults(
        channel=True,
        timers=True,
        points=True,
        redeems=False,
        community_events=True,
        raid_responses=False,
        kamikaze=False,
        viewer_queue=False,
        shoutouts=True,
        socials=False,
        counters=False
    ),
    timer_messages=DEVELOPER_NINJAKAING_TIMER_MESSAGES,
    community_messages=DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES,
    points=DEVELOPER_NINJAKAING_POINTS
)
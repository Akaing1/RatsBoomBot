from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.channels.ninjakaing.commands.points import NinjakaingPointsCommands
from bot.channels.ninjakaing.profile_details import (
    NINJAKAING_COMMUNITY_MESSAGES,
    NINJAKAING_POINTS,
    NINJAKAING_RAID_MESSAGES,
    NINJAKAING_REDEEMS,
    NINJAKAING_TIMER_MESSAGES
)
from bot.profiles import (
    ChannelProfile,
    FeatureDefaults
)


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(
        NinjakaingCommands,
        NinjakaingPointsCommands
    ),
    features=FeatureDefaults(
        channel=True,
        timers=True,
        points=True,
        redeems=True,
        community_events=True,
        raid_responses=True,
        kamikaze=True,
        viewer_queue=True,
        shoutouts=True,
        socials=True,
        counters=True
    ),
    timer_messages=NINJAKAING_TIMER_MESSAGES,
    community_messages=NINJAKAING_COMMUNITY_MESSAGES,
    raid_messages=NINJAKAING_RAID_MESSAGES,
    redeems=NINJAKAING_REDEEMS,
    points=NINJAKAING_POINTS
)
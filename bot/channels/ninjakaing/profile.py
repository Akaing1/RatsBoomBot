from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.channels.ninjakaing.commands.points import NinjakaingPointsCommands
from bot.channels.ninjakaing.profile_details import NINJAKAING_COMMUNITY_MESSAGES, NINJAKAING_POINTS, NINJAKAING_RAID_MESSAGES, NINJAKAING_REDEEMS, NINJAKAING_SHOUTOUT_MESSAGES, NINJAKAING_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(NinjakaingCommands, NinjakaingPointsCommands),
    features=FeatureDefaults(
        channel=True,
        timers=True,
        points=True,
        redeems=True,
        community_events=True,
        raid_responses=True
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
        viewer_queue=True,
        shoutouts=True,
        socials=True,
        settings=True,
        hi=True,
        choice=True,
        kaboom=True,
        stinky=True,
        lucky=True,
        smart=True,
        lurk=True,
        help=False,
        explode=True,
        reklop=True,
        randy=True,
        bark=True,
        car=True,
        kamikaze=True
    ),
    timer_messages=NINJAKAING_TIMER_MESSAGES,
    community_messages=NINJAKAING_COMMUNITY_MESSAGES,
    raid_messages=NINJAKAING_RAID_MESSAGES,
    shoutout_messages=NINJAKAING_SHOUTOUT_MESSAGES,
    redeems=NINJAKAING_REDEEMS,
    points=NINJAKAING_POINTS
)

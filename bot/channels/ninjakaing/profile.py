from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.channels.ninjakaing.commands.points import NinjakaingPointsCommands
from bot.channels.ninjakaing.profile_details import NINJAKAING_COMMUNITY_MESSAGES, NINJAKAING_POINTS, NINJAKAING_RAID_BOSSES, NINJAKAING_RAID_MESSAGES, NINJAKAING_REDEEMS, NINJAKAING_SHOUTOUT_MESSAGES, NINJAKAING_SOCIAL_MESSAGES, NINJAKAING_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(NinjakaingCommands, NinjakaingPointsCommands),
    shared_counters_enabled=True,
    features=FeatureDefaults(
        channel=True,
        timers=True,
        ad_announcements=True,
        points=True,
        redeems=True,
        community_events=True,
        raid_responses=True,
        raid_bosses=True
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
        viewer_queue=True,
        shoutouts=True,
        socials=True,
        settings=True,
        clips=True,
        hi=True,
        choice=True,
        kaboom=True,
        stinky=True,
        lucky=True,
        smart=True,
        height=True,
        pp=True,
        lurk=True,
        help=False,
        kamikaze=True
    ),
    timer_messages=NINJAKAING_TIMER_MESSAGES,
    community_messages=NINJAKAING_COMMUNITY_MESSAGES,
    raid_messages=NINJAKAING_RAID_MESSAGES,
    shoutout_messages=NINJAKAING_SHOUTOUT_MESSAGES,
    social_messages=NINJAKAING_SOCIAL_MESSAGES,
    redeems=NINJAKAING_REDEEMS,
    points=NINJAKAING_POINTS,
    raid_bosses=NINJAKAING_RAID_BOSSES
)

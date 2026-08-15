from bot.channels.milky_galaxyvt.commands.general import MilkyGalaxyCommands
from bot.channels.milky_galaxyvt.commands.points import MilkyGalaxyPointsCommands
from bot.channels.milky_galaxyvt.profile_details import MILKY_GALAXYVT_COMMUNITY_MESSAGES, MILKY_GALAXYVT_POINTS, MILKY_GALAXYVT_RAID_MESSAGES, MILKY_GALAXYVT_REDEEMS, MILKY_GALAXYVT_TIMER_MESSAGES, MILKY_GALAXYVT_SHOUTOUT_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

MILKY_GALAXYVT_PROFILE = ChannelProfile(
    channel_name="Milky_GalaxyVT",
    components=(MilkyGalaxyCommands,),
    features=FeatureDefaults(
        channel=False,
        timers=False,
        points=False,
        redeems=False,
        community_events=False,
        raid_responses=False
    ),
    globals=GlobalCommandDefaults(
        enabled=False,
        points=False,
        viewer_queue=False,
        shoutouts=False,
        socials=False,
        settings=False,
        hi=False,
        choice=False,
        kaboom=False,
        stinky=False,
        lucky=False,
        smart=False,
        lurk=False,
        help=False,
        explode=False,
        reklop=False,
        randy=False,
        bark=False,
        car=False,
        kamikaze=False
    ),
    timer_messages=MILKY_GALAXYVT_TIMER_MESSAGES,
    community_messages=MILKY_GALAXYVT_COMMUNITY_MESSAGES,
    raid_messages=MILKY_GALAXYVT_RAID_MESSAGES,
    redeems=MILKY_GALAXYVT_REDEEMS,
    points=MILKY_GALAXYVT_POINTS,
    shoutout_messages=MILKY_GALAXYVT_SHOUTOUT_MESSAGES
)

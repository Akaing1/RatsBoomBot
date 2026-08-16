from bot.channels.milky_galaxyvt.commands.general import MilkyGalaxyCommands
from bot.channels.milky_galaxyvt.commands.points import MilkyGalaxyPointsCommands
from bot.channels.milky_galaxyvt.games.overwatch import MilkyGalaxyOverwatchCommands
from bot.channels.milky_galaxyvt.profile_details import MILKY_GALAXYVT_COMMUNITY_MESSAGES, MILKY_GALAXYVT_OVERWATCH, MILKY_GALAXYVT_POINTS, MILKY_GALAXYVT_RAID_MESSAGES, MILKY_GALAXYVT_REDEEMS, MILKY_GALAXYVT_TIMER_MESSAGES, MILKY_GALAXYVT_SHOUTOUT_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

MILKY_GALAXYVT_PROFILE = ChannelProfile(
    channel_name="Milky_GalaxyVT",
    components=(MilkyGalaxyCommands, MilkyGalaxyPointsCommands, MilkyGalaxyOverwatchCommands),
    features=FeatureDefaults(
        channel=True,
        timers=True,
        points=True,
        redeems=True,
        community_events=False,
        raid_responses=True
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
        viewer_queue=False,
        shoutouts=True,
        socials=True,
        settings=True,
        clips=True,
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
        kamikaze=True
    ),
    timer_messages=MILKY_GALAXYVT_TIMER_MESSAGES,
    community_messages=MILKY_GALAXYVT_COMMUNITY_MESSAGES,
    raid_messages=MILKY_GALAXYVT_RAID_MESSAGES,
    redeems=MILKY_GALAXYVT_REDEEMS,
    points=MILKY_GALAXYVT_POINTS,
    shoutout_messages=MILKY_GALAXYVT_SHOUTOUT_MESSAGES,
    overwatch=MILKY_GALAXYVT_OVERWATCH
)

from bot.channels.meinya_yozakura.commands.general import MeinyaCommands
from bot.channels.meinya_yozakura.commands.points import MeinyaPointsCommands
from bot.channels.meinya_yozakura.profile_details import MEINYA_COMMUNITY_MESSAGES, MEINYA_POINTS, MEINYA_RAID_MESSAGES, MEINYA_REDEEMS, MEINYA_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

MEINYA_PROFILE = ChannelProfile(
    channel_name="MeinyaYozakura",
    components=(MeinyaCommands,),
    features=FeatureDefaults(
        channel=False,
        timers=False,
        points=False,
        redeems=False,
        community_events=False,
        raid_responses=False
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
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
        car=False,
        kamikaze=True
    ),
    timer_messages=MEINYA_TIMER_MESSAGES,
    community_messages=MEINYA_COMMUNITY_MESSAGES,
    raid_messages=MEINYA_RAID_MESSAGES,
    redeems=MEINYA_REDEEMS,
    points=MEINYA_POINTS
)

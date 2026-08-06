from bot.channels.developer_ninjakaing.commands.general import DeveloperNinjakaingCommands
from bot.channels.developer_ninjakaing.commands.points import DeveloperPointsCommands
from bot.channels.developer_ninjakaing.profile_details import DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES, DEVELOPER_NINJAKAING_POINTS, DEVELOPER_NINJAKAING_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults


DEVELOPER_NINJAKAING_PROFILE = ChannelProfile(
    channel_name="developer_ninjakaing",
    components=(DeveloperNinjakaingCommands, DeveloperPointsCommands),
    features=FeatureDefaults(
        channel=True,
        timers=True,
        points=True,
        redeems=False,
        community_events=True,
        raid_responses=False
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
        viewer_queue=False,
        shoutouts=True,
        socials=False,
        settings=True,
        hi=True,
        choice=True,
        kaboom=True,
        stinky=True,
        lucky=True,
        smart=True,
        lurk=True,
        help=True,
        explode=False,
        reklop=False,
        randy=False,
        car=False,
        kamikaze=False
    ),
    timer_messages=DEVELOPER_NINJAKAING_TIMER_MESSAGES,
    community_messages=DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES,
    points=DEVELOPER_NINJAKAING_POINTS
)

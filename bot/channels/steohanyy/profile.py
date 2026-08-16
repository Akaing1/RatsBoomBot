from bot.channels.steohanyy.commands.general import SteohanyyCommands
from bot.channels.steohanyy.commands.points import SteohanyyPointsCommands
from bot.channels.steohanyy.profile_details import STEOHANYY_COMMUNITY_MESSAGES, STEOHANYY_POINTS, STEOHANYY_RAID_MESSAGES, STEOHANYY_REDEEMS, STEOHANYY_TIMER_MESSAGES, STEOHANYY_SHOUTOUT_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

STEOHANYY_PROFILE = ChannelProfile(
    channel_name="steohanyy",
    components=(SteohanyyCommands, SteohanyyPointsCommands),
    features=FeatureDefaults(
        channel=True,
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
    timer_messages=STEOHANYY_TIMER_MESSAGES,
    community_messages=STEOHANYY_COMMUNITY_MESSAGES,
    raid_messages=STEOHANYY_RAID_MESSAGES,
    redeems=STEOHANYY_REDEEMS,
    points=STEOHANYY_POINTS,
    shoutout_messages=STEOHANYY_SHOUTOUT_MESSAGES
)

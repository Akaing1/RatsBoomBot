from bot.channels.steohanyy.commands.general import SteohanyyCommands
from bot.channels.steohanyy.commands.points import SteohanyyPointsCommands
from bot.channels.steohanyy.profile_details import STEOHANYY_COMMUNITY_MESSAGES, STEOHANYY_LEAGUE, STEOHANYY_POINTS, STEOHANYY_RAID_MESSAGES, STEOHANYY_REDEEMS, STEOHANYY_SHOUTOUT_MESSAGES, STEOHANYY_SOCIAL_MESSAGES, STEOHANYY_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

STEOHANYY_PROFILE = ChannelProfile(
    channel_name="steohanyy",
    components=(SteohanyyCommands, SteohanyyPointsCommands),
    features=FeatureDefaults(
        channel=True,
        timers=False,
        ad_announcements=False,
        points=True,
        redeems=False,
        community_events=True,
        raid_responses=True
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
        viewer_queue=True,
        shoutouts=True,
        socials=False,
        settings=False,
        clips=True,
        hi=False,
        choice=False,
        kaboom=False,
        stinky=False,
        lucky=False,
        smart=False,
        height=False,
        pp=False,
        lurk=False,
        help=False,
        explode=True,
        reklop=True,
        randy=True,
        bark=False,
        car=True,
        kamikaze=True
    ),
    timer_messages=STEOHANYY_TIMER_MESSAGES,
    community_messages=STEOHANYY_COMMUNITY_MESSAGES,
    raid_messages=STEOHANYY_RAID_MESSAGES,
    redeems=STEOHANYY_REDEEMS,
    points=STEOHANYY_POINTS,
    shoutout_messages=STEOHANYY_SHOUTOUT_MESSAGES,
    social_messages=STEOHANYY_SOCIAL_MESSAGES,
    league=STEOHANYY_LEAGUE
)

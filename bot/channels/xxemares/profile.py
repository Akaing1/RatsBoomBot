from bot.channels.xxemares.commands.general import XxemaresCommands
from bot.channels.xxemares.commands.points import XxemaresPointsCommands
from bot.channels.xxemares.profile_details import XXEMARES_CLIPS, XXEMARES_COMMUNITY_MESSAGES, XXEMARES_FIRST_CHAT_SHOUTOUTS, XXEMARES_POINTS, XXEMARES_RAID_MESSAGES, XXEMARES_REDEEMS, XXEMARES_SHOUTOUT_MESSAGES, XXEMARES_SOCIAL_MESSAGES, XXEMARES_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

XXEMARES_PROFILE = ChannelProfile(
    channel_name="xxemares",
    components=(XxemaresCommands, XxemaresPointsCommands),
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
        clips=False,
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
    timer_messages=XXEMARES_TIMER_MESSAGES,
    community_messages=XXEMARES_COMMUNITY_MESSAGES,
    raid_messages=XXEMARES_RAID_MESSAGES,
    redeems=XXEMARES_REDEEMS,
    points=XXEMARES_POINTS,
    shoutout_messages=XXEMARES_SHOUTOUT_MESSAGES,
    social_messages=XXEMARES_SOCIAL_MESSAGES,
    first_chat_shoutouts=XXEMARES_FIRST_CHAT_SHOUTOUTS,
    clips=XXEMARES_CLIPS,
)

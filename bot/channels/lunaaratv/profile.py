from bot.channels.lunaaratv.commands.general import LunaaratvCommands
from bot.channels.lunaaratv.commands.points import LunaaratvPointsCommands
from bot.channels.lunaaratv.profile_details import LUNAARATV_CLIPS, LUNAARATV_COMMUNITY_MESSAGES, LUNAARATV_FIRST_CHAT_SHOUTOUTS, LUNAARATV_POINTS, LUNAARATV_RAID_MESSAGES, LUNAARATV_REDEEMS, LUNAARATV_SHOUTOUT_MESSAGES, LUNAARATV_SOCIAL_MESSAGES, LUNAARATV_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

LUNAARATV_PROFILE = ChannelProfile(
    channel_name="lunaaratv",
    components=(LunaaratvCommands, LunaaratvPointsCommands),
    features=FeatureDefaults(
        channel=False,
        timers=False,
        ad_announcements=False,
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
        height=False,
        pp=False,
        lurk=False,
        help=False,
        kamikaze=False
    ),
    timer_messages=LUNAARATV_TIMER_MESSAGES,
    community_messages=LUNAARATV_COMMUNITY_MESSAGES,
    raid_messages=LUNAARATV_RAID_MESSAGES,
    redeems=LUNAARATV_REDEEMS,
    points=LUNAARATV_POINTS,
    shoutout_messages=LUNAARATV_SHOUTOUT_MESSAGES,
    social_messages=LUNAARATV_SOCIAL_MESSAGES,
    first_chat_shoutouts=LUNAARATV_FIRST_CHAT_SHOUTOUTS,
    clips=LUNAARATV_CLIPS,
)

from bot.channels.onedaybread.commands.general import OnedaybreadCommands
from bot.channels.onedaybread.commands.points import OnedaybreadPointsCommands
from bot.channels.onedaybread.profile_details import ONEDAYBREAD_CLIPS, ONEDAYBREAD_COMMUNITY_MESSAGES, ONEDAYBREAD_FIRST_CHAT_SHOUTOUTS, ONEDAYBREAD_POINTS, ONEDAYBREAD_RAID_MESSAGES, ONEDAYBREAD_REDEEMS, ONEDAYBREAD_SHOUTOUT_MESSAGES, ONEDAYBREAD_SOCIAL_MESSAGES, ONEDAYBREAD_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

ONEDAYBREAD_PROFILE = ChannelProfile(
    channel_name="onedaybread",
    components=(OnedaybreadCommands, OnedaybreadPointsCommands),
    features=FeatureDefaults(
        channel=True,
        timers=False,
        ad_announcements=False,
        points=True,
        redeems=True,
        community_events=False,
        raid_responses=False
    ),
    globals=GlobalCommandDefaults(
        enabled=True,
        points=True,
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
    timer_messages=ONEDAYBREAD_TIMER_MESSAGES,
    community_messages=ONEDAYBREAD_COMMUNITY_MESSAGES,
    raid_messages=ONEDAYBREAD_RAID_MESSAGES,
    redeems=ONEDAYBREAD_REDEEMS,
    points=ONEDAYBREAD_POINTS,
    shoutout_messages=ONEDAYBREAD_SHOUTOUT_MESSAGES,
    social_messages=ONEDAYBREAD_SOCIAL_MESSAGES,
    first_chat_shoutouts=ONEDAYBREAD_FIRST_CHAT_SHOUTOUTS,
    clips=ONEDAYBREAD_CLIPS,
)

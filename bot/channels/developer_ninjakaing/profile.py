from bot.channels.developer_ninjakaing.commands.general import DeveloperNinjakaingCommands
from bot.channels.developer_ninjakaing.commands.points import DeveloperPointsCommands
from bot.channels.developer_ninjakaing.profile_details import (
    DEVELOPER_NINJAKAING_CLIPS,
    DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES,
    DEVELOPER_NINJAKAING_FIRST_CHAT_SHOUTOUTS,
    DEVELOPER_NINJAKAING_POINTS,
    DEVELOPER_NINJAKAING_RAID_MESSAGES,
    DEVELOPER_NINJAKAING_REDEEMS,
    DEVELOPER_NINJAKAING_SHOUTOUT_MESSAGES,
    DEVELOPER_NINJAKAING_SOCIAL_MESSAGES,
    DEVELOPER_NINJAKAING_TIMER_MESSAGES
)
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

DEVELOPER_NINJAKAING_PROFILE = ChannelProfile(
    channel_name="developer_ninjakaing",
    components=(DeveloperNinjakaingCommands, DeveloperPointsCommands),
    protected_user_ids=("1251948863",),
    shared_counters_enabled=True,
    features=FeatureDefaults(
        channel=True,
        timers=True,
        ad_announcements=False,
        points=True,
        redeems=True,
        community_events=True,
        raid_responses=True
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
        help=True,
        kamikaze=True
    ),
    timer_messages=DEVELOPER_NINJAKAING_TIMER_MESSAGES,
    community_messages=DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES,
    raid_messages=DEVELOPER_NINJAKAING_RAID_MESSAGES,
    shoutout_messages=DEVELOPER_NINJAKAING_SHOUTOUT_MESSAGES,
    social_messages=DEVELOPER_NINJAKAING_SOCIAL_MESSAGES,
    first_chat_shoutouts=DEVELOPER_NINJAKAING_FIRST_CHAT_SHOUTOUTS,
    clips=DEVELOPER_NINJAKAING_CLIPS,
    redeems=DEVELOPER_NINJAKAING_REDEEMS,
    points=DEVELOPER_NINJAKAING_POINTS
)

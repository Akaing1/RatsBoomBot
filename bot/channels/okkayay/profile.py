from bot.channels.okkayay.commands.general import OkkayayCommands
from bot.channels.okkayay.commands.points import OkkayayPointsCommands
from bot.channels.okkayay.profile_details import OKKAYAY_CLIPS, OKKAYAY_COMMUNITY_MESSAGES, OKKAYAY_FIRST_CHAT_SHOUTOUTS, OKKAYAY_POINTS, OKKAYAY_RAID_MESSAGES, OKKAYAY_REDEEMS, OKKAYAY_SHOUTOUT_MESSAGES, OKKAYAY_SOCIAL_MESSAGES, OKKAYAY_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

OKKAYAY_PROFILE = ChannelProfile(
    channel_name="okkayay",
    components=(OkkayayCommands, OkkayayPointsCommands),
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
    timer_messages=OKKAYAY_TIMER_MESSAGES,
    community_messages=OKKAYAY_COMMUNITY_MESSAGES,
    raid_messages=OKKAYAY_RAID_MESSAGES,
    redeems=OKKAYAY_REDEEMS,
    points=OKKAYAY_POINTS,
    shoutout_messages=OKKAYAY_SHOUTOUT_MESSAGES,
    social_messages=OKKAYAY_SOCIAL_MESSAGES,
    first_chat_shoutouts=OKKAYAY_FIRST_CHAT_SHOUTOUTS,
    clips=OKKAYAY_CLIPS,
)

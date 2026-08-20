from bot.channels.pikalulz.commands.general import PikalulzCommands
from bot.channels.pikalulz.commands.points import PikalulzPointsCommands
from bot.channels.pikalulz.profile_details import PIKALULZ_CLIPS, PIKALULZ_COMMUNITY_MESSAGES, PIKALULZ_FIRST_CHAT_SHOUTOUTS, PIKALULZ_POINTS, PIKALULZ_RAID_MESSAGES, PIKALULZ_REDEEMS, PIKALULZ_SHOUTOUT_MESSAGES, PIKALULZ_SOCIAL_MESSAGES, PIKALULZ_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

PIKALULZ_PROFILE = ChannelProfile(
    channel_name="pikalulz",
    components=(PikalulzCommands, PikalulzPointsCommands),
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
        lurk=False,
        help=False,
        explode=False,
        reklop=False,
        randy=False,
        bark=False,
        car=False,
        kamikaze=False
    ),
    timer_messages=PIKALULZ_TIMER_MESSAGES,
    community_messages=PIKALULZ_COMMUNITY_MESSAGES,
    raid_messages=PIKALULZ_RAID_MESSAGES,
    redeems=PIKALULZ_REDEEMS,
    points=PIKALULZ_POINTS,
    shoutout_messages=PIKALULZ_SHOUTOUT_MESSAGES,
    social_messages=PIKALULZ_SOCIAL_MESSAGES,
    first_chat_shoutouts=PIKALULZ_FIRST_CHAT_SHOUTOUTS,
    clips=PIKALULZ_CLIPS,
)

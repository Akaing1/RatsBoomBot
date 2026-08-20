from bot.channels.barbatos2upusr3x.commands.general import Barbatos2upusr3xCommands
from bot.channels.barbatos2upusr3x.commands.points import Barbatos2upusr3xPointsCommands
from bot.channels.barbatos2upusr3x.profile_details import BARBATOS2UPUSR3X_CLIPS, BARBATOS2UPUSR3X_COMMUNITY_MESSAGES, BARBATOS2UPUSR3X_FIRST_CHAT_SHOUTOUTS, BARBATOS2UPUSR3X_POINTS, BARBATOS2UPUSR3X_RAID_MESSAGES, BARBATOS2UPUSR3X_REDEEMS, BARBATOS2UPUSR3X_SHOUTOUT_MESSAGES, BARBATOS2UPUSR3X_SOCIAL_MESSAGES, BARBATOS2UPUSR3X_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

BARBATOS2UPUSR3X_PROFILE = ChannelProfile(
    channel_name="barbatos2upusr3x",
    components=(Barbatos2upusr3xCommands, Barbatos2upusr3xPointsCommands),
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
    timer_messages=BARBATOS2UPUSR3X_TIMER_MESSAGES,
    community_messages=BARBATOS2UPUSR3X_COMMUNITY_MESSAGES,
    raid_messages=BARBATOS2UPUSR3X_RAID_MESSAGES,
    redeems=BARBATOS2UPUSR3X_REDEEMS,
    points=BARBATOS2UPUSR3X_POINTS,
    shoutout_messages=BARBATOS2UPUSR3X_SHOUTOUT_MESSAGES,
    social_messages=BARBATOS2UPUSR3X_SOCIAL_MESSAGES,
    first_chat_shoutouts=BARBATOS2UPUSR3X_FIRST_CHAT_SHOUTOUTS,
    clips=BARBATOS2UPUSR3X_CLIPS,
)

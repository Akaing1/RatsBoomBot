from bot.channels.template_profile.commands.general import TemplateCommands
from bot.channels.template_profile.commands.points import TemplatePointsCommands
from bot.channels.template_profile.profile_details import TEMPLATE_CLIPS, TEMPLATE_COMMUNITY_MESSAGES, TEMPLATE_FIRST_CHAT_SHOUTOUTS, TEMPLATE_POINTS, TEMPLATE_RAID_MESSAGES, TEMPLATE_REDEEMS, TEMPLATE_SHOUTOUT_MESSAGES, TEMPLATE_SOCIAL_MESSAGES, TEMPLATE_TIMER_MESSAGES
from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults

TEMPLATE_PROFILE = ChannelProfile(
    channel_name="template_channel",
    components=(TemplateCommands, TemplatePointsCommands),
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
    timer_messages=TEMPLATE_TIMER_MESSAGES,
    community_messages=TEMPLATE_COMMUNITY_MESSAGES,
    raid_messages=TEMPLATE_RAID_MESSAGES,
    redeems=TEMPLATE_REDEEMS,
    points=TEMPLATE_POINTS,
    shoutout_messages=TEMPLATE_SHOUTOUT_MESSAGES,
    social_messages=TEMPLATE_SOCIAL_MESSAGES,
    first_chat_shoutouts=TEMPLATE_FIRST_CHAT_SHOUTOUTS,
    clips=TEMPLATE_CLIPS,
)

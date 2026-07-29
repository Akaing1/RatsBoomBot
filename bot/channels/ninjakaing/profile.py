from bot.channels.ninjakaing.commands.general import NinjakaingCommands
from bot.profiles import (
    ChannelProfile,
    CommunityMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
)


NINJAKAING_PROFILE = ChannelProfile(
    channel_name="ninjakaing",
    components=(
        NinjakaingCommands,
    ),
    timer_messages=(
        "Lost something? Maybe you left it in the basement: {discord_url}",
        "Missed something? Go check out Rat's YouTube! {youtube_url}",
        "Ready to gamble? Use !help to get a list of commands you can use!",
    ),
    community_messages=CommunityMessages(
        follow=(
            "{username} has snuck their way into the basement! "
            "Thanks for following!"
        ),
        subscription=(
            "{username} has subscribed! Rats stronk together!"
        ),
        resubscription=(
            "{username} resubscribed for {months} months! "
            "Thank you for your continued support!"
        ),
    ),
    raid_messages=RaidMessages(
        incoming=(
            "@{raider_name} has raided the basement with "
            "{viewer_count} {viewer_word}! Rats stronk together!"
        ),
    ),
    redeems=RedeemConfig(
        enabled=True,
        daily_title="Daily Bread",
        first_title="First",
        daily_amount=100,
        first_amount=250,
        daily_double_chance=0.05,
        claim_milestones=(
            10,
            25,
            50,
            100,
            250,
            500,
            1000,
        ),
        messages=RedeemMessages(
            stream_offline=(
                "@{username}, this redeem only works while "
                "the stream is live."
            ),
            daily_already_claimed=(
                "@{username}, you already claimed your stream "
                "daily stale bread."
            ),
            daily_success=(
                "@{username} claimed their stream daily stale bread "
                "and received {amount} bread! They have collected "
                "their daily stale bread {claim_count} times!"
            ),
            daily_double=(
                "Lucky day! @{username} found an extra stale loaf "
                "and received {amount} bread! They have collected "
                "their daily stale bread {claim_count} times!"
            ),
            daily_milestone=(
                " Milestone! @{username} has collected their daily "
                "stale bread {claim_count} times!"
            ),
            first_already_claimed_by=(
                "@{username}, this stream's first redeem was already "
                "claimed by @{winner}."
            ),
            first_already_claimed=(
                "@{username}, this stream's first redeem was "
                "already claimed."
            ),
            first_success=(
                "@{username} was first in the basement this stream "
                "and received {amount} bread! They have stolen the "
                "first bread {claim_count} times!"
            ),
            first_milestone=(
                " Milestone! @{username} has stolen the first bread "
                "{claim_count} times!"
            ),
        ),
    ),
)

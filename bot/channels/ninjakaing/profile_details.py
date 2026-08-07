from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages
)


NINJAKAING_TIMER_MESSAGES = (
    "Lost something? Maybe you left it in the basement: {discord_url}",
    "Missed something? Go check out Rat's YouTube! {youtube_url}",
    "Ready to gamble? Use !help to get a list of commands you can use!"
)


NINJAKAING_COMMUNITY_MESSAGES = CommunityMessages(
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
    )
)


NINJAKAING_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} has raided the basement with "
        "{viewer_count} {viewer_word}! Rats stronk together!"
    )
)


NINJAKAING_REDEEMS = RedeemConfig(
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
        1000
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
            "Milestone! @{username} has collected their daily "
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
            "Milestone! @{username} has stolen the first bread "
            "{claim_count} times!"
        )
    )
)


NINJAKAING_POINTS = PointsConfig(
    command_name="bread",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self=(
            "{username}, you have {points} pieces of stale bread!"
        ),
        balance_other=(
            "{username} has {points} pieces of stale bread!"
        ),
        leaderboard_empty=(
            "No stale bread has been collected yet. "
            "What an upstanding citizen!"
        ),
        leaderboard_entry=(
            "{position}. {username}: {points} bread"
        ),
        leaderboard_title=(
            "Top stale bread hoarders: {leaderboard}"
        ),
        reset_denied=(
            "Only the broadcaster can reset the stale bread stash."
        ),
        reset_success=(
            "This channel's stale bread has been thrown away. "
            "The leaderboard has been reset."
        ),
        add_denied=(
            "Only moderators can add stale bread to viewers."
        ),
        add_invalid=(
            "Bread amount must be greater than 0."
        ),
        add_success=(
            "Added {amount} pieces of stale bread to "
            "{username}'s stash."
        ),
        gamble_no_points=(
            "You don't have any stale bread to gamble."
        ),
        gamble_usage=(
            "Use it like this: !{command} gamble 50 "
            "or !{command} gamble all"
        ),
        gamble_invalid=(
            "You need to gamble at least 1 piece of stale bread."
        ),
        gamble_insufficient=(
            "You only have {points} pieces of stale bread."
        ),
        gamble_win=(
            "{username} found {amount} stale bread on the ground "
            "and now has {new_balance} bread."
        ),
        gamble_all_win=(
            "{username} raided the pantry and found a hidden stash "
            "of stale bread! You now have {new_balance} bread."
        ),
        gamble_loss=(
            "{username} got caught by a rat trap and lost {amount} "
            "stale bread and now has {new_balance} bread."
        ),
        gamble_all_loss=(
            "{username} got into a fight with the other rats and "
            "got mugged. You lost all your stale bread."
        ),
        duel_usage=(
            "Use it like this: !{command} duel @user 100"
        ),
        duel_amount_invalid=(
            "Duel amount must be a number or 'all'."
        ),
        duel_self=(
            "You can't duel yourself. The rats are confused."
        ),
        duel_invalid=(
            "Duel amount must be greater than 0."
        ),
        duel_challenger_insufficient=(
            "You only have {points} stale bread."
        ),
        duel_opponent_insufficient=(
            "{username} only has {points} stale bread."
        ),
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a "
            "stale bread duel for {amount} bread! "
            "Type !{command} duel accept or "
            "!{command} duel decline. This duel expires in "
            "{expiration} seconds."
        ),
        duel_missing=(
            "You don't have any pending bread duels, "
            "or your duel has expired."
        ),
        duel_cancelled=(
            "This duel was cancelled because someone no longer "
            "has enough stale bread."
        ),
        duel_result=(
            "@{winner} beat @{loser} up and stole {amount} bread."
        ),
        duel_declined=(
            "{username} has a family and decided to decline."
        )
    )
)
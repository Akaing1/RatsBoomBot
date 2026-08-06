from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages
)


DEVELOPER_NINJAKAING_TIMER_MESSAGES = (
    "Developer timer test message one.",
    "Developer timer test message two."
)


DEVELOPER_NINJAKAING_COMMUNITY_MESSAGES = CommunityMessages(
    follow=(
        "{username} found the developer cave!"
    ),
    subscription=(
        "{username} subscribed to the dev channel!"
    ),
    resubscription=(
        "{username} has been here for {months} months!"
    )
)


DEVELOPER_NINJAKAING_POINTS = PointsConfig(
    command_name="ores",
    points_per_message=25,
    message_cooldown_seconds=10,
    gamble_win_chance=0.50,
    duel_expiration_seconds=30,
    messages=PointsMessages(
        balance_self=(
            "{username}, you have mined {points} ores!"
        ),
        balance_other=(
            "{username} has mined {points} ores!"
        ),
        leaderboard_empty=(
            "No ores have been mined yet."
        ),
        leaderboard_entry=(
            "{position}. {username}: {points} ores"
        ),
        leaderboard_title=(
            "Top miners: {leaderboard}"
        ),
        reset_denied=(
            "Only the broadcaster can collapse the mine."
        ),
        reset_success=(
            "The mine has collapsed. "
            "All ore balances have been reset."
        ),
        add_denied=(
            "Only moderators can give ores to viewers."
        ),
        add_invalid=(
            "The ore amount must be greater than 0."
        ),
        add_success=(
            "Added {amount} ores to {username}'s inventory."
        ),
        gamble_no_points=(
            "You don't have any ores to gamble."
        ),
        gamble_usage=(
            "Use it like this: !{command} gamble 50 "
            "or !{command} gamble all"
        ),
        gamble_invalid=(
            "You need to gamble at least 1 ore."
        ),
        gamble_insufficient=(
            "You only have {points} ores."
        ),
        gamble_win=(
            "{username} struck a rich vein and found {amount} ores! "
            "They now have {new_balance} ores."
        ),
        gamble_all_win=(
            "{username} discovered a massive ore deposit and doubled "
            "their inventory to {new_balance} ores!"
        ),
        gamble_loss=(
            "{username}'s tunnel collapsed and they lost {amount} ores. "
            "They now have {new_balance} ores."
        ),
        gamble_all_loss=(
            "{username} dropped their entire ore inventory "
            "into a lava pit."
        ),
        duel_usage=(
            "Use it like this: !{command} duel @user 100"
        ),
        duel_amount_invalid=(
            "The duel amount must be a number or 'all'."
        ),
        duel_self=(
            "You can't challenge yourself to a mining duel."
        ),
        duel_invalid=(
            "The mining duel amount must be greater than 0."
        ),
        duel_challenger_insufficient=(
            "You only have {points} ores."
        ),
        duel_opponent_insufficient=(
            "{username} only has {points} ores."
        ),
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a mining "
            "duel for {amount} ores! Type !{command} duel accept or "
            "!{command} duel decline. This challenge expires in "
            "{expiration} seconds."
        ),
        duel_missing=(
            "You don't have a pending mining duel, "
            "or the challenge has expired."
        ),
        duel_cancelled=(
            "The mining duel was cancelled because someone "
            "no longer has enough ores."
        ),
        duel_result=(
            "@{winner} out-mined @{loser} and claimed {amount} ores."
        ),
        duel_declined=(
            "{username} decided the mine was too dangerous "
            "and declined the duel."
        )
    )
)
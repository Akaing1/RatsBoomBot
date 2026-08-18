from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages
)


STEOHANYY_TIMER_MESSAGES = (
    "Timer Placeholder"
)


STEOHANYY_COMMUNITY_MESSAGES = CommunityMessages(
    follow="@{username} pulled up a seat at the bar! Welcome in!",
    subscription="@{username} just ordered a fresh round! Thanks for subscribing!",
    resubscription=(
        "@{username} has kept their tab open for {months} months! "
        "Thanks for another round—cheers!"
    )
)


STEOHANYY_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    ),
    outgoing="Last call! We're bringing the bar to @{target_name}! Cheers!",
    outgoing_subscriber="Grab your drinks—the bar is raiding @{target_name}! Cheers!"
)


STEOHANYY_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Go check out @{username}! They were last playing {game_name}. "
        "They are a cool rat: {channel_url}"
    ),
    without_game=(
        "Go check out @{username}! They are a cool rat: {channel_url}"
    )
)


STEOHANYY_REDEEMS = RedeemConfig(
    daily_title="Daily Points",
    first_title="First",
    daily_amount=100,
    first_amount=250,
    daily_double_chance=0.05,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(

    )
)


STEOHANYY_POINTS = PointsConfig(
    command_name="drinks",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have {points} drinks stocked behind the bar!",
        balance_other="{username} has {points} drinks stocked behind the bar!",
        leaderboard_empty="The bar is empty—nobody has collected any drinks yet.",
        leaderboard_entry="{position}. {username}: {points} drinks",
        leaderboard_title="The bar's top drink collectors: {leaderboard}",
        reset_denied="Only the broadcaster can clear out the bar.",
        reset_success="Last call! Every drink has been cleared from the bar.",
        add_denied="Only moderators can serve drinks to viewers.",
        add_invalid="The number of drinks must be greater than 0.",
        add_success="Served {amount} drinks to {username}.",
        gamble_no_points="You do not have any drinks to put on the line.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 drink.",
        gamble_insufficient="You only have {points} drinks available.",
        gamble_win="{username} won {amount} drinks and now has {new_balance}! Cheers!",
        gamble_all_win="{username} doubled their entire drink order and now has {new_balance}!",
        gamble_loss="{username} spilled {amount} drinks and now has {new_balance}.",
        gamble_all_loss="{username} spilled their entire drink order. The bar is dry!",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The drink amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a drink-off.",
        duel_invalid="The drink-off must be for at least 1 drink.",
        duel_challenger_insufficient="You only have {points} drinks available.",
        duel_opponent_insufficient="{username} only has {points} drinks available.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a drink-off for "
            "{amount} drinks! Type !{command} duel accept or !{command} duel "
            "decline. This challenge expires in {expiration} seconds."
        ),
        duel_missing="You do not have a pending drink-off, or the challenge expired.",
        duel_cancelled="The drink-off was cancelled because someone no longer has enough drinks.",
        duel_result="@{winner} outdrank @{loser} and won {amount} drinks!",
        duel_declined="{username} declined the drink-off."
    )
)

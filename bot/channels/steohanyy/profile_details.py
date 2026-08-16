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
    follow="Thanks for following, {username}!",
    subscription="Thanks for subscribing, {username}!",
    resubscription="Thanks for subscribing for {months} months, {username}!"
)


STEOHANYY_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    )
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
        balance_self="{username}, you have {points} drinks!",
        balance_other="{username} has {points} sakura petals!",
        leaderboard_empty="No sakura petals have been gathered in the Garden yet.",
        leaderboard_entry="{position}. {username}: {points} sakura petals",
        leaderboard_title="Top sakura petal collectors: {leaderboard}",
        reset_denied="Only the broadcaster can clear the Garden's sakura petals.",
        reset_success="The Garden's sakura petals have been reset.",
        add_denied="Only moderators can give sakura petals to viewers.",
        add_invalid="The SakuraPetal amount must be greater than 0.",
        add_success="Added {amount} sakura petals to {username}.",
        gamble_no_points="You do not have any sakura petals to gamble.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 SakuraPetal.",
        gamble_insufficient="You only have {points} sakura petals.",
        gamble_win="{username} gained {amount} sakura petals and now has {new_balance}!",
        gamble_all_win="{username} doubled their sakura petals and now has {new_balance}!",
        gamble_loss="{username} lost {amount} sakura petals and now has {new_balance}.",
        gamble_all_loss="{username} lost all their sakura petals.",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The duel amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a SakuraPetal duel.",
        duel_invalid="The duel amount must be greater than 0.",
        duel_challenger_insufficient="You only have {points} sakura petals.",
        duel_opponent_insufficient="{username} only has {points} sakura petals.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a duel for "
            "{amount} sakura petals! Type !{command} duel accept or "
            "!{command} duel decline. This duel expires in "
            "{expiration} seconds."
        ),
        duel_missing="You do not have a pending sakura petal duel, or it expired.",
        duel_cancelled="The duel was cancelled because someone no longer has enough sakura petals.",
        duel_result="@{winner} defeated @{loser} and won {amount} sakura petals.",
        duel_declined="{username} declined the SakuraPetal duel."
    )
)


from bot.profiles import (
    CommunityMessages,
    LeagueConfig,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    SocialMessages
)


STEOHANYY_LEAGUE = LeagueConfig(
    enabled=True,
    provider="opgg",
    game_name="steohany",
    tag_line="ant",
    region="NA",
    display_name="Steohany"
)


STEOHANYY_TIMER_MESSAGES = (
    "Timer Placeholder"
)


STEOHANYY_SOCIAL_MESSAGES = SocialMessages(
    overview="Keep the drinks flowing: Discord: {discord_url} | YouTube: {youtube_url}",
    discord="Pull up a seat and join the community: {discord_url}",
    youtube="Grab a drink and catch up on YouTube: {youtube_url}"
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
    display_name="drinks",
    command_name="drinks",
    points_per_message=25,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have {points} {currency} stocked behind the bar!",
        balance_other="{username} has {points} {currency} stocked behind the bar!",
        leaderboard_empty="The bar is empty—nobody has collected any {currency} yet.",
        leaderboard_entry="{position}. {username}: {points} {currency}",
        leaderboard_title="The bar's top {currency} collectors: {leaderboard}",
        reset_denied="Only the broadcaster can clear out the bar.",
        reset_success="Last call! Every {currency} has been cleared from the bar.",
        add_denied="Only moderators can serve {currency} to viewers.",
        add_invalid="The number of {currency} must be greater than 0.",
        add_success="Served {amount} {currency} to {username}.",
        gamble_no_points="You do not have any {currency} to put on the line.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 {currency}.",
        gamble_insufficient="You only have {points} {currency} available.",
        gamble_win="{username} won {amount} {currency} and now has {new_balance}! Cheers!",
        gamble_all_win="{username} doubled their entire {currency} order and now has {new_balance}!",
        gamble_loss="{username} spilled {amount} {currency} and now has {new_balance}.",
        gamble_all_loss="{username} spilled their entire {currency} order. The bar is dry!",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The {currency} amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a {currency}-off.",
        duel_invalid="The {currency}-off must be for at least 1 {currency}.",
        duel_challenger_insufficient="You only have {points} {currency} available.",
        duel_opponent_insufficient="{username} only has {points} {currency} available.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a {currency}-off for "
            "{amount} {currency}! Type !{command} duel accept or !{command} duel "
            "decline. This challenge expires in {expiration} seconds."
        ),
        duel_missing="You do not have a pending {currency}-off, or the challenge expired.",
        duel_cancelled="The {currency}-off was cancelled because someone no longer has enough {currency}.",
        duel_result="@{winner} outdrank @{loser} and won {amount} {currency}!",
        duel_declined="{username} declined the {currency}-off."
    )
)

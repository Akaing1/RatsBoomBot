from bot.profiles import (
    ClipConfig,
    ClipMessages,
    CommunityMessages,
    FirstChatShoutout,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    SocialMessages
)


ONEDAYBREAD_SOCIAL_MESSAGES = SocialMessages(
    overview="Follow the channel elsewhere: Discord: {discord_url} | YouTube: {youtube_url}",
    discord="Join the channel community on Discord: {discord_url}",
    youtube="Catch up with the channel on YouTube: {youtube_url}"
)


ONEDAYBREAD_FIRST_CHAT_SHOUTOUTS = (
    FirstChatShoutout(
        user_id="TWITCH_USER_ID",
        username="twitch_username",
        message="Welcome in @{username}! Go show them some love: {channel_url}",
        native_shoutout=True
    ),
)


ONEDAYBREAD_CLIPS = ClipConfig(
    duration=60,
    short_duration=30,
    cooldown_seconds=120,
    processing_timeout_seconds=15,
    title="{channel_name} clipped by {username}",
    messages=ClipMessages(
        processing="Creating a {duration}-second clip for @{username}...",
        success="@{username} caught that! {clip_url}"
    )
)


ONEDAYBREAD_TIMER_MESSAGES = (
    "Timer Placeholder",
)


ONEDAYBREAD_COMMUNITY_MESSAGES = CommunityMessages(
    follow="Welcome to our newest bunbun {username}!",
    subscription="Enjoy your wonderful sub, wonderful {username}!",
    resubscription="Thankies for resub and hope both sides of your pillow stay cold user {username}!"
)


ONEDAYBREAD_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    ),
    outgoing=" GivePLZ GivePLZ GivePLZ DELICIOUS BUNS",
    outgoing_subscriber="oneday12Flowybunn oneday12Pompom BREAD RAID oneday12Pompom DELIVERING FRESH, "
                        "DAY OLD BUNBUNS TO YOUR PORCH oneday12Flowybunn!"
)


ONEDAYBREAD_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Showing appreciation to @{username} ❤️ "
        "Do check them out at {channel_url}"
    ),
    without_game=(
        "Showing appreciation to @{username} ❤️ Do check them out at {channel_url}"
    )
)


ONEDAYBREAD_REDEEMS = RedeemConfig(
    daily_title="Redeem Daily",
    first_title="First",
    second_title="Second",
    daily_amount=100,
    first_amount=250,
    second_amount=1000,
    daily_double_chance=0.00,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(
        daily_success="@{username} is hoarding {claim_count} pieces of bread under their pillow!",
        daily_milestone="",
        first_success="Bestie @{username} claimed first {claim_count} times!",
        first_milestone="",
        second_success="Everyone's favorite pentose parent @{username} claimed second {claim_count} times!",
        second_milestone=""
    )
)


ONEDAYBREAD_POINTS = PointsConfig(
    command_name="mews",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have collected {points} mews!",
        balance_other="{username} has collected {points} mews!",
        leaderboard_empty="The cat choir is quiet—no mews have been collected yet.",
        leaderboard_entry="{position}. {username}: {points} mews",
        leaderboard_title="The loudest meowers: {leaderboard}",
        reset_denied="Only the broadcaster can quiet all the mews.",
        reset_success="The cat choir has gone silent. All mews have been reset.",
        add_denied="Only moderators can give viewers more mews.",
        add_invalid="The number of mews must be greater than 0.",
        add_success="Gave {amount} mews to {username}.",
        gamble_no_points="You do not have any mews to gamble.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 mew.",
        gamble_insufficient="You only have {points} mews.",
        gamble_win="{username} let out {amount} triumphant mews and now has {new_balance}!",
        gamble_all_win="{username}'s mews echoed back twice as loud! They now have {new_balance} mews!",
        gamble_loss="{username} lost {amount} mews and now has {new_balance}.",
        gamble_all_loss="{username} lost their voice and all of their mews.",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The mew amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a meow-off.",
        duel_invalid="The meow-off must be for at least 1 mew.",
        duel_challenger_insufficient="You only have {points} mews.",
        duel_opponent_insufficient="{username} only has {points} mews.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a meow-off for {amount} mews! "
            "Type !{command} duel accept or !{command} duel decline. This challenge "
            "expires in {expiration} seconds."
        ),
        duel_missing="You do not have a pending meow-off, or it expired.",
        duel_cancelled="The meow-off was cancelled because someone no longer has enough mews.",
        duel_result="@{winner} out-meowed @{loser} and won {amount} mews!",
        duel_declined="{username} declined the meow-off."
    )
)

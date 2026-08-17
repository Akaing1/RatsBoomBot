from bot.profiles import (
    CommunityMessages,
    FirstChatShoutout,
    PointsConfig,
    PointsMessages,
    OverwatchConfig,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    TargetTimeoutRedeemConfig,
    TimeoutRedeemConfig
)


MILKY_GALAXYVT_FIRST_CHAT_SHOUTOUTS = (
    FirstChatShoutout(
        user_id="1251948863",
        username="ninjakaing",
        message="Our favorite rat @{username} has arrived! {channel_url}",
        native_shoutout=True
    ),
)


MILKY_GALAXYVT_TIMER_MESSAGES = (
    "Join us in The Milky Way https://discord.gg/bsRcYhnRC3 (its scuffed rn)"
)


MILKY_GALAXYVT_COMMUNITY_MESSAGES = CommunityMessages(
    follow="Thanks for following, {username}!",
    subscription="Thanks for subscribing, {username}!",
    resubscription="Thanks for subscribing for {months} months, {username}!"
)


MILKY_GALAXYVT_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    ),
    outgoing=(
        "BrainSlug BrainSlug Delivery From The Stars BrainSlug BrainSlug "
        "Delivery From The Stars BrainSlug BrainSlug Delivery From The Stars "
        "BrainSlug BrainSlug Delivery From The Stars BrainSlug BrainSlug"
    ),
    outgoing_subscriber=(
        "milkyg10Raid milkyg10Raid Raid Delivery From The Stars "
        "milkyg10Raid milkyg10Raid Raid Delivery From The Stars "
        "milkyg10Raid milkyg10Raid Raid Delivery From The Stars "
        "milkyg10Raid milkyg10Raid"
    )
)

MILKY_GALAXYVT_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Go check out @{username}! They were last playing {game_name}. "
        "They are a cool rat: {channel_url}"
    ),
    without_game=(
        "Go check out @{username}! They are a cool rat: {channel_url}"
    )
)


MILKY_GALAXYVT_REDEEMS = RedeemConfig(
    daily_title="Catch a Comet (daily)",
    first_title="First",
    second_title="Second",
    daily_amount=0,
    first_amount=0,
    second_amount=0,
    daily_double_chance=0,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(
        first_already_claimed_by="@{username}, First was already claimed by @{winner} this stream.",
        first_already_claimed="@{username}, First was already claimed this stream.",
        first_success="Welcome in @{username}, you have been first {claim_count} times!",
        first_milestone="",
        second_already_claimed_by="@{username}, Second was already claimed by @{winner} this stream.",
        second_already_claimed="@{username}, Second was already claimed this stream.",
        second_success="Welcome in @{username}, you have been second {claim_count} times!",
        second_milestone="",
        timeout_success="@{username} has timed themselves out for {minutes} minutes!",
        timeout_failed="@{username}, Twitch could not time you out."
    ),
    timeout=TimeoutRedeemConfig(
        title="3 Minute Timeout",
        duration_seconds=180,
        reason="Redeemed 3 Minute Timeout."
    ),
    target_timeouts=(
        TargetTimeoutRedeemConfig(
            title="Slime Mason",
            target_user_id="208244235",
            target_username="unfitend",
            duration_seconds=86400,
            success_message="@{target_username} has been slimed out for {hours} hours!",
            failure_message="Twitch could not slime out @{target_username}.",
            reason="You've been slimed out."
        ),
    )
)


MILKY_GALAXYVT_POINTS = PointsConfig(
    command_name="shards",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have {points} star shards!",
        balance_other="{username} has {points} star shards!",
        leaderboard_empty="No star shards have been collected yet.",
        leaderboard_entry="{position}. {username}: {points} star shards",
        leaderboard_title="Top star shard collectors: {leaderboard}",
        reset_denied="Only the broadcaster can reset the star shards.",
        reset_success="The galaxy's star shards have been reset.",
        add_denied="Only moderators can give viewers star shards.",
        add_invalid="The star shard amount must be greater than 0.",
        add_success="Added {amount} star shards to {username}.",
        gamble_no_points="You do not have any star shards to gamble.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 star shard.",
        gamble_insufficient="You only have {points} star shards.",
        gamble_win="{username} found {amount} star shards and now has {new_balance}!",
        gamble_all_win="{username} doubled their star shards and now has {new_balance}!",
        gamble_loss="{username} lost {amount} star shards and now has {new_balance}.",
        gamble_all_loss="{username} lost all their star shards in the void.",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The duel amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a star shard duel.",
        duel_invalid="The duel amount must be greater than 0.",
        duel_challenger_insufficient="You only have {points} star shards.",
        duel_opponent_insufficient="{username} only has {points} star shards.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a duel for {amount} "
            "star shards! Type !{command} duel accept or !{command} duel decline. "
            "This duel expires in {expiration} seconds."
        ),
        duel_missing="You do not have a pending star shard duel, or it expired.",
        duel_cancelled="The duel was cancelled because someone no longer has enough star shards.",
        duel_result="@{winner} defeated @{loser} and won {amount} star shards.",
        duel_declined="{username} declined the star shard duel."
    )
)


MILKY_GALAXYVT_OVERWATCH = OverwatchConfig(
    player_id="Galaxy-17159",
    platform="pc"
)

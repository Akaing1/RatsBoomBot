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
    SocialMessages,
    TargetTimeoutRedeemConfig,
    TimeoutRedeemConfig
)


DEVELOPER_NINJAKAING_SOCIAL_MESSAGES = SocialMessages(
    overview="Developer channel links: Discord: {discord_url} | YouTube: {youtube_url}",
    discord="Join the developer test community: {discord_url}",
    youtube="Watch developer channel uploads: {youtube_url}"
)


DEVELOPER_NINJAKAING_FIRST_CHAT_SHOUTOUTS = (
    FirstChatShoutout(
        user_id="1251948863",
        username="ninjakaing",
        message="The lead developer @{username} has entered the test environment! {channel_url}",
        native_shoutout=True
    ),
    FirstChatShoutout(
        user_id="1185298405",
        username="randomuser1727",
        # message="An explosive threat @{username} has entered the test environment! {channel_url}",
        native_shoutout=True
    ),
    FirstChatShoutout(
        user_id="230369508",
        username="reklop",
        # message="An explosive threat @{username} has entered the test environment! {channel_url}",
        native_shoutout=True
    )
)


DEVELOPER_NINJAKAING_CLIPS = ClipConfig(
    duration=60,
    short_duration=30,
    cooldown_seconds=30,
    processing_timeout_seconds=15,
    title="Developer test clip created by {username}",
    messages=ClipMessages(
        processing="Compiling a {duration}-second clip for @{username}...",
        success="@{username}, the clip build passed! {clip_url}"
    )
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


DEVELOPER_NINJAKAING_RAID_MESSAGES = RaidMessages(
    incoming="@{raider_name} deployed {viewer_count} {viewer_word} into the developer environment!",
    outgoing="Developer raid test for @{target_name}! {target_url}",
    outgoing_subscriber="Subscriber developer raid test for @{target_name}! {target_url}"
)


DEVELOPER_NINJAKAING_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Deploy some support to @{username}! They were last debugging "
        "{game_name}: {channel_url}"
    ),
    without_game=(
        "Deploy some support to @{username}: {channel_url}"
    )
)


DEVELOPER_NINJAKAING_REDEEMS = RedeemConfig(
    daily_title="Dev Daily",
    first_title="Dev First",
    second_title="Dev Second",
    daily_amount=100,
    first_amount=250,
    second_amount=150,
    daily_double_chance=0.50,
    claim_milestones=(2, 5, 10),
    messages=RedeemMessages(
        daily_success="@{username} completed dev check-in #{claim_count} and received {amount} ores!",
        daily_double="Double build! @{username} received {amount} ores on dev check-in #{claim_count}!",
        daily_milestone="Dev milestone: @{username} has checked in {claim_count} times!",
        first_success="@{username} won Dev First and received {amount} ores! Total wins: {claim_count}.",
        second_success="@{username} won Dev Second and received {amount} ores! Total wins: {claim_count}.",
        timeout_success="@{username} entered debug jail for {minutes} minutes!",
        timeout_failed="@{username}, the debug timeout failed."
    ),
    timeout=TimeoutRedeemConfig(
        title="Dev Self Timeout",
        duration_seconds=60,
        reason="Developer self-timeout test."
    ),
    target_timeouts=(
        TargetTimeoutRedeemConfig(
            title="Dev Target Timeout",
            target_user_id="1251948863",
            target_username="ninjakaing",
            duration_seconds=60,
            success_message="@{target_username} was sent to debug jail for {minutes} minute!",
            failure_message="The targeted debug timeout for @{target_username} failed.",
            reason="Developer targeted-timeout test."
        ),
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

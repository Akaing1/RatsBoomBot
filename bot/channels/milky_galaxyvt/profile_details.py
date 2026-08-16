from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    OverwatchConfig,
    RaidMessages,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages
)


MILKY_GALAXYVT_TIMER_MESSAGES = (
    "Timer Placeholder"
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
    outgoing="Milky's galaxy is raiding @{target_name}!",
    outgoing_subscriber="The galaxy is on the move! We're raiding @{target_name}!"
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
    daily_title="Daily Points",
    first_title="First",
    daily_amount=100,
    first_amount=250,
    daily_double_chance=0.05,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(

    )
)


MILKY_GALAXYVT_POINTS = PointsConfig(
    command_name="points",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(

    )
)


MILKY_GALAXYVT_OVERWATCH = OverwatchConfig(
    player_id="Galaxy-17159",
    platform="pc"
)

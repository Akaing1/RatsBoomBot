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
    ShoutoutMessages
)


TEMPLATE_FIRST_CHAT_SHOUTOUTS = (
    FirstChatShoutout(
        user_id="TWITCH_USER_ID",
        username="twitch_username",
        message="Welcome in @{username}! Go show them some love: {channel_url}",
        native_shoutout=True
    ),
)


TEMPLATE_CLIPS = ClipConfig(
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


TEMPLATE_TIMER_MESSAGES = (
    "Timer Placeholder"
)


TEMPLATE_COMMUNITY_MESSAGES = CommunityMessages(
    follow="Thanks for following, {username}!",
    subscription="Thanks for subscribing, {username}!",
    resubscription="Thanks for subscribing for {months} months, {username}!"
)


TEMPLATE_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    ),
    outgoing="We're raiding @{target_name}!",
    outgoing_subscriber="Subscriber raid message for @{target_name}!"
)


TEMPLATE_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Go check out @{username}! They were last playing {game_name}. "
        "They are a cool rat: {channel_url}"
    ),
    without_game=(
        "Go check out @{username}! They are a cool rat: {channel_url}"
    )
)


TEMPLATE_REDEEMS = RedeemConfig(
    daily_title="Daily Points",
    first_title="First",
    daily_amount=100,
    first_amount=250,
    daily_double_chance=0.05,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(

    )
)


TEMPLATE_POINTS = PointsConfig(
    command_name="points",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(

    )
)

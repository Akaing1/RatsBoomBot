from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RedeemConfig,
    RedeemMessages
)


MEINYA_TIMER_MESSAGES = (
    "Still a regular stinky? Upgrade to premium stinky — get ad-free viewing, sub emotes, sub badge, and support the blood sakura garden 🩸",
    "2.0 MODEL RIGGING GOAL ON THRONE: https://throne.com/meinya/item/81c32121-0be2-44c6-b29f-be926b04b92b Help fund the Meinya model 🖤 Donating toward this is absolutely never expected — just lurking, chatting, and hanging out already supports me a ton ♡",
    "Still a wandering soul? Join the Blood Sakura Shrine by following before you get lost!",
    "You can support my stream by tipping on Throne or using Twitch Bits :3 (Everything that comes from the stream goes back into my stream ^^.): https://throne.com/meinya",
    "Stinky car is now a youtuber HYPERS ! For now we're only posting vods and some clips, but, maybe we'll do full videos in the future, who knows Shrug Go ahead and subscribe, it's greatly appreciated https://www.youtube.com/@MeinyaYozakura",
    "Join the Garden :3 <3 https://discord.gg/E7Q2yTmVp4"

)


MEINYA_COMMUNITY_MESSAGES = CommunityMessages(
    follow="A new wandering spirit has joined the Garden! 🌸 Thank you for the follow {username}, Nya! ✨~",
    subscription="🌸 A sacred bond has been forged! Thank you {username} for subscribing and supporting the Garden.~ You are now an elite guardian of the Blood Sakura Garden! Enjoy the perks and cute emotes :3. Mya~ ✨",
    resubscription="🌸 Another month in the Sakura Garden! Thank you for staying by my side for {months} months {username}, mya~"
)


MEINYA_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    )
)


MEINYA_REDEEMS = RedeemConfig(
    daily_title="Daily Check-in",
    first_title="FIRST",
    daily_amount=100,
    first_amount=250,
    daily_double_chance=0.05,
    claim_milestones=(10, 25, 50, 100, 250, 500, 1000),
    messages=RedeemMessages(
        stream_offline=(
            "@{username}, this redeem only works while "
            "the stream is live."
        ),
        daily_already_claimed=(
            "@{username}, you already given your "
            "blood offering for today."
        ),
        daily_success=(
            "@{username} has given their daily blood offering "
            "and received {amount} sakura petals! They have offered their blood"
            "{claim_count} times!"
        ),
        daily_double=(
            "You have received a blessing! @{username} has been "
            "rewarded with {amount} sakura petals! They have offered their blood"
            "{claim_count} times!"
        ),
        daily_milestone=(
            "A dedicated Devotee! @{username} has offered their blood"
            "{claim_count} times!"
        ),
        first_already_claimed_by=(
            "@{username}, this stream's first blessing was already "
            "given to @{winner}."
        ),
        first_already_claimed=(
            "@{username}, this stream's first blessing was already "
            "given."
        ),
        first_success=(
            "@{username} was given the first blessing for the stream "
            "and received {amount} sakura petals! They have been blessed "
            "first {claim_count} times!"
        ),
        first_milestone=(
            "Milestone! @{username} has blessed first "
            "{claim_count} times!"
        )
    )
)


MEINYA_POINTS = PointsConfig(
    command_name="points",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(

    )
)


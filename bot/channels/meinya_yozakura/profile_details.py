from bot.profiles import (
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RaidBossConfig,
    RaidBossNames,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    SocialMessages
)


MEINYA_RAID_BOSSES = RaidBossConfig(
    enabled=True,
    names=RaidBossNames(
        melee="Dragon-king Thordan",
        ranged="The Ultima Weapon",
        magic="Bahamut Prime"
    ),
    mini_names=RaidBossNames(
        melee="Behemoth",
        ranged="Magitek Gunship",
        magic="Ahriman"
    ),
    mini_hp_min=20000,
    mini_hp_max=50000,
    mini_hp_step=15000,
    weapon_cost=5000,
    potion_cost=2500
)


MEINYA_TIMER_MESSAGES = (
    "Still a regular stinky? Upgrade to premium stinky — get ad-free viewing, sub emotes, sub badge, and support the blood sakura garden 🩸",
    "2.0 MODEL RIGGING GOAL ON THRONE: https://throne.com/meinya/item/81c32121-0be2-44c6-b29f-be926b04b92b Help fund the Meinya model 🖤 Donating toward this is absolutely never expected — just lurking, chatting, and hanging out already supports me a ton ♡",
    "Still a wandering soul? Join the Blood Sakura Shrine by following before you get lost!",
    "You can support my stream by tipping on Throne or using Twitch Bits :3 (Everything that comes from the stream goes back into my stream ^^.): https://throne.com/meinya",
    "Stinky car is now a youtuber HYPERS ! For now we're only posting vods and some clips, but, maybe we'll do full videos in the future, who knows Shrug Go ahead and subscribe, it's greatly appreciated https://www.youtube.com/@MeinyaYozakura",
    "Join the Garden :3 <3 https://discord.gg/E7Q2yTmVp4"

)


MEINYA_SOCIAL_MESSAGES = SocialMessages(
    overview="Find more from the Blood Sakura Garden: Discord: {discord_url} | YouTube: {youtube_url}",
    discord="Join the Blood Sakura Garden: {discord_url}",
    youtube="Visit Meinya's YouTube for VODs and clips: {youtube_url}"
)


MEINYA_COMMUNITY_MESSAGES = CommunityMessages(
    follow="A new wandering spirit has joined the Garden! 🌸 Thank you for the follow {username}, Nya! ✨~",
    subscription="🌸 A sacred bond has been forged! Thank you {username} for subscribing and supporting the Garden.~ You are now an elite guardian of the Blood Sakura Garden! Enjoy the perks and cute emotes :3. Mya~ ✨",
    resubscription="🌸 Another month in the Sakura Garden! Thank you for staying by my side for {months} months {username}, mya~"
)


MEINYA_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} raided with {viewer_count} {viewer_word}!"
    ),
    outgoing="TombRaid GlitchCat PowerUpL NYXI RAID PowerUpR GlitchCat TombRaid",
    outgoing_subscriber=(
        "meinya3Sprays meinya3Bark Meinya sprays us if we don't raid "
        "meinya3Sprays meinya3Bark Meinya sprays us if we don't raid "
        "meinya3Sprays meinya3Bark Meinya sprays us if we don't raid"
    )
)


MEINYA_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Go show @{username} some love! They were last playing {game_name}. "
        "Visit their corner of the garden: {channel_url}"
    ),
    without_game=(
        "Go show @{username} some love! Visit their corner of the garden: "
        "{channel_url}"
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
        stream_offline="@{username}, this redeem only works while the stream is live.",
        daily_already_claimed="@{username}, you have already given your blood offering for today.",
        daily_success=(
            "@{username} has given their daily blood offering "
            "and received {amount} sakura petals! They have offered their blood "
            "{claim_count} times!"
        ),
        daily_double=(
            "You have received a blessing! @{username} has been "
            "rewarded with {amount} sakura petals! They have offered their blood "
            "{claim_count} times!"
        ),
        daily_milestone="A dedicated Devotee! @{username} has offered their blood {claim_count} times!",
        first_already_claimed_by="@{username}, this stream's first blessing was already given to @{winner}.",
        first_already_claimed="@{username}, this stream's first blessing was already given.",
        first_success=(
            "@{username} was given the first blessing for the stream "
            "and received {amount} sakura petals! They have been blessed "
            "first {claim_count} times!"
        ),
        first_milestone="Milestone! @{username} has blessed first {claim_count} times!"
    )
)


MEINYA_POINTS = PointsConfig(
    command_name="petals",
    points_per_message=10,
    message_cooldown_seconds=60,
    gamble_win_chance=0.5,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have {points} sakura petals!",
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

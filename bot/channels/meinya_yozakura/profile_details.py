from bot.profiles import (
    ChannelAchievementNames,
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidMessages,
    RaidBossConfig,
    RaidBossNames,
    RaidWeaponNames,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    SocialMessages
)


MEINYA_ACHIEVEMENT_NAMES = ChannelAchievementNames(
    check_ins="Garden Devotee",
    messages="Whispers in the Garden",
    points="Petal Collector",
    gambling="Fortune in Bloom",
    damage="Limit Breaker",
    bosses="Warrior of Light",
    weapons="Relic Hunter",
    buffs="Party Support",
    consumables="Prepared Adventurer"
)


MEINYA_RAID_BOSSES = RaidBossConfig(
    enabled=True,
    tutorial_name="Striking Dummy",
    names=RaidBossNames(
        melee="Dragon-king Thordan",
        ranged="The Ultima Weapon",
        magic="Bahamut Prime"
    ),
    mini_names=RaidBossNames(
        melee=("Behemoth", "Garula"),
        ranged=("Magitek Gunship", "Barreltender"),
        magic=("Ahriman", "Chieftain Moglin")
    ),
    weapon_names=RaidWeaponNames(
        overclocked_bow="Failnaught",
        overclocked_sword="Galatyn",
        overclocked_tome="Organum",
        basic_sword="Weathered Shortsword",
        refined_sword="Lost Allagan Saber",
        masterwork_sword="Burtgang",
        mythical_blade="Ultimate Sword of the Heavens",
        basic_bow="Weathered Shortbow",
        refined_bow="Lost Allagan Composite Bow",
        masterwork_bow="Rosenbogen",
        mythical_longbow="Ultimate Bow of the Heavens",
        apprentice_tome="Weathered Grimoire",
        enchanted_tome="Lost Allagan Grimoire",
        archmage_grimoire="Ona Ramuhda",
        mythical_grimoire="Ultimate Grimoire of the Heavens"
    ),
    weapon_cost=5000,
    potion_cost=1500
)


MEINYA_TIMER_MESSAGES = (
    ("Mei is trying to reach YouTube partnership! If you would like to help support, please leave a lurk on YouTube here as well :3 https://www.youtube.com/@MeinyaYozakura", "announcement", "orange"),
    "Still a regular stinky? Upgrade to premium stinky — get ad-free viewing, sub emotes, sub badge, and support the blood sakura garden 🩸",
    "2.0 MODEL RIGGING GOAL ON THRONE: https://throne.com/meinya/item/81c32121-0be2-44c6-b29f-be926b04b92b Help fund the Meinya model 🖤 Donating toward this is absolutely never expected — just lurking, chatting, and hanging out already supports me a ton ♡",
    "Still a wandering soul? Join the Blood Sakura Shrine by following before you get lost!",
    "You can support my stream by tipping on Throne or using Twitch Bits :3 (Everything that comes from the stream goes back into my stream ^^.): https://throne.com/meinya",
    "Stinky car is now a youtuber HYPERS ! For now we're only posting vods and some clips, but, maybe we'll do full videos in the future, who knows Shrug Go ahead and subscribe, it's greatly appreciated https://www.youtube.com/@MeinyaYozakura",
    "Join the Garden :3 <3 https://discord.gg/E7Q2yTmVp4"

)


MEINYA_AD_ANNOUNCEMENT_MESSAGE = "3 minutes of ads starting in ~{time}! We have to run 3 minutes of ads at the top of every hour to disable the prerolls, so please forgive me! See you soon!"
MEINYA_LURK_MESSAGE = "@{username} fades into the shadows of the garden. Rest well, wandering spirit!"


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
    vip_title="VIP REDEEM",
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
        first_milestone="Milestone! @{username} has blessed first {claim_count} times!",
        vip_success="@{username} is now a VIP! We appreciate your patronage and support of the Blood Sakura Garden!"
    )
)


MEINYA_POINTS = PointsConfig(
    display_name="sakura petals",
    command_name="petals",
    points_per_message=25,
    message_cooldown_seconds=60,
    roulette_max_bet=1000,
    subscription_reward=500,
    cheer_reward=50,
    cheer_minimum_bits=100,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self="{username}, you have {points} {currency}!",
        balance_other="{username} has {points} {currency}!",
        leaderboard_empty="No {currency} have been gathered in the Garden yet.",
        leaderboard_entry="{position}. {username}: {points} {currency}",
        leaderboard_title="Top {currency} collectors: {leaderboard}",
        reset_denied="Only the broadcaster can clear the Garden's {currency}.",
        reset_success="The Garden's {currency} have been reset.",
        add_denied="Only moderators can give {currency} to viewers.",
        add_invalid="The {currency} amount must be greater than 0.",
        add_success="Added {amount} {currency} to {username}.",
        gamble_no_points="You do not have any {currency} to gamble.",
        gamble_usage="Use it like this: !{command} gamble 50 or !{command} gamble all",
        gamble_invalid="You need to gamble at least 1 {currency}.",
        gamble_insufficient="You only have {points} {currency}.",
        gamble_win="{username} gained {amount} {currency} and now has {new_balance}!",
        gamble_all_win="{username} doubled their {currency} and now has {new_balance}!",
        gamble_loss="{username} lost {amount} {currency} and now has {new_balance}.",
        gamble_all_loss="{username} lost all their {currency}.",
        roulette_usage="Use it like this: !{command} roulette red 100 or !{command} spin black 100",
        roulette_color_invalid="Choose red, black, or green.",
        roulette_bet_invalid="Your roulette bet must be at least 1 {currency}.",
        roulette_bet_maximum="The maximum roulette bet is {maximum} {currency}.",
        roulette_insufficient="You only have {points} {currency}.",
        roulette_win="The wheel landed on {number} {result}! {username} won {profit} {currency} and now has {new_balance}!",
        roulette_loss="The wheel landed on {number} {result}. {username} lost {bet} {currency} and now has {new_balance}.",
        duel_usage="Use it like this: !{command} duel @user 100",
        duel_amount_invalid="The duel amount must be a number or 'all'.",
        duel_self="You cannot challenge yourself to a {currency} duel.",
        duel_invalid="The duel amount must be greater than 0.",
        duel_challenger_insufficient="You only have {points} {currency}.",
        duel_opponent_insufficient="{username} only has {points} {currency}.",
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a duel for "
            "{amount} {currency}! Type !{command} duel accept or "
            "!{command} duel decline. This duel expires in "
            "{expiration} seconds."
        ),
        duel_missing="You do not have a pending {currency} duel, or it expired.",
        duel_cancelled="The duel was cancelled because someone no longer has enough {currency}.",
        duel_result="@{winner} defeated @{loser} and won {amount} {currency}.",
        duel_declined="{username} declined the {currency} duel."
    )
)

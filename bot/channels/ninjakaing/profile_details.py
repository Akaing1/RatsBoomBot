from bot.profiles import (
    ChannelAchievementNames,
    CommunityMessages,
    PointsConfig,
    PointsMessages,
    RaidBossConfig,
    RaidBossNames,
    RaidMessages,
    RaidWeaponNames,
    RedeemConfig,
    RedeemMessages,
    ShoutoutMessages,
    SocialMessages
)


NINJAKAING_ACHIEVEMENT_NAMES = ChannelAchievementNames(
    check_ins="Rat Pack Regular",
    messages="Sewer Socialite",
    points="Breadwinner",
    gambling="Cheese Chaser",
    damage="Heavy Hitter",
    bosses="Apex Rat",
    weapons="Armed & Cheesy",
    buffs="Pack Tactics",
    consumables="Prepared Pack Rat"
)


NINJAKAING_RAID_BOSSES = RaidBossConfig(
    enabled=True,
    names=RaidBossNames(
        melee=("Rift Herald", "Atakan"),
        ranged="Elder",
        magic="Baron"
    ),
    mini_names=RaidBossNames(
        melee=("Noxian Warhound", "Frostguard Reaver", "Petricite Colossus"),
        ranged=("Chemtech Abomination", "Bilgewater Sea Serpent"),
        magic=("Voidborn Ravager", "Black Mist Wraith")
    ),
    weapon_names=RaidWeaponNames(
        basic_sword="Long Sword",
        refined_sword="Serrated Dirk",
        masterwork_sword="Doran's Blade",
        mythical_blade="Voltaic Cyclo-sword",
        basic_bow="Dagger",
        refined_bow="Recurve Bow",
        masterwork_bow="Doran's Bow",
        mythical_longbow="Immortal Shieldbow",
        apprentice_tome="Amplifying Tome",
        enchanted_tome="Fiendish Codex",
        archmage_grimoire="Doran's Ring",
        mythical_grimoire="Rite of Ruin"
    )
)


NINJAKAING_TIMER_MESSAGES = (
    "Lost something? Maybe you left it in the basement: {discord_url}",
    "Missed something? Go check out Rat's YouTube! {youtube_url}",
    "Ready to gamble? Use !help to get a list of commands you can use!"
)


NINJAKAING_SOCIAL_MESSAGES = SocialMessages(
    overview="Lost in the basement? Discord: {discord_url} | YouTube: {youtube_url}",
    discord="Lost something? Maybe you left it in the basement: {discord_url}",
    youtube="Missed something? Go check out Rat's YouTube! {youtube_url}"
)


NINJAKAING_COMMUNITY_MESSAGES = CommunityMessages(
    follow=(
        "{username} has snuck their way into the basement! "
        "Thanks for following!"
    ),
    subscription=(
        "{username} has subscribed! Rats stronk together!"
    ),
    resubscription=(
        "{username} resubscribed for {months} months! "
        "Thank you for your continued support!"
    )
)


NINJAKAING_RAID_MESSAGES = RaidMessages(
    incoming=(
        "@{raider_name} has raided the basement with "
        "{viewer_count} {viewer_word}! Rats stronk together!"
    ),
    outgoing="The basement is raiding @{target_name}! Rats stronk together!",
    outgoing_subscriber="Rats stronk together! The basement is raiding @{target_name}!"
)


NINJAKAING_SHOUTOUT_MESSAGES = ShoutoutMessages(
    with_game=(
        "Go check out @{username}! They were last playing {game_name}. "
        "They are a cool rat: {channel_url}"
    ),
    without_game=(
        "Go check out @{username}! They are a cool rat: {channel_url}"
    )
)


NINJAKAING_REDEEMS = RedeemConfig(
    daily_title="Steal Some Cheese",
    first_title="First",
    daily_amount=100,
    first_amount=250,
    daily_double_chance=0.05,
    claim_milestones=(
        10,
        25,
        50,
        100,
        250,
        500,
        1000
    ),
    messages=RedeemMessages(
        stream_offline=(
            "@{username}, this redeem only works while "
            "the stream is live."
        ),
        daily_already_claimed=(
            "@{username}, you already claimed your stream "
            "daily stale bread."
        ),
        daily_success=(
            "@{username} claimed their stream daily stale bread "
            "and received {amount} bread! They have collected "
            "their daily stale bread {claim_count} times!"
        ),
        daily_double=(
            "Lucky day! @{username} found an extra stale loaf "
            "and received {amount} bread! They have collected "
            "their daily stale bread {claim_count} times!"
        ),
        daily_milestone=(
            "Milestone! @{username} has collected their daily "
            "stale bread {claim_count} times!"
        ),
        first_already_claimed_by=(
            "@{username}, this stream's first redeem was already "
            "claimed by @{winner}."
        ),
        first_already_claimed=(
            "@{username}, this stream's first redeem was "
            "already claimed."
        ),
        first_success=(
            "@{username} was first in the basement this stream "
            "and received {amount} bread! They have stolen the "
            "first bread {claim_count} times!"
        ),
        first_milestone=(
            "Milestone! @{username} has stolen the first bread "
            "{claim_count} times!"
        )
    )
)


NINJAKAING_POINTS = PointsConfig(
    display_name="stale bread",
    command_name="bread",
    points_per_message=25,
    message_cooldown_seconds=60,
    gamble_win_chance=0.45,
    duel_expiration_seconds=60,
    messages=PointsMessages(
        balance_self=(
            "{username}, you have {points} {currency}!"
        ),
        balance_other=(
            "{username} has {points} {currency}!"
        ),
        leaderboard_empty=(
            "No {currency} has been collected yet. "
            "What an upstanding citizen!"
        ),
        leaderboard_entry=(
            "{position}. {username}: {points} {currency}"
        ),
        leaderboard_title=(
            "Top {currency} hoarders: {leaderboard}"
        ),
        reset_denied=(
            "Only the broadcaster can reset the {currency} stash."
        ),
        reset_success=(
            "This channel's {currency} has been thrown away. "
            "The leaderboard has been reset."
        ),
        add_denied=(
            "Only moderators can add {currency} to viewers."
        ),
        add_invalid=(
            "{currency} amount must be greater than 0."
        ),
        add_success=(
            "Added {amount} {currency} to "
            "{username}'s stash."
        ),
        gamble_no_points=(
            "You don't have any {currency} to gamble."
        ),
        gamble_usage=(
            "Use it like this: !{command} gamble 50 "
            "or !{command} gamble all"
        ),
        gamble_invalid=(
            "You need to gamble at least 1 {currency}."
        ),
        gamble_insufficient=(
            "You only have {points} {currency}."
        ),
        gamble_win=(
            "{username} found {amount} {currency} on the ground "
            "and now has {new_balance} {currency}."
        ),
        gamble_all_win=(
            "{username} raided the pantry and found a hidden stash "
            "of {currency}! You now have {new_balance} {currency}."
        ),
        gamble_loss=(
            "{username} got caught by a rat trap and lost {amount} "
            "{currency} and now has {new_balance} {currency}."
        ),
        gamble_all_loss=(
            "{username} got into a fight with the other rats and "
            "got mugged. You lost all your {currency}."
        ),
        duel_usage=(
            "Use it like this: !{command} duel @user 100"
        ),
        duel_amount_invalid=(
            "Duel amount must be a number or 'all'."
        ),
        duel_self=(
            "You can't duel yourself. The rats are confused."
        ),
        duel_invalid=(
            "Duel amount must be greater than 0."
        ),
        duel_challenger_insufficient=(
            "You only have {points} {currency}."
        ),
        duel_opponent_insufficient=(
            "{username} only has {points} {currency}."
        ),
        duel_challenge=(
            "@{opponent}, @{challenger} challenged you to a "
            "{currency} duel for {amount} {currency}! "
            "Type !{command} duel accept or "
            "!{command} duel decline. This duel expires in "
            "{expiration} seconds."
        ),
        duel_missing=(
            "You don't have any pending {currency} duels, "
            "or your duel has expired."
        ),
        duel_cancelled=(
            "This duel was cancelled because someone no longer "
            "has enough {currency}."
        ),
        duel_result=(
            "@{winner} beat @{loser} up and stole {amount} {currency}."
        ),
        duel_declined=(
            "{username} has a family and decided to decline."
        )
    )
)

import logging
from dataclasses import dataclass
from enum import Enum

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class FeatureName(Enum):
    CHANNEL = "channel"
    TIMERS = "timers"
    AD_ANNOUNCEMENTS = "ad_announcements"
    POINTS = "points"
    REDEEMS = "redeems"
    COMMUNITY_EVENTS = "community_events"
    RAID_RESPONSES = "raid_responses"


class GlobalCommandGroup(Enum):
    GLOBALS = "globals"
    POINTS = "points"
    VIEWER_QUEUE = "viewer_queue"
    SHOUTOUTS = "shoutouts"
    SOCIALS = "socials"
    SETTINGS = "settings"
    CLIPS = "clips"


class GlobalCommandName(Enum):
    HI = "hi"
    CHOICE = "choice"
    KABOOM = "kaboom"
    STINKY = "stinky"
    LUCKY = "lucky"
    SMART = "smart"
    HEIGHT = "height"
    PP = "pp"
    LURK = "lurk"
    HELP = "help"

    EXPLODE = "explode"
    REKLOP = "reklop"
    RANDY = "randy"
    BARK = "bark"
    CAR = "car"

    KAMIKAZE = "kamikaze"


@dataclass(frozen=True)
class FeatureDefaults:
    channel: bool = True
    timers: bool = True
    ad_announcements: bool = False
    points: bool = True
    redeems: bool = True
    community_events: bool = True
    raid_responses: bool = True

    def is_enabled(self, feature: FeatureName) -> bool:
        return bool(getattr(self, feature.value))

    def as_dict(self) -> dict[FeatureName, bool]:
        return {feature: self.is_enabled(feature) for feature in FeatureName}


@dataclass(frozen=True)
class GlobalCommandDefaults:
    enabled: bool = True

    points: bool = True
    viewer_queue: bool = True
    shoutouts: bool = True
    socials: bool = True
    settings: bool = True
    clips: bool = True

    hi: bool = True
    choice: bool = True
    kaboom: bool = True
    stinky: bool = True
    lucky: bool = True
    smart: bool = True
    height: bool = True
    pp: bool = True
    lurk: bool = True
    help: bool = True

    explode: bool = True
    reklop: bool = True
    randy: bool = True
    bark: bool = True
    car: bool = True

    kamikaze: bool = True

    def is_group_enabled(self, group: GlobalCommandGroup) -> bool:
        if group is GlobalCommandGroup.GLOBALS:
            return self.enabled

        return bool(getattr(self, group.value))

    def is_command_enabled(self, command: GlobalCommandName) -> bool:
        return bool(getattr(self, command.value))

    def groups_as_dict(self) -> dict[GlobalCommandGroup, bool]:
        return {group: self.is_group_enabled(group) for group in GlobalCommandGroup}

    def commands_as_dict(self) -> dict[GlobalCommandName, bool]:
        return {command: self.is_command_enabled(command) for command in GlobalCommandName}


@dataclass(frozen=True)
class CommunityMessages:
    follow: str | None = None
    subscription: str | None = None
    resubscription: str | None = None


@dataclass(frozen=True)
class RaidMessages:
    incoming: str | None = None
    outgoing: str | None = None
    outgoing_subscriber: str | None = None


@dataclass(frozen=True)
class ShoutoutMessages:
    with_game: str = (
        "Go check out @{username}! They were last playing {game_name}. "
        "They are a cool rat: {channel_url}"
    )
    without_game: str = (
        "Go check out @{username}! They are a cool rat: {channel_url}"
    )


@dataclass(frozen=True)
class SocialMessages:
    overview: str = "Discord: {discord_url} | YouTube: {youtube_url}"
    discord: str = "Join the community on Discord: {discord_url}"
    youtube: str = "Catch up on YouTube: {youtube_url}"
    discord_unavailable: str = "No Discord link has been set for this channel yet."
    youtube_unavailable: str = "No YouTube link has been set for this channel yet."


@dataclass(frozen=True)
class FirstChatShoutout:
    user_id: str
    username: str
    message: str | None = None
    native_shoutout: bool = True


@dataclass(frozen=True)
class ClipMessages:
    processing: str = "Creating a {duration}-second clip for @{username}..."
    success: str = "@{username} caught that! {clip_url}"
    cooldown: str = "@{username}, clips are on cooldown for another {seconds} seconds."
    in_progress: str = "@{username}, another clip is already being created."
    offline: str = "@{username}, clips can only be created while the stream is live."
    unavailable: str = "@{username}, clips are not available for this stream."
    authorization_required: str = "The broadcaster needs to reconnect their Twitch account before clips can be created."
    failed: str = "@{username}, Twitch could not create that clip. Please try again later."
    usage: str = "Use !clip for 60 seconds or !clip short for 30 seconds."


@dataclass(frozen=True)
class ClipConfig:
    duration: int = 60
    short_duration: int = 30
    cooldown_seconds: int = 120
    processing_timeout_seconds: int = 15
    title: str = "{channel_name} clipped by {username}"
    messages: ClipMessages = ClipMessages()


@dataclass(frozen=True)
class RedeemMessages:
    stream_offline: str = "@{username}, this redeem only works while the stream is live."
    daily_already_claimed: str = "@{username}, you already claimed your stream daily reward."
    daily_success: str = (
        "@{username} claimed their stream daily reward and received "
        "{amount} points! They have collected their daily reward "
        "{claim_count} times!"
    )
    daily_double: str = (
        "Lucky day! @{username} received a double daily reward of "
        "{amount} points! They have collected their daily reward "
        "{claim_count} times!"
    )
    daily_milestone: str = (
        "Milestone! @{username} has collected their daily reward "
        "{claim_count} times!"
    )
    first_already_claimed_by: str = (
        "@{username}, this stream's first redeem was already "
        "claimed by @{winner}."
    )
    first_already_claimed: str = "@{username}, this stream's first redeem was already claimed."
    first_success: str = (
        "@{username} was first this stream and received "
        "{amount} points! They have claimed first "
        "{claim_count} times!"
    )
    first_milestone: str = (
        "Milestone! @{username} has claimed first "
        "{claim_count} times!"
    )
    second_already_claimed_by: str = (
        "@{username}, this stream's second redeem was already "
        "claimed by @{winner}."
    )
    second_already_claimed: str = "@{username}, this stream's second redeem was already claimed."
    second_success: str = (
        "@{username} was second this stream and received "
        "{amount} points! They have claimed second "
        "{claim_count} times!"
    )
    second_milestone: str = (
        "Milestone! @{username} has claimed second "
        "{claim_count} times!"
    )
    timeout_success: str = "@{username} has timed themselves out for {minutes} minutes!"
    timeout_failed: str = "@{username}, Twitch could not time you out."


@dataclass(frozen=True)
class TimeoutRedeemConfig:
    title: str = ""
    duration_seconds: int = 0
    reason: str = "Bye bye."
    restore_moderator: bool = False


@dataclass(frozen=True)
class TargetTimeoutRedeemConfig:
    title: str
    target_user_id: str
    target_username: str
    duration_seconds: int
    success_message: str = "@{target_username} has been timed out for {minutes} minutes!"
    failure_message: str = "Twitch could not time out @{target_username}."
    reason: str = "Targeted channel point redemption."
    counter_name: str | None = None
    counter_message: str | None = None


@dataclass(frozen=True)
class RedeemConfig:
    daily_title: str = ""
    first_title: str = ""
    second_title: str = ""
    daily_amount: int = 0
    first_amount: int = 0
    second_amount: int = 0
    daily_double_chance: float = 0.05
    claim_milestones: tuple[int, ...] = (10, 25, 50, 100, 250, 500, 1000)
    messages: RedeemMessages = RedeemMessages()
    timeout: TimeoutRedeemConfig = TimeoutRedeemConfig()
    target_timeouts: tuple[TargetTimeoutRedeemConfig, ...] = ()


@dataclass(frozen=True)
class PointsMessages:
    balance_self: str = "{username}, you have {points} points!"
    balance_other: str = "{username} has {points} points!"
    leaderboard_empty: str = "No points have been collected yet."
    leaderboard_entry: str = "{position}. {username}: {points} points"
    leaderboard_title: str = "Top point holders: {leaderboard}"
    reset_denied: str = "Only the broadcaster can reset the points."
    reset_success: str = "This channel's points have been reset."
    add_denied: str = "Only moderators can add points to viewers."
    add_invalid: str = "The points amount must be greater than 0."
    add_success: str = "Added {amount} points to {username}."
    gamble_no_points: str = "You do not have any points to gamble."
    gamble_usage: str = "Use it like this: !{command} gamble 50 or !{command} gamble all"
    gamble_invalid: str = "You need to gamble at least 1 point."
    gamble_insufficient: str = "You only have {points} points."
    gamble_win: str = "{username} won {amount} points and now has {new_balance} points!"
    gamble_all_win: str = "{username} doubled their points and now has {new_balance} points!"
    gamble_loss: str = "{username} lost {amount} points and now has {new_balance} points."
    gamble_all_loss: str = "{username} lost all their points."
    duel_usage: str = "Use it like this: !{command} duel @user 100"
    duel_amount_invalid: str = "The duel amount must be a number or 'all'."
    duel_self: str = "You cannot duel yourself."
    duel_invalid: str = "The duel amount must be greater than 0."
    duel_challenger_insufficient: str = "You only have {points} points."
    duel_opponent_insufficient: str = "{username} only has {points} points."
    duel_challenge: str = (
        "@{opponent}, @{challenger} challenged you for {amount} points! "
        "Type !{command} duel accept or !{command} duel decline. "
        "This duel expires in {expiration} seconds."
    )
    duel_missing: str = "You do not have a pending duel, or it expired."
    duel_cancelled: str = "The duel was cancelled because someone no longer has enough points."
    duel_result: str = "@{winner} beat @{loser} and won {amount} points."
    duel_declined: str = "{username} declined the duel."


@dataclass(frozen=True)
class PointsConfig:
    command_name: str = "points"
    points_per_message: int = 10
    message_cooldown_seconds: int = 60
    gamble_win_chance: float = 0.45
    duel_expiration_seconds: int = 60
    messages: PointsMessages = PointsMessages()


@dataclass(frozen=True)
class OverwatchConfig:
    player_id: str = ""
    platform: str = "pc"
    allowed_games: tuple[str, ...] = ("Overwatch 2",)


@dataclass(frozen=True)
class ChannelProfile:
    channel_name: str
    components: tuple[type[commands.Component], ...] = ()
    protected_user_ids: tuple[str, ...] = ()
    features: FeatureDefaults = FeatureDefaults()
    globals: GlobalCommandDefaults = GlobalCommandDefaults()
    timer_messages: tuple[str, ...] = ()
    community_messages: CommunityMessages = CommunityMessages()
    raid_messages: RaidMessages = RaidMessages()
    shoutout_messages: ShoutoutMessages = ShoutoutMessages()
    social_messages: SocialMessages = SocialMessages()
    first_chat_shoutouts: tuple[FirstChatShoutout, ...] = ()
    clips: ClipConfig = ClipConfig()
    redeems: RedeemConfig = RedeemConfig()
    points: PointsConfig = PointsConfig()
    overwatch: OverwatchConfig = OverwatchConfig()

    def is_user_protected(self, user_id: str) -> bool:
        return str(user_id) in self.protected_user_ids


CHANNEL_PROFILES: dict[str, ChannelProfile] = {}
ACTIVE_CHANNEL_PROFILES: dict[str, ChannelProfile] = {}


def register_profile(profile: ChannelProfile) -> None:
    channel_name = profile.channel_name.lower()

    if channel_name in CHANNEL_PROFILES:
        LOGGER.error(
            "[Profiles] Duplicate profile registration attempted for %s.",
            channel_name
        )
        raise ValueError(f"A channel profile is already registered for {channel_name}.")

    CHANNEL_PROFILES[channel_name] = profile

    LOGGER.debug(
        "[Profiles] Registered channel profile %s.",
        channel_name
    )


def activate_profile(broadcaster_id: str, profile: ChannelProfile) -> None:
    broadcaster_id = str(broadcaster_id)
    ACTIVE_CHANNEL_PROFILES[broadcaster_id] = profile

    LOGGER.info(
        "[Profiles] Activated profile %s for broadcaster %s.",
        profile.channel_name,
        broadcaster_id
    )


def get_active_profile(broadcaster_id: str) -> ChannelProfile | None:
    broadcaster_id = str(broadcaster_id)
    profile = ACTIVE_CHANNEL_PROFILES.get(broadcaster_id)

    if profile is None:
        LOGGER.debug(
            "[Profiles] No active profile found for broadcaster %s.",
            broadcaster_id
        )

    return profile


def render_profile_message(template: str | None, **values) -> str | None:
    if not template:
        LOGGER.debug(
            "[Profiles] Skipping message rendering because no template was configured."
        )
        return None

    try:
        return template.format_map(values).strip()
    except KeyError as error:
        LOGGER.warning(
            "[Profiles] Unknown placeholder %s in profile message template: %s",
            error,
            template
        )
        return None


def clear_profiles() -> None:
    registered_count = len(CHANNEL_PROFILES)
    active_count = len(ACTIVE_CHANNEL_PROFILES)

    CHANNEL_PROFILES.clear()
    ACTIVE_CHANNEL_PROFILES.clear()

    LOGGER.info(
        "[Profiles] Cleared %d registered profiles and %d active profiles.",
        registered_count,
        active_count
    )

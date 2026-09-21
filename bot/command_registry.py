from dataclasses import dataclass
from enum import Enum

from bot.profiles import ChannelProfile, FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName


class CommandPermission(str, Enum):
    EVERYONE = "Everyone"
    MODERATOR = "Broadcaster/mod"
    BROADCASTER = "Broadcaster"


class CommandAvailability(str, Enum):
    ALWAYS = "always"
    LIVE_ONLY = "live_only"


class CommandSlowmode(str, Enum):
    SHARED = "shared"
    EXEMPT = "exempt"


class CommandVisibility(str, Enum):
    PUBLIC = "public"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class CommandDefinition:
    syntax: str
    description: str
    permission: CommandPermission = CommandPermission.EVERYONE
    feature: FeatureName | None = None
    global_group: GlobalCommandGroup | None = None
    global_command: GlobalCommandName | None = None
    profile_feature: ProfileFeatureName | None = None
    aliases: tuple[str, ...] = ()
    availability: CommandAvailability = CommandAvailability.ALWAYS
    slowmode: CommandSlowmode = CommandSlowmode.SHARED
    visibility: CommandVisibility = CommandVisibility.PUBLIC

    def __post_init__(self) -> None:
        enum_fields = (
            ("permission", self.permission, CommandPermission),
            ("availability", self.availability, CommandAvailability),
            ("slowmode", self.slowmode, CommandSlowmode),
            ("visibility", self.visibility, CommandVisibility),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise TypeError(f"Command {field_name} must be a {enum_type.__name__} for {self.syntax}.")

        normalized_aliases = tuple(alias.casefold().strip() for alias in self.aliases if alias.strip())

        if len(normalized_aliases) != len(set(normalized_aliases)):
            raise ValueError(f"Command aliases must be unique for {self.syntax}.")

        object.__setattr__(self, "aliases", normalized_aliases)

    @property
    def name(self) -> str:
        return self.syntax.removeprefix("!").split(maxsplit=1)[0].casefold()

    @property
    def is_root_command(self) -> bool:
        tokens = self.syntax.removeprefix("!").split(maxsplit=1)
        return len(tokens) == 1 or tokens[1].startswith(("<", "["))


@dataclass(frozen=True)
class CommandGroupDefinition:
    name: str
    description: str
    commands: tuple[CommandDefinition, ...]


@dataclass(frozen=True)
class CommandHelpItem:
    syntax: str
    description: str
    permission: str
    enabled: bool


@dataclass(frozen=True)
class CommandHelpGroup:
    name: str
    description: str
    commands: tuple[CommandHelpItem, ...]

    @property
    def enabled_count(self) -> int:
        return sum(command.enabled for command in self.commands)


UTILITY_COMMANDS = CommandGroupDefinition(
    name="Utility",
    description="Quick chat interactions and random community commands.",
    commands=(
        CommandDefinition("!hi [username]", "Say hello to yourself or another chatter.", global_command=GlobalCommandName.HI),
        CommandDefinition("!choice <options>", "Randomly choose from the supplied space-separated options.", global_command=GlobalCommandName.CHOICE),
        CommandDefinition("!kaboom [username]", "Blow yourself or another chatter up.", global_command=GlobalCommandName.KABOOM),
        CommandDefinition("!stinky [username]", "Generate a random stinky percentage.", global_command=GlobalCommandName.STINKY),
        CommandDefinition("!lucky [username]", "Generate a random luck percentage.", global_command=GlobalCommandName.LUCKY),
        CommandDefinition("!smart [username]", "Generate a random smart percentage.", global_command=GlobalCommandName.SMART),
        CommandDefinition("!height [username]", "Generate a height from 1' 0\" through 8' 0\".", global_command=GlobalCommandName.HEIGHT),
        CommandDefinition("!pp [username]", "Generate a measurement from -1in through 20in.", global_command=GlobalCommandName.PP),
        CommandDefinition("!lurk", "Let chat know you are stepping away to lurk.", global_command=GlobalCommandName.LURK),
        CommandDefinition("!help", "Show the compact command list in Twitch chat.", global_command=GlobalCommandName.HELP),
        CommandDefinition("!stats [username]", "Open your public chatter profile or another chatter's profile.", global_command=GlobalCommandName.STATS)
    )
)

VIEWER_QUEUE_COMMANDS = CommandGroupDefinition(
    name="Viewer queue",
    description="Manage the channel's viewer-game queue.",
    commands=(
        CommandDefinition("!open", "Open the viewer queue.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!close", "Close the viewer queue without clearing it.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!join", "Join the currently open viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!leave", "Leave the viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!queue", "Display the current viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!next", "Remove and announce the next queued viewer.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!remove <position>", "Remove a viewer by their queue position.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!swap <position> <position>", "Exchange two viewers' queue positions.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!requeue <position> <new position>", "Move a queued viewer to another position.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!clear", "Remove everyone from the viewer queue.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.VIEWER_QUEUE)
    )
)

SOCIAL_COMMANDS = CommandGroupDefinition(
    name="Socials",
    description="Share the channel's configured community links.",
    commands=(
        CommandDefinition("!socials", "Show every configured social link.", global_group=GlobalCommandGroup.SOCIALS),
        CommandDefinition("!socials discord", "Show the configured Discord link.", global_group=GlobalCommandGroup.SOCIALS),
        CommandDefinition("!socials youtube", "Show the configured YouTube link.", global_group=GlobalCommandGroup.SOCIALS)
    )
)

SETTINGS_COMMANDS = CommandGroupDefinition(
    name="Settings",
    description="Update stream information, channel links, and recurring timer messages.",
    commands=(
        CommandDefinition("!set game <game name>", "Change the stream's Twitch category.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!set title <stream title>", "Change the stream title.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!set slowmode on|off", "Limit viewers to one command every two minutes, shared across commands; mods, broadcaster, and kamikaze are exempt.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!set discord <url>", "Update the channel's Discord link.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!set youtube <url>", "Update the channel's YouTube link.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!timers [on|off]", "View or change the recurring timer-message state.", CommandPermission.MODERATOR, global_group=GlobalCommandGroup.SETTINGS)
    )
)

SHOUTOUT_COMMANDS = CommandGroupDefinition(
    name="Shoutouts",
    description="Promote another Twitch broadcaster in chat.",
    commands=(
        CommandDefinition(
            "!so <username>",
            "Queue a profile message and native Twitch shoutout.",
            CommandPermission.MODERATOR,
            global_group=GlobalCommandGroup.SHOUTOUTS,
            aliases=("shoutout",)
        ),
    )
)

CLIP_COMMANDS = CommandGroupDefinition(
    name="Clips",
    description="Create a Twitch clip from the current broadcast.",
    commands=(
        CommandDefinition(
            "!clip",
            "Create a clip using the profile's normal duration.",
            global_group=GlobalCommandGroup.CLIPS,
            aliases=("clips",),
            availability=CommandAvailability.LIVE_ONLY
        ),
        CommandDefinition(
            "!clip short",
            "Create a clip using the profile's short duration.",
            global_group=GlobalCommandGroup.CLIPS,
            availability=CommandAvailability.LIVE_ONLY
        )
    )
)

RAID_COMMANDS = CommandGroupDefinition(
    name="Raids",
    description="Start an outgoing raid and send both configured raid messages.",
    commands=(
        CommandDefinition(
            "!startraid <channel>",
            "Start a Twitch raid to another channel.",
            CommandPermission.BROADCASTER,
            feature=FeatureName.RAID_RESPONSES,
            availability=CommandAvailability.LIVE_ONLY
        ),
    )
)

RAID_BOSS_COMMANDS = CommandGroupDefinition(
    name="Raid Bosses",
    description="Fight live raid bosses, manage your equipment, and spend loyalty points on raid upgrades.",
    commands=(
        CommandDefinition("!raid", "Show the current raid encounter and its remaining health.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition(
            "!raid attack",
            "Attack the active boss once per stream; Second Wind can grant one extra attack.",
            feature=FeatureName.RAID_BOSSES,
            availability=CommandAvailability.LIVE_ONLY
        ),
        CommandDefinition("!raid help", "Open the complete public raid guide, shop, and crafting reference.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid shop", "Show Basic weapons and the Power Potion in Twitch chat.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid buy <item>", "Buy a Basic weapon, Power Potion, Second Wind, Berserk, or Blessing of the Gods.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid craft <sword|bow|tome>", "Automatically craft the highest available tier from two matching weapons and points.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid sell <weapon>", "Sell one Basic, Refined, Masterwork, or Overclocked weapon for half its value.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid equip <weapon>", "Equip an owned raid weapon for future attacks.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid unequip", "Unequip your current weapon and use base damage instead.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid inventory", "Show owned weapons, equipped durability, and stored consumables.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid repair <weapon>", "Restore an owned weapon to full durability for loyalty points.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid loot", "Show rewards earned from your most recent completed raid.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid leaderboard", "Show the current boss’s damage leaderboard.", feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid spawn <tier> <type>", "Schedule a tutorial, mini, or main boss for testing or moderation.", CommandPermission.MODERATOR, feature=FeatureName.RAID_BOSSES),
        CommandDefinition("!raid end", "Conclude the active encounter and distribute the points earned from damage.", CommandPermission.MODERATOR, feature=FeatureName.RAID_BOSSES)
    )
)

MODERATION_COMMANDS = CommandGroupDefinition(
    name="Moderation",
    description="Community moderation games and actions.",
    commands=(
        CommandDefinition(
            "!kamikaze <username>",
            "Time out yourself and a selected chatter.",
            global_command=GlobalCommandName.KAMIKAZE,
            slowmode=CommandSlowmode.EXEMPT
        ),
    )
)

OVERWATCH_COMMANDS = CommandGroupDefinition(
    name="Overwatch",
    description="Live Overwatch rank and competitive session tracking commands.",
    commands=(
        CommandDefinition("!ow", "Show the current session record and available competitive ranks.", profile_feature=ProfileFeatureName.OVERWATCH),
        CommandDefinition("!owrank", "Show available competitive ranks.", profile_feature=ProfileFeatureName.OVERWATCH),
        CommandDefinition("!owrecord <win|loss>", "Record a match result for the current session.", CommandPermission.MODERATOR, profile_feature=ProfileFeatureName.OVERWATCH),
        CommandDefinition("!owreset", "Reset the current session record to 0W-0L.", CommandPermission.MODERATOR, profile_feature=ProfileFeatureName.OVERWATCH)
    )
)

LEAGUE_COMMANDS = CommandGroupDefinition(
    name="League of Legends",
    description="Ranked champion statistics, broadcaster builds, and the channel's community League ladder.",
    commands=(
        CommandDefinition("!champs", "Show the broadcaster's five most-played ranked champions this season.", profile_feature=ProfileFeatureName.LEAGUE),
        CommandDefinition("!champs <champion>", "Show the broadcaster's common three-item core from ranked games in the last 14 days.", profile_feature=ProfileFeatureName.LEAGUE),
        CommandDefinition("!register <Riot ID> [region]", "Register your Riot ID and join this channel's League ladder.", profile_feature=ProfileFeatureName.LEAGUE),
        CommandDefinition("!unregister", "Remove your League registration and saved rank history from this channel.", profile_feature=ProfileFeatureName.LEAGUE),
        CommandDefinition("!rank [chatter]", "Show your rank or another registered chatter's rank.", profile_feature=ProfileFeatureName.LEAGUE),
        CommandDefinition("!ladder", "Show the channel's Solo/Duo community leaderboard.", profile_feature=ProfileFeatureName.LEAGUE)
    )
)

BASE_COMMAND_GROUPS = (
    UTILITY_COMMANDS,
    VIEWER_QUEUE_COMMANDS,
    SOCIAL_COMMANDS,
    SETTINGS_COMMANDS,
    SHOUTOUT_COMMANDS,
    CLIP_COMMANDS,
    RAID_COMMANDS,
    RAID_BOSS_COMMANDS,
    MODERATION_COMMANDS
)


HIDDEN_SHARED_COMMANDS = (
    CommandDefinition(
        "!gamble [amount|all]",
        "Show how to use the channel's grouped gamble command.",
        feature=FeatureName.POINTS,
        global_group=GlobalCommandGroup.POINTS,
        visibility=CommandVisibility.HIDDEN
    ),
    CommandDefinition("!explode", "Private shared counter.", aliases=("rat",), visibility=CommandVisibility.HIDDEN),
    CommandDefinition("!reklop", "Private shared counter.", visibility=CommandVisibility.HIDDEN),
    CommandDefinition("!randy", "Private shared counter.", visibility=CommandVisibility.HIDDEN),
    CommandDefinition("!bark", "Private shared counter.", aliases=("wxlfiix",), visibility=CommandVisibility.HIDDEN),
    CommandDefinition("!car", "Private shared counter.", visibility=CommandVisibility.HIDDEN),
    CommandDefinition(
        "!raid nextstream",
        "Raid testing control.",
        CommandPermission.MODERATOR,
        feature=FeatureName.RAID_BOSSES,
        visibility=CommandVisibility.HIDDEN
    )
)


PROFILE_TEST_COMMANDS = {
    "barbatos2upusr3x": "templatetest",
    "developer_ninjakaing": "devtest",
    "lunaaratv": "lunatest",
    "milky_galaxyvt": "milkygalaxytest",
    "ninjakaing": "ninjatest",
    "okkayay": "oktest",
    "onedaybread": "breadtest",
    "pikalulz": "pikatest",
    "steohanyy": "steohanyytest",
    "template_profile": "templatetest",
    "xxemares": "xxemarestest"
}


def build_points_group(profile: ChannelProfile) -> CommandGroupDefinition:
    command = profile.points.command_name or "points"
    commands = [
        CommandDefinition(f"!{command} [username]", "Show your balance or another chatter's balance.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} leaderboard", "Show the channel's points leaderboard.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} give <username> <amount>", "Give some of your points to another chatter.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} gamble <amount|all>", "Gamble some or all of your current balance.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} duel <username> <amount>", "Challenge another chatter to a points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} duel accept", "Accept your pending points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} duel decline", "Decline your pending points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} add <username> <amount>", "Add points to a chatter's balance.", CommandPermission.MODERATOR, feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
        CommandDefinition(f"!{command} reset", "Reset every stored balance for the channel.", CommandPermission.BROADCASTER, feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS)
    ]

    commands.append(CommandDefinition(
        f"!{command} roulette <red|black|green> <amount>",
        "Bet channel points on a roulette color.",
        feature=FeatureName.POINTS,
        global_group=GlobalCommandGroup.POINTS,
        aliases=("spin",)
    ))

    return CommandGroupDefinition(
        name="Points",
        description="View, earn, gamble, and challenge others with the channel's loyalty currency.",
        commands=tuple(commands)
    )


def get_profile_command_groups(profile: ChannelProfile) -> tuple[CommandGroupDefinition, ...]:
    channel_name = profile.channel_name.lower()
    groups: list[CommandGroupDefinition] = []

    if channel_name == "meinyayozakura":
        groups.append(CommandGroupDefinition(
            name="Channel-specific",
            description="Commands created specifically for MeinyaYozakura.",
            commands=(
                CommandDefinition("!hbd", "Send Meinya a happy birthday message.", feature=FeatureName.CHANNEL),
                CommandDefinition("!throne", "Show Meinya's Throne support link.", feature=FeatureName.CHANNEL),
                CommandDefinition("!discord", "Show Meinya's configured Discord link.", feature=FeatureName.CHANNEL),
                CommandDefinition("!youtube", "Show Meinya's configured YouTube link.", feature=FeatureName.CHANNEL)
            )
        ))

    if profile.overwatch.player_id:
        groups.append(OVERWATCH_COMMANDS)

    if profile.league.enabled or profile.league.game_name or profile.league.tag_line:
        groups.append(LEAGUE_COMMANDS)

    return tuple(groups)


def get_registered_definitions(profile: ChannelProfile) -> tuple[CommandDefinition, ...]:
    """Return public and hidden metadata for every command available to a profile."""
    groups = (*BASE_COMMAND_GROUPS, build_points_group(profile), *get_profile_command_groups(profile))
    definitions = tuple(command for group in groups for command in group.commands) + HIDDEN_SHARED_COMMANDS
    test_command = PROFILE_TEST_COMMANDS.get(profile.channel_name.casefold())

    if test_command:
        definitions += (CommandDefinition(
            f"!{test_command}",
            "Profile connectivity test.",
            feature=FeatureName.CHANNEL,
            visibility=CommandVisibility.HIDDEN
        ),)

    validate_command_definitions(definitions)
    return definitions


def get_shared_command_definitions() -> tuple[CommandDefinition, ...]:
    """Return metadata for every command registered by a shared component."""
    default_points = build_points_group(ChannelProfile(channel_name="registry"))
    groups = (*BASE_COMMAND_GROUPS, default_points, OVERWATCH_COMMANDS, LEAGUE_COMMANDS)
    return tuple(command for group in groups for command in group.commands) + HIDDEN_SHARED_COMMANDS


def validate_command_definitions(definitions: tuple[CommandDefinition, ...]) -> None:
    """Fail fast when registry metadata is malformed or internally contradictory."""
    seen_syntax = set()

    for command in definitions:
        if not command.syntax.startswith("!"):
            raise ValueError(f"Command syntax must start with !: {command.syntax}")

        normalized_syntax = " ".join(command.syntax.casefold().split())

        if normalized_syntax in seen_syntax:
            raise ValueError(f"Duplicate command syntax: {command.syntax}")

        seen_syntax.add(normalized_syntax)

        if command.name in command.aliases:
            raise ValueError(f"Command {command.syntax} cannot alias itself.")


SHARED_COMMAND_DEFINITIONS = get_shared_command_definitions()
validate_command_definitions(SHARED_COMMAND_DEFINITIONS)


def command_is_enabled(features, broadcaster_id: str, command: CommandDefinition) -> bool:
    if command.profile_feature is not None and not features.is_profile_feature_enabled(broadcaster_id, command.profile_feature):
        return False

    if command.feature is not None and not features.is_enabled(broadcaster_id, command.feature):
        return False

    if command.global_group is not None and not features.is_global_group_enabled(broadcaster_id, command.global_group):
        return False

    if command.global_command is not None and not features.is_global_command_enabled(broadcaster_id, command.global_command):
        return False

    return True


def build_command_help_groups(features, broadcaster_id: str, profile: ChannelProfile) -> tuple[CommandHelpGroup, ...]:
    definitions = (*BASE_COMMAND_GROUPS, build_points_group(profile), *get_profile_command_groups(profile))
    groups = []

    for definition in definitions:
        commands = tuple(CommandHelpItem(
            syntax=command.syntax,
            description=command.description,
            permission=command.permission.value,
            enabled=command_is_enabled(features, broadcaster_id, command)
        ) for command in definition.commands)
        groups.append(CommandHelpGroup(definition.name, definition.description, commands))

    return tuple(groups)


def build_enabled_command_help_groups(features, broadcaster_id: str, profile: ChannelProfile) -> tuple[CommandHelpGroup, ...]:
    groups = build_command_help_groups(features, broadcaster_id, profile)
    enabled_groups = []

    for group in groups:
        commands = tuple(command for command in group.commands if command.enabled)

        if commands:
            enabled_groups.append(CommandHelpGroup(group.name, group.description, commands))

    return tuple(enabled_groups)

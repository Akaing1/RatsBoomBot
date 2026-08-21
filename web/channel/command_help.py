from dataclasses import dataclass

from bot.profiles import ChannelProfile, FeatureName, GlobalCommandGroup, GlobalCommandName


@dataclass(frozen=True)
class CommandDefinition:
    syntax: str
    description: str
    permission: str = "Everyone"
    feature: FeatureName | None = None
    global_group: GlobalCommandGroup | None = None
    global_command: GlobalCommandName | None = None


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
        CommandDefinition("!help", "Show the compact command list in Twitch chat.", global_command=GlobalCommandName.HELP)
    )
)

VIEWER_QUEUE_COMMANDS = CommandGroupDefinition(
    name="Viewer queue",
    description="Manage the channel's viewer-game queue.",
    commands=(
        CommandDefinition("!open", "Open the viewer queue.", "Broadcaster/mod", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!close", "Close the viewer queue without clearing it.", "Broadcaster/mod", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!join", "Join the currently open viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!leave", "Leave the viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!queue", "Display the current viewer queue.", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!next", "Remove and announce the next queued viewer.", "Broadcaster/mod", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!remove <position>", "Remove a viewer by their queue position.", "Broadcaster/mod", global_group=GlobalCommandGroup.VIEWER_QUEUE),
        CommandDefinition("!clear", "Remove everyone from the viewer queue.", "Broadcaster/mod", global_group=GlobalCommandGroup.VIEWER_QUEUE)
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
    description="Update channel links and control recurring timer messages.",
    commands=(
        CommandDefinition("!setdiscord <url>", "Update the channel's Discord link.", "Broadcaster/mod", global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!setyoutube <url>", "Update the channel's YouTube link.", "Broadcaster/mod", global_group=GlobalCommandGroup.SETTINGS),
        CommandDefinition("!timers [on|off]", "View or change the recurring timer-message state.", "Broadcaster/mod", global_group=GlobalCommandGroup.SETTINGS)
    )
)

COUNTER_COMMANDS = CommandGroupDefinition(
    name="Counters",
    description="Increment the channel's persistent community counters.",
    commands=(
        CommandDefinition("!explode", "Add one explosion to the channel counter.", global_command=GlobalCommandName.EXPLODE),
        CommandDefinition("!reklop", "Add one Reklop to the channel counter.", global_command=GlobalCommandName.REKLOP),
        CommandDefinition("!randy", "Add one Randy to the channel counter.", global_command=GlobalCommandName.RANDY),
        CommandDefinition("!bark", "Add one bark to the channel counter.", global_command=GlobalCommandName.BARK),
        CommandDefinition("!car", "Add one car to the channel counter.", global_command=GlobalCommandName.CAR)
    )
)

SHOUTOUT_COMMANDS = CommandGroupDefinition(
    name="Shoutouts",
    description="Promote another Twitch broadcaster in chat.",
    commands=(
        CommandDefinition("!so <username>", "Queue a profile message and native Twitch shoutout.", "Broadcaster/mod", global_group=GlobalCommandGroup.SHOUTOUTS),
    )
)

CLIP_COMMANDS = CommandGroupDefinition(
    name="Clips",
    description="Create a Twitch clip from the current broadcast.",
    commands=(
        CommandDefinition("!clip", "Create a clip using the profile's normal duration.", global_group=GlobalCommandGroup.CLIPS),
        CommandDefinition("!clip short", "Create a clip using the profile's short duration.", global_group=GlobalCommandGroup.CLIPS)
    )
)

RAID_COMMANDS = CommandGroupDefinition(
    name="Raids",
    description="Start an outgoing raid and send both configured raid messages.",
    commands=(
        CommandDefinition("!startraid <channel>", "Start a Twitch raid to another channel.", "Broadcaster", feature=FeatureName.RAID_RESPONSES),
    )
)

MODERATION_COMMANDS = CommandGroupDefinition(
    name="Moderation",
    description="Community moderation games and actions.",
    commands=(
        CommandDefinition("!kamikaze <username>", "Time out yourself and a selected chatter.", global_command=GlobalCommandName.KAMIKAZE),
    )
)

BASE_COMMAND_GROUPS = (
    UTILITY_COMMANDS,
    VIEWER_QUEUE_COMMANDS,
    SOCIAL_COMMANDS,
    SETTINGS_COMMANDS,
    COUNTER_COMMANDS,
    SHOUTOUT_COMMANDS,
    CLIP_COMMANDS,
    RAID_COMMANDS,
    MODERATION_COMMANDS
)


def build_points_group(profile: ChannelProfile) -> CommandGroupDefinition:
    command = profile.points.command_name or "points"

    return CommandGroupDefinition(
        name="Points",
        description="View, earn, gamble, and challenge others with the channel's loyalty currency.",
        commands=(
            CommandDefinition(f"!{command} [username]", "Show your balance or another chatter's balance.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} leaderboard", "Show the channel's points leaderboard.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} gamble <amount|all>", "Gamble some or all of your current balance.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} duel <username> <amount>", "Challenge another chatter to a points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} duel accept", "Accept your pending points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} duel decline", "Decline your pending points duel.", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} add <username> <amount>", "Add points to a chatter's balance.", "Broadcaster/mod", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS),
            CommandDefinition(f"!{command} reset", "Reset every stored balance for the channel.", "Broadcaster", feature=FeatureName.POINTS, global_group=GlobalCommandGroup.POINTS)
        )
    )


def get_profile_command_groups(profile: ChannelProfile) -> tuple[CommandGroupDefinition, ...]:
    channel_name = profile.channel_name.lower()
    groups: list[CommandGroupDefinition] = []

    if channel_name == "meinyayozakura":
        groups.append(CommandGroupDefinition(
            name="Channel-specific",
            description="Commands created specifically for MeinyaYozakura.",
            commands=(CommandDefinition("!hbd", "Send Meinya a happy birthday message.", feature=FeatureName.CHANNEL),)
        ))

    if channel_name == "milky_galaxyvt":
        groups.append(CommandGroupDefinition(
            name="Overwatch",
            description="Milky's live Overwatch rank and session tracking commands.",
            commands=(
                CommandDefinition("!ow", "Show the current session record and available competitive ranks.", feature=FeatureName.CHANNEL),
                CommandDefinition("!owrank", "Show available competitive ranks.", feature=FeatureName.CHANNEL),
                CommandDefinition("!owrecord <win|loss>", "Record a match result for the current session.", "Broadcaster/mod", feature=FeatureName.CHANNEL),
                CommandDefinition("!owreset", "Reset the current session record to 0W-0L.", "Broadcaster/mod", feature=FeatureName.CHANNEL)
            )
        ))

    return tuple(groups)


def command_is_enabled(features, broadcaster_id: str, command: CommandDefinition) -> bool:
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
            permission=command.permission,
            enabled=command_is_enabled(features, broadcaster_id, command)
        ) for command in definition.commands)
        groups.append(CommandHelpGroup(definition.name, definition.description, commands))

    return tuple(groups)

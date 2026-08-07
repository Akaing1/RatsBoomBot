import logging

LOGGER = logging.getLogger("RatBoomBot")


class HelpService:

    def __init__(self, bot):
        self.bot = bot

    def get_commands(self) -> list[str]:
        command_names: set[str] = set()

        for command in self.bot.commands.values():
            self._collect_command(command, command_names)

        commands = sorted(command_names)

        LOGGER.debug(
            "[Commands] Collected %d commands for the help message.",
            len(commands)
        )

        return commands

    def _collect_command(self, command, command_names: set[str]) -> None:
        name = getattr(command, "qualified_name", command.name)
        command_names.add(name)

        subcommands = getattr(command, "commands", None)

        if not subcommands:
            return

        for subcommand in subcommands.values():
            self._collect_command(subcommand, command_names)

    def format_help_message(self) -> str:
        commands = self.get_commands()

        if not commands:
            LOGGER.warning(
                "[Commands] Help message requested while no commands were loaded."
            )
            return "No commands are currently loaded."

        command_text = ", ".join(f"!{name}" for name in commands)

        LOGGER.debug(
            "[Commands] Formatted help message with %d commands.",
            len(commands)
        )

        return f"Available commands: {command_text}"

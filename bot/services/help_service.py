class HelpService:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self) -> list[str]:
        command_names = set()

        for command in self.bot.commands.values():
            self._collect_command(command, command_names)

        return sorted(command_names)

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
            return "No commands are currently loaded."

        command_text = ", ".join(f"!{name}" for name in commands)

        return f"Available commands: {command_text}"
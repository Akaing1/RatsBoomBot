class HelpService:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self) -> list[str]:
        names = set()

        for command in self.bot.commands.values():
            name = getattr(command, "qualified_name", command.name)
            names.add(name)

        return sorted(names)

    def format_help_message(self) -> str:
        commands = self.get_commands()

        if not commands:
            return "No commands are currently loaded."

        command_text = ", ".join(f"!{name}" for name in commands)

        return f"Available commands: {command_text}"
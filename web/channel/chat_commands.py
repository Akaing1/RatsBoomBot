"""Completion metadata drawn from the same registry as command help."""
import re

from bot.command_registry import CommandPermission, CommandVisibility, command_is_enabled, get_registered_definitions


def chat_command_catalog(features, broadcaster_id, profile, *, moderator=False):
    if profile is None:
        return []
    result = []
    for definition in get_registered_definitions(profile):
        if definition.visibility is not CommandVisibility.PUBLIC:
            continue
        if moderator and definition.permission is CommandPermission.BROADCASTER:
            continue
        if not command_is_enabled(features, broadcaster_id, definition):
            continue
        syntaxes = [definition.syntax]
        tokens = re.findall(r'<[^>]+>|\[[^\]]+\]|\S+', definition.syntax)
        literal_count = next((i for i, token in enumerate(tokens) if token.startswith(('<', '['))), len(tokens))
        for alias in definition.aliases:
            alternate = tokens.copy()
            index = max(0, literal_count - 1)
            alternate[index] = ('!' if index == 0 else '') + alias
            syntaxes.append(' '.join(alternate))
        for syntax in syntaxes:
            value = syntax.split()[0]
            result.append(dict(kind='command', name=value[1:], value=value, syntax=syntax,
                               label=syntax, detail='BOT COMMAND', description=definition.description))
    return result

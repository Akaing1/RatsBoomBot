# Command standardization

Command metadata is owned by `bot/command_registry.py`. The registry is the backend source of truth for command documentation and for the policies a command is expected to follow.

Each command definition records:

- public syntax and aliases;
- viewer permission level;
- feature, global-group, global-command, or profile-feature gates;
- whether the command is available offline or only while live;
- whether it participates in shared command slowmode;
- whether it is public or intentionally hidden.

The channel and public help pages consume this backend registry through the compatibility exports in `web/channel/command_help.py`. Web code must not maintain a second command catalog.

## Adding a command

1. Implement the TwitchIO command in the appropriate shared or channel component.
2. Add its metadata to `bot/command_registry.py` in the matching command group.
3. Use the existing feature helpers and permission helpers that match the recorded metadata.
4. Add any decorator aliases to the registry entry. Shared-command tests require the aliases to match exactly.
5. Mark internal test and private commands as `CommandVisibility.HIDDEN`; do not omit them from the registry.
6. Add focused behavior tests for the handler and update registry-policy tests when introducing a new policy combination.

The shared registry is validated at import time for malformed and duplicate syntax. Tests also compare every shared top-level TwitchIO command and alias against the registry, so an unregistered command fails CI.

## Migration boundary

This first phase records and validates existing behavior without moving permission or feature decisions out of handlers. Later phases can consume the same metadata from common guards, one policy at a time, after parity tests exist for the affected command group.

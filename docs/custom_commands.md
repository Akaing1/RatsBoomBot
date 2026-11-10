# Custom Commands — first version

Custom Commands lives under **For You**, alongside Notes, Quotes, and Clips.
Select **Add command**, enter a name without `!`, and build its response using
blocks. Save it, preview it with **Run test**, then enable it from its list row.
New commands are disabled. Existing saved names are immutable; delete and recreate
a command to rename it. Only one command editor opens at a time. Full screen gives
nested branches more room. Blocks can be added to any branch and moved up or down
within that branch. Dragging blocks is not implemented in this first version.

Supported blocks:

- Send a message, with `{user}`, `{channel}`, `{args}`, and `{arg1}` values.
- If/else: argument present, complete arguments equal text (case insensitive),
  moderator or broadcaster, and broadcaster only.
- Random message: one of up to five choices.
- Repeat: run a sequence one to five times.

The test panel uses the same Python interpreter as chat delivery. It accepts
sample arguments and a viewer role, and returns branch traces and messages. It
never sends to Twitch, consumes cooldowns, or changes stored commands. Placeholder
values are inserted once; viewer text is never interpreted as another template.

The server accepts only the declared block schema. There is no JavaScript,
expression evaluation, network access, external command invocation, persistent
variable storage, or points mutation. Each command is limited to 40 blocks, six
nested levels, 64 execution steps, and three messages on its most expensive path.
Nested repeats count toward the same totals. Replies are single-line messages
with a maximum of 450 characters after placeholder substitution.

Permissions are everyone, moderators and broadcaster, or broadcaster only.
A shared channel cooldown (10–3600 seconds, set by the last command used) limits
all custom commands together. Existing command slowmode also applies. Built-in
commands and points aliases take priority. Incoming shared-chat relay messages
and bot messages do not invoke custom commands. Runtime definitions are cached
and refreshed after dashboard changes; startup reloads them from SQLite.

Commands are scoped to the authenticated channel. Moderators with settings
access can manage that channel's commands through their For You page. Saves,
toggles, and deletes require CSRF protection and a matching revision. A channel
can store up to 50 commands. Migration 81 creates the storage table.

The initial editor uses explicit add/move buttons. Future additions can include
dragging blocks, templates, persistent counters, and additional approved actions.

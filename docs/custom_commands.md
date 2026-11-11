# Custom Commands — first version

Custom Commands lives under **For You**, alongside Notes, Quotes, and Clips.
Select **Add command**, enter a name without `!`, and build its response using
blocks. Save it, preview it with **Run test**, then enable it from its list row.
New commands are disabled and default to a zero-second cooldown. Existing command
names can be edited; saving a rename preserves the command and checks that its new
name is available. Green/red toggles show enabled/disabled state.

The editor uses a compact canvas and a separate properties/test panel. Select a
block to edit its fields. Drag blocks to arrange the canvas; positions do not
change execution order. Drop onto another block to run before it, or onto a
True/False/Repeat body port to move into that branch. Select a branch port and
click a toolbox button to add there, or drag a toolbox block onto the canvas.
Right-click a block (or press Shift+F10) to edit, copy, duplicate, paste after,
move earlier/later, move to the main flow, or delete. Copies include branches.
Right-click blank canvas to paste into the main flow. The clipboard stays within
the current page session. Move earlier/later buttons also reorder the selected block. Arrows show sequence
and branch entry. Pan the canvas, zoom, or use Auto arrange to organize the flow.
Full screen gives the toolbox its own left column and keeps the canvas and
properties/test panel side by side on wide screens. Escape exits full screen.

Supported blocks:

- Send a message with structured values: `{user.name}`, `{user.mention}`,
  `{user.channel}`, `{arg.name}`, `{arg.mention}`, `{arg.channel}`,
  `{channel.name}`, and `{channel.url}`. The argument fields use the first
  argument as a Twitch username (an optional leading `@` is removed). Channel
  values are Twitch URLs; invalid/missing usernames produce an empty value.
  Existing `{user}`, `{channel}`, `{args}`, and `{arg1}` placeholders still work.
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
A shared channel cooldown (0–3600 seconds, set by the last command used) limits
all custom commands together. Zero adds no cooldown; it does not clear an already
active cooldown from another command. Existing command slowmode also applies. Built-in
commands and points aliases take priority. Incoming shared-chat relay messages
and bot messages do not invoke custom commands. Runtime definitions are cached
and refreshed after dashboard changes; startup reloads them from SQLite.

Commands are scoped to the authenticated channel. Moderators with settings
access can manage that channel's commands through their For You page. Saves,
renames, toggles, and deletes require CSRF protection and a matching revision. A channel
can store up to 50 commands. Migration 81 creates the storage table.

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
- Random Number: generate a whole number between inclusive minimum/maximum
  bounds (default 1–100) into a named, per-run result. For example, name it
  `roll`, then send `{user.name} rolled {random.roll}!`. Bounds must be between
  -1 billion and 1 billion; equal bounds always return that number. Multiple
  references reuse the same result until another block overwrites that name.
  The value picker only offers results guaranteed to have run before the selected
  message. Save and preview reject early references, including a roll defined
  in only one branch and then used after the branches merge.
  Results do not persist between invocations. Referencing a result before its
  block runs fails the command before counter changes or messages are committed.
  Test output includes generated values and their ranges.
- Counter: increase, decrease, or set a named channel counter. Missing counters
  start at 0. Counters persist across streams and are shared by all commands in
  that channel. Add a counter block named `deaths` with Increase by 1, followed
  by a message `Deaths: {counter.deaths}`. Use Set to 0 to reset it.

Repeat is removed from the toolbox. Saved legacy Repeat blocks remain supported
for compatibility, including their original execution/output limits.

The test panel uses the same Python interpreter as chat delivery. It accepts
sample arguments and a viewer role, and returns branch traces and messages. It
never sends to Twitch, consumes cooldowns, or changes stored commands or counters.
Tests start with the saved channel counters and show simulated counter results. Placeholder
values are inserted once; viewer text is never interpreted as another template.

The server accepts only the declared block schema. There is no JavaScript,
expression evaluation, network access, external command invocation, arbitrary persistent
variable storage, or points mutation. Named integer counters are the only mutable
custom-command state. Each command is limited to 40 blocks, six
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
can store up to 50 commands. Migration 81 creates the command table; migration 82 creates the counter table.
Counter updates within one invocation commit atomically before chat delivery,
preventing lost increments when commands run concurrently. A delivery failure
does not undo an already committed count. Counters are limited to 100 per channel,
with values between -1 trillion and 1 trillion, and block amounts between
-1 billion and 1 billion. Counter names follow the command naming rules.

Live custom-command replies are spaced at least 1.1 seconds apart per channel.
Twitch message drops (including duplicate replies) are logged as warnings and
later replies continue. An HTTP 429 pauses delivery for 30 seconds, then retries
only the failed reply once per invocation; a second 429 stops the remaining
replies and starts another 30-second backoff. Counter changes are never rerun
on delivery retries. Invocations arriving while that channel is already executing
or backing off are ignored before counters execute, preventing a growing queue.
Configured cooldowns remain independent of these delivery protections.

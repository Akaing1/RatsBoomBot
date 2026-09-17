# Command slowmode

Moderators and broadcasters can use `!set slowmode on` or `!set slowmode off`.
`!set slowmode` reports the current state. The setting defaults to off and is saved per channel.

When enabled, each viewer can invoke one bot command every 120 seconds, shared across commands and aliases. Further attempts are silently ignored before execution and do not extend the deadline. Moderators, the broadcaster, and `!kamikaze` are exempt; kamikaze retains its own cooldown and does not consume this one. Ordinary chat is unaffected. The rule applies online and offline.

The setting survives restarts. Viewer cooldown timers reset on restart and are cleared when slowmode is disabled. Admitted attempts consume the slot even if later validation rejects their arguments or action.

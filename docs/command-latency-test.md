# Command latency comparison

Deploy v11.6.2 to the environment exhibiting the delay before testing. Use the same bot/environment and the same sending account in both channels. Use Minamichimaa and one previously fast code-profile channel; both may be offline.

1. Ensure the test account is a moderator/broadcaster in both channels, or disable command slowmode temporarily in both with `!set slowmode off` and restore its prior state afterward. Note whether the account is a moderator in each channel and whether Twitch Non-Mod Chat Delay is enabled.
2. On the Pi, watch the relevant service:

   ```bash
   sudo journalctl -u ratsboombot.service -f -o short-iso-precise
   ```

   For UAT use `ratsboombot-uat.service` instead. Do not compare production against UAT.
3. Send `!hi` in Minamichimaa, wait for its response, and wait another 10 seconds. Send `!hi` in the fast channel. Repeat this pair three times. Record the channel, command, approximate local send time, and observed delay; a short screen recording with both chats visible is useful if convenient.
4. Repeat the same sequence three times with bare `!points` (no username or subcommand). This gives 12 commands total. Avoid gambling or other concurrent test commands.
5. Export the full journal window so wrapped lines, API errors, and custom-identity fallback logs are preserved:

   ```bash
   sudo journalctl -u ratsboombot.service --since "20 minutes ago" -o short-iso-precise --no-pager > /tmp/ratsboombot-command-latency.log
   ```

   Substitute the UAT service when appropriate. Share this file with the observations.

## Reading the results

Each `[CommandTiming]` record includes channel name/ID, incoming message ID, command, stage, and monotonic elapsed milliseconds. No message arguments, reply bodies, or tokens are logged.

- `received`: command context created locally. This is not the time the viewer sent the message or the socket received the EventSub frame.
- `send_start`: reply handling begins. `elapsed_ms` measures local work since context creation.
- `send_complete`: reply handling returned. `send_ms` includes the API request and any retry/custom-identity fallback. `is_sent` reports the returned Twitch response field when available, not viewer-visible delivery.
- `send_failed`: reply handling raised; existing error handling remains in effect.

Large `elapsed_ms` at send_start indicates delay before sending. Large `send_ms` indicates delay in the outbound path. If both are small but the visible reply takes seconds, these logs alone cannot distinguish inbound delivery delay from downstream chat display delay; compare the screen observations next. Missing send markers may mean the command was blocked/disabled, failed before sending, or had an empty configured response.

Diagnostics are limited to `!hi` and `!points` (including points subcommands). INFO records appear in the service journal offline without enabling global DEBUG logging. These markers do not change slowmode or command behavior.

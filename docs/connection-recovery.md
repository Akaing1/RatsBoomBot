# Connection recovery and warning handling

Version 15.3.3 adds a local shard watchdog after Twitch startup completes.
Every 15 seconds it checks the connected shard count. Five continuous minutes
with missing/disconnected shards triggers a diagnostic snapshot and runtime exit.
A healthy sample resets the grace period; quiet chat is not a failure signal.
This is intended for the existing single-process-per-conduit deployment.

Snapshots every five minutes include RSS, thread/file-descriptor/task counts and
event-loop lag. Before recovery, up to 30 task stack locations are recorded,
without frame locals. Existing performance history remains enabled.

Recovery first unwinds the runtime. A daemon timer forces exit after 20 seconds
if cleanup hangs, allowing systemd's Restart=always to relaunch the process.
Forced exit can interrupt in-flight work; this is a fallback for sustained
disconnection, not evidence that its underlying cause has been fixed.
The web server also has a ten-second graceful-shutdown deadline.
The watchdog cannot detect an event loop that never resumes or a connection
that appears locally connected but stops delivering events; startup is not monitored.

## Deployment

Use the existing deployment procedure after merging. For the restart rate limit,
update the installed service unit as well (the deploy script does not copy it):

```bash
sudo install -m 644 /opt/ratsboombot/deploy/linux/ratsboombot.service /etc/systemd/system/ratsboombot.service
sudo systemctl daemon-reload
```

The unit permits five starts per hour, including manual starts. If the limit is
hit, investigate before using `sudo systemctl reset-failed ratsboombot.service`.
Apply the analogous UAT unit only when deploying to UAT.

```bash
sudo journalctl -u ratsboombot.service --since "1 hour ago" --no-pager -o cat | grep -F '[ConnectionWatchdog]'
```

7TV transport failures retain warnings but use capped exponential retry delays
(10 seconds up to five minutes) without repeated tracebacks. Unexpected failures
retain tracebacks. An announcement HTTP 403 uses normal chat for one hour, then
rechecks permission. Fix the sending account's moderator role/authorization to
restore announcements.

## Database-backed League accounts

Broadcaster Riot names and tags now come only from dashboard profile settings,
stored in channel_profile_overrides. No channel account is hardcoded.
Before deploying, save the current valid Riot name and tag using each channel's
dashboard League settings if they have only existed as code defaults. Existing
database overrides survive the upgrade. Accounts not saved there remain
unconfigured until entered; there is no automatic import of obsolete defaults.

For Steohanyy's channel, enter Riot game name `stowh bean`, tag `ant`, and
confirm the region in dashboard settings. Save both fields. These instructions
do not change the production database.

A confirmed provider "Summoner not found" clears the broadcaster's saved name
and tag atomically and stops subsequent account refreshes until replacement.
The log and !champs prompt request re-evaluation in dashboard settings. A response
for an older identity cannot clear a newer dashboard edit. Network errors do not
clear identities. Historical match/champion data is retained. A changed identity
gets a new seasonal refresh key, so its first refresh is not delayed by the old
account's refresh timestamp. Community !register accounts are unchanged.

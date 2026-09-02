# RatsBoomBot

RatsBoomBot is a multi-channel Twitch chatbot and streamer dashboard built with Python, TwitchIO, FastAPI, and SQLite. It provides shared Twitch automation while allowing each connected broadcaster to have their own commands, messages, loyalty currency, redeems, game integrations, and feature defaults.

The project currently supports Ninjakaing and a small group of invited streamers. It is a privately operated bot rather than a public self-service platform.

Current version: **8.7.2**

## Highlights

- Multi-channel Twitch chat and EventSub handling
- Channel-specific profiles, commands, currencies, messages, and feature defaults
- Twitch OAuth for the bot account and connected broadcasters
- Optional premium per-channel Twitch bot identities with automatic fallback
- Public global and per-channel chatter profiles with searchable community statistics
- Persistent points, counters, redeem history, settings, and moderation data
- Daily, first, second, self-timeout, and targeted-timeout redeems
- Streamer.bot and Mix It Up redeem-history import tools
- Viewer queues managed through chat or either dashboard
- Native Twitch shoutout queue with cooldown and retry protection
- Automatic first-chat shoutouts for selected profile users
- Incoming and outgoing raid responses
- Viewer-created 60-second and 30-second Twitch clips
- Optional game integrations, including Overwatch session tracking and League champion statistics
- Channel-isolated stream logs with retention, downloads, and manual deletion
- Real-time server performance and application logs
- Administrator and Twitch-authenticated channel dashboards
- SQLite migrations, deployment backups, health checks, and automated tests

## Tech Stack

- Python 3.11+
- TwitchIO 3.2
- FastAPI and Uvicorn
- SQLite and asqlite
- Jinja2 and Starlette signed sessions
- HTTPX
- Argon2 password hashing
- Rich logging
- pytest and pytest-asyncio

## Project Structure

```text
RatsBoomBot
├── app/                    Shared bot and web runtime
├── bot/
│   ├── channels/           Broadcaster profiles, commands, and game modules
│   ├── services/
│   │   ├── channels/       Broadcaster state, settings, and feature overrides
│   │   ├── engagement/     Points, redeems, clips, queues, and game services
│   │   ├── stream/         Timers, ads, shoutouts, and stream logs
│   │   └── support/        Help and moderation services
│   └── shared/             Reusable commands and EventSub listeners
├── config/                 Environment settings and application version
├── deploy/                 Linux, systemd, backup, and Windows deployment tools
├── docs/                   Project documentation and style guide
├── scripts/                Administration and data-import utilities
├── storage/                Database access and versioned migrations
├── tests/                  Automated tests
├── web/
│   ├── admin/              Administrator authentication and routes
│   ├── channel/            Broadcaster authentication and routes
│   ├── shared/             Shared web helpers and health routes
│   ├── templates/          Dashboard pages
│   └── static/             Styles and assets
└── main.py                 Application entry point
```

Commands validate chat input, services own shared behavior and persistence, and profiles define broadcaster-specific configuration. The runtime starts and stops the Twitch bot and FastAPI application together.

## Channel Profiles

Profiles live under `bot/channels/<channel_name>/`. Each profile can configure:

- Enabled components and protected Twitch users
- Feature, command-group, and individual-command defaults
- Timer, community, raid, shoutout, clip, point, and redeem messages
- Loyalty currency, reward rate, gambling, and duels
- Daily, first, second, self-timeout, and targeted-timeout rewards
- Optional persistent counters attached to targeted redeems
- Selected first-chat shoutout users
- Profile-specific game integrations

The repository includes a disabled `template_profile` and an enabled developer profile for integration testing. Dashboard overrides are stored separately from profile defaults; resetting an override returns the channel to its configured default.

## Engagement Features

### Loyalty Points

Each channel can name its currency and choose its command. The shared system supports passive chat rewards, balance checks, leaderboards, moderator grants, broadcaster resets, gambling, and viewer duels.

Points can remain disabled without disabling unrelated redeem tracking. Meinya silently awards 500 petals for a new subscription and 200 petals for a cheer of at least 100 Bits. These rewards use existing subscription and chat-message events and do not require additional OAuth scopes.

### Chatter Profiles

`!stats` opens the invoking viewer's public chatter profile, while `!stats <username>` opens another chatter's profile. Global profiles summarize exact tracked messages, channels visited, raid damage, boss participation, final hits, and bot-earned loyalty rewards. Each connected channel links to a detail page with the chatter's current balance, lifetime earnings, redeems, raid record, and inventory.

Historical message totals are seeded from the previous point-eligible message count. After migration 13, every non-bot message is counted independently of the loyalty cooldown. Historical lifetime earnings begin with the balance present at migration; future totals include chat, redeem, raid, gamble, and other bot rewards while excluding moderator grants and viewer transfers.

### Redeems and Stream Activity

The redeem service supports one daily claim per user per stream, first and second winners, historical totals, milestones, self-timeouts, reusable fixed-target timeouts, and optional targeted-redeem counters. Successful rewards and other channel-point activity appear on the dashboards.

Redeems are matched by the exact Twitch reward title configured in the channel profile.

### Viewer Queue

Viewers can join and leave a per-channel queue through chat. Moderators and broadcasters can open, close, advance, remove, or clear it. Both dashboards update the queue automatically and allow direct removal.

Viewer queue state and ordered members are stored in SQLite. Open and closed queues resume with the same members and positions after an application restart.

### Shoutouts and Raids

`!so` sends a profile-specific message and queues a native Twitch shoutout. The queue observes Twitch cooldowns, prevents duplicate targets, and retries temporary failures up to three times.

Profiles can automatically shout out selected users when they send their first message of a live stream. Twitch stream IDs are persisted so restarting the bot does not trigger the shoutout again during the same stream.

Incoming raids can trigger chat and shoutout behavior. Broadcasters can also start outgoing raids with subscriber and non-subscriber messages configured by profile.

### Clips

`!clip` or `!clips` creates a 60-second clip. Adding `short` requests a 30-second clip. Clip creation includes per-channel cooldowns, in-progress protection, live validation, and profile-specific responses.

### Moderation

Moderation support includes protected users, timeout actions, `!kamikaze`, and configurable bot-detection modes:

- `learning` records observations without action.
- `shadow` records what would have happened.
- `active` applies moderation actions.

### Game Integrations

Game components live inside each profile's `games/` package. The Overwatch integration provides profile and rank summaries plus manually tracked session wins and losses. Commands can be limited to streams where the broadcaster is live in an allowed category.

The League integration uses OP.GG's official MCP service to show a broadcaster's five most-played ranked champions for the current season. It collects recent ranked matches every four hours and calculates common three-item cores from a rolling 14-day window. Seasonal summaries refresh every 12 hours, and collected data persists in `.data/league.db` across restarts.

Third-party game APIs may require public player profiles and do not expose every type of live match data.

## Dashboards

### Streamer Dashboard

The root URL is the broadcaster-facing entry point. Twitch-authenticated connected broadcasters can view stream status, viewer queues, check-ins, other redeems, and social links; remove viewers; and manage supported feature and command overrides.

Channel sessions are isolated by Twitch user ID and persist for the configured session lifetime.

### Administrator Dashboard

The administrator dashboard at `/admin` provides:

- Runtime, database, and OAuth status
- Broadcaster onboarding and removal
- Per-channel feature and command controls
- Owner-managed premium custom bot access entitlements
- Viewer queue and redeem activity inspection
- Real-time CPU, memory, disk, temperature, uptime, and process metrics
- Real-time application logs
- Stream-log browsing, downloads, and deletion
- Owner-managed administrator accounts

Forms use CSRF protection, and sessions are signed with `SESSION_SECRET`.

### Premium Custom Bot Identities

An owner can grant a connected channel access to a dedicated Twitch chat identity from its administrator page. Once enabled, the streamer enters the dedicated bot's Twitch username from the Customization page in Streamer Control. RatsBoomBot verifies the account and generates a single-use authorization link that expires after 15 minutes. The link can be opened in a private window, another browser, or another device without the broadcaster's dashboard session.

The custom account authorizes through the existing public channel OAuth callback. The account returned by Twitch must exactly match the username selected by the broadcaster before it can be connected. The bot is then used for command responses, timers, community events, redeems, raids, shoutouts, ad warnings, and announcements in that channel only. No additional environment variable or Twitch Developer Console redirect URI is required for this self-service flow.

Custom identities are database-backed and do not require per-customer environment variables or a separate bot process. If a custom account cannot send, RatsBoomBot retries with the standard bot identity and records the failure in the channel's persistent stream log. Billing is intentionally external to the entitlement toggle so subscriptions can be managed manually or connected to a payment provider later.

## Stream Logs

Per-stream logs are stored under:

```text
.data/logs/<channel>/<timestamp>_stream-<stream_id>/log.txt
```

Channel records are routed only to their matching broadcaster. The administrator runtime log is limited to application-health categories such as startup, database, services, EventSub, and shutdown. Channel activity such as viewer queue changes is written to the active channel's persistent stream log instead.

The service resumes the same Twitch stream after a bot restart. Each channel retains its ten newest sessions. Older inactive sessions are pruned automatically, while active sessions are protected from automatic and manual deletion.

## Database and Migrations

The default SQLite database is `.data/tokens.db`. It stores OAuth tokens, broadcaster connections, premium chat identity assignments, administrator accounts, settings, overrides, points, chatter profiles, counters, redeem history, dashboard activity, viewer queues, raid bosses and scheduler state, first-chat shoutouts, moderation data, and migration history.

League statistics are stored separately in `.data/league.db`. This database contains replaceable external cache data, including seasonal champion summaries, recent ranked matches, and item metadata.

Migrations run automatically during startup:

1. Initial application schema
2. Redeem statistics
3. Administrator accounts
4. Imported redeem totals
5. Redemption activity
6. Second-redeem constraints
7. First-chat shoutout history
8. Chatter identity cache
9. Reklop counter seed
10. Persistent viewer queues
11. Persistent raid bosses and scheduler state
12. Premium custom bot identities
13. Public chatter profile statistics
14. Removal of the three pre-release raid test encounters
15. Passive point payout history
16. Removal of the remaining pre-release Ahirman test encounter
17. Removal of the complete failed Ahirman test encounter
18. Removal of the correctly spelled Ahriman test encounter
19. Single-use custom bot authorization links

Use a new migration for schema changes instead of rebuilding the production database.

## Historical Redeem Imports

Two preview-first tools are included:

- `scripts/import_streamerbot_redeems.py` imports Streamer.bot user-variable JSON.
- `scripts/import_mixitup_redeems.py` imports Mix It Up tab-separated First, Second, and daily totals.

Both require a broadcaster ID and only write when `--apply` is supplied. Imports replace the corresponding totals for that broadcaster, so create a backup first.

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Akaing1/RatsBoomBot.git
cd RatsBoomBot
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell activation:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the environment

Copy `.env.example` to `.env` and configure the Twitch application, account IDs, callbacks, session secret, and scopes.

```env
CLIENT_ID=
CLIENT_SECRET=
BOT_ID=
OWNER_ID=

DATABASE_PATH=.data/tokens.db
LEAGUE_DATABASE_PATH=.data/league.db
STREAM_LOGS_PATH=.data/logs

ADMIN_HOST=127.0.0.1
ADMIN_PORT=4345
ADMIN_BASE_URL=http://127.0.0.1:4345
PUBLIC_BASE_URL=http://127.0.0.1:4345
DASHBOARD_BASE_URL=http://127.0.0.1:4345

SESSION_SECRET=
SESSION_COOKIE_DOMAIN=
ENVIRONMENT=local
SESSION_HTTPS_ONLY=false
TRUST_PROXY_HEADERS=false

BOT_REDIRECT_URI=http://127.0.0.1:4345/admin/oauth/bot
CHANNEL_REDIRECT_URI=http://127.0.0.1:4345/admin/oauth/channel
PUBLIC_CHANNEL_REDIRECT_URI=http://127.0.0.1:4345/oauth/channel/connect
```

Keep `SESSION_SECRET` stable across deployments or existing browser sessions will become invalid. Administrator sessions default to eight hours; broadcaster sessions default to 30 days. In production, set `SESSION_COOKIE_DOMAIN=.ratsboombot.com` so an authenticated session is available to both the public site and dashboard subdomain.

Register each callback exactly in the Twitch developer application. Changing scopes requires the affected account to reconnect.

### 4. Run

```bash
python main.py
```

```text
Public landing page: http://127.0.0.1:4345/
Streamer dashboard:  http://127.0.0.1:4345/channel
Admin dashboard:    http://127.0.0.1:4345/admin
Health endpoint:    http://127.0.0.1:4345/health
```

Create the first owner account with the administration script before opening the admin dashboard. Administrator passwords must contain at least 12 characters.

## Commands

The default prefix is `!`. Availability depends on the profile and dashboard overrides.

| Group | Commands |
| --- | --- |
| Utility | `!hi`, `!choice`, `!kaboom`, `!stinky`, `!lucky`, `!smart`, `!height`, `!pp`, `!lurk`, `!help`, `!stats [username]` |
| Viewer queue | `!open`, `!close`, `!join`, `!leave`, `!queue`, `!next`, `!remove`, `!clear` |
| Socials | `!socials`, `!socials discord`, `!socials youtube`, `!setdiscord`, `!setyoutube` |
| Settings | `!set game <game name>`, `!set title <stream title>`, `!timers`, `!timers on`, `!timers off` |
| Shoutouts | `!so <username>` |
| Clips | `!clip`, `!clip short` |
| Raids | `!startraid <channel>` |
| Moderation | `!kamikaze <username>` |
| Points | Profile currency command with `leaderboard`, `gamble`, `duel`, `add`, and `reset` subcommands; Meinya also supports `!petals roulette` / `!petals spin` |
| Overwatch | `!ow`, `!owrank`, `!owrecord`, `!owreset` |
| League of Legends | `!champs`, `!champs <champion>`, `!register <Riot ID> [region]`, `!unregister`, `!rank [chatter]`, `!ladder` |

While a channel is live, connected logged-in chatters earn 10 passive points every two minutes. Twitch's connected-chatter list is used as an approximation of watch activity; the broadcaster and configured bot identities are excluded. The bot identity used by the channel must authorize `moderator:read:chatters` and be a moderator in that channel. Payout intervals are persisted so a bot restart cannot award the same interval twice.

Meinya's roulette uses a standard single-zero wheel: 18 red, 18 black, and one green. Red and black return 2× the wager, green returns 5×, and bets are capped at 1,000 petals. Green is intentionally a high-risk novelty bet rather than an equal-odds choice. Wagers and payouts settle atomically to prevent concurrent commands from overspending a balance.

Point commands use the profile's currency command and provide `leaderboard`, `reset`, `add`, `gamble`, and `duel` subcommands. Permission-sensitive actions are restricted to moderators or the broadcaster where appropriate.

## Production Deployment

The production instance runs on a Raspberry Pi under systemd and HTTPS. Assets under `deploy/` include the service unit, Linux deployment with pre-deployment backup, scheduled SQLite backups with integrity checks and retention, a Windows PowerShell deployment wrapper, and Cloudflare tunnel support.

Merges and direct pushes to `master` publish the configured application version and then deploy production through a self-hosted GitHub Actions runner on the Raspberry Pi. Register the runner with the custom label `ratsboombot` and run its service as the `rats-bot` user. The runner invokes `/opt/ratsboombot/deploy/linux/deploy.sh`, which retains the existing backup, compile check, systemd restart, health check, and automatic rollback behavior.

The runner host must allow the `rats-bot` user to run the two systemd commands used by the deployment script without an interactive password:

```text
rats-bot ALL=(root) NOPASSWD: /usr/bin/systemctl restart ratsboombot, /usr/bin/systemctl is-active --quiet ratsboombot
```

Keep the production runner restricted to the `ratsboombot` label. The deployment job runs only after the GitHub release job succeeds on `master`; pull requests never execute code on the Pi.

Production should configure:

```env
ENVIRONMENT=production
SESSION_HTTPS_ONLY=true
TRUST_PROXY_HEADERS=true
```

Use public HTTPS callback URLs, restrict `.env` and database permissions, retain backups, and monitor `/health` after deployment.

## Testing

Run the suite from the repository root:

```bash
pytest
```

New behavior should include tests for the affected service and, when relevant, authentication, authorization, CSRF, persistence, and channel isolation.

## Versioning

RatsBoomBot uses a practical three-part version number:

- Patch (`X.Y.Z`) — bug fixes, copy updates, and very small changes
- Minor (`X.Y.0`) — additive, non-breaking work such as a profile or contained enhancement
- Major (`X.0.0`) — a new system, major capability, architectural checkpoint, or release milestone

Version **8.7.2** aligns the premium custom bot controls and styles account disconnection as a destructive action.

Version **8.7.1** replaces session-bound custom bot authorization with username-verified, single-use links that can be opened in a separate browser or device.

Version **8.7.0** adds streamer-managed OAuth onboarding for premium custom bot identities. Administrators grant access, while streamers securely connect and manage their own dedicated Twitch bot accounts from Streamer Control.

Version **8.6.1** fixes the public raid page's recent-history query against the production raid schema.

Version **8.6.0** adds public `/raid/{channel}` guides with live encounter progress, contributor rankings, shop details, mechanics, rewards, commands, and recent raid history.

Version **8.5.3** moves public channel command references to `/help/{channel}` and collapses active raid leaderboards after the top ten contributors.

Version **8.5.2** corrects the Ahriman test-run cleanup and converts the public command Help page to full-width dropdown sections with an active raid contributor leaderboard.

Version **8.5.0** adds standard single-zero roulette as a Meinya loyalty-points game.

Version **8.4.1** removes the remaining pre-release Ahirman test encounter from raid history.

Version **8.4.0** adds persistent passive point earnings for connected live chatters.

Version **6.0.0** marks the checkpoint where RatsBoomBot became a structured multi-channel platform with profile-specific engagement, streamer dashboards, migration tools, clips, raids, first-chat shoutouts, and production-oriented stream logging.

## Current Limitations

- Broadcaster onboarding is intended for invited channels and is not invitation-gated in the application.
- New channels require a registered profile for complete behavior.
- Some game data depends on third-party services and public player profiles.
- Production deployment requires a registered self-hosted Raspberry Pi runner.
- Not every profile-specific message and redeem has a dashboard editor.

## Development Guidelines

Follow `docs/styling_guide.md`. Keep commands thin, put shared behavior in services, keep broadcaster customization in profiles, and use migrations for persistent schema changes.

## License

RatsBoomBot is a personal project without a formal open-source license. Add a license before public distribution or accepting outside contributions.

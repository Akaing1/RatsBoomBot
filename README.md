# RatsBoomBot

RatsBoomBot is a personal multi-channel Twitch chatbot built with Python, TwitchIO, FastAPI, and SQLite.

The project acts as a lightweight StreamElements-style replacement for a small group of Twitch channels. Shared functionality lives in reusable command, event, and service modules, while each broadcaster can define a separate channel profile containing their own point theme, messages, timer announcements, redeems, and channel-specific commands.

The project is primarily built for Ninjakaing and friends rather than as a public, one-size-fits-all Twitch bot.

Current version: **4.1.1**

---

## Features

RatsBoomBot currently supports:

- Twitch chat commands through TwitchIO
- Multi-broadcaster OAuth authorization
- SQLite-backed token storage
- Twitch token refresh and restoration
- Shared commands and event listeners
- Broadcaster-specific channel profiles
- Per-channel loyalty-point themes
- Passive points earned from chat activity
- Leaderboards, gambling, and viewer duels
- Daily and first channel-point redeems
- Persistent meme counters
- Viewer queues
- Social-link commands
- Rotating timer announcements
- Upcoming ad warnings
- Follow, subscription, raid, redeem, and stream events
- Per-stream text logs
- A FastAPI administration dashboard
- Browser-based bot and broadcaster OAuth
- Database migrations
- Structured runtime logging
- Automated tests
- Optional Windows system-tray operation

---

## Tech Stack

- Python 3.11+
- TwitchIO 3.2
- SQLite
- asqlite
- FastAPI
- Uvicorn
- Jinja2
- HTTPX
- Rich
- python-dotenv
- pystray
- Pillow
- pytest
- pytest-asyncio

---

## Current Architecture

RatsBoomBot is separated into several major layers:

```text
Application Runtime
│
├── Twitch Bot
│   ├── Shared Commands
│   ├── Shared Events
│   ├── Channel Profiles
│   ├── Channel-Specific Components
│   └── Service Container
│
├── Storage
│   ├── SQLite Connection Pool
│   ├── OAuth Tokens
│   ├── EventSub Subscription State
│   ├── Viewer Data
│   ├── Redeem Claims
│   ├── Broadcaster Settings
│   └── Versioned Migrations
│
├── Administration Dashboard
│   ├── Authentication
│   ├── Bot OAuth
│   ├── Broadcaster OAuth
│   ├── Channel Management
│   └── Stream Log Browser
│
└── Windows Tray Application
```

The general responsibilities are:

- **Commands** receive and validate chat input.
- **Events** respond to Twitch and EventSub activity.
- **Services** contain shared business logic and persistent operations.
- **Profiles** configure channel-specific behavior.
- **Storage** owns SQLite access and migrations.
- **Web routers** provide dashboard and OAuth functionality.
- **Runtime** coordinates startup and shutdown.

---

## Project Structure

```text
RatsBoomBot/
│
├── app/
│   ├── runtime.py
│   └── tray.py
│
├── assets/
│   └── NinjaDoro.ico
│
├── bot/
│   ├── channels/
│   │   ├── component.py
│   │   │
│   │   ├── developer_ninjakaing/
│   │   │   ├── commands/
│   │   │   ├── games/
│   │   │   └── profile.py
│   │   │
│   │   └── ninjakaing/
│   │       ├── commands/
│   │       ├── games/
│   │       └── profile.py
│   │
│   ├── services/
│   │   ├── ad_announcement_service.py
│   │   ├── broadcaster_service.py
│   │   ├── broadcaster_settings_service.py
│   │   ├── channel_service.py
│   │   ├── counter_service.py
│   │   ├── help_service.py
│   │   ├── points_service.py
│   │   ├── redeem_service.py
│   │   ├── service_container.py
│   │   ├── stream_log_service.py
│   │   ├── timer_service.py
│   │   └── viewer_queue_service.py
│   │
│   ├── shared/
│   │   ├── commands/
│   │   │   ├── counters.py
│   │   │   ├── moderation.py
│   │   │   ├── points.py
│   │   │   ├── settings.py
│   │   │   ├── shoutout.py
│   │   │   ├── socials.py
│   │   │   ├── utility.py
│   │   │   └── viewer_queue.py
│   │   │
│   │   └── events/
│   │       ├── chat.py
│   │       ├── community.py
│   │       ├── raids.py
│   │       ├── redeems.py
│   │       └── streams.py
│   │
│   ├── bot.py
│   ├── component_loader.py
│   └── profiles.py
│
├── config/
│   └── settings.py
│
├── storage/
│   ├── migrations/
│   │   ├── v001_initial_schema.py
│   │   └── v002_redeem_stats.py
│   │
│   ├── database.py
│   └── migration_runner.py
│
├── tests/
│   ├── conftest.py
│   ├── test_admin_auth.py
│   ├── test_log_browser.py
│   ├── test_stream_log_service.py
│   └── test_viewer_queue_service.py
│
├── web/
│   ├── routers/
│   │   ├── auth.py
│   │   ├── channels.py
│   │   ├── dashboard.py
│   │   ├── logs.py
│   │   └── oauth.py
│   │
│   ├── app.py
│   ├── common.py
│   └── log_browser.py
│
├── main.py
├── pytest.ini
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Shared and Channel-Specific Behavior

Version 4 introduced a distinction between globally reusable behavior and broadcaster-specific behavior.

### Shared Components

Shared commands and events are loaded for every supported channel.

Examples include:

- Utility commands
- Social commands
- Viewer queues
- Shoutouts
- Settings commands
- Moderation commands
- Chat tracking
- Follow and subscription events
- Raids
- Redeems
- Stream online and offline events

Shared files live under:

```text
bot/shared/
```

### Channel Profiles

Each broadcaster can have a profile under:

```text
bot/channels/<channel_name>/profile.py
```

A profile can configure:

- Twitch username
- Channel-specific messages
- Timer messages
- Point-system name
- Point-system command
- Points earned per message
- Message reward cooldown
- Gamble chance
- Duel expiration
- Daily redeem behavior
- First redeem behavior
- Redeem milestones
- Follow messages
- Subscription messages
- Raid messages
- Channel-specific commands
- Game-specific modules

This allows Ninjakaing to keep rat-themed behavior without forcing the same theme onto every other channel.

---

## Included Channel Profiles

The current repository includes profiles for:

```text
ninjakaing
developer_ninjakaing
```

The developer channel is useful for testing profile loading, alternate point themes, commands, messages, and authorization without using the main channel.

Additional broadcasters can be added by creating another package under `bot/channels/` and registering its profile.

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Akaing1/RatsBoomBot.git
cd RatsBoomBot
git checkout release/4.1.1-local
```

The `-local` branch names are repository development branches. Replace the checkout target with the final published release branch when applicable.

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Create a `.env` file in the project root.

```env
CLIENT_ID=
CLIENT_SECRET=

BOT_ID=
OWNER_ID=

PREFIX=!

DATABASE_PATH=.data/tokens.db
STREAM_LOGS_PATH=.data/logs

ADMIN_HOST=127.0.0.1
ADMIN_PORT=4345
ADMIN_BASE_URL=http://127.0.0.1:4345

ADMIN_SECRET=
SESSION_SECRET=

BOT_REDIRECT_URI=http://127.0.0.1:4345/oauth/bot
CHANNEL_REDIRECT_URI=http://127.0.0.1:4345/oauth/channel

BOT_SCOPES=user:read:chat user:write:chat user:bot
CHANNEL_SCOPES=channel:bot moderator:manage:banned_users moderator:read:followers channel:read:redemptions channel:read:subscriptions channel:read:ads channel:manage:moderators

IGNORED_USERS=streamelements,nightbot,ratsboombot

DAILY_REDEEM_TITLE=Steal some cheese
FIRST_REDEEM_TITLE=first

DAILY_REDEEM_BREAD=100
FIRST_REDEEM_BREAD=250
```

Generate strong random values for:

```env
ADMIN_SECRET=
SESSION_SECRET=
```

The application will refuse to start if either is missing.

---

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `CLIENT_ID` | Twitch application client ID |
| `CLIENT_SECRET` | Twitch application client secret |
| `BOT_ID` | Twitch user ID of the bot account |
| `OWNER_ID` | Twitch user ID of the primary owner account |
| `PREFIX` | Chat command prefix |
| `DATABASE_PATH` | SQLite database path |
| `STREAM_LOGS_PATH` | Directory used for per-stream logs |
| `ADMIN_HOST` | Dashboard bind address |
| `ADMIN_PORT` | Dashboard port |
| `ADMIN_BASE_URL` | Public base URL used by the dashboard |
| `ADMIN_SECRET` | Password or secret used for dashboard authentication |
| `SESSION_SECRET` | Secret used to sign dashboard sessions |
| `BOT_REDIRECT_URI` | OAuth callback for the bot account |
| `CHANNEL_REDIRECT_URI` | OAuth callback for broadcaster accounts |
| `BOT_SCOPES` | OAuth scopes requested for the bot account |
| `CHANNEL_SCOPES` | OAuth scopes requested for broadcasters |
| `IGNORED_USERS` | Users excluded from passive point rewards |
| `DAILY_REDEEM_TITLE` | Default title for the daily redeem |
| `FIRST_REDEEM_TITLE` | Default title for the first redeem |
| `DAILY_REDEEM_BREAD` | Default daily redeem reward |
| `FIRST_REDEEM_BREAD` | Default first redeem reward |

Profile values can override or replace some channel-facing defaults.

---

## Twitch Application Configuration

Create a Twitch developer application and configure its OAuth redirect URLs.

For local development, the expected callbacks are:

```text
http://127.0.0.1:4345/oauth/bot
http://127.0.0.1:4345/oauth/channel
```

These must match the values configured in both Twitch and `.env`.

---

## OAuth Scopes

### Bot Scopes

```text
user:read:chat
user:write:chat
user:bot
```

These allow the bot account to participate in Twitch chat through TwitchIO.

### Broadcaster Scopes

```text
channel:bot
moderator:manage:banned_users
moderator:read:followers
channel:read:redemptions
channel:read:subscriptions
channel:read:ads
channel:manage:moderators
```

These support:

- Registering the bot for a channel
- Timeouts and bans
- Follow events
- Channel-point redeems
- Subscription events
- Ad schedules and ad warnings
- Moderator lookup
- Restoring moderator status after `!kamikaze`

### Reauthorization Requirement

Adding a scope to `.env` does not update previously issued tokens.

After changing either scope list, reauthorize the affected account through the dashboard so Twitch issues a new token with the updated permissions.

---

## Running the Bot

### System Tray Mode

Run:

```bash
python main.py
```

Without additional arguments, the application launches using the Windows tray interface.

### Runtime-Only Mode

Run:

```bash
python main.py --runtime
```

This starts the Twitch bot and FastAPI dashboard directly without the tray interface.

The dashboard is available by default at:

```text
http://127.0.0.1:4345
```

---

## Administration Dashboard

The FastAPI dashboard provides browser-based management for the bot.

Current dashboard areas include:

- Administrator authentication
- Bot-account OAuth
- Broadcaster OAuth
- Authorized channel management
- Channel information
- Stream-log browsing
- Runtime access to the active bot and database

The dashboard routes are split into separate routers:

```text
web/routers/auth.py
web/routers/channels.py
web/routers/dashboard.py
web/routers/logs.py
web/routers/oauth.py
```

This keeps the main FastAPI application small and separates each feature area.

---

## Database and Migrations

RatsBoomBot uses SQLite through `asqlite`.

The default database location is:

```text
.data/tokens.db
```

Database changes are applied through versioned migrations.

Current migrations include:

```text
v001_initial_schema.py
v002_redeem_stats.py
```

At startup, the migration runner:

1. Determines which migrations have already been applied.
2. Runs any missing migrations in order.
3. Records completed migrations.
4. Reports whether the database is current.

Do not manually recreate the database for ordinary schema upgrades. Add a new migration instead.

---

## Persistent Data

The database stores information including:

- OAuth access tokens
- OAuth refresh tokens
- EventSub subscription records
- Authorized broadcaster records
- Per-channel viewer balances
- Viewer message counts
- Counter values
- Broadcaster settings
- Redeem claims
- Redeem statistics
- Migration history

Points are separated by broadcaster, meaning the same viewer can have a different balance in each channel.

---

## Logging

Version 4.1 introduced structured logging throughout the core application.

Logging covers:

- Application startup
- Runtime initialization
- Database migrations
- OAuth tokens
- Broadcaster discovery
- Channel-profile loading
- Component loading
- Service setup
- Service startup and shutdown
- Twitch EventSub activity
- Chat events
- Commands
- Points
- Redeems
- Viewer queues
- Timers
- Ads
- Stream logs
- Moderation
- Exceptions and background-task failures

Common subsystem prefixes include:

```text
[Startup]
[Database]
[OAuth]
[Profiles]
[Components]
[Services]
[Commands]
[EventSub]
[Chat]
[Points]
[Redeems]
[Timers]
[Ads]
[Moderation]
[Shutdown]
```

Routine high-volume activity is generally logged at `DEBUG`, while state changes and major lifecycle events use `INFO`.

Failures use contextual exception logging with tracebacks.

---

## Stream Logs

A separate text log is created for each detected live-stream session.

The default root directory is:

```text
.data/logs
```

Logs are organized by channel and stream ID.

Example:

```text
.data/logs/
└── ninjakaing/
    └── 2026-08-01_200000_stream-123456789/
        └── log.txt
```

Stream logs may contain:

- Chat messages
- Follows
- Subscriptions
- Raids
- Redeems
- Stream lifecycle events
- Bot startup and shutdown markers

When the bot restarts during an active stream, it attempts to resume the existing stream session rather than create an unrelated duplicate.

The dashboard includes a browser for reviewing these logs.

---

## Commands

The default command prefix is:

```text
!
```

Actual commands can vary by active profile.

### Shared Utility Commands

| Command | Description |
| --- | --- |
| `!hi` | Greets the caller |
| `!hi @user` | Greets another viewer |
| `!choice ...` | Randomly chooses from the provided options |
| `!kaboom` | Sends an explosion message |
| `!stinky` | Generates a random stinkiness percentage |
| `!lucky` | Generates a random luck percentage |
| `!smart` | Generates a random smartness percentage |
| `!lurk` | Sends a lurk response |
| `!help` | Lists currently loaded commands |

### Social Commands

| Command | Description |
| --- | --- |
| `!socials` | Shows configured channel social links |
| `!socials discord` | Shows the configured Discord link |
| `!socials youtube` | Shows the configured YouTube link |
| `!setdiscord <url>` | Updates the channel Discord link |
| `!setyoutube <url>` | Updates the channel YouTube link |

Settings commands require broadcaster or moderator permission.

### Timer Settings

| Command | Description |
| --- | --- |
| `!timers` | Shows whether timers are enabled |
| `!timers on` | Enables timer announcements |
| `!timers off` | Disables timer announcements |

Timer settings are persisted separately for each broadcaster.

### Viewer Queue Commands

| Command | Description |
| --- | --- |
| `!open` | Opens the viewer queue |
| `!close` | Closes the viewer queue |
| `!join` | Adds the caller to the queue |
| `!leave` | Removes the caller from the queue |
| `!queue` | Shows the queue preview |
| `!next` | Selects the next viewer |
| `!clear` | Clears the queue |

Queue administration commands require broadcaster or moderator access.

Viewer queues are currently held in memory and reset when the bot restarts.

### Shoutout Command

| Command | Description |
| --- | --- |
| `!so <username>` | Sends a Twitch shoutout message |

The shoutout command requires broadcaster or moderator permission.

### Counter Commands

| Command | Description |
| --- | --- |
| `!explode` | Increments the explosion counter |
| `!reklop` | Increments the Reklop counter |
| `!randy` | Increments the Randy counter |
| `!car` | Increments the car counter |

Counter values are stored persistently in SQLite.

---

## Point Systems

Point-system commands and terminology are selected by the channel profile.

For example:

- Ninjakaing can use a rat-themed Stale Bread system.
- The developer channel can use an alternate test currency such as ores.

A point profile can configure:

- Whether points are enabled
- Command name
- Currency display name
- Singular and plural terminology
- Points earned per message
- Message cooldown
- Gamble chance
- Duel expiration
- Response messages

Typical point commands include:

```text
!<points-command>
!<points-command> @user
!<points-command> leaderboard
!<points-command> add @user <amount>
!<points-command> reset
!<points-command> gamble <amount>
!<points-command> gamble all
!<points-command> duel @user <amount>
!<points-command> duel @user all
!<points-command> duel accept
!<points-command> duel decline
```

Balances are stored per broadcaster and per viewer.

---

## Gambling

A viewer can gamble either a fixed amount or their entire balance.

General behavior:

- The amount must be positive.
- The viewer must have enough points.
- The win chance comes from the active profile.
- A win adds the gambled amount.
- A loss removes the gambled amount.
- Profiles can define separate messages for ordinary and all-in results.

---

## Viewer Duels

Viewers can challenge each other for points.

General behavior:

- A viewer cannot duel themselves.
- Both users must have enough points.
- A duel is stored as pending for the targeted opponent.
- The opponent can accept or decline.
- Pending duels expire after a profile-configured period.
- Balances are checked again at acceptance time.
- A winner is randomly selected.
- The loser pays the duel amount to the winner.

---

## Channel-Point Redeems

RatsBoomBot supports profile-configured channel-point redeem behavior.

Current redeem types include:

### Daily Redeem

- Can be claimed once per viewer per stream.
- Awards a profile-configured point amount.
- Can have a random double-reward chance.
- Tracks total lifetime claims.
- Supports claim milestones.

### First Redeem

- Can only be claimed once per stream.
- Awards a profile-configured point amount.
- Records the first winner.
- Supports lifetime milestones.

Redeem claims are associated with the Twitch stream ID, preventing duplicate claims during the same broadcast.

---

## Timer Announcements

Timer announcements are evaluated per channel.

Current default service behavior:

- Checks periodically in the background.
- Only considers live broadcasters.
- Requires enough time since the last announcement.
- Requires enough recent chat activity.
- Respects each channel's enabled or disabled setting.
- Uses messages from the active channel profile.
- Skips templates that require a missing social link.
- Rotates through the available messages.

This allows every channel to share the timer service while using its own announcement text.

---

## Ad Warnings

The ad announcement service checks active broadcasters for upcoming scheduled ads.

When an ad is close enough, the bot sends a warning message to that channel.

The service avoids sending the same warning repeatedly for the same scheduled ad.

---

## Event Handling

Shared events currently cover:

### Chat Messages

Chat messages can:

- Be written to the active stream log
- Count toward timer activity
- Award passive points
- Trigger commands through TwitchIO

### Community Events

Community events include:

- Follows
- Subscriptions
- Subscription messages
- Related channel notifications

Messages are rendered from the active channel profile.

### Raids

Raid events can:

- Log the source channel
- Record the viewer count
- Send a profile-specific raid message
- Write the raid to the active stream log

### Redeems

Channel-point redemption events are matched against the active profile and forwarded to `RedeemService`.

### Stream Events

Stream events start and stop stream-log sessions when a broadcaster goes online or offline.

---

## `!kamikaze`

`!kamikaze` is a chat-based timeout command.

Usage:

```text
!kamikaze
!kamikaze @user
```

Current behavior:

- Calling it without a target attempts to time out the caller.
- Targeting yourself has the same result.
- A target attempt rolls a random number.
- On success, the target receives a short timeout.
- On failure, the caller receives the timeout.
- The broadcaster cannot be targeted.
- The bot account cannot be targeted.
- Regular moderators can be targeted.
- The command checks moderator status before the timeout.
- If a moderator is timed out, a background task restores their moderator status afterward.

The broadcaster authorization token must include:

```text
channel:manage:moderators
```

Without this scope, the bot cannot reliably check or restore moderator status.

---

## Services

### `ServiceContainer`

Creates shared service instances and manages their setup, startup, and shutdown order.

### `BroadcasterService`

Tracks authorized broadcasters and resolves their Twitch information and live status.

### `BroadcasterSettingsService`

Persists channel settings such as:

- Discord URL
- YouTube URL
- Timer enabled state

### `PointsService`

Handles:

- Viewer balances
- Passive message rewards
- Leaderboards
- Point additions and removals
- Resets
- Gambling-related balance operations
- Pending duels
- Legacy point-data migration

### `RedeemService`

Handles:

- Daily claims
- First claims
- Stream-specific duplicate prevention
- Reward payouts
- Claim counts
- Milestones
- Offline checks

### `CounterService`

Stores and increments persistent named counters.

### `TimerService`

Tracks message activity and sends profile-specific announcements while channels are live.

### `AdAnnouncementService`

Checks upcoming ad schedules and sends one warning per ad.

### `ViewerQueueService`

Maintains separate in-memory queues for each broadcaster.

### `StreamLogService`

Creates, resumes, writes, and closes per-stream log sessions.

### `HelpService`

Discovers loaded commands and subcommands and formats the help response.

---

## Adding a New Channel

A new channel generally needs:

```text
bot/channels/<channel_name>/
├── commands/
├── games/
├── __init__.py
└── profile.py
```

The profile should define the channel's:

- Twitch username
- Enabled features
- Point configuration
- Redeem configuration
- Community-event messages
- Timer announcements
- Channel-specific components

The broadcaster must then authorize the application through the dashboard.

Broadcaster IDs are resolved from Twitch usernames, so permanent IDs do not need to be manually hardcoded into every profile.

---

## Adding Channel-Specific Commands

Channel-only commands belong under:

```text
bot/channels/<channel_name>/commands/
```

General commands available to every channel belong under:

```text
bot/shared/commands/
```

Game-specific commands can be organized under:

```text
bot/channels/<channel_name>/games/
```

The component loader imports the appropriate packages for each active profile.

---

## Testing

Run the complete test suite with:

```bash
pytest
```

Current automated coverage includes:

- Admin authentication
- Log-browser behavior
- Stream-log sessions
- Viewer queues

New logic should generally include a focused test, especially for database behavior, permission checks, service lifecycle behavior, and profile-specific functionality.

---

## Troubleshooting

### The dashboard refuses to start

Confirm these are present:

```env
ADMIN_SECRET=
SESSION_SECRET=
```

### OAuth redirects fail

Confirm the callback URLs match in all three places:

- Twitch developer-console application settings
- `.env`
- The address used to open the dashboard

### A newly added scope is still missing

Reauthorize the account. Refreshing an old token does not add newly requested scopes.

### Moderator restoration fails

Confirm the broadcaster token has:

```text
channel:manage:moderators
```

Then reauthorize the broadcaster.

### Follow events do not appear

Confirm the broadcaster token includes:

```text
moderator:read:followers
```

Also confirm the relevant EventSub subscription was created successfully.

### Redeems do not fire

Confirm:

```text
channel:read:redemptions
```

is authorized and the reward title matches the active profile.

### Subscription messages do not fire

Confirm:

```text
channel:read:subscriptions
```

is authorized for the broadcaster.

### Ads cannot be read

Confirm:

```text
channel:read:ads
```

is authorized.

### Database migrations fail

Review the `[Database]` migration logs and verify that the SQLite file and its parent directory are writable.

### No timer announcement is sent

Timer announcements require:

- The broadcaster to be live
- Timers to be enabled
- Enough elapsed time
- Enough recent messages
- At least one usable profile timer message

### No stream log is created

A stream log is only active while the service detects an active Twitch stream session.

---

## Version History

### 4.1.1 — Moderation Fix

- Fixed moderator handling in `!kamikaze`.
- Allowed ordinary moderators to remain valid command targets.
- Added moderator-status checks before timeout execution.
- Added delayed moderator restoration after the timeout.
- Protected the broadcaster from targeting.
- Protected the bot account from targeting.
- Added the `channel:manage:moderators` broadcaster scope.
- Improved moderator restoration logging and task retention.

### 4.1.0 — Structured Logging

- Added structured logging throughout the core application.
- Standardized the main logger as `RatBoomBot`.
- Added subsystem prefixes for easier log filtering.
- Improved startup and shutdown visibility.
- Added contextual logging to services, commands, events, storage, OAuth, and component loading.
- Added traceback logging for unexpected failures.
- Improved background-task lifecycle handling.
- Moved high-volume routine activity to `DEBUG`.
- Added meaningful state-change logs at `INFO`.

### 4.0.0 — Channel Profile Refactor

- Introduced broadcaster-specific channel profiles.
- Separated shared commands from channel-specific commands.
- Separated shared events from channel-specific behavior.
- Added dynamic profile and component loading.
- Added separate profile packages for Ninjakaing and the developer channel.
- Moved rat-themed behavior into the Ninjakaing profile.
- Added per-channel point-system themes.
- Added per-channel timer messages.
- Added per-channel follow, subscription, raid, and redeem messages.
- Added per-channel social settings.
- Refactored points into broadcaster-specific balances.
- Expanded multi-broadcaster support.
- Improved broadcaster discovery using Twitch usernames.
- Reorganized the old global command and event packages under `bot/shared/`.

### 3.0.0 — Migrations, Web Routers, and Tests

- Added a versioned database migration system.
- Added an initial-schema migration.
- Added redeem-statistics migration support.
- Added migration tracking and ordered execution.
- Split the administration dashboard into dedicated FastAPI routers.
- Added separate routers for authentication, channels, dashboard pages, logs, and OAuth.
- Added shared web utilities.
- Added a dedicated stream-log browser module.
- Reduced the size and responsibilities of `web/app.py`.
- Added pytest configuration.
- Added automated tests for admin authentication.
- Added automated tests for log browsing.
- Added automated tests for stream logging.
- Added automated tests for viewer queues.
- Expanded development and test dependencies.

### 2.0.0 — Runtime, Dashboard, OAuth, and Stream Operations

- Added a coordinated application runtime.
- Added concurrent Twitch bot and FastAPI dashboard operation.
- Added a browser-based administration interface.
- Added bot-account OAuth handling.
- Added broadcaster authorization through the dashboard.
- Added persistent broadcaster and EventSub state.
- Added stream-log support.
- Added administration secrets and signed sessions.
- Added configurable dashboard host, port, and base URL.
- Added separate bot and broadcaster redirect URIs.
- Moved runtime configuration toward `.data` storage paths.
- Expanded the service layer beyond the original chat-command implementation.
- Added support for managing multiple authorized channels from one running application.
- Improved Windows tray integration around the new runtime.

### 1.0.0 — Initial Modular Release

- Added a TwitchIO-based chatbot.
- Added modular command components.
- Added Twitch EventSub chat support.
- Added SQLite-backed OAuth token storage.
- Added a rat-themed Stale Bread loyalty system.
- Added passive chat rewards.
- Added leaderboards.
- Added gambling.
- Added viewer duels.
- Added persistent counters.
- Added viewer queues.
- Added social commands.
- Added utility commands.
- Added timer announcements.
- Added ad warnings.
- Added follow and subscription responses.
- Added a Windows tray launcher.

---

## Development Direction

RatsBoomBot is intentionally designed for a small number of known channels.

The goal is not to become a public bot platform. New features should favor:

- Clear channel profiles
- Reusable shared services
- Simple configuration
- Reliable logging
- Safe moderation behavior
- Persistent migrations
- Focused tests
- Easy maintenance for a small group of streamers

---

## License

This is a personal project. Add a formal license before distributing or accepting outside contributions.
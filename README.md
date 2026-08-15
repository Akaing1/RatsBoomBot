# RatsBoomBot

RatsBoomBot is a multi-channel Twitch chatbot built with Python, TwitchIO, FastAPI, and SQLite. It combines Twitch chat automation, channel-specific profiles, persistent viewer data, EventSub integrations, an administrator dashboard, and a self-service channel dashboard.

The project is currently intended for Ninjakaing and a small group of invited streamers. It is not yet a public, self-service bot platform.

Latest release: **5.3.6**  
Active development branch: **`feature/admin-dash`**

## Features

- Multi-channel Twitch chat through TwitchIO
- Browser-based bot and broadcaster OAuth
- SQLite-backed tokens, settings, counters, points, and redeem data
- Channel-specific profiles, messages, point themes, commands, and game components
- Per-channel feature, command-group, and command overrides
- Passive loyalty points, leaderboards, gambling, and viewer duels
- Viewer queues with moderator chat commands and dashboard removal controls
- Channel-point daily and first redeems
- Follow, subscription, raid, redeem, stream, and ad events
- Social links and rotating timer announcements
- Persistent counters and per-stream text logs
- Password-based administrator accounts with owner-only account management
- A protected administrator dashboard for runtime, channel, feature, queue, OAuth, and log management
- A Twitch-authenticated channel dashboard for channel owners
- CSRF protection, signed sessions, production cookie settings, and OAuth state validation
- Health endpoint, structured logging, database migrations, and automated tests

## Tech Stack

- Python 3.11+
- TwitchIO 3.2
- FastAPI and Uvicorn
- SQLite and asqlite
- Jinja2
- HTTPX
- Argon2 password hashing
- Starlette signed sessions
- Rich logging
- pytest and pytest-asyncio

## Architecture

```text
RatsBoomBot
├── app/                 Coordinated bot and web runtime
├── bot/
│   ├── channels/        Broadcaster profiles and channel components
│   ├── services/        Shared business logic and background services
│   └── shared/          Reusable commands and EventSub handlers
├── config/              Environment settings and application version
├── storage/             SQLite repositories and versioned migrations
├── web/
│   ├── routers/         Admin, OAuth, channel, health, and log routes
│   ├── templates/       Administrator and channel dashboard pages
│   └── static/          Dashboard styles and assets
├── tests/               Automated tests
├── docs/                Project documentation and style guide
└── main.py              Application entry point
```

Commands receive and validate chat input. Services own shared behavior and persistence. Profiles define channel-specific defaults. Storage owns SQLite access and migrations. Web routers expose the administrator, OAuth, and channel-owner workflows. The runtime starts and stops the Twitch bot and FastAPI server together.

## Channel Profiles and Feature Controls

Each supported broadcaster has a profile under `bot/channels/<channel_name>/`. A profile can define:

- Channel-specific components and messages
- Feature defaults
- Global command-group and individual command defaults
- Timer messages
- Point-system name, command, rewards, gambling, and duel behavior
- Follow, subscription, raid, and redeem responses

Dashboard overrides are stored separately from profile defaults. Administrators and authenticated channel owners can enable, disable, or reset:

- Channel, timers, points, redeems, community events, and raid responses
- Points, viewer queue, shoutout, social, and settings command groups
- Independent utility, counter, and moderation commands

Resetting an override returns the channel to its profile default.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Akaing1/RatsBoomBot.git
cd RatsBoomBot
git checkout release/5.3.6
```

Use `feature/admin-dash` only when testing the current in-development dashboard changes.

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure the Environment

Copy `.env.example` to `.env`, then fill in the Twitch credentials, IDs, OAuth callbacks, session secret, and scopes.

```env
CLIENT_ID=
CLIENT_SECRET=
BOT_ID=
OWNER_ID=

PREFIX=!
DATABASE_PATH=.data/tokens.db
STREAM_LOGS_PATH=.data/logs
IGNORED_USERS=

ADMIN_HOST=127.0.0.1
ADMIN_PORT=4345
ADMIN_BASE_URL=http://127.0.0.1:4345

SESSION_SECRET=
ADMIN_SESSION_MAX_AGE_SECONDS=28800
CHANNEL_SESSION_MAX_AGE_SECONDS=2592000
ENVIRONMENT=local
SESSION_HTTPS_ONLY=false
TRUST_PROXY_HEADERS=false

BOT_REDIRECT_URI=http://127.0.0.1:4345/admin/oauth/bot
CHANNEL_REDIRECT_URI=http://127.0.0.1:4345/admin/oauth/channel
PUBLIC_CHANNEL_REDIRECT_URI=http://127.0.0.1:4345/oauth/channel/connect

BOT_SCOPES=user:read:chat user:write:chat user:bot
CHANNEL_SCOPES=channel:bot moderator:manage:banned_users moderator:read:followers moderator:read:blocked_terms moderator:read:chat_settings moderator:read:unban_requests moderator:read:chat_messages moderator:read:warnings moderator:read:moderators moderator:read:vips channel:read:redemptions channel:read:subscriptions channel:read:ads channel:manage:moderators moderator:manage:shoutouts

SERYBOT_USER_ID=402337290
BOT_DETECTION_MODE=learning
LOG_LEVEL=INFO
```

Generate a long random value for `SESSION_SECRET`. The application refuses to start without it.

The signed browser session lasts for `CHANNEL_SESSION_MAX_AGE_SECONDS` so broadcasters do not need to
repeat Twitch OAuth on every visit. Administrator authentication expires independently after
`ADMIN_SESSION_MAX_AGE_SECONDS`. Keep `SESSION_SECRET` stable across deployments or all existing browser
sessions will become invalid.

`BOT_DETECTION_MODE` accepts `learning`, `shadow`, or `active`. `ENVIRONMENT` accepts `local` or `production`.

## Twitch Application Configuration

Create a Twitch developer application and register every OAuth callback exactly as configured in `.env`.

Local callbacks:

```text
http://127.0.0.1:4345/admin/oauth/bot
http://127.0.0.1:4345/admin/oauth/channel
http://127.0.0.1:4345/oauth/channel/connect
```

The bot callback authorizes the bot account. The administrator channel callback connects broadcasters from the admin dashboard. The public channel callback signs a broadcaster into their channel dashboard.

Changing a scope does not update existing tokens. Reauthorize the affected account after changing `BOT_SCOPES` or `CHANNEL_SCOPES`.

## Running Locally

```bash
python main.py
```

The bot runtime and web dashboard start together. The default streamer entry point is:

```text
http://127.0.0.1:4345
```

The administrator dashboard is available at `http://127.0.0.1:4345/admin`.

The health endpoint is available at `/health` and returns the application name, version, environment, and health state.

## First Administrator Account

Administrator authentication uses database-backed accounts and Argon2 password hashes. The original owner account must be created before the admin dashboard can be used. Additional administrator accounts can then be created, disabled, re-enabled, or assigned a new password from the owner-only **Admin Users** page.

Administrator passwords must contain at least 12 characters. The owner account is protected from dashboard disabling and password replacement by another administrator.

## Dashboards

### Administrator Dashboard

The administrator dashboard provides:

- Runtime and database status
- Bot OAuth authorization
- Broadcaster connection and removal
- Connected-channel status and details
- Feature, command-group, and command overrides
- Viewer-queue inspection and direct viewer removal
- Stream-log browsing
- Administrator account management

### Channel Dashboard

Broadcasters can connect with Twitch at `/connect`. After Twitch identity and connected-channel verification, a channel owner can:

- View their channel and live status
- Inspect their viewer queue and remove viewers
- View channel settings
- Enable, disable, or reset their own feature and command overrides

Channel sessions are isolated by the authenticated Twitch broadcaster ID. Dashboard forms use CSRF tokens.

## Production Deployment

The current production instance is deployed to a Raspberry Pi and updated over SSH. A production deployment should also provide:

- HTTPS through a reverse proxy
- `ENVIRONMENT=production`
- `SESSION_HTTPS_ONLY=true`
- `TRUST_PROXY_HEADERS=true` when proxy headers come from a trusted local proxy
- Public HTTPS values for `ADMIN_BASE_URL` and all OAuth redirect URIs
- A process manager such as systemd
- Restricted `.env` and database permissions
- Backups for `.data/tokens.db` and `.data/logs`
- Health monitoring against `/health`

The repository does not yet include a universal installation script or committed production service configuration. The existing Raspberry Pi setup is operator-managed and should not be treated as a turnkey public deployment.

## Data and Migrations

The default SQLite database is `.data/tokens.db`. It stores OAuth tokens, EventSub subscription state, authorized broadcasters, administrator accounts, channel settings, feature overrides, points, counters, redeems, and migration history.

Migrations run automatically at startup in version order. Current migrations cover:

1. Initial application schema
2. Redeem statistics
3. Administrator accounts

Add a new migration for schema changes instead of manually recreating the database.

Viewer queues are currently held in memory and reset when the application restarts.

## Commands

The default prefix is `!`. Available commands depend on the active profile and dashboard overrides.

| Group | Commands |
| --- | --- |
| Utility | `!hi`, `!choice`, `!kaboom`, `!stinky`, `!lucky`, `!smart`, `!lurk`, `!help` |
| Viewer queue | `!open`, `!close`, `!join`, `!leave`, `!queue`, `!next`, `!clear` |
| Socials | `!socials`, `!socials discord`, `!socials youtube`, `!setdiscord`, `!setyoutube` |
| Settings | `!timers`, `!timers on`, `!timers off` |
| Counters | `!explode`, `!reklop`, `!randy`, `!car` |
| Shoutouts | `!so <username>` |
| Moderation | `!kamikaze <username>` |

Queue administration, settings, shoutout, and moderation actions require broadcaster or moderator permissions where applicable.

Point commands use the active profile's configured command name. They support balance checks, leaderboards, broadcaster resets, moderator grants, gambling, and viewer duels.

## Stream Logs and Logging

Structured runtime logging covers startup, migrations, OAuth, profiles, commands, EventSub, services, moderation, and shutdown. Per-stream text logs are stored beneath `.data/logs/<channel>/` and can include chat, follows, subscriptions, raids, redeems, and lifecycle events.

If the bot restarts during an active stream, the stream-log service attempts to resume that stream's existing session.

## Testing

Run the automated test suite with:

```bash
pytest
```

New dashboard work should include tests for authentication, authorization, CSRF validation, channel isolation, and the affected service behavior.

## Current Limitations

- Broadcaster onboarding is not invitation-gated; do not expose the connect URL publicly yet.
- New channels still require a registered channel profile for complete behavior.
- Viewer queues do not persist across restarts.
- Raspberry Pi deployment is not yet reproducible solely from repository files.
- Public production operation still requires backups, monitoring, hardened error handling, and deployment documentation.

## Development Guidelines

Follow `docs/styling_guide.md` for project formatting and organization. Keep changes consistent with nearby code, use existing service and profile patterns, and prefer compact function signatures and calls when they remain readable.

## License

RatsBoomBot is currently a personal project without a formal open-source license. Add a license before public distribution or outside contributions.

# RatsBoomBot

RatsBoomBot is a multi-channel Twitch chatbot and streamer dashboard built with Python, TwitchIO, FastAPI, and SQLite. It provides shared Twitch automation while allowing each connected broadcaster to have their own commands, messages, loyalty currency, redeems, game integrations, and feature defaults.

The project currently supports Ninjakaing and a small group of invited streamers. It is a privately operated bot rather than a public self-service platform.

Current application version: **15.0.0** (see [`config/version.py`](config/version.py)). Active development targets `release/15.0.0`; the branch name denotes the next release milestone.

## Highlights

- Multi-channel Twitch chat and EventSub handling
- Channel-specific profiles, commands, currencies, messages, and feature defaults
- Twitch OAuth for the bot account and connected broadcasters
- Optional premium per-channel Twitch bot identities with automatic fallback
- Public global and per-channel chatter profiles with searchable community statistics
- Persistent loyalty points, achievements, counters, redeem history, settings, and moderation data
- Global pet collections, summon tickets, equipment, and passive bonuses
- Boss Hunt encounters with weapons, crafting, consumables, loot, and adaptive mini-boss difficulty
- Combined Twitch/YouTube chat with platform-aware sending and emotes
- Twitch raid browser with recommendations, favorites, stream previews, and raid countdowns
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

- Python 3.13 for CI and deployment
- TwitchIO 3.2
- FastAPI and Uvicorn
- SQLite and asqlite
- Jinja2 and Starlette signed sessions
- HTTPX
- Argon2 password hashing
- Rich logging
- pytest and pytest-asyncio; Node.js built-in test runner for frontend tests

## Project Structure

```text
RatsBoomBot
├── app/                    Shared bot and web runtime
├── bot/
│   ├── channels/           Broadcaster profiles, commands, and game modules
│   ├── services/
│   │   ├── channels/       Broadcaster state, settings, and feature overrides
│   │   ├── engagement/     Points, redeems, clips, and queues
│   │   ├── stream/         Timers, ads, shoutouts, and stream logs
│   │   └── support/        Help and moderation services
│   └── shared/             Reusable commands and EventSub listeners
├── config/                 Environment settings and application version
├── deploy/                 Linux, systemd, backup, and Windows deployment tools
├── docs/                   Project documentation and style guide
├── pets/                   Pet ownership and passive bonuses
├── rpg_minigame/           Boss encounters, inventory, loot, and RPG settings
├── scripts/                Administration and data-import utilities
├── storage/                Database access and versioned migrations
├── tests/                  Automated tests
├── web/
│   ├── admin/              Administrator authentication and routes
│   ├── channel/            Broadcaster authentication and routes
│   ├── public/             Public profiles, guides, and patch notes
│   ├── viewer/             Chatter sign-in and account actions
│   ├── shared/             Shared web helpers, raid discovery, and preview chat
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

`!stats` links to the invoking chatter's profile for the current channel; `!me` links to their global profile. Chatter sign-in provides account actions, including channel-specific shopping, crafting, selling, and gambling. Global profiles summarize exact tracked messages, channels visited, raid damage, boss participation, final hits, and bot-earned loyalty rewards. Each connected channel links to a detail page with the chatter's current balance, lifetime earnings, redeems, raid record, and inventory.

Historical message totals are seeded from the previous point-eligible message count. After migration 13, every non-bot message is counted independently of the loyalty cooldown. Historical lifetime earnings begin with the balance present at migration; future totals include chat, redeem, raid, gamble, and other bot rewards while excluding moderator grants and viewer transfers.

### Pets

The `pets/` package owns global pet collections, summon tickets, equipment, and passive bonuses. One pet is equipped across all channels. `!pets buy ticket` costs 50,000 loyalty points in the current channel; `!pets summon` consumes a ticket, and `!pets equip <full pet name>` changes the equipped pet. Duplicate refunds return to the ticket's purchase channel.

The eight current Common pets each have a 12.5% summon chance. Their fixed passives cover Loyalty Gain, Gamble Luck, Boss Hunt Damage, and Boss Hunt Profit. Leveling and feeding are not implemented yet. See [`docs/pets.md`](docs/pets.md) for rates, passives, and the asset workflow.

Administrators can grant a pet to an existing chatter identity using the selected environment's database:

```bash
python -m scripts.grant_pet chatter_name --pet rat
```

Selectors are `bat`, `rat`, `fox`, `wolf`, `raven`, `cat`, `dog`, and `hen`. Grants equip the pet and preserve an existing copy's level and passive. `--passive` is a testing override. The grant script is an administrator utility; chatters acquire pets through tickets.

### Achievements

Achievements track chat, loyalty, gambling, community, channel-specific, and Boss Hunt milestones. Their service currently lives in `bot/services/channels/achievements.py`; Loyalty Points and Achievements have not yet been extracted into standalone packages. See [`docs/achievements.md`](docs/achievements.md) and the related achievement guides.

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

The channel dashboard's raid browser includes Browse, Favorites, and Stream team views; category, language, tag, and relationship filters; compatibility ranking; and video/chat previews. Shared pending-raid state keeps browser actions, `/raid`, `/unraid`, and `!startraid` synchronized with the countdown banner. Follow raid is a persisted channel preference. Favorites and excluded channels are stored locally in each browser.

Some directory sorting and suggested-streamer lookups use Twitch's unsupported public website GraphQL interface, isolated from the official Helix lookups. Existing accounts may need to reconnect Twitch for the newly requested chat-reading, following, and raid-management scopes.

### Boss Hunt

Boss Hunt is the separate RPG minigame with scheduled bosses, attacks, weapons, and loyalty point rewards. Streamers can monitor and manage encounters from the Boss Hunt sidebar page. Viewers use the existing `!raid` commands and `/raid/{channel}` guide; those names remain valid so saved commands and links continue to work. This feature is distinct from Twitch raids.

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

The root URL is the public landing page with chatter sign-in. Connected broadcasters use `/channel` for stream status, combined Twitch/YouTube chat, viewer queues, check-ins, redeems, raid discovery, and feature/customization controls.

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

Migrations run automatically during startup. The authoritative ordered registry is [`storage/migrations/__init__.py`](storage/migrations/__init__.py). It includes the original engagement schema, Boss Hunt progression, achievements, YouTube chat, viewer sessions, quotes, global pets, and raid-browser settings.

Recent migrations add incoming-raid recency (65), repair the development migration-number collision that could omit Honey Hen (66), and persist Follow raid (67). Applied migration versions and names are recorded in `schema_migrations`.

Migrations are grouped into core, loyalty, achievements, Boss Hunts, and pets while retaining one global version sequence. See the [migration contributor guide](docs/migrations.md) for numbering, registration, upgrade tests, and recovery. Use a new migration for schema changes instead of rebuilding the production database.

## Historical Redeem Imports

Two preview-first tools are included:

- `scripts/import_streamerbot_redeems.py` imports Streamer.bot user-variable JSON.
- `scripts/import_mixitup_redeems.py` imports Mix It Up tab-separated First, Second, and daily totals.

Both require a broadcaster ID and only write when `--apply` is supplied. Imports replace the corresponding totals for that broadcaster, so create a backup first.

## Local Development

Streamers and chatters use the hosted website; no desktop installation is required. Maintainers can run the Python service and dashboard locally for development and testing. See [the local-development guide](docs/development.md) for environment setup, OAuth callbacks, and test commands.

## Commands

The default prefix is `!`. Availability depends on the profile and dashboard overrides.

| Group | Commands |
| --- | --- |
| Utility | `!hi`, `!choice`, `!kaboom`, `!stinky`, `!lucky`, `!smart`, `!height`, `!pp`, `!lurk`, `!help`, `!stats`, `!me` |
| Viewer queue | `!open`, `!close`, `!join`, `!leave`, `!queue`, `!next`, `!remove`, `!clear` |
| Socials | `!socials`, `!socials discord`, `!socials youtube` |
| Settings | `!set discord <url>`, `!set youtube <url>`, `!set game <game name>`, `!set title <stream title>`, `!timers`, `!timers on`, `!timers off` |
| Shoutouts | `!so <username>` |
| Clips | `!clip`, `!clip short` |
| Raids | `!startraid <channel>` |
| Moderation | `!kamikaze <username>` |
| Points | `!points` or the profile currency command with `leaderboard`, `give`, `gamble`, `roulette` / `spin`, `duel`, `add`, and `reset` subcommands |
| Pets | `!pets`, `!pets buy ticket`, `!pets summon`, `!pets equip <full pet name>` |
| Quotes | `!quote`, `!quote <number>`, `!quote add <message>`, `!quote remove <number>` |
| Overwatch | `!ow`, `!owrank`, `!owrecord`, `!owreset` |
| League of Legends | `!champs`, `!champs <champion>`, `!register <Riot ID> [region]`, `!unregister`, `!rank [chatter]`, `!ladder` |

While a channel is live, connected logged-in chatters earn 15 passive points every two minutes. Twitch's connected-chatter list is used as an approximation of watch activity; the broadcaster and configured bot identities are excluded. The bot identity used by the channel must authorize `moderator:read:chatters` and be a moderator in that channel. Payout intervals are persisted so a bot restart cannot award the same interval twice.

Bits spent through native Cheers earn the configured channel reward directly. Sound Alerts Bits purchases use the same reward ratio when the official `soundalerts` chatbot posts its purchase confirmation; anonymous or unresolvable purchasers are skipped, and processed chat-message IDs are persisted to prevent duplicate payouts.

Roulette uses a standard single-zero wheel: 18 red, 18 black, and one green. Red and black return 2× the wager, green returns 5×, and the default cap is 1,000 units of the channel's loyalty currency. Green is intentionally a high-risk novelty bet rather than an equal-odds choice. Wagers and payouts settle atomically to prevent concurrent commands from overspending a balance.

Point commands use the profile's currency command and provide `leaderboard`, `reset`, `add`, `give`, `gamble`, `roulette` / `spin`, and `duel` subcommands. Permission-sensitive actions are restricted to moderators or the broadcaster where appropriate.

## Production Deployment

The production instance runs on a Raspberry Pi under systemd and HTTPS. Assets under `deploy/` include the service unit, Linux deployment with pre-deployment backup, scheduled SQLite backups with integrity checks and retention, a Windows PowerShell deployment wrapper, and Cloudflare tunnel support.

Merges and direct pushes to `master` publish the configured application version and then deploy production through a self-hosted GitHub Actions runner on the Raspberry Pi. Register the runner with the custom label `ratsboombot` and run its service as the `rats-bot` user. The runner invokes `/opt/ratsboombot/deploy/linux/deploy.sh`, which retains the existing backup, compile check, systemd restart, health check, and rollback after failed health polling. Earlier script failures can exit before rollback; consult the deployment logs if a job fails.

The runner host must allow the `rats-bot` user to run the two systemd commands used by the deployment script without an interactive password:

```text
rats-bot ALL=(root) NOPASSWD: /usr/bin/systemctl restart ratsboombot, /usr/bin/systemctl is-active --quiet ratsboombot
```

Keep the production runner restricted to the `ratsboombot` label. The deployment job runs only after the GitHub release job succeeds on `master`; production pull requests do not deploy production. Eligible release-branch pull requests can deploy the separate UAT instance.

Production should configure:

```env
ENVIRONMENT=production
SESSION_HTTPS_ONLY=true
TRUST_PROXY_HEADERS=true
```

Use public HTTPS callback URLs, restrict `.env` and database permissions, retain backups, and monitor `/health` after deployment.

## UAT Deployment

The UAT instance runs independently beside production and can deploy validated commits from `uat` and `release/**` branches:

- Production: `/opt/ratsboombot`, port `4345`, `ratsboombot.service`, production Twitch accounts and databases
- UAT: `/opt/ratsboombot-uat`, port `4346`, `ratsboombot-uat.service`, test Twitch accounts and separate databases

UAT uses `https://uat.ratsboombot.com`, an independent Twitch application, and the test bot/broadcaster accounts configured in its own `.env`. Never copy the production `.env` or SQLite databases into UAT.

Pull requests targeting `uat` or `release/**`, and pushes to those branches, run Python compilation and pytest. When `UAT_DEPLOY_ENABLED` is `true`, eligible pushes and same-repository, non-draft PRs targeting `release/**` deploy UAT after validation. The workflow also supports manual dispatch. UAT deployments do not publish GitHub releases or restart the production service.

Complete the one-time Raspberry Pi, Twitch, Cloudflare, and GitHub setup in [`deploy/linux/UAT.md`](deploy/linux/UAT.md). Open feature and fix PRs against the active release branch (`release/15.0.0`), verify them in UAT, and merge the release branch into `master` when ready to ship.

## Testing

Run the suite from the repository root:

```bash
python -m pytest
node --test tests/js/*.test.cjs
```

The current UAT workflow runs Python tests; run the JavaScript suite explicitly for frontend changes.

New behavior should include tests for the affected service and, when relevant, authentication, authorization, CSRF, persistence, and channel isolation.

## Versioning

The application version is defined in [`config/version.py`](config/version.py). Published release history and unreleased changes live in [`CHANGELOG.md`](CHANGELOG.md), with links to GitHub releases and pull requests.

RatsBoomBot uses a practical three-part version number:

- Patch (`X.Y.Z`) — bug fixes, copy updates, and very small changes.
- Minor (`X.Y.0`) — additive, non-breaking work such as a profile or contained enhancement.
- Major (`X.0.0`) — a new system, major capability, architectural checkpoint, or release milestone.

The active release branch is `release/15.0.0`. Branch names denote planned milestones; only published GitHub releases belong in the dated changelog. The home page's **What's New** panel is updated for minor and major releases; patch history remains in the changelog and GitHub releases.

## Current Limitations

- Broadcaster onboarding is intended for invited channels and is not invitation-gated in the application.
- Connected channels without a registered profile receive a generic profile; custom behavior still uses explicit profiles and overrides.
- Some game data depends on third-party services and public player profiles.
- Production deployment requires a registered self-hosted Raspberry Pi runner.
- Not every profile-specific message and redeem has a dashboard editor.

## Development Guidelines

Follow `docs/styling_guide.md`. Keep commands thin, put shared behavior in services, keep broadcaster customization in profiles, and use migrations for persistent schema changes.

## Licensing Status

RatsBoomBot is a privately operated project and is not currently offered under an open-source license. No general source-code license is granted by this repository. All rights in copyrightable original contributions are reserved by their respective copyright holders, except where permission has already been granted or applicable law provides otherwise.

This notice does not revoke existing permissions, override GitHub's terms (including viewing and forking rights for public repositories), or replace the licenses of third-party dependencies and assets. Permission to use the hosted service is separate from permission to reuse its source code. Contact the maintainers about source-code licensing; any future project-wide license must account for contributor and third-party rights.

This is a statement of the current licensing status, not a new open-source license or a transfer of contributors' copyright. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) and [the no-license explanation](https://choosealicense.com/no-permission/).

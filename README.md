# RatsBoomBot

RatsBoomBot is a modular Python Twitch chatbot built with TwitchIO, SQLite, and a rat-themed loyalty system.

The project is designed as a personal StreamElements-style replacement for a Twitch channel. Instead of keeping everything in one script, RatsBoomBot separates chat commands, Twitch event listeners, persistent storage, and long-running background services into clear modules.

Current release branch: `release/1.0.0`

---

## What the Bot Does

RatsBoomBot currently supports:

- Twitch chat commands through TwitchIO
- Twitch EventSub chat integration
- OAuth token storage and refresh using SQLite
- Rat-themed loyalty points called **Stale Bread**
- Passive Stale Bread earning from chat activity
- Stale Bread leaderboard
- Stale Bread gambling
- Stale Bread duels
- Meme counters
- Social link commands
- Utility and fun commands
- Moderation/fun timeout command
- Viewer queue system for playing with viewers
- Timer announcements while the broadcaster is live
- Ad warning announcements
- Follow, subscription, and resubscription chat messages
- Auto-discovered help command
- Optional Windows system tray launcher

---

## Tech Stack

- Python 3.11+
- TwitchIO `~3.2.2`
- SQLite
- asqlite `~2.0.0`
- python-dotenv
- pystray
- Pillow

---

## Project Structure

```text
RatsBoomBot/
│
├── assets/
│   └── NinjaDoro.ico
│
├── bot/
│   ├── commands/
│   │   ├── counters.py
│   │   ├── moderation.py
│   │   ├── points.py
│   │   ├── socials.py
│   │   ├── utility.py
│   │   └── viewer_queue.py
│   │
│   ├── events/
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── ad_announcement_service.py
│   │   ├── broadcaster_service.py
│   │   ├── counter_service.py
│   │   ├── help_service.py
│   │   ├── points_service.py
│   │   ├── service_container.py
│   │   ├── timer_service.py
│   │   └── viewer_queue_service.py
│   │
│   └── bot.py
│
├── config/
│   └── settings.py
│
├── database/
│   └── db.py
│
├── main.py
├── tray_launcher.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Architecture Overview

RatsBoomBot is built around a service-based structure.

The `TwitchBot` class owns a `ServiceContainer`. The service container owns the bot's long-running services and shared business logic.

```text
TwitchBot
│
├── Command Components
│   ├── UtilityCommands
│   ├── SocialCommands
│   ├── PointsCommands
│   ├── ModerationCommands
│   ├── CounterCommands
│   └── ViewerQueueCommands
│
├── Event Components
│   └── ChatEvents
│
└── ServiceContainer
    ├── BroadcasterService
    ├── HelpService
    ├── TimerService
    ├── PointsService
    ├── CounterService
    ├── AdAnnouncementService
    └── ViewerQueueService
```

The general rule is:

- Commands handle Twitch chat input.
- Events listen for Twitch/EventSub activity.
- Services contain business logic.
- SQLite stores persistent data.
- `.env` stores configuration.
- User-facing language stays rat-themed.

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Akaing1/RatsBoomBot.git
cd RatsBoomBot
git checkout release/1.0.0
```

### 2. Create and Activate a Virtual Environment

Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bash
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` File

Create a `.env` file in the project root.

```env
CLIENT_ID=
CLIENT_SECRET=

BOT_ID=
OWNER_ID=

PREFIX=!
DATABASE_PATH=tokens.db

IGNORED_USERS=streamelements,nightbot,ratsboombot

DISCORD=
YOUTUBE=
```

### Environment Variable Notes

| Variable | Purpose |
| --- | --- |
| `CLIENT_ID` | Twitch application client ID |
| `CLIENT_SECRET` | Twitch application client secret |
| `BOT_ID` | Twitch user ID of the bot account |
| `OWNER_ID` | Twitch user ID of the bot owner |
| `PREFIX` | Chat command prefix, defaults to `!` |
| `DATABASE_PATH` | SQLite database file path, defaults to `tokens.db` |
| `IGNORED_USERS` | Comma-separated usernames that should not earn Stale Bread |
| `DISCORD` | Discord invite/link used by social commands and timers |
| `YOUTUBE` | YouTube link used by social commands and timers |

---

## Running the Bot

Development mode:

```bash
python main.py
```

Windows tray launcher mode:

```bash
pythonw tray_launcher.py
```

The tray launcher starts the bot automatically and provides a small menu with:

- Start Bot
- Stop Bot
- Exit

The tray icon uses:

```text
assets/NinjaDoro.ico
```

---

## Twitch Authorization

RatsBoomBot uses TwitchIO `AutoBot`, stores OAuth tokens in SQLite, and reloads saved tokens when the bot starts.

The bot currently creates EventSub subscriptions for:

- Chat messages
- Channel follows
- Channel subscriptions
- Channel resubscription messages
- Channel bans
- Ad break begin events

The exact Twitch scopes needed depend on which features you enable. At minimum, the bot is written around chat read/write access, bot/broadcaster authorization, moderation timeout ability, follower/subscription events, and ad schedule access.

When a broadcaster authorizes the bot, the bot saves their token and adds them as a tracked broadcaster.

---

## Database

RatsBoomBot uses SQLite through `asqlite`.

By default, the database path is:

```text
tokens.db
```

You can change this with:

```env
DATABASE_PATH=your_database_name.db
```

### `tokens`

Stores OAuth tokens.

```text
tokens
------
user_id TEXT PRIMARY KEY
token   TEXT NOT NULL
refresh TEXT NOT NULL
```

### `viewers`

Stores chat activity and Stale Bread balances.

```text
viewers
-------
user_id  TEXT PRIMARY KEY
username TEXT NOT NULL
points   INTEGER NOT NULL DEFAULT 0
messages INTEGER NOT NULL DEFAULT 0
```

Internally, Stale Bread is still stored as `points`.

### `counters`

Stores meme counter values.

```text
counters
--------
name  TEXT PRIMARY KEY
value INTEGER NOT NULL DEFAULT 0
```

---

## Commands

The default prefix is `!`.

### Utility Commands

| Command | Description                                       |
| --- |---------------------------------------------------|
| `!hi` | Greets the user.                                  |
| `!hi @user` | Says hello to another user.                       |
| `!choice option1 option2 option3` | Randomly chooses one option.                      |
| `!kaboom` | Says the user blew up.                            |
| `!kaboom @user` | Says the user blew up another user.               |
| `!stinky` | Gives the user a random stinkiness percentage.    |
| `!stinky @user` | Gives user user a random stinkiness percentage.   |
| `!lucky` | Gives the user a random luck percentage.          |
| `!lucky @user` | Gives another user a random luck percentage.      |
| `!smart` | Gives the user a random smartness percentage.     |
| `!smart @user` | Gives another user a random smartness percentage. |
| `!lurk` | Sends a rat-themed lurk message.                  |
| `!help` | Lists available commands discovered from the bot. |

---

### Social Commands

| Command | Description |
| --- | --- |
| `!socials` | Shows configured Discord and YouTube links. |
| `!socials discord` | Shows the Discord link. |
| `!socials youtube` | Shows the YouTube link. |

Social links come from:

```env
DISCORD=
YOUTUBE=
```

---

### Stale Bread Commands

Stale Bread is the bot's loyalty point system.

Viewers earn Stale Bread by chatting. The bot tracks eligible chat messages and awards bread automatically.

Current earning behavior:

- Viewers earn **10 Stale Bread** per eligible message.
- Each viewer has a **60-second cooldown** between earning events.
- Ignored users do not earn Stale Bread.
- Stale Bread is stored persistently in SQLite.

| Command | Description |
| --- | --- |
| `!bread` | Shows your Stale Bread balance. |
| `!bread @user` | Shows another viewer's Stale Bread balance. |
| `!bread leaderboard` | Shows the top 5 Stale Bread holders. |
| `!bread add @user amount` | Adds Stale Bread to a viewer. Moderator/broadcaster intended. |
| `!bread reset` | Resets every viewer's Stale Bread to 0. Broadcaster only. |
| `!bread gamble amount` | Gambles a specific amount of Stale Bread. |
| `!bread gamble all` | Gambles all of your Stale Bread. |
| `!bread duel @user amount` | Challenges another viewer to a Stale Bread duel. |
| `!bread duel @user all` | Challenges another viewer with all of your Stale Bread. |
| `!bread duel accept` | Accepts a pending duel. |
| `!bread duel decline` | Declines a pending duel. |

#### Gamble Rules

- A gamble can use a number or `all`.
- The viewer must have enough Stale Bread.
- Winning chance is currently **45%**.
- Winning adds the gambled amount.
- Losing removes the gambled amount.
- All-in wins and losses use special rat-themed messages.

#### Duel Rules

- A viewer challenges another viewer for a bread amount.
- The opponent must accept or decline.
- Pending duels expire after **60 seconds**.
- The challenger and opponent cannot be the same user.
- Both balances are checked when the duel is created.
- Both balances are checked again when the duel is accepted.
- The winner is randomly chosen.
- The winner steals the duel amount from the loser.

---

### Counter Commands

Counter commands increment persistent SQLite-backed counters.

| Command | Counter Key | Description                                 |
| --- | --- |---------------------------------------------|
| `!explode` | `explode` | Increments Rat's explosion count.           |
| `!reklop` | `reklop` | Increments the Reklop meme counter.         |
| `!randy` | `randy` | Increments Randy's int counter.             |
| `!car` | `car` | Increments Car's creeper explosion counter. |

Each counter is stored by name in the `counters` table and persists between bot restarts.

---

### Viewer Queue Commands

The viewer queue is an in-memory queue for playing with viewers on stream.

| Command | Description |
| --- | --- |
| `!open` | Opens the viewer queue. |
| `!close` | Closes the viewer queue. |
| `!join` | Adds the caller to the queue if the queue is open. |
| `!leave` | Removes the caller from the queue if the queue is open. |
| `!queue` | Shows the first 5 users in the queue. |
| `!next` | Pulls the next viewer from the queue. Broadcaster/mod only. |
| `!clear` | Clears the queue. Broadcaster/mod only. |

Current queue behavior:

- The queue starts closed.
- Viewers cannot join while it is closed.
- Usernames are stored lowercase.
- Duplicate joins are blocked.
- `!queue` previews the first 5 users and shows how many more are waiting.
- `!next` pops the first viewer from the queue.
- `!clear` empties the queue.
- Queue data is not stored in SQLite, so it resets when the bot restarts.

Implementation note:

- `!next` and `!clear` check for moderator or broadcaster access.
- `!open` and `!close` currently do not check permissions in the command file.
- `ViewerQueueService.next_viewer()` returns a closed-queue message string if the queue is closed, so the command should ideally handle that separately to avoid treating the message like a username.

---

### Moderation/Fun Command

| Command | Description                                                                                      |
| --- |--------------------------------------------------------------------------------------------------|
| `!kamikaze` | Times out the user for 10 seconds.                                                               |
| `!kamikaze @user` | Attempts to time out another user for 10 seconds. If it misses, the user gets timed out instead. |

Current behavior:

- Timeout duration is **10 seconds**.
- Calling `!kamikaze` without a target times out the caller.
- Targeting yourself times out the caller.
- The broadcaster and moderators cannot be targeted.
- The command rolls a random number from 1 to 100.
- If the roll is greater than 75, the target gets timed out.
- Otherwise, the caller gets timed out.

---

## Event Handling

`ChatEvents` currently listens for:

### Chat Messages

On each chat message, the bot:

1. Logs the message.
2. Tracks the message for timer announcements.
3. Tracks the message for Stale Bread earning.

### Follows

Sends a rat-themed follower message:

```text
<user> has snuck their way into the basement! Thanks for following!
```

### Subscriptions

Sends a rat-themed subscription message:

```text
<user> has subscribed! Rats stronk together!
```

### Resubscriptions

Sends a message including the cumulative subscription month count.

---

## Services

### `ServiceContainer`

Creates and owns the bot's shared services:

- `BroadcasterService`
- `HelpService`
- `TimerService`
- `PointsService`
- `CounterService`
- `AdAnnouncementService`
- `ViewerQueueService`

It also controls startup and shutdown for long-running services.

### `BroadcasterService`

Tracks broadcasters that have authorized the bot.

Main responsibilities:

- Load known broadcaster IDs.
- Add newly authorized broadcasters.
- Check which broadcasters are live.
- Check which broadcasters are offline.

This service is used by timer announcements and ad warnings so the bot only sends certain automated messages to active/live channels.

### `PointsService`

Owns the Stale Bread system.

Main responsibilities:

- Create the `viewers` table.
- Track chat activity.
- Apply earning cooldowns.
- Add Stale Bread.
- Remove Stale Bread.
- Reset all balances.
- Read leaderboard data.
- Create, resolve, expire, and remove pending duels.

Important constants:

```python
BREAD_PER_MESSAGE = 10
MESSAGE_COOLDOWN_SECONDS = 60
DUEL_EXPIRATION_SECONDS = 60
```

### `CounterService`

Owns persistent meme counters.

Main responsibilities:

- Create the `counters` table.
- Read a counter value.
- Increment a counter.
- Store the updated counter value.

### `HelpService`

Discovers loaded commands from `self.bot.commands`.

The help service recursively collects command names and subcommand names, then formats a single chat-friendly help message.

### `TimerService`

Sends rotating announcement messages while live.

Current behavior:

- Checks every **5 seconds**.
- Requires a broadcaster to be live.
- Requires **30 minutes** since the last announcement.
- Requires **20 tracked chat messages** before sending.
- Rotates through a small hardcoded list of messages.
- Resets message count after sending an announcement.

Current hardcoded timer messages promote:

- Discord
- YouTube
- `!help`

### `AdAnnouncementService`

Checks live broadcasters for upcoming ads.

Current behavior:

- Checks every **30 seconds**.
- Looks at Twitch ad schedule data.
- Warns chat when an ad is starting in approximately **60 seconds or less**.
- Avoids warning twice for the same scheduled ad time.

Current warning message:

```text
Hide! The humans are coming! Ads starting in ~<seconds> seconds!
```

### `ViewerQueueService`

Owns the viewer queue state.

Main responsibilities:

- Open the queue.
- Close the queue.
- Add users.
- Remove users.
- List the queue.
- Pop the next viewer.
- Clear the queue.
- Report queue size.

The queue uses:

```python
collections.deque
```

It also keeps a `set` of usernames to prevent duplicate joins.

---

## Startup Flow

When `python main.py` runs:

1. Logging is configured.
2. An SQLite connection pool is opened.
3. `setup_database()` creates the `tokens` table if needed.
4. Stored OAuth tokens are loaded.
5. Stored broadcaster IDs are collected from token rows.
6. Initial chat subscriptions are created for stored broadcasters.
7. `TwitchBot` is created.
8. Saved tokens are added back into TwitchIO.
9. The bot starts with `load_tokens=False`.
10. `setup_hook()` creates the `ServiceContainer`.
11. Services create their required tables.
12. Command and event components are added.
13. Timer and ad services start.
14. Loaded commands are logged.

---

## Windows Tray Launcher

`tray_launcher.py` is an optional Windows-style launcher.

It uses:

- `pystray`
- `Pillow`
- `subprocess`
- `assets/NinjaDoro.ico`

Behavior:

- Starts the bot automatically when the tray app opens.
- Launches `main.py` in a new console window.
- Provides menu items to start, stop, and exit.
- Terminates the bot process when stopped or when the tray app exits.

---

## Current Implementation Notes

These are useful details to know while developing the bot:

- Commands are intentionally thin and mostly call services.
- Persistent features should use SQLite-backed services.
- The viewer queue is currently memory-only.
- Timer messages are hardcoded in `TimerService`.
- Social links come from environment variables.
- The help command lists loaded command names automatically.
- Stale Bread is user-facing branding; internally, the database still uses `points`.
- EventSub subscriptions are created both from saved tokens and when OAuth authorization happens.
- The tray launcher assumes a Windows environment because it uses `subprocess.CREATE_NEW_CONSOLE`.

---

## Known Gaps / Future Improvements

### Configuration

- Add a real `.env.example` file to the repository.
- Validate required environment variables at startup.
- Avoid starting the bot when required values are missing.

### Viewer Queue

- Add moderator/broadcaster checks to `!open` and `!close`.
- Make `ViewerQueueService.next_viewer()` return `None` or a structured result when the queue is closed.
- Optionally persist the queue if stream restarts should not wipe it.
- Add queue position lookup.
- Add max queue size.
- Add optional game/mode labels.

### Commands

- Add custom commands stored in SQLite.
- Add edit/remove command support.
- Add command aliases.
- Add permissions metadata.
- Improve command error messages.

### Timers

- Move timer messages to SQLite.
- Add chat commands for adding/removing timers.
- Add enable/disable state.
- Add per-channel timer configuration.
- Add dashboard support.

### Stale Bread

- Add daily claim command.
- Add bread shop/rewards.
- Add cooldown display.
- Add transfer/gift command.
- Add more mini-games.
- Add clearer moderator-only checks and messages.

### Dashboard

Long-term dashboard ideas:

- Start/stop bot
- Reload commands
- Manage timers
- Manage custom commands
- View leaderboard
- Manage counters
- Configure social links
- View queue
- Control queue
- View logs

### Integrations

Possible future integrations:

- OBS
- Streamer.bot
- Channel point redemptions
- Giveaways
- Quotes
- AI chat features

---

## Development Conventions

Preferred project style:

- Keep commands small.
- Put reusable logic in services.
- Keep Twitch event listeners simple.
- Keep persistent state in SQLite.
- Keep secrets and stream-specific values in `.env`.
- Keep chat responses fun, rat-themed, and stream-specific.
- Prefer reusable services over one-off command logic.

---

## Troubleshooting

### `ServiceContainer` has no attribute `viewer_queue`

Make sure your branch includes:

```python
from bot.services.viewer_queue_service import ViewerQueueService
```

and that `ServiceContainer.__init__()` contains:

```python
self.viewer_queue = ViewerQueueService(bot)
```

Also make sure the bot process was restarted after pulling changes.

### Queue Commands Do Not Work

Check that `ViewerQueueCommands` is imported and added in `bot/bot.py`:

```python
from bot.commands.viewer_queue import ViewerQueueCommands
```

and:

```python
await self.add_component(ViewerQueueCommands(self))
```

### Users Cannot Earn Stale Bread

Check:

- The bot is receiving chat messages.
- The user is not listed in `IGNORED_USERS`.
- The user is outside the 60-second earning cooldown.
- The `viewers` table exists in SQLite.
- `ChatEvents.event_message()` is loaded.

### Social Commands Return Empty Links

Check the `.env` values:

```env
DISCORD=
YOUTUBE=
```

### Timers Are Not Sending

Timers only send when:

- A tracked broadcaster is live.
- At least 30 minutes have passed.
- At least 20 chat messages have been tracked.
- The bot can send messages to the broadcaster's chat.

### Tray Launcher Does Not Start

Check:

- `assets/NinjaDoro.ico` exists.
- Dependencies are installed.
- You are running in an environment that supports `pystray`.
- On Windows, try running:

```bash
python tray_launcher.py
```

instead of `pythonw tray_launcher.py` so errors are visible.

---

## Personal Project Note

RatsBoomBot is a personal stream bot project. The goal is to slowly replace more external bot functionality with custom-built features that fit the stream's rat-themed identity.

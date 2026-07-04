# RatsBoomBot

A modular Python Twitch chatbot built with TwitchIO, SQLite, and a rat-themed loyalty system.

RatsBoomBot is inspired by StreamElements, but customized specifically for my stream. The long-term goal is to replace more of my StreamElements setup with my own bot features, including loyalty points, timers, custom commands, counters, giveaways, moderation tools, and eventually a web dashboard.

## Features

* TwitchIO 3.2.2 AutoBot setup
* EventSub chat integration
* OAuth token storage and refresh through SQLite
* Modular command components
* Service-based architecture
* SQLite-backed loyalty system
* Rat-themed loyalty points called **Stale Bread**
* Chat activity tracking
* Timer service
* Automatic command help discovery
* Social commands
* Moderation commands
* Stale Bread leaderboard
* Stale Bread gamble command
* Stale Bread duel command with 60-second expiration
* Direct meme counter command: `!explode`
* System tray launcher support

## Tech Stack

* Python 3.11
* TwitchIO 3.2.2
* SQLite
* asqlite
* python-dotenv
* pystray
* pillow

## Project Structure

```text
RatBoomBot/
│
├── assets/
│
├── bot/
│   ├── commands/
│   │   ├── counters.py
│   │   ├── moderation.py
│   │   ├── points.py
│   │   ├── socials.py
│   │   └── utility.py
│   │
│   ├── events/
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── counter_service.py
│   │   ├── help_service.py
│   │   ├── points_service.py
│   │   ├── service_container.py
│   │   └── timer_service.py
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
└── .env.example
```

## Architecture

RatsBoomBot uses a service-based structure.

The bot owns a `ServiceContainer`, and the container owns the long-running services.

```text
ServiceContainer
│
├── HelpService
├── TimerService
├── PointsService
└── CounterService
```

Commands and events are kept lightweight.

General rule:

* Commands handle Twitch chat input
* Events listen for Twitch events
* Services contain business logic
* SQLite stores persistent data
* `.env` stores configuration

## Configuration

Create a `.env` file based on `.env.example`.

Current settings:

```env
CLIENT_ID=
CLIENT_SECRET=
BOT_ID=
OWNER_ID=
PREFIX=!
DATABASE_PATH=tokens.db
IGNORED_USERS=
```

`IGNORED_USERS` should be a comma-separated list of usernames that should not earn Stale Bread.

Example:

```env
IGNORED_USERS=streamelements,nightbot,ratsboombot
```

## Setup

Clone the repository:

```bash
git clone https://github.com/Akaing1/RatsBoomBot.git
cd RatsBoomBot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your `.env` file:

```bash
copy .env.example .env
```

Then fill in your Twitch application values.

Run the bot:

```bash
python main.py
```

## Twitch Authorization

The bot uses Twitch OAuth through TwitchIO AutoBot.

Current chat functionality requires bot/broadcaster authorization for chat access.

The bot account needs:

```text
user:read:chat
user:write:chat
user:bot
```

The broadcaster account needs:

```text
channel:bot
```

Additional future EventSub features, such as follower and subscriber alerts, may require more scopes.

## Stale Bread Loyalty System

Viewers earn **Stale Bread** by chatting.

Current behavior:

* Viewers earn 10 Stale Bread per eligible message
* There is a 60-second cooldown per viewer
* Ignored users do not earn Stale Bread
* Stale Bread is stored in SQLite
* Internally, the database still stores this as `points`
* User-facing messages call it Stale Bread

Database table:

```text
viewers
--------
user_id
username
points
messages
```

## Bread Commands

### Check Bread

```text
!bread
```

Shows how much Stale Bread the user has.

### Leaderboard

```text
!bread leaderboard
```

Shows the top Stale Bread hoarders.

### Add Bread

```text
!bread add @user amount
```

Moderator or broadcaster only.

Adds Stale Bread to a viewer.

### Reset Bread

```text
!bread reset
```

Broadcaster only.

Resets everyone’s Stale Bread to 0.

### Gamble

```text
!bread gamble 50
!bread gamble all
```

Lets viewers gamble their Stale Bread.

Current gamble behavior:

* 45% chance to win
* Winning adds the gambled amount
* Losing removes the gambled amount
* `all` gambles the user’s full Stale Bread stash
* All-in wins/losses have special rat-themed messages

### Duel

```text
!bread duel @user 100
!bread duel @user all
!bread duel accept
!bread duel decline
```

Lets one viewer challenge another viewer to a Stale Bread duel.

Current duel behavior:

* The challenger chooses an amount
* The opponent must accept or decline
* Duels expire after 60 seconds
* Balances are checked when the duel is created
* Balances are checked again when the duel is accepted
* Winner is chosen randomly
* Winner steals the duel amount from the loser

## Counter Commands

RatsBoomBot supports direct meme-style counter commands.

### Explode

```text
!explode
```

Increments the explode counter and sends a message like:

```text
Rat has exploded 5 times.
```

Counter data is stored in SQLite.

Database table:

```text
counters
--------
name
value
```

## Timer Service

The timer service sends rotating announcements based on time and chat activity.

Current timer behavior:

* Tracks chat message count
* Sends announcements after a configured interval
* Requires minimum chat activity before sending
* Rotates through timer messages

Future timer improvements:

* Store timers in SQLite
* Add timers from chat
* Remove timers from chat
* Enable or disable timers
* Support multiple timer groups
* Dashboard integration

## Help System

RatsBoomBot includes a `HelpService` that discovers commands automatically.

This avoids hardcoding command lists manually.

Future help improvements:

* Hide moderator-only commands from viewers
* Group commands by category
* Read command docstrings
* Improve formatting

## Social Commands

Social commands are currently grouped under:

```text
!socials
!socials discord
```

More socials can be added as needed.

## System Tray Launcher

The project includes a tray launcher for running the bot more like a desktop application.

Development usage:

```bash
python main.py
```

Daily-use goal:

```bash
pythonw tray_launcher.py
```

The tray launcher uses:

```text
assets/NinjaDoro.ico
```

Future tray menu ideas:

* Start Bot
* Stop Bot
* Restart Bot
* Open Dashboard
* Reload Commands
* Reload Timers
* Open Logs
* Exit

## Roadmap

Planned features:

1. Custom commands

   * `!addcommand`
   * `!editcommand`
   * `!removecommand`
   * SQLite-backed responses

2. Database-backed timers

   * Add/remove timers
   * Enable/disable timers
   * Multiple timer groups

3. Bread shop

   * Spend Stale Bread
   * Fun rewards
   * Streamer.bot integration

4. More Stale Bread games

   * Daily Bread
   * More gamble variants
   * More duel flavor

5. Quotes

6. Giveaways

7. Follower and subscriber chat alerts

8. Web dashboard

9. OBS and Streamer.bot integration

10. AI chat features

## Development Notes

This project is being built like a real modular application instead of a collection of scripts.

Current conventions:

* Keep commands thin
* Keep events simple
* Put business logic in services
* Store persistent data in SQLite
* Use `.env` for configuration
* Keep user-facing language themed around rats and Stale Bread
* Prefer reusable services over one-off command logic

## License

Personal stream project.

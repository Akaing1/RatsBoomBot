# Local Development

RatsBoomBot is a hosted web service, not a desktop application. These instructions are for maintainers running the bot and dashboard locally to develop and test changes. Streamers and chatters use the hosted website and do not install Python or this repository.

Use separate development Twitch accounts, an independent Twitch application, and a local database. Do not connect a local instance to production data or run a second bot instance against the same live accounts.

Use Python 3.13 to match CI and deployment. Install Node.js to run the frontend tests.

## 1. Clone and create a virtual environment

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

## 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure the environment

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

YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REDIRECT_URI=http://127.0.0.1:4345/oauth/youtube/connect
YOUTUBE_CHAT_DISCOVERY_SECONDS=30
```

Keep `SESSION_SECRET` stable across deployments or existing browser sessions will become invalid. Administrator sessions default to eight hours; broadcaster sessions default to 30 days. In production, set `SESSION_COOKIE_DOMAIN=.ratsboombot.com` so an authenticated session is available to both the public site and dashboard subdomain.

Register each callback exactly in the Twitch developer application. Changing scopes requires the affected account to reconnect.

To enable combined Twitch and YouTube chat, enable the YouTube Data API v3 in a Google Cloud project and create an OAuth 2.0 Web application. Add `YOUTUBE_REDIRECT_URI` as an exact authorized redirect URI, then set its client ID and secret in `.env`. The integration requests `youtube.force-ssl` to read and send live-chat messages. It uses streaming with polling fallback, token renewal, and reconnect handling. Dashboard messages can target Twitch, YouTube, or both; YouTube must have an active live chat. If the OAuth consent screen is still in Testing, add each broadcaster as a test user.

Connected broadcasters receive three private OBS Browser Source URLs under **Customization → Socials → YouTube chat**: chat without commands, commands only, and both. Regenerating these URLs invalidates the previous set.

## 4. Run

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

## Tests and feature branches

Run from the repository root with the virtual environment active:

```bash
python -m pytest
node --test tests/js/*.test.cjs
```

Open changes against the active release branch (`release/15.0.0`) and verify the feature in UAT before the release is merged into `master`. See the [README deployment sections](../README.md#production-deployment) and [UAT setup guide](../deploy/linux/UAT.md).

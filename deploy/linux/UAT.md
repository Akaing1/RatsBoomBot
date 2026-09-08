# RatsBoomBot UAT Environment

UAT runs beside production on the Raspberry Pi without sharing code, processes, ports, credentials, databases, logs, cookies, or Twitch accounts.

| Setting | Production | UAT |
| --- | --- | --- |
| Git branch | `master` | `uat` |
| Checkout | `/opt/ratsboombot` | `/opt/ratsboombot-uat` |
| Service | `ratsboombot.service` | `ratsboombot-uat.service` |
| Local port | `4345` | `4346` |
| Public URL | `https://ratsboombot.com` | `https://uat.ratsboombot.com` |
| Bot account | RatsBoomBot | akaing1 |
| Broadcaster | Production channels | developer_ninjakaing |
| SQLite data | Production checkout | UAT checkout |

## 1. Create the UAT Twitch application

Create a separate Twitch Developer application for UAT. Register these exact OAuth callbacks:

```text
https://uat.ratsboombot.com/admin/oauth/bot
https://uat.ratsboombot.com/admin/oauth/channel
https://uat.ratsboombot.com/oauth/channel/connect
```

Use the application's client ID and secret only in `/opt/ratsboombot-uat/.env`. The bot account is `akaing1`; authorize only `developer_ninjakaing` as the broadcaster.

## 2. Create the isolated Pi checkout

```bash
sudo install -d -o rats-bot -g rats-bot /opt/ratsboombot-uat
sudo -u rats-bot git clone --branch uat https://github.com/Akaing1/RatsBoomBot.git /opt/ratsboombot-uat
sudo -u rats-bot python3 -m venv /opt/ratsboombot-uat/.venv
sudo -u rats-bot /opt/ratsboombot-uat/.venv/bin/python -m pip install -r /opt/ratsboombot-uat/requirements.txt
sudo -u rats-bot cp /opt/ratsboombot-uat/.env.uat.example /opt/ratsboombot-uat/.env
sudo chmod 600 /opt/ratsboombot-uat/.env
```

Edit `/opt/ratsboombot-uat/.env` and supply the UAT Twitch credentials, numeric account IDs, and a new UAT-only session secret. Do not copy the production database or session secret. Keeping `SESSION_COOKIE_DOMAIN` empty makes UAT browser cookies host-only.

## 3. Add the Cloudflare hostname

Add this rule before the catch-all entry in `/etc/cloudflared/config.yml`:

```yaml
ingress:
  - hostname: uat.ratsboombot.com
    service: http://127.0.0.1:4346
```

Route the hostname to the existing tunnel and restart Cloudflare:

```bash
cloudflared tunnel route dns <tunnel-name-or-id> uat.ratsboombot.com
sudo systemctl restart cloudflared
```

Confirm that `https://uat.ratsboombot.com/health` reaches the UAT instance only after its service is started.

## 4. Install the UAT service

```bash
sudo cp /opt/ratsboombot-uat/deploy/linux/ratsboombot-uat.service /etc/systemd/system/ratsboombot-uat.service
sudo systemctl daemon-reload
sudo systemctl enable --now ratsboombot-uat
```

Allow the existing runner user to operate only the UAT service in addition to production:

```text
rats-bot ALL=(root) NOPASSWD: /usr/bin/systemctl restart ratsboombot-uat, /usr/bin/systemctl is-active --quiet ratsboombot-uat
```

Use `visudo` to add the rule.

## 5. Initialize UAT

Create the UAT owner account against its empty database:

```bash
cd /opt/ratsboombot-uat
sudo -u rats-bot .venv/bin/python scripts/create_owner.py
```

Then open `https://uat.ratsboombot.com/admin`:

1. Authorize `akaing1` through the bot OAuth link.
2. Authorize `developer_ninjakaing` as the broadcaster.
3. Confirm the health response reports `"environment": "uat"`.
4. Confirm production still reports `"environment": "production"`.

## 6. Enable automated UAT deployment

Create the GitHub repository variable:

```text
UAT_DEPLOY_ENABLED=true
```

The workflow is deliberately guarded by this variable. Until it is enabled, pushes to `uat` run validation but skip the Pi deployment.

## Development flow

1. Branch from `uat`.
2. Open the feature PR back into `uat`.
3. The UAT workflow compiles the project and runs all tests.
4. Merge the PR to deploy it to `https://uat.ratsboombot.com`.
5. Test with `akaing1` in `developer_ninjakaing`.
6. When the release is ready, open a PR from `uat` into `master` with the final version bump.
7. Never delete the permanent `uat` branch after merging a release.

UAT does not publish GitHub releases and cannot restart `ratsboombot.service`.

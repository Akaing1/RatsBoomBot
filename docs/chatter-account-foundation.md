# Chatter account foundation

The `/me` route gives a viewer a signed-in, read-only view of their existing public chatter profile. `/chatters/{login}` and channel profile URLs remain public. A viewer with no recorded activity receives a welcome page rather than a 404.

`!stats` posts the caller's channel profile URL and `!me` posts the caller's global profile URL. Both public pages offer Twitch sign-in and return the viewer to that page afterward. The signed session cookie lasts up to 30 days (the existing channel session maximum) and is reused across visits until sign-out or expiry.

Viewer login uses a dedicated Twitch OAuth callback (`/oauth/viewer/connect`) with an empty scope list. The callback exchanges the authorization code, fetches the Twitch user's stable ID, and keeps only that ID and display information in the signed session. It does not onboard a broadcaster or persist the viewer's access or refresh token. Signing out clears the viewer identity without disconnecting a broadcaster session.

## Deployment

Register the exact `VIEWER_REDIRECT_URI` in the Twitch developer console for each environment's Twitch app. Set it to `https://ratsboombot.com/oauth/viewer/connect` in production and `https://uat.ratsboombot.com/oauth/viewer/connect` in UAT (adjust if the configured public host differs). Local development uses `http://127.0.0.1:4345/oauth/viewer/connect`. Keep the viewer redirect on the same host as the app session cookie.

The existing `PUBLIC_BASE_URL` supplies the default redirect URI if `VIEWER_REDIRECT_URI` is unset. The URL still needs to be registered with Twitch before the sign-in button works.

## Next development stages

1. Add a private account layout and channel selector on top of these existing stats.
2. Move the chat command rules for points, inventory, crafting, gambling, and raids into services callable from both web and chat. Use stable Twitch user IDs and channel IDs and transactional balance changes.
3. Before enabling any account writes, add server-side session expiration/revocation and request throttling, then run concurrency checks on the SQLite-backed actions in UAT.
4. Add channel-level choices for which website actions announce in chat.

Linking YouTube identities to Twitch accounts will need an explicit ownership verification flow; matching usernames is insufficient.

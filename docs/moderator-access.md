# Moderator dashboard (16.1.3)

Channel owners grant access from **Moderator access**, using the existing Twitch-user search and confirmation. Grants use stable Twitch user IDs. Twitch moderator status alone does not grant dashboard access, and granting bot access does not add a Twitch moderator badge.

| Level | Access |
| --- | --- |
| Moderator | Overview, own-account chat, moderation, viewer queue controls, Notes, and prediction API actions |
| Super moderator | Moderator plus ad management and bot settings/customization, feature switches, protected users, queue blacklist and stream metadata |

Migration 74 removes legacy View grants without promoting them and limits stored roles to Moderator and Super moderator. Streamers can re-add former viewers explicitly. Existing Moderator/Super moderator grants are preserved. Revoking a grant blocks future pages/actions and removes the channel from the signed-in personal profile's right-side Mod Bar. Public chatter profiles never receive grants.

## Entry and navigation

Sign in through `/me` (the `!me` entry point) and choose a channel in the Mod Bar. `/me/mod/{channel}` now opens the shared channel Overview; Notes moved to `/me/mod/{channel}/notes`. The left navigation contains My account, Overview, Settings for Super moderators, and a separated list of granted channels, with SVG icons when collapsed. Notes is an Overview circle shortcut opening a note composer dialog. Moderator and Super moderator users can save a new titled note directly to the channel’s For You notes collection. Creation rechecks the grant transactionally, audits the actor, and deduplicates retries by submission ID. Polls, Predictions and Shouts are disabled coming-soon circles. Overview hides the Predictions panel, audience statistics (also filtered from its API), raid browser, personal workspace flip, bot identity, account connections, widget secrets and access management. Super moderators receive a Settings navigation item. Owner-only pages are not registered under moderator URLs.

The dashboard uses the existing Overview template and feed services. Only an explicit allowlist of routes is exposed under the moderator prefix. Every request validates the viewer's server-backed session, channel grant and capability before resolving the target channel on request state. It never replaces `channel_user_id` in the session. JSON/form inputs cannot choose the actor or target broadcaster. Redirects remain under the same moderator prefix.

## Twitch authorization and actions

The red, top-centered **Authorize Twitch** button requests authorization from the signed-in moderator's own Twitch account using the existing viewer OAuth callback URI. The callback checks CSRF state, the existing session, the current channel grant and the returned Twitch user ID. Using another Twitch account is rejected. Cancellation returns to the moderator Overview, not administrator sign-in.

Ordinary `/me` sign-in remains identity-only. Moderator action access/refresh tokens are kept in the separate `moderator_twitch_tokens` database table, not the session cookie or broadcaster/bot token registry. They do not onboard a channel. User-authenticated chat always uses that actor as `sender_id`; moderator API calls use that actor as `moderator_id`. There is no fallback to broadcaster credentials. YouTube chat remains visible, but moderator messages are Twitch-only because this flow does not authorize the moderator's YouTube identity.

Moderator/Super moderator authorization requests `user:write:chat`, `user:read:emotes` and the scopes for message deletion/pins, bans, announcements, chat settings, AutoMod, warnings and shoutouts. A bot grant cannot bypass Twitch's own moderator and scope checks. The button is hidden when stored consent satisfies the current role scopes and authorization revision. It reappears for missing scopes, a role upgrade, or a release that increments `AUTHORIZATION_REVISION`. Routine version bumps do not revoke consent. Migration 73 preserves existing consent at revision 1. A failed token refresh (400/401) or a repeated API 401 invalidates the revision; chat failures and window focus refresh the banner without background polling.

Supported slash commands: `/ban`, `/timeout`, `/unban`, `/clear`, `/warn`, announcement colors, slow/follower/subscriber/emote/unique-chat modes, and `/shoutout`. Owner-only commands such as `/mod`, `/raid` and `/commercial` are not forwarded through the moderator chat endpoint. Ad status and controls are restricted to Super moderators at the UI and API.

Twitch prediction APIs require the broadcaster's user token. Authorized Moderator/Super moderator requests use that channel's existing server-side authorization and are attributed to the actor in the audit log. Broadcasters must reconnect once to grant the newly requested `channel:manage:predictions` scope, and the channel must be eligible for Channel Points predictions. Prediction endpoints remain available, but the panel and its script are no longer mounted in Overview; there is no prediction polling. Resolution verifies the prediction and selected outcome belong to this channel.

Token transport refreshes once on HTTP 401; other rejected/uncertain writes are not retried automatically. Signed tokens, upstream response bodies and message contents are not returned in error messages or copied into the audit log.

## Revocation and auditing

Normal requests check the database grant every time. Live-chat streams check session/grant validity during the connection and before delivering subsequent messages, with checks throttled to five seconds and idle checks at the existing 15-second heartbeat. On revocation they close and unsubscribe; the browser stops reconnecting after the access-revoked event. Already completed external actions are not undone.

Migration 72 expands the grant constraint for the three roles and creates the dedicated moderator token table. Settings overrides identify the actor as `moderator:{id}`. Completed moderator POST requests and native slash commands are recorded in `channel_access_audit`; failed form submissions that return a redirect can also appear as submitted attempts. There is no audit viewer yet.

## UAT walkthrough

1. Grant a second Twitch account Moderator; open its `/me`, select the channel, and verify the stream embed, chat, activity, moderation and queue status. Confirm there are no raid shortcuts or Settings link.
2. Authorize that same account for chat and send/reply to a message. Confirm Twitch displays the moderator account, never the broadcaster or bot. Try a different account during OAuth; it must be rejected.
3. Test moderation with a Twitch account that has a real moderator badge. Test create/lock/resolve or cancel on a prediction-enabled channel after the broadcaster reconnects.
4. Grant Super moderator, change a feature switch and a command setting, and verify the intended channel updates. Connections, bot identity, widget URLs and access management must remain inaccessible.
5. Downgrade or revoke access while the page is open. Future privileged actions must fail; an open chat connection must stop within the heartbeat window. Another channel must remain inaccessible.
6. Review live Twitch behavior in UAT. Local Chromium checks covered desktop/mobile Moderator and Super moderator pages, the mobile carousel, the chat composer and queue actions. Those previews used mocked feed data and a placeholder video embed; real Twitch OAuth, playback and actions still need UAT validation.

Role badges are green for Moderator and orange for Super moderator. Owners change existing roles directly with the role dropdown; failed changes restore the prior selection. Moderator pages return a styled Unauthorized page (401/403) after lost access, while API failures remain JSON. The Overview omits stream online/offline status. The right-side My account Mod Bar uses compact channel rows and role labels.

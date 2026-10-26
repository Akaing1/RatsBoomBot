# Moderator access (16.0.0)

This first increment delegates **Notes** only. Owners open **Moderator access** in the channel dashboard, enter a Twitch username and choose View or Edit. Saving resolves the username to a Twitch user ID; grants are stored by ID. View reads existing notes. Edit also updates existing notes. Creating/deleting notes, other dashboard features, bot authorization and access management remain owner-only.

Moderators sign in through `/me` (the `!me` entry point). The right-hand Mod Bar lists explicitly granted channels. It also appears for accounts with no chatter activity. On narrow screens it becomes a collapsible panel above the content. Public chatter pages never receive the channel list. Moderators do not connect their own channel or acquire the owner's session.

Migration 71 adds `channel_access` and `channel_access_audit`. Every moderator page/save validates the server-backed viewer session and reads the current grant. A save checks Edit permission and updates the note within one write transaction, so grant revocation and updates cannot race through a cached permission. Existing revision checks protect against concurrent owner/moderator edits; a conflict page preserves the submitted draft. Reads paginate 20 notes at a time. There are no polling loops or background tasks.

Grant/revoke actions and successful edits are audited with channel, actor, action, subject and timestamp. Note contents and auth tokens are not copied into the audit log. There is no audit viewer yet.

To try it in UAT after merging/deploying:

1. Sign in as a channel owner, open Moderator access, and grant a different Twitch account Notes/View.
2. Sign in as that account through `/me`, select the channel in the right-hand Mod Bar, and verify Notes are read-only.
3. Change the grant to Edit; refresh the moderator page and save an existing note. Verify it in the owner's For You page.
4. Revoke access while the moderator page is open. Saving/refreshing must fail, and refreshing `/me` must remove that channel.
5. Check a second channel and a public chatter URL: neither should expose the first channel's private notes or grants.

Further features should receive explicit capabilities and server-side checks before becoming available here. Do not implement switching by replacing `channel_user_id` with a granted channel ID: that would grant the owner's unrelated privileges.

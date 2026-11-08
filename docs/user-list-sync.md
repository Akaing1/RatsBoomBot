# Sync user lists between environments

Open the dashboard, settings, or followers page while signed in to the same Twitch channel in each environment. The console helper is `ratsLists`.

In the source environment's browser console, copy an export:

```js
exportLists()
```

In the destination environment's console, paste it into the prompt:

```js
importLists()
```

Imports merge with existing entries by default. To replace the supplied lists:

```js
importLists({replace: true})
```

The export command copies to the clipboard. If clipboard access is unavailable, it opens a prompt where you can copy the text manually. The import command opens a paste prompt; cancelling it leaves all lists unchanged. A success dialog appears after importing, showing the entry count for each imported list. Reload the destination page after importing to update all open panels. This transfers list membership without changing shoutout triggers or enablement settings.

For long lists, transfer a JSON file instead of pasting text:

```js
exportLists({file: true})
```

Then select that file in the destination environment:

```js
importLists({file: true})
```

File imports also merge by default; add `replace: true` to replace the supplied lists. Do not copy abbreviated console previews containing `...`; the complete JSON is required.

Exports contain only a format version, Twitch channel ID, and these lists:

Both commands print progress in the console with a `[User lists]` prefix, including validation, server/browser saves, list counts, completion, and errors. Export messages distinguish preparing the data from copying it or starting the file download.

| List | Entries | Stored in |
| --- | --- | --- |
| `raidFavorites` | Twitch user IDs | Current browser |
| `raidBlacklist` | Twitch user IDs | Current browser |
| `automaticShoutouts` | Twitch usernames | Server settings |
| `incomingRaidBlacklist` | Twitch usernames | Server settings |
| `queueBlacklist` | Twitch usernames | Server settings |

To transfer fewer lists, remove unwanted keys from the export's `lists` object. Omitted lists stay unchanged, including when replacing. Exports include no credentials. Imports reject exports for a different Twitch channel, invalid entries, and lists over their limits. Adding someone to the queue blacklist uses the usual behavior, including removing them from an active queue.

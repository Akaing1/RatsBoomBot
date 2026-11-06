# 8ball

Use `!8ball <yes/no question>` for a short conversational answer. Questions may be
up to 400 characters. The command replies with just the answer, without repeating
the question or username. It follows the channel's global-command switch, its
own `!8ball` switch under Chat, and the existing shared command slowmode.

This is a local rule-based feature with no API calls or usage fees. It does not
know facts about chatters or learn automatically from the history.

## Responses and matching

Edit `bot/services/engagement/eight_ball_responses.json` and restart the bot to
change the shared response library. Each entry has a unique stable `id`, an
`outcome` (`yes`, `maybe`, or `no`), a list of compatible `categories`, and `text`.
Keep IDs stable when editing wording. Do not include username placeholders.

Categories:

| Category | Matching questions | Example answer |
| --- | --- | --- |
| statement | Is/are/am/was/were/do/does/did/has/have, including common negatives | The evidence is overwhelming. |
| prediction | Will/won't | Looking pretty good. |
| advice | Should/shall/could/would I | The rats advise against it. |
| ability | Can I | You've got this. |
| general | Other wording; also eligible for every category | Honestly? Could go either way. |

First-person advice and encouragement are only eligible for first-person
questions. `Can Meinya win?` uses general answers rather than `You've got this.`
Matching ignores case and repeated whitespace. Unrecognized wording falls back
to general answers. Future rules can extend `question_category`.

Every request rolls yes/maybe/no with equal probability before selecting wording.
Response pool size and history do not alter those odds. Recent response IDs are
excluded when possible; if the selected outcome's pool is exhausted, the oldest
exclusions are relaxed first. Immediate repeats are prevented by requiring at
least two general responses for each outcome.

## History

Migration 78 adds `eight_ball_history` to the existing SQLite database. It stores
the normalized question, category, outcome, response ID, channel, and timestamp.
Only the latest 100 entries per channel are retained; the latest five influence
repeat avoidance. History survives restarts and stays separate between channels.
It can be inspected to find matching rules or response wording worth improving.
This version does not include an automatic training or feedback system.

# Timer rotation

Messages and promotional announcements share a 30-minute delivery buffer per
channel. Each entry keeps its configured interval and optional chat-message
requirement. When several entries become eligible, only the oldest waiting entry
is sent. Other entries remain pending until a later slot; list order breaks ties.
A successful delivery starts the channel buffer and resets that entry's interval
and message baseline. Failed deliveries do not consume the slot, so another
eligible entry can still be sent. Different channels have independent buffers.

Profiles accept plain strings (normal messages) or typed entries:

```python
timer_messages=(
    ("Join our community!", "message"),
    ("Support the channel!", "announcement", "orange"),
)
```

Announcement color defaults to `primary`. Supported colors are primary, blue,
green, orange, and purple. The admin and channel customization editors expose
the delivery type and color. Existing newline-separated saved timers still load
as messages; mixed lists retain their types and colors when saved.

Meinya's YouTube partnership announcement is now the first entry in her default
rotation. It no longer runs on a separate hourly/30-message schedule. With seven
entries, a full default rotation takes at least 3.5 hours. A saved timer override
replaces the default list; add the promotion through customization if that channel
uses an override.

Failed announcements fall back to chat. If both attempts fail, the same entry
remains pending. Timer counters, delivery buffers, and progress remain in memory and reset
on restart. Stream lifecycle announcements (ads and raid events) are independent
of this promotional timer rotation.

# Timer rotation

Messages and promotional announcements share one rotation per channel. One entry
is sent after at least 30 minutes and 20 tracked chat messages. A successful send
resets both gates and advances the rotation by one slot.

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
remains pending. Timer counters and rotation position remain in memory and reset
on restart. Stream lifecycle announcements (ads and raid events) are independent
of this promotional timer rotation.

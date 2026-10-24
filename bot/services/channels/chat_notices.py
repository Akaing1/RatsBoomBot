"""Presentation metadata shared by the dashboard and the preview chat relay."""

NOTICE_LABELS = {
    "sub": "Subscription", "resub": "Resubscription", "sub_gift": "Gift sub",
    "community_sub_gift": "Gift subs", "gift_paid_upgrade": "Gift subscription upgrade",
    "prime_paid_upgrade": "Prime subscription upgrade", "watch_streak": "Watch streak",
    "raid": "Incoming raid",
}


def notification_details(notice_type, system_message, data=None):
    kind = str(notice_type or "").removeprefix("shared_chat_")
    if kind not in NOTICE_LABELS:
        return None

    def value(key, default=None):
        return data.get(key, default) if isinstance(data, dict) else getattr(data, key, default)

    label = NOTICE_LABELS[kind]
    if kind in {"sub", "resub"} and (value("is_prime", value("prime", False)) or value("sub_plan") == "Prime"):
        label = f"Prime {label.lower()}"
    summary = str(system_message or label)
    streak_months = value("streak_months") if kind == "resub" else None
    if streak_months:
        streak = f"{streak_months} consecutive months"
        if streak not in summary:
            summary += f" · {streak}"
    return {"notice_type": kind, "notice_label": label, "notice": summary}

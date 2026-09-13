TIER_NAMES = ("Bronze", "Silver", "Gold", "Platinum")
ACHIEVEMENTS = {
    "explorer": ("Community Explorer", "Check into unique channels.", "compass"),
    "regular": ("Daily Regular", "Complete daily check-ins across all channels.", "calendar"),
    "familiar": ("Familiar Face", "Complete daily check-ins in a single channel.", "home"),
}


class AchievementService:

    def __init__(self, db):
        self.db = db

    async def get_collection(self, user_id: str, channel_metadata) -> dict:
        async with self.db.acquire() as connection:
            tiers = await connection.fetchall("SELECT * FROM achievement_tiers ORDER BY achievement_id, tier")
            progress = await connection.fetchall("SELECT * FROM achievement_progress WHERE user_id = ?", (str(user_id),))
            unlocks = await connection.fetchall("SELECT * FROM achievement_unlocks WHERE user_id = ? ORDER BY tier", (str(user_id),))
            observations = await connection.fetchall("SELECT broadcaster_id FROM chatter_channel_observations WHERE user_id = ?", (str(user_id),))

        counts = {(row["achievement_id"], row["broadcaster_id"]): int(row["progress"]) for row in progress}
        earned = {(row["achievement_id"], row["broadcaster_id"], int(row["tier"])): dict(row) for row in unlocks}
        channels = {str(row["broadcaster_id"]) for row in observations}
        channels.update(str(row["broadcaster_id"]) for row in progress if row["broadcaster_id"])
        channels.update(str(row["broadcaster_id"]) for row in unlocks if row["broadcaster_id"])
        cards = []
        for name, channel in [("explorer", ""), ("regular", "")] + [("familiar", channel) for channel in sorted(channels)]:
            title, description, icon = ACHIEVEMENTS[name]
            steps = []
            for row in tiers:
                if row["achievement_id"] != name:
                    continue
                tier = int(row["tier"])
                unlock = earned.get((name, channel, tier))
                steps.append({"name": TIER_NAMES[tier - 1], "threshold": int(row["threshold"]), "earned": unlock is not None, "date": unlock["unlocked_at"] if unlock else None})
            highest = next((step for step in reversed(steps) if step["earned"]), None)
            next_tier = next((step for step in steps if not step["earned"]), None)
            count = counts.get((name, channel), 0)
            target = next_tier["threshold"] if next_tier else steps[-1]["threshold"]
            cards.append({
                "title": title, "description": description, "icon": icon,
                "scope": "channel" if channel else "global",
                "channel": channel_metadata(channel) if channel else None,
                "tier": highest["name"] if highest else "Locked", "steps": steps,
                "progress": count, "target": target, "next_tier": next_tier,
                "percent": min(100, round(count * 100 / target)),
            })
        return {"cards": cards, "unlocked": len(unlocks), "available": len(cards) * 4}

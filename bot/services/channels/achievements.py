TIER_NAMES = ("Bronze", "Silver", "Gold", "Platinum")
ACHIEVEMENTS = {
    "explorer": ("Community Explorer", "Check into unique channels.", "compass"),
    "regular": ("Daily Regular", "Complete daily check-ins across all channels.", "calendar"),
    "familiar": ("Familiar Face", "Complete daily check-ins in a single channel.", "home"),
    "collector": ("Point Collector", "Earn loyalty points across all channels.", "coins"),
    "winner": ("Lucky Break", "Earn gambling profit across all channels.", "dice"),
    "damage": ("Damage Dealer", "Deal raid damage across all channels.", "swords"),
    "weapons": ("Weapons Master", "Purchase weapons across all channels.", "swords"),
    "buffs": ("Team Player", "Purchase raid buffs across all channels.", "banner"),
    "consumables": ("Well Stocked", "Purchase raid consumables across all channels.", "potion"),
    "house": ("The House Always Wins", "Lose 500,000 loyalty points gambling across all channels. Thank you for your generous donation.", "house"),
    "stones": ("Collecting the Stones", "Collect all five Blessed Unique weapons across all channels.", "stones"),
    "exterminator": ("Rat Exterminator", "Successfully blow up another chatter with !kamikaze 100 times across all channels.", "bomb"),
}


class AchievementService:

    def __init__(self, db):
        self.db = db

    async def record_kamikaze_success(self, broadcaster_id: str, message_id: str, user_id: str, target_id: str) -> None:
        if str(user_id) == str(target_id):
            return
        async with self.db.acquire() as connection:
            await connection.execute(
                "INSERT OR IGNORE INTO kamikaze_successes (broadcaster_id,message_id,user_id,target_id) VALUES (?,?,?,?)",
                (str(broadcaster_id),str(message_id),str(user_id),str(target_id))
            )

    async def get_collection(self, user_id: str, channel_metadata) -> dict:
        async with self.db.acquire() as connection:
            tiers = await connection.fetchall("SELECT * FROM achievement_tiers ORDER BY achievement_id, tier")
            progress = await connection.fetchall("SELECT * FROM achievement_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_chat_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_raid_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_hidden_progress WHERE user_id = ?", (str(user_id),))
            unlocks = await connection.fetchall("SELECT * FROM achievement_unlocks WHERE user_id = ? ORDER BY tier", (str(user_id),))

        counts = {(row["achievement_id"], row["broadcaster_id"]): int(row["progress"]) for row in progress}
        earned = {(row["achievement_id"], row["broadcaster_id"], int(row["tier"])): dict(row) for row in unlocks}
        counts[("familiar", "")] = max((int(row["progress"]) for row in progress if row["achievement_id"] == "familiar"), default=0)
        # A tier earned in any channel qualifies globally. Retain the original
        # per-channel records so historical achievements are never revoked.
        for tier in range(1, 5):
            matches = [dict(row) for row in unlocks if row["achievement_id"] == "familiar" and int(row["tier"]) == tier]
            if matches:
                earned[("familiar", "", tier)] = min(matches, key=lambda row: row["unlocked_at"] or "")
        cards = []
        for name, channel in [(name, "") for name in ACHIEVEMENTS]:
            if name in {"house", "stones", "exterminator"} and (name, channel, 4) not in earned:
                continue
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
                "category": "raids" if name in {"damage", "weapons", "buffs", "consumables", "stones"} else "chat" if name in {"collector", "winner", "house", "exterminator"} else "check_ins",
                "unit": {"stones": "unique blessed weapons", "exterminator": "successful kamikazes", "damage": "damage", "weapons": "weapons purchased", "buffs": "buffs purchased", "consumables": "consumables purchased", "explorer": "unique channels", "collector": "loyalty points", "winner": "loyalty points", "house": "loyalty points"}.get(name, "check-ins"),
                "standalone": name in {"house", "stones", "exterminator"},
                "scope": "channel" if channel else "global",
                "channel": channel_metadata(channel) if channel else None,
                "tier": highest["name"] if highest else "Locked", "steps": steps,
                "progress": count, "target": target, "next_tier": next_tier,
                "percent": min(100, round(count * 100 / target)),
            })
        return {"cards": cards, "unlocked": sum(step["earned"] for card in cards for step in card["steps"]), "available": sum(len(card["steps"]) for card in cards)}

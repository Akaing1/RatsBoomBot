TIER_NAMES = ("Bronze", "Silver", "Gold", "Platinum")
ACHIEVEMENT_TIER_XP = {1: 100, 2: 250, 3: 500, 4: 1000}
CHANNEL_TIER_REWARDS = {1: 500, 2: 2000, 3: 7500, 4: 25000}
SECRET_CHANNEL_ACHIEVEMENTS = {
    "whisker": ("By a Whisker", "Finish a main or mini boss that has exactly 1 HP remaining.", "swords", "raids", "finishing blows"),
    "not_close": ("Not Even Close", "Leave a main or mini boss at exactly 1 HP with your attack.", "swords", "raids", "attacks"),
    "average": ("Perfectly Average", "Get measured at 50% stinky, smart, and lucky in this channel.", "dice", "chat", "completed sets"),
    "character_development": ("Character Development", "Earn both opposite measurement badges for one command in this channel.", "trophy", "chat", "completed pairs"),
    "shower": ("You Need a Shower", "Roll 100% stinky.", "house", "chat", "qualifying rolls"),
    "spotless": ("Squeaky Clean", "Roll 0% stinky.", "house", "chat", "qualifying rolls"),
    "lights_out": ("Lights On, but No One's Home", "Roll 0% smart.", "home", "chat", "qualifying rolls"),
    "genius": ("Big Brain Energy", "Roll 100% smart.", "compass", "chat", "qualifying rolls"),
    "tiny": ("I Almost Didn't See You Down There", "Get measured at exactly 1 foot tall.", "home", "chat", "qualifying rolls"),
    "towering": ("How's the Weather Up There?", "Get measured at exactly 8 feet tall.", "home", "chat", "qualifying rolls"),
    "gamble_all": ("Have You Considered Using Gamble All?", "Roll 100% lucky.", "dice", "chat", "qualifying rolls"),
    "unlucky": ("Maybe Sit This One Out", "Roll 0% lucky.", "dice", "chat", "qualifying rolls"),
    "loss_streak": ("Can't End on a Loss", "Lose 10 consecutive settled !gamble bets in this channel.", "dice", "chat", "losses in a row"),
    "win_streak": ("Quit While You're Ahead", "Win 10 consecutive settled !gamble bets in this channel.", "dice", "chat", "wins in a row"),
}
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
    "nice_try_global": ("Nice Try", "Miss with !kamikaze across all channels.", "bomb"),
    "loss_streak_global": ("Can't End on a Loss", "Lose 10 consecutive settled !gamble bets in a single channel.", "dice"),
    "win_streak_global": ("Quit While You're Ahead", "Win 10 consecutive settled !gamble bets in a single channel.", "dice"),
}
CHANNEL_ACHIEVEMENTS = {
    "watch_time": ("watch_time", "Spend time connected to this channel's live chat (hours).", "home", "chat", "hours"),
    "stream_regular": ("stream_regular", "Be present in chat during distinct live streams in this channel.", "calendar", "chat", "streams"),
    "flag_support": ("flag_support", "Contribute Flag Bearer bonus damage against main and mini bosses in this channel.", "banner", "raids", "bonus damage"),
    "crafts": ("crafts", "Craft Refined or Masterwork weapons in this channel.", "swords", "raids", "weapons crafted"),
    "repairs": ("repairs", "Restore weapon durability with repairs in this channel.", "swords", "raids", "repairs"),
    "familiar": ("check_ins", "Complete daily check-ins in this channel.", "home", "check_ins", "check-ins"),
    "channel_messages": ("messages", "Send messages while this channel is live.", "chat", "chat", "live messages"),
    "collector": ("points", "Earn loyalty points in this channel.", "coins", "chat", "loyalty points"),
    "winner": ("gambling", "Earn gambling profit in this channel.", "dice", "chat", "loyalty points"),
    "damage": ("damage", "Deal raid damage in this channel.", "swords", "raids", "damage"),
    "channel_bosses": ("bosses", "Help defeat raid bosses in this channel.", "trophy", "raids", "bosses defeated"),
    "weapons": ("weapons", "Purchase raid weapons in this channel.", "swords", "raids", "weapons purchased"),
    "buffs": ("buffs", "Purchase raid buffs in this channel.", "banner", "raids", "buffs purchased"),
    "consumables": ("consumables", "Purchase raid consumables in this channel.", "potion", "raids", "consumables purchased"),
    "nice_try": (None, "Miss with !kamikaze in this channel.", "bomb", "chat", "missed kamikazes"),
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

    async def record_kamikaze_failure(self, broadcaster_id: str, message_id: str, user_id: str) -> None:
        async with self.db.acquire() as connection:
            await connection.execute(
                "INSERT OR IGNORE INTO kamikaze_failures (broadcaster_id,message_id,user_id) VALUES (?,?,?)",
                (str(broadcaster_id),str(message_id),str(user_id))
            )

    async def record_command_roll(self, broadcaster_id: str, message_id: str, command: str, user_id: str, value: int) -> None:
        endpoints = {"stinky": (0, 50, 100), "smart": (0, 50, 100), "lucky": (0, 50, 100), "height": (12, 96)}
        if command not in endpoints:
            raise ValueError("Unsupported achievement roll")
        if int(value) not in endpoints[command]:
            return
        async with self.db.acquire() as connection:
            await connection.execute(
                "INSERT OR IGNORE INTO command_achievement_rolls (broadcaster_id,message_id,command,user_id,value) VALUES (?,?,?,?,?)",
                (str(broadcaster_id),str(message_id),command,str(user_id),int(value))
            )

    async def get_collection(self, user_id: str, channel_metadata) -> dict:
        async with self.db.acquire() as connection:
            tiers = await connection.fetchall("SELECT * FROM achievement_tiers ORDER BY achievement_id, tier")
            progress = await connection.fetchall("SELECT * FROM achievement_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_chat_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_raid_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM achievement_hidden_progress WHERE user_id = ?", (str(user_id),))
            progress += await connection.fetchall("SELECT * FROM secret_global_progress WHERE user_id = ?", (str(user_id),))
            unlocks = await connection.fetchall("SELECT * FROM achievement_unlocks WHERE user_id = ? ORDER BY tier", (str(user_id),))
            origins = await connection.fetchall("SELECT achievement_id,channel_name FROM gamble_streak_origins WHERE user_id=?", (str(user_id),))

        counts = {(row["achievement_id"], row["broadcaster_id"]): int(row["progress"]) for row in progress}
        earned = {(row["achievement_id"], row["broadcaster_id"], int(row["tier"])): dict(row) for row in unlocks}
        streak_origins = {row["achievement_id"]: row["channel_name"] for row in origins}
        counts[("familiar", "")] = max((int(row["progress"]) for row in progress if row["achievement_id"] == "familiar"), default=0)
        # A tier earned in any channel qualifies globally. Retain the original
        # per-channel records so historical achievements are never revoked.
        for tier in range(1, 5):
            matches = [dict(row) for row in unlocks if row["achievement_id"] == "familiar" and int(row["tier"]) == tier]
            if matches:
                earned[("familiar", "", tier)] = min(matches, key=lambda row: row["unlocked_at"] or "")
        cards = []
        for name, channel in [(name, "") for name in ACHIEVEMENTS]:
            if name in {"house", "stones", "exterminator", "loss_streak_global", "win_streak_global"} and (name, channel, 4) not in earned:
                continue
            title, description, icon = ACHIEVEMENTS[name]
            if name in streak_origins:
                description += f" Earned in {streak_origins[name]}."
            steps = []
            for row in tiers:
                if row["achievement_id"] != name:
                    continue
                tier = int(row["tier"])
                unlock = earned.get((name, channel, tier))
                steps.append({"name": TIER_NAMES[tier - 1], "threshold": int(row["threshold"]), "earned": unlock is not None, "date": unlock["unlocked_at"] if unlock else None, "reward": None, "xp": ACHIEVEMENT_TIER_XP[tier]})
            highest = next((step for step in reversed(steps) if step["earned"]), None)
            next_tier = next((step for step in steps if not step["earned"]), None)
            count = counts.get((name, channel), 0)
            target = next_tier["threshold"] if next_tier else steps[-1]["threshold"]
            cards.append({
                "title": title, "description": description, "icon": icon,
                "category": "raids" if name in {"damage", "weapons", "buffs", "consumables", "stones"} else "chat" if name in {"collector", "winner", "house", "exterminator", "nice_try_global", "loss_streak_global", "win_streak_global"} else "check_ins",
                "unit": {"stones": "unique blessed weapons", "exterminator": "successful kamikazes", "nice_try_global": "missed kamikazes", "loss_streak_global": "losses in a row", "win_streak_global": "wins in a row", "damage": "damage", "weapons": "weapons purchased", "buffs": "buffs purchased", "consumables": "consumables purchased", "explorer": "unique channels", "collector": "loyalty points", "winner": "loyalty points", "house": "loyalty points"}.get(name, "check-ins"),
                "standalone": name in {"house", "stones", "exterminator", "loss_streak_global", "win_streak_global"},
                "scope": "channel" if channel else "global",
                "channel": channel_metadata(channel) if channel else None,
                "tier": highest["name"] if highest else "Locked", "steps": steps,
                "progress": count, "target": target, "next_tier": next_tier,
                "percent": min(100, round(count * 100 / target)),
            })
        return {
            "cards": cards,
            "unlocked": sum(step["earned"] for card in cards for step in card["steps"]),
            "available": sum(len(card["steps"]) for card in cards),
            "summary": "Celebrate your milestones across RatsBoomBot communities.",
            "currency_name": None
        }

    async def get_channel_collection(self, user_id: str, broadcaster_id: str, names, channel_metadata, currency_name: str) -> dict:
        user_id = str(user_id)
        broadcaster_id = str(broadcaster_id)
        achievement_ids = tuple(CHANNEL_ACHIEVEMENTS) + tuple(SECRET_CHANNEL_ACHIEVEMENTS)
        placeholders = ",".join("?" for _ in achievement_ids)
        async with self.db.acquire() as connection:
            tiers = await connection.fetchall(f"SELECT * FROM achievement_tiers WHERE achievement_id IN ({placeholders}) ORDER BY achievement_id,tier", achievement_ids)
            progress = await connection.fetchall("SELECT * FROM achievement_channel_progress WHERE user_id=? AND broadcaster_id=?", (user_id, broadcaster_id))
            progress += await connection.fetchall("SELECT * FROM secret_channel_progress WHERE user_id=? AND broadcaster_id=?", (user_id, broadcaster_id))
            progress += await connection.fetchall("SELECT * FROM community_achievement_progress WHERE user_id=? AND broadcaster_id=?", (user_id, broadcaster_id))
            unlocks = await connection.fetchall(
                f"SELECT * FROM achievement_unlocks WHERE user_id=? AND broadcaster_id=? AND achievement_id IN ({placeholders}) ORDER BY tier",
                (user_id, broadcaster_id, *achievement_ids)
            )
        counts = {str(row["achievement_id"]): int(row["progress"]) for row in progress}
        earned = {(str(row["achievement_id"]), int(row["tier"])): dict(row) for row in unlocks}
        channel = channel_metadata(broadcaster_id)
        cards = []
        for achievement_id, (name_field, description, icon, category, unit) in {**CHANNEL_ACHIEVEMENTS, **{key:(None,*value[1:]) for key,value in SECRET_CHANNEL_ACHIEVEMENTS.items()}}.items():
            if achievement_id in SECRET_CHANNEL_ACHIEVEMENTS and (achievement_id, 4) not in earned:
                continue
            steps = []
            for row in tiers:
                if str(row["achievement_id"]) != achievement_id:
                    continue
                tier = int(row["tier"])
                unlock = earned.get((achievement_id, tier))
                steps.append({
                    "name": TIER_NAMES[tier - 1], "threshold": int(row["threshold"]) // 60 if achievement_id == "watch_time" else int(row["threshold"]),
                    "earned": unlock is not None, "date": unlock["unlocked_at"] if unlock else None,
                    "reward": CHANNEL_TIER_REWARDS[tier], "xp": ACHIEVEMENT_TIER_XP[tier]
                })
            highest = next((step for step in reversed(steps) if step["earned"]), None)
            next_tier = next((step for step in steps if not step["earned"]), None)
            count = counts.get(achievement_id, 0)
            if achievement_id == "watch_time":
                count = round(count / 60, 2)
            target = next_tier["threshold"] if next_tier else steps[-1]["threshold"]
            cards.append({
                "title": str(getattr(names, name_field)) if name_field else ("Nice Try" if achievement_id == "nice_try" else SECRET_CHANNEL_ACHIEVEMENTS[achievement_id][0]), "description": description, "icon": icon,
                "category": category, "unit": unit, "standalone": achievement_id in SECRET_CHANNEL_ACHIEVEMENTS, "scope": "channel", "channel": channel,
                "tier": highest["name"] if highest else "Locked", "steps": steps,
                "progress": count, "target": target, "next_tier": next_tier,
                "percent": min(100, round(count * 100 / target))
            })
        return {
            "cards": cards,
            "unlocked": sum(step["earned"] for card in cards for step in card["steps"]),
            "available": sum(len(card["steps"]) for card in cards),
            "summary": f"Earn themed badges and {currency_name} through activity in this channel.",
            "currency_name": currency_name
        }

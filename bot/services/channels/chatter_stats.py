import logging
from typing import Any

from bot.profiles import get_active_profile
from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")


class ChatterStatsService:

    def __init__(self, bot, db, broadcasters):
        self.bot = bot
        self.db = db
        self.broadcasters = broadcasters

    async def setup(self) -> None:
        LOGGER.info("[Chatter Stats] Chatter profile storage is ready.")

    async def track_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        user_id = str(payload.chatter.id)
        username = str(payload.chatter.name).lower()

        if user_id == str(self.bot.bot_id) or username in settings.IGNORED_USERS:
            return

        services = getattr(self.bot, "services", None)

        if services is not None and services.chat_identity.is_custom_bot(user_id):
            return

        query = """
        INSERT INTO chatter_channel_stats (broadcaster_id, user_id, messages_sent, updated_at)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            messages_sent = messages_sent + 1,
            updated_at = CURRENT_TIMESTAMP
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (broadcaster_id, user_id))

    async def record_points_earned(self, broadcaster_id: str, user_id: str, amount: int, connection=None) -> None:
        if amount <= 0:
            return

        query = """
        INSERT INTO chatter_channel_stats (broadcaster_id, user_id, lifetime_points_earned, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(broadcaster_id, user_id) DO UPDATE SET
            lifetime_points_earned = lifetime_points_earned + excluded.lifetime_points_earned,
            updated_at = CURRENT_TIMESTAMP
        """
        values = (str(broadcaster_id), str(user_id), int(amount))

        if connection is not None:
            await connection.execute(query, values)
            return

        async with self.db.acquire() as managed_connection:
            await managed_connection.execute(query, values)

    async def resolve_identity(self, value: str):
        value = value.strip().removeprefix("@").strip()

        if not value:
            return None

        query = """
        SELECT user_id, login, display_name, first_seen_at, last_seen_at
        FROM chatter_identities
        WHERE user_id = ? OR login = ? COLLATE NOCASE OR display_name = ? COLLATE NOCASE
        LIMIT 1
        """

        async with self.db.acquire() as connection:
            return await connection.fetchone(query, (value, value, value))

    async def get_global_profile(self, value: str) -> dict[str, Any] | None:
        identity = await self.resolve_identity(value)

        if identity is None:
            return None

        user_id = str(identity["user_id"])

        async with self.db.acquire() as connection:
            totals = await connection.fetchone(
                """
                SELECT COALESCE(SUM(stats.messages_sent), 0) AS messages_sent,
                       COALESCE(SUM(stats.lifetime_points_earned), 0) AS lifetime_points_earned,
                       (SELECT COUNT(*) FROM chatter_channel_observations WHERE user_id = ?) AS channels_interacted
                FROM chatter_channel_stats AS stats
                WHERE stats.user_id = ?
                """,
                (user_id, user_id)
            )
            raid = await connection.fetchone(
                """
                SELECT COALESCE(SUM(attacks.damage), 0) AS damage_dealt,
                       COUNT(DISTINCT attacks.event_id) AS bosses_attacked,
                       COUNT(DISTINCT CASE WHEN events.status = 'defeated' THEN attacks.event_id END) AS bosses_defeated,
                       COUNT(DISTINCT CASE WHEN events.final_hitter_id = ? THEN events.id END) AS final_hits
                FROM raid_boss_attacks AS attacks
                JOIN raid_boss_events AS events ON events.id = attacks.event_id
                WHERE attacks.user_id = ?
                """,
                (user_id, user_id)
            )
            highest = await connection.fetchone(
                """
                SELECT COALESCE(MAX(event_damage), 0) AS highest_contribution
                FROM (
                    SELECT SUM(damage) AS event_damage
                    FROM raid_boss_attacks
                    WHERE user_id = ?
                    GROUP BY event_id
                )
                """,
                (user_id,)
            )
            claims = await connection.fetchone(
                """
                SELECT COALESCE(SUM(claim_count), 0) AS daily_check_ins
                FROM (
                    SELECT COUNT(*) AS claim_count FROM redeem_claims WHERE user_id = ? AND redeem_type = 'daily'
                    UNION ALL
                    SELECT COALESCE(SUM(claim_count), 0) FROM imported_redeem_totals WHERE user_id = ? AND redeem_type = 'daily'
                )
                """,
                (user_id, user_id)
            )
            rewards = await connection.fetchone(
                """
                SELECT COALESCE(SUM(contribution_points + final_hit_points + bonus_points), 0) AS points
                FROM raid_boss_reward_summaries
                WHERE user_id = ?
                """,
                (user_id,)
            )
            top_contributor = await connection.fetchone(
                """
                WITH contributions AS (
                    SELECT event_id, user_id, SUM(damage) AS damage
                    FROM raid_boss_attacks
                    GROUP BY event_id, user_id
                )
                SELECT COUNT(*) AS finishes
                FROM contributions AS mine
                JOIN raid_boss_events AS events ON events.id = mine.event_id
                WHERE mine.user_id = ?
                  AND events.status IN ('defeated', 'failed')
                  AND mine.damage = (SELECT MAX(others.damage) FROM contributions AS others WHERE others.event_id = mine.event_id)
                """,
                (user_id,)
            )
            recent_raids = await connection.fetchall(self._recent_raids_query(), (user_id, user_id))
            channels = await connection.fetchall(
                """
                SELECT observations.broadcaster_id,
                       COALESCE(stats.messages_sent, 0) AS messages_sent,
                       COALESCE(stats.lifetime_points_earned, 0) AS lifetime_points_earned,
                       COALESCE(viewers.points, 0) AS current_points,
                       COALESCE((SELECT SUM(damage) FROM raid_boss_attacks WHERE broadcaster_id = observations.broadcaster_id AND user_id = observations.user_id), 0) AS raid_damage
                FROM chatter_channel_observations AS observations
                LEFT JOIN chatter_channel_stats AS stats
                  ON stats.broadcaster_id = observations.broadcaster_id
                 AND stats.user_id = observations.user_id
                LEFT JOIN viewers
                  ON viewers.broadcaster_id = observations.broadcaster_id
                 AND viewers.user_id = observations.user_id
                WHERE observations.user_id = ?
                ORDER BY observations.last_seen_at DESC
                """,
                (user_id,)
            )

        channel_summaries = [self._channel_summary(row) for row in channels]
        favorite_channel = max(channel_summaries, key=lambda channel: channel["messages_sent"], default=None)

        return {
            "identity": dict(identity),
            "messages_sent": int(totals["messages_sent"]),
            "lifetime_points_earned": int(totals["lifetime_points_earned"]),
            "channels_interacted": int(totals["channels_interacted"]),
            "daily_check_ins": int(claims["daily_check_ins"]),
            "favorite_channel": favorite_channel,
            "damage_dealt": int(raid["damage_dealt"]),
            "highest_contribution": int(highest["highest_contribution"]),
            "bosses_attacked": int(raid["bosses_attacked"]),
            "bosses_defeated": int(raid["bosses_defeated"]),
            "final_hits": int(raid["final_hits"]),
            "raid_reward_points": int(rewards["points"]),
            "top_contributor_finishes": int(top_contributor["finishes"]),
            "recent_raids": [self._raid_history(row) for row in recent_raids],
            "channels": channel_summaries
        }

    async def get_channel_profile(self, chatter_value: str, channel_value: str) -> dict[str, Any] | None:
        identity = await self.resolve_identity(chatter_value)
        broadcaster = self._resolve_broadcaster(channel_value)

        if identity is None or broadcaster is None:
            return None

        user_id = str(identity["user_id"])
        broadcaster_id = str(broadcaster.id)

        async with self.db.acquire() as connection:
            observation = await connection.fetchone("SELECT 1 FROM chatter_channel_observations WHERE broadcaster_id = ? AND user_id = ?", (broadcaster_id, user_id))

            if observation is None:
                return None

            summary = await connection.fetchone(
                """
                SELECT COALESCE(stats.messages_sent, 0) AS messages_sent,
                       COALESCE(stats.lifetime_points_earned, 0) AS lifetime_points_earned,
                       COALESCE(viewers.points, 0) AS current_points
                FROM chatter_channel_observations AS observations
                LEFT JOIN chatter_channel_stats AS stats
                  ON stats.broadcaster_id = observations.broadcaster_id AND stats.user_id = observations.user_id
                LEFT JOIN viewers
                  ON viewers.broadcaster_id = observations.broadcaster_id AND viewers.user_id = observations.user_id
                WHERE observations.broadcaster_id = ? AND observations.user_id = ?
                """,
                (broadcaster_id, user_id)
            )
            raid = await connection.fetchone(
                """
                SELECT COALESCE(SUM(attacks.damage), 0) AS damage_dealt,
                       COUNT(DISTINCT attacks.event_id) AS bosses_attacked,
                       COUNT(DISTINCT CASE WHEN events.status = 'defeated' THEN attacks.event_id END) AS bosses_defeated,
                       COUNT(DISTINCT CASE WHEN events.final_hitter_id = ? THEN events.id END) AS final_hits
                FROM raid_boss_attacks AS attacks
                JOIN raid_boss_events AS events ON events.id = attacks.event_id
                WHERE attacks.broadcaster_id = ? AND attacks.user_id = ?
                """,
                (user_id, broadcaster_id, user_id)
            )
            highest = await connection.fetchone(
                "SELECT COALESCE(MAX(event_damage), 0) AS highest_contribution FROM (SELECT SUM(damage) AS event_damage FROM raid_boss_attacks WHERE broadcaster_id = ? AND user_id = ? GROUP BY event_id)",
                (broadcaster_id, user_id)
            )
            claims = await connection.fetchall(
                """
                SELECT redeem_type, SUM(claim_count) AS claim_count
                FROM (
                    SELECT redeem_type, COUNT(*) AS claim_count
                    FROM redeem_claims
                    WHERE broadcaster_id = ? AND user_id = ?
                    GROUP BY redeem_type
                    UNION ALL
                    SELECT redeem_type, SUM(claim_count) AS claim_count
                    FROM imported_redeem_totals
                    WHERE broadcaster_id = ? AND user_id = ?
                    GROUP BY redeem_type
                )
                GROUP BY redeem_type
                """,
                (broadcaster_id, user_id, broadcaster_id, user_id)
            )
            inventory = await connection.fetchall(
                """
                SELECT inventory.item_id, inventory.quantity, inventory.durability,
                       CASE WHEN players.equipped_weapon = inventory.item_id THEN 1 ELSE 0 END AS equipped
                FROM raid_boss_inventory AS inventory
                LEFT JOIN raid_boss_players AS players
                  ON players.broadcaster_id = inventory.broadcaster_id AND players.user_id = inventory.user_id
                WHERE inventory.broadcaster_id = ? AND inventory.user_id = ? AND inventory.quantity > 0
                ORDER BY equipped DESC, inventory.item_id
                """,
                (broadcaster_id, user_id)
            )
            rewards = await connection.fetchone(
                """
                SELECT COALESCE(SUM(contribution_points + final_hit_points + bonus_points), 0) AS points,
                       COUNT(*) AS raids_rewarded
                FROM raid_boss_reward_summaries
                WHERE broadcaster_id = ? AND user_id = ?
                """,
                (broadcaster_id, user_id)
            )
            top_contributor = await connection.fetchone(
                """
                WITH contributions AS (
                    SELECT event_id, user_id, SUM(damage) AS damage
                    FROM raid_boss_attacks
                    WHERE broadcaster_id = ?
                    GROUP BY event_id, user_id
                )
                SELECT COUNT(*) AS finishes
                FROM contributions AS mine
                JOIN raid_boss_events AS events ON events.id = mine.event_id
                WHERE mine.user_id = ?
                  AND events.status IN ('defeated', 'failed')
                  AND mine.damage = (SELECT MAX(others.damage) FROM contributions AS others WHERE others.event_id = mine.event_id)
                """,
                (broadcaster_id, user_id)
            )
            recent_raids = await connection.fetchall(self._recent_raids_query(channel=True), (user_id, user_id, broadcaster_id))

        profile = get_active_profile(broadcaster_id)
        claim_counts = {str(row["redeem_type"]): int(row["claim_count"]) for row in claims}

        return {
            "identity": dict(identity),
            "channel": self._channel_metadata(broadcaster_id),
            "messages_sent": int(summary["messages_sent"]),
            "lifetime_points_earned": int(summary["lifetime_points_earned"]),
            "current_points": int(summary["current_points"]),
            "currency_name": profile.points.command_name if profile and profile.points.command_name else "points",
            "damage_dealt": int(raid["damage_dealt"]),
            "highest_contribution": int(highest["highest_contribution"]),
            "bosses_attacked": int(raid["bosses_attacked"]),
            "bosses_defeated": int(raid["bosses_defeated"]),
            "final_hits": int(raid["final_hits"]),
            "raid_reward_points": int(rewards["points"]),
            "raids_rewarded": int(rewards["raids_rewarded"]),
            "top_contributor_finishes": int(top_contributor["finishes"]),
            "recent_raids": [self._raid_history(row) for row in recent_raids],
            "daily_check_ins": claim_counts.get("daily", 0),
            "firsts": claim_counts.get("first", 0),
            "seconds": claim_counts.get("second", 0),
            "inventory": [dict(row) | {"display_name": profile.raid_bosses.weapon_names.display(str(row["item_id"])) if profile else str(row["item_id"]).replace("_", " ").title()} for row in inventory]
        }

    def _resolve_broadcaster(self, value: str):
        normalized = value.strip().casefold()
        return next((broadcaster for broadcaster in self.broadcasters.get_broadcasters().values() if normalized in {str(broadcaster.id), str(broadcaster.login or "").casefold(), str(broadcaster.display_name or "").casefold()}), None)

    def _channel_summary(self, row) -> dict[str, Any]:
        summary = self._channel_metadata(str(row["broadcaster_id"]))
        summary.update(messages_sent=int(row["messages_sent"]), lifetime_points_earned=int(row["lifetime_points_earned"]), current_points=int(row["current_points"]), raid_damage=int(row["raid_damage"]))
        return summary

    def _channel_metadata(self, broadcaster_id: str) -> dict[str, Any]:
        broadcaster = self.broadcasters.get_broadcasters().get(str(broadcaster_id))

        if broadcaster is None:
            return {"id": str(broadcaster_id), "login": str(broadcaster_id), "display_name": f"Channel {broadcaster_id}", "profile_image_url": None}

        return {
            "id": str(broadcaster.id),
            "login": broadcaster.login or str(broadcaster.id),
            "display_name": broadcaster.display_name or broadcaster.login or str(broadcaster.id),
            "profile_image_url": broadcaster.profile_image_url
        }

    @staticmethod
    def _recent_raids_query(channel: bool = False) -> str:
        channel_filter = "AND events.broadcaster_id = ?" if channel else ""
        return f"""
        WITH contributions AS (
            SELECT event_id, user_id, SUM(damage) AS damage
            FROM raid_boss_attacks
            GROUP BY event_id, user_id
        )
        SELECT events.id, events.broadcaster_id, events.boss_name, events.boss_tier, events.status, events.spawned_at,
               mine.damage,
               COALESCE(summaries.contribution_points + summaries.final_hit_points + summaries.bonus_points, 0) AS reward_points,
               CASE WHEN mine.damage = (SELECT MAX(others.damage) FROM contributions AS others WHERE others.event_id = events.id) THEN 1 ELSE 0 END AS top_contributor
        FROM raid_boss_events AS events
        JOIN contributions AS mine ON mine.event_id = events.id
        LEFT JOIN raid_boss_reward_summaries AS summaries ON summaries.event_id = events.id AND summaries.user_id = ?
        WHERE mine.user_id = ? {channel_filter}
          AND events.status IN ('defeated', 'failed')
        ORDER BY events.id DESC
        LIMIT 5
        """

    def _raid_history(self, row) -> dict[str, Any]:
        return {
            "event_id": int(row["id"]),
            "channel": self._channel_metadata(str(row["broadcaster_id"])),
            "boss_name": str(row["boss_name"]),
            "boss_tier": str(row["boss_tier"]),
            "status": str(row["status"]),
            "date": str(row["spawned_at"])[:10],
            "damage": int(row["damage"]),
            "reward_points": int(row["reward_points"]),
            "top_contributor": bool(row["top_contributor"])
        }

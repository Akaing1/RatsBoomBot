import logging
import random

from twitchio.ext import commands

from bot.profiles import FeatureName, RaidBossConfig, get_active_profile
from bot.shared.commands.helpers import get_context_broadcaster_id, is_feature_enabled

LOGGER = logging.getLogger("RatBoomBot")


def can_manage_raid(ctx: commands.Context) -> bool:
    chatter = ctx.chatter
    broadcaster = getattr(ctx, "broadcaster", None) or getattr(ctx, "channel", None)
    return bool(getattr(chatter, "moderator", False) or str(chatter.id) == str(getattr(broadcaster, "id", "")))


class RaidBossCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    def get_context(self, ctx: commands.Context) -> tuple[str, RaidBossConfig] | None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if (
            broadcaster_id is None
            or not is_feature_enabled(self.bot, ctx, FeatureName.RAID_BOSSES)
            or not is_feature_enabled(self.bot, ctx, FeatureName.POINTS)
        ):
            return None

        profile = get_active_profile(broadcaster_id)

        if profile is None or not profile.raid_bosses.enabled:
            return None

        return broadcaster_id, profile.raid_bosses

    @commands.group(name="raid", invoke_fallback=True)
    async def raid(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        event = await self.bot.services.raid_bosses.get_active_event(context[0])

        if event is None:
            await ctx.send("There is no active raid boss right now.")
            return

        percent = event.current_hp / event.max_hp * 100
        streams_remaining = event.stream_limit - event.streams_used + 1
        await ctx.send(f"{event.boss_name} [{event.boss_tier.title()} Boss / {event.boss_type.title()}] — {event.current_hp:,}/{event.max_hp:,} HP ({percent:.1f}%). {streams_remaining} raid stream(s) remain. Use !raid attack once this stream!")

    @raid.command(name="attack")
    async def attack(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        broadcaster_id, config = context
        stream_id = await self.get_stream_id(broadcaster_id, config)

        if stream_id is None:
            await ctx.reply("You can only attack while the stream is live.")
            return

        event, failed_reward = await self.bot.services.raid_bosses.register_stream(broadcaster_id, stream_id)

        if event is None:
            await ctx.send(f"The raid boss's stream limit was reached. Raiders received a reduced {failed_reward:,}-point pool based on contribution.")
            return

        chatter = ctx.chatter
        result = await self.bot.services.raid_bosses.attack(broadcaster_id, stream_id, str(chatter.id), chatter.name, config)

        if result.error:
            await ctx.reply(result.error)
            return

        bonuses = []

        if result.weapon:
            bonuses.append(result.weapon)

        if result.potion_used:
            bonuses.append("power potion")

        if result.critical_hit:
            bonuses.append("critical hit")

        if result.broken_weapon:
            bonuses.append(f"broken {result.broken_weapon}; base damage only")

        bonus_text = f" using {' + '.join(bonuses)}" if bonuses else ""

        if result.defeated:
            drop_text = " Loot: " + ", ".join(f"{username} found {item_id.replace('_', ' ')}" for username, item_id in result.drops) + "!" if result.drops else ""
            await ctx.send(f"@{chatter.name} dealt the final {result.damage:,} damage{bonus_text} and defeated {result.boss_name}! The {result.reward:,}-point reward pool has been distributed by contribution!{drop_text}")
            return

        await ctx.send(f"@{chatter.name} dealt {result.damage:,} damage to {result.boss_name}{bonus_text}! {result.current_hp:,} HP remains.")

    @raid.command(name="shop")
    async def shop(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        config = context[1]
        await ctx.send(f"Raid shop: sword (melee), bow (ranged), or spellbook (magic) — {config.weapon_cost:,} points each with +{config.weapon_attack} attack and {config.weapon_durability} durability. Matching weapons double their attack stat. Power potion — {config.potion_cost:,} points for {config.potion_attacks} attacks at {config.potion_multiplier:g}x damage. Full repair — {config.repair_cost:,} points. Use !raid buy <item> or !raid repair <weapon>.")

    @raid.command(name="buy")
    async def buy(self, ctx: commands.Context, item: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        if not item:
            await ctx.reply("Use !raid shop to see items, then !raid buy <item>.")
            return

        chatter = ctx.chatter
        result = await self.bot.services.raid_bosses.buy(context[0], str(chatter.id), chatter.name, item, context[1])

        if result is None:
            await ctx.reply("That item is not in the raid shop. Use !raid shop to see the available items.")
        elif result == "insufficient":
            await ctx.reply("You do not have enough loyalty points for that item.")
        elif result == "owned":
            await ctx.reply("You already own that weapon. Use !raid equip to select it.")
        else:
            await ctx.reply(f"You purchased {item.lower()}! Use !raid equip {item.lower()} if it is a weapon.")

    @raid.command(name="equip")
    async def equip(self, ctx: commands.Context, weapon: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        if not weapon:
            await ctx.reply("Use !raid equip sword, !raid equip bow, or !raid equip spellbook.")
            return

        chatter = ctx.chatter
        equipped = await self.bot.services.raid_bosses.equip(context[0], str(chatter.id), chatter.name, weapon)

        if not equipped:
            await ctx.reply("You do not own that weapon. Use !raid shop to see the available equipment.")
            return

        await ctx.reply(f"You equipped your {weapon.lower()}.")

    @raid.command(name="inventory")
    async def inventory(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        chatter = ctx.chatter
        weapons, equipped, durability, potion_attacks = await self.bot.services.raid_bosses.get_inventory(context[0], str(chatter.id))
        weapon_text = ", ".join(weapons) if weapons else "none"
        durability_text = f"{durability}/{context[1].weapon_durability}" if equipped else "none"
        await ctx.reply(f"Weapons: {weapon_text}. Equipped: {equipped or 'none'}. Durability: {durability_text}. Power-potion attacks: {potion_attacks}.")

    @raid.command(name="repair")
    async def repair(self, ctx: commands.Context, weapon: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        if not weapon:
            await ctx.reply("Use !raid repair sword, !raid repair bow, or !raid repair spellbook.")
            return

        chatter = ctx.chatter
        result = await self.bot.services.raid_bosses.repair(context[0], str(chatter.id), weapon, context[1])

        if result == "invalid":
            await ctx.reply("That is not a repairable raid weapon.")
        elif result == "not_owned":
            await ctx.reply("You do not own that weapon.")
        elif result == "full":
            await ctx.reply("That weapon already has full durability.")
        elif result == "insufficient":
            await ctx.reply("You do not have enough loyalty points for that repair.")
        else:
            await ctx.reply(f"Your {weapon.lower()} was repaired to {context[1].weapon_durability} durability for {context[1].repair_cost:,} points.")

    @raid.command(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        entries = await self.bot.services.raid_bosses.get_leaderboard(context[0])

        if not entries:
            await ctx.send("No one has damaged the current raid boss yet.")
            return

        leaderboard = " | ".join(f"{position}. {username}: {damage:,}" for position, (username, damage) in enumerate(entries, start=1))
        await ctx.send(f"Top raiders: {leaderboard}")

    @raid.command(name="spawn")
    async def spawn_boss(self, ctx: commands.Context, boss_tier: str | None = None, boss_type: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None or not can_manage_raid(ctx):
            return

        if boss_tier not in {"mini", "main"} or boss_type not in {"melee", "ranged", "magic", "random"}:
            await ctx.reply("Use !raid spawn <mini|main> <melee|ranged|magic|random>.")
            return

        if boss_type == "random":
            boss_type = random.choice(("melee", "ranged", "magic"))

        event = await self.bot.services.raid_bosses.spawn(context[0], boss_type, context[1], boss_tier)

        if event is None:
            await ctx.reply("A raid boss is already active.")
            return

        stream_id = await self.get_stream_id(context[0], context[1])

        if stream_id is not None:
            event, _ = await self.bot.services.raid_bosses.register_stream(context[0], stream_id)

        await ctx.send(f"{event.boss_name} [{event.boss_tier.title()} Boss / {event.boss_type.title()}] has appeared with {event.max_hp:,} HP for {event.stream_limit} streams! Everyone gets one !raid attack per stream.")

    @raid.command(name="nextstream")
    async def next_raid_stream(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None or not context[1].offline_testing_enabled or not can_manage_raid(ctx):
            return

        if await self.get_live_stream_id(context[0]) is not None:
            await ctx.reply("Offline raid-stream simulation is unavailable while the channel is live.")
            return

        event = await self.bot.services.raid_bosses.get_active_event(context[0])

        if event is None:
            await ctx.reply("There is no active raid boss. Use !raid spawn <mini|main> <type|random> first.")
            return

        stream_id = self.get_offline_stream_id(event.id, event.streams_used + 1)
        event, failed_reward = await self.bot.services.raid_bosses.register_stream(context[0], stream_id)

        if event is None:
            await ctx.send(f"The simulated stream limit was reached. Raiders received a reduced {failed_reward:,}-point pool based on contribution.")
            return

        await ctx.send(f"Offline raid testing advanced to simulated stream {event.streams_used}. Everyone can use !raid attack again.")

    @raid.command(name="end")
    async def end_boss(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None or not can_manage_raid(ctx):
            return

        event = await self.bot.services.raid_bosses.get_active_event(context[0])

        if event is None:
            await ctx.reply("There is no active raid boss to end.")
            return

        remaining_ratio = event.current_hp / event.max_hp
        reward = await self.bot.services.raid_bosses.resolve(context[0], defeated=False)
        fraction = "half" if remaining_ratio <= 0.25 else "one quarter of"
        await ctx.send(f"The subjugation of {event.boss_name} failed. Raiders earned {fraction} the reward pool ({reward:,} points) based on contribution.")

    async def get_stream_id(self, broadcaster_id: str, config: RaidBossConfig) -> str | None:
        stream_id = await self.get_live_stream_id(broadcaster_id)

        if stream_id is not None or not config.offline_testing_enabled:
            return stream_id

        event = await self.bot.services.raid_bosses.get_active_event(broadcaster_id)

        if event is None:
            return None

        return self.get_offline_stream_id(event.id, max(event.streams_used, 1))

    async def get_live_stream_id(self, broadcaster_id: str) -> str | None:
        active_session = self.bot.services.stream_logs.active_sessions.get(str(broadcaster_id))

        if active_session is not None:
            return str(active_session.stream_id)

        try:
            broadcaster = self.bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))
            stream = await broadcaster.fetch_stream() if broadcaster is not None else None
        except Exception:
            LOGGER.exception("[Raid Bosses] Failed to resolve the active stream for broadcaster %s.", broadcaster_id)
            return None

        stream_id = getattr(stream, "id", None) or getattr(stream, "stream_id", None)
        return str(stream_id) if stream_id is not None else None

    @staticmethod
    def get_offline_stream_id(event_id: int, stream_number: int) -> str:
        return f"offline-test:{event_id}:{stream_number}"

from urllib.parse import quote

from twitchio.ext import commands

from bot.profiles import FeatureName, GlobalCommandName
from bot.shared.commands.helpers import get_context_broadcaster_id, is_feature_enabled, is_global_command_enabled
from config.settings import settings


def rarity_label(rarity: str) -> str:
    return "UR" if rarity == "ultra_rare" else rarity.title()


class PetsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    def enabled(self, ctx) -> bool:
        return is_global_command_enabled(self.bot, ctx, GlobalCommandName.PETS)

    @commands.group(name="pets", invoke_fallback=True, case_insensitive=True)
    async def pets(self, ctx: commands.Context) -> None:
        if not self.enabled(ctx):
            return
        service = self.bot.services.pets
        pet = await service.get_equipped_pet(str(ctx.chatter.id))
        tickets = await service.ticket_count(str(ctx.chatter.id))
        identity = await self.bot.services.chatter_stats.resolve_identity(str(ctx.chatter.id))
        login = str(identity["login"]) if identity else str(ctx.chatter.name)
        url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chatters/{quote(login, safe='')}#pets"
        status = f"{pet.display_name} ({rarity_label(pet.rarity)}) equipped: {pet.passive_percent_label}% {pet.passive_description}." if pet else "No pet equipped."
        await ctx.reply(f"{status} Summon tickets: {tickets}. Buy: !pets buy ticket (50,000 points). Use: !pets summon. Collection: {url}")

    @pets.command(name="buy")
    async def buy(self, ctx: commands.Context, *, item: str = "") -> None:
        if not self.enabled(ctx):
            return
        if " ".join(item.casefold().split()) not in {"ticket", "summon", "summon ticket"}:
            await ctx.reply("Buy a summon ticket for 50,000 points: !pets buy ticket, !pets buy summon, or !pets buy summon ticket.")
            return
        if not is_feature_enabled(self.bot, ctx, FeatureName.POINTS):
            await ctx.reply("Loyalty points are disabled in this channel.")
            return
        try:
            balance = await self.bot.services.pets.buy_ticket(get_context_broadcaster_id(ctx), str(ctx.chatter.id))
        except ValueError as error:
            await ctx.reply(str(error))
            return
        await ctx.reply(f"Bought 1 summon ticket for 50,000 points. Balance: {balance:,}. Use !pets summon. Odds: 70% Common / 20% Rare / 10% UR.")

    @pets.command(name="summon")
    async def summon(self, ctx: commands.Context, *, item: str = "ticket") -> None:
        if not self.enabled(ctx):
            return
        if item.strip().casefold() != "ticket":
            await ctx.reply("Use !pets summon or !pets summon ticket.")
            return
        try:
            result = await self.bot.services.pets.summon(str(ctx.chatter.id), str(ctx.chatter.name))
        except ValueError as error:
            await ctx.reply(str(error))
            return
        status = f"Duplicate! {result.refund:,} points returned to the ticket's purchase channel." if result.duplicate else ("Equipped globally!" if result.equipped else f"Added to your collection. Equip with !pets equip {result.display_name}.")
        await ctx.reply(f"Summoned {result.display_name} ({rarity_label(result.rarity)}). {status}")

    @pets.command(name="equip")
    async def equip(self, ctx: commands.Context, *, name: str = "") -> None:
        if not self.enabled(ctx):
            return
        try:
            pet = await self.bot.services.pets.equip(str(ctx.chatter.id), name)
        except ValueError as error:
            await ctx.reply(str(error))
            return
        await ctx.reply(f"{pet.display_name} equipped across all channels: {pet.passive_percent_label}% {pet.passive_description}.")

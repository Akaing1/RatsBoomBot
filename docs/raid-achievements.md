# Raid achievements (9.6.0)

Global totals across channels, in the Raids category:

| Achievement | Bronze / Silver / Gold / Platinum |
| --- | --- |
| Damage Dealer | 10,000 / 100,000 / 1,000,000 / 10,000,000 credited raid damage |
| Weapons Master | 1 / 10 / 50 / 100 weapon purchases |
| Team Player | 1 / 10 / 50 / 100 global buff purchases |
| Well Stocked | 10 / 50 / 250 / 1,000 consumable purchases |

Damage uses the existing contribution view, including credited Flag Bearer damage. Migration 31 backfills saved damage with unknown historical unlock dates. New triggers monitor the underlying attack and bonus-contribution tables.

Purchase tracking begins at deployment. Basic and Overclocked weapon purchases count, including repeats. Blessing, Ancient Pact, and Flag Bearer count as buffs; potions, Second Wind, Berserk, Lucky Dice, and Fool's Card count as consumables. One purchase counts once even when it grants several charges. Drops, crafting, repairs, sales, and item use do not count. Inventory is not backfilled as purchase history.

The buy method now wraps balance, item/effect, purchase counter, and achievement unlock writes in one database transaction. Existing failure checks return without incrementing counters; errors roll back the entire purchase. XP and achievement rewards remain deferred.

UAT: inspect the Raids filter, historical damage tiers, purchase each category, reject an unaffordable purchase, and verify a repeat buff purchase does not advance progress. Lucky Break's description is now 'Earn gambling profit across all channels.' Its counting rules are unchanged.

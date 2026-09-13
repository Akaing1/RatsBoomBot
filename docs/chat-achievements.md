# Global chat achievements (9.5.0)

Point Collector: 10,000 / 100,000 / 500,000 / 1,000,000 recorded lifetime loyalty points earned.
Lucky Break: 5,000 / 50,000 / 250,000 / 1,000,000 gambling profit. Profit excludes returned stakes.
The House Always Wins: one permanent Platinum unlock at 500,000 cumulative gambling losses. Later wins do not reduce losses. The secret is excluded server-side from cards, progress, and available counts until unlocked. It appears on the public profile after unlocking.

All totals are summed by Twitch user ID across channels and labeled loyalty points. Spending does not reduce lifetime earned progress. Existing recorded earnings are backfilled with unknown unlock dates. This uses existing lifetime_points_earned semantics, including gambling profit where already recorded; balances are not used as a substitute for earnings.

Migration 30 creates per-viewer/channel gambling totals and atomic achievement triggers. Gambling and roulette share settle_wager; totals update only after the conditional balance debit succeeds, in the same transaction as settlement. Loss is max(bet - payout, 0). Individual gambling history starts at deployment: old channel loss totals cannot be attributed to viewers. No retroactive win/loss guesses are made.

XP, leveling, raid achievements, and economic rewards remain deferred. Unlocks remain silent.

UAT: check cross-channel sums, a successful win (profit only), a loss, rejected wagers, secret visibility below/exactly at 500,000, permanent unlock after later wins, and the Chat filter. Never test large wagers using production viewer balances.

# Command-roll and gambling-streak achievements (v11.1.0)

Migration 34 adds visible Nice Try achievements for confirmed missed `!kamikaze` attacks. Global misses add together across channels; channel misses are separate. Both use Bronze / Silver / Gold / Platinum at 1 / 10 / 50 / 100 misses. Global badges do not pay points; channel tiers use the normal 500 / 2,000 / 7,500 / 25,000 reward schedule.

Eight secret channel Platinum badges unlock for exact outcomes: `!stinky` at 0% or 100%, `!smart` at 0% or 100%, `!height` at exactly 1'0" or 8'0", and `!lucky` at 0% or 100%. Commands continue working normally on and off stream, but only each measured viewer's first result per command during a live stream is eligible for achievements. The person measured earns the badge, whether they issued the command or were named as the target. Each achievement awards 25,000 channel loyalty points once.

Two secret streak pairs (channel and global) unlock for 10 consecutive **settled `!gamble`** losses or 10 consecutive wins in a *single channel*. Roulette and invalid/insufficient bets do not change the streak. The global badge is badge-only and retains the originating channel's login; the channel badge pays a one-time 25,000 points. A different outcome resets the current streak; earned badges and rewards are never revoked. Each channel tracks its own streak across restarts.

All new counters start on deployment. Nothing is inferred from existing totals or retroactively rewarded. Unlocks and channel payouts share the same SQLite transaction as the event or settled bet, and both unlock and reward ledgers have unique keys.

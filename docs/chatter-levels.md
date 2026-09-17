# Global chatter levels — v11.5.0

Public chatter profiles display one global level across every connected RatsBoomBot community. The level is calculated from permanent achievement unlocks and contributed raid clears, so retries and service restarts cannot award duplicate XP.

Achievement tiers award 100 XP for Bronze, 250 XP for Silver, 500 XP for Gold, and 1,000 XP for Platinum. A viewer who contributed to a defeated encounter earns 25 XP for a tutorial, 50 XP for a mini boss, or 100 XP for a main boss. Raid rank and damage do not change the XP award.

Level `L` begins at `500 × (L − 1)²` total XP. Level 1 begins at 0 XP, Level 2 at 500 XP, Level 3 at 2,000 XP, and Level 4 at 4,500 XP. Existing recorded unlocks and defeated raid participation count immediately.

Twitch profile images are cached in `chatter_identities` for 24 hours. Public profile requests refresh stale images through Twitch and retain the cached image if that refresh fails.

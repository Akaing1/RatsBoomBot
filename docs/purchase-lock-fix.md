# Purchase transactions and Familiar Face (9.6.1)

Raid purchases now use BEGIN IMMEDIATE before reading balances or stock. This reserves the SQLite writer at transaction entry instead of attempting to upgrade a deferred read transaction after another connection has written. Errors and cancellations still roll back the transaction. Extended external write locks can still exhaust SQLite's configured timeout.

Familiar Face is one global card. Progress is the maximum daily check-in total in any single channel, not the sum. Existing per-channel unlock records remain as evidence; each tier is displayed once globally if earned anywhere. Historical unknown dates stay unknown. No migration or reset is needed.

Regression coverage includes simultaneous purchases sharing a balance and cross-channel Familiar Face totals that must not be summed.

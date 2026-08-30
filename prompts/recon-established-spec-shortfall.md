# Recon: why do Established/Speculative bucket targets undershoot so badly?

This is a **recon task, not a fix task** — the goal is a clear diagnosis
Luis can make a decision from, not a code change. Only touch code if you
find an unambiguous bug (see "If you find a real bug" at the bottom); if
it's ambiguous, report the ambiguity rather than guessing at a fix.

## Report your findings

When done, write your findings to
`./wrap-ups/recon-established-spec-shortfall-out.md`. Write it for
someone who wasn't watching you work (Cowork will read it cold in a
later session): state the conclusion first (which of the three
hypotheses below is actually happening, for each owner), then the
supporting numbers, then anything you weren't able to determine.

## Context

The investment-agent recently moved from a model where Equities/ETF/
Crypto/Commodities were % of "deployable" (post-cash) capital scaled down
by a hidden `investedScale` factor, to a cleaner model where Equities/
ETF/Crypto/Commodities/**Cash** are five direct peer percentages of total
portfolio value, summing to 100 (see `wrap-ups/allocation-admin-gap-fix-out.md`
for that change's history — commits `2a7c628`/`963869c`/`e184776`). That
fix cleanly resolved reconciliation for the ETF/Crypto/Commodities
buckets: their "(unallocated)" bucket-level ADD targets now match
`totalPortfolioValue × bucketPct` exactly.

Established and Speculative Equities did NOT get fixed by that change,
and the gap is large — not a rounding footnote:

**Andrea Morales** (target model: Equities 45%, ETF 30%, Crypto 10%,
Commodities 10%, Cash 5%; est/spec split 50/50; total portfolio $31,454):
- Established+Speculative combined bucket target: 45% × 0.5 split × 2 =
  22.5% each × $31,454 = **$7,077 + $7,077 = $14,154**.
- Actual individual moves shown in Recommended Moves (Established:
  AMD $947, NVDA $947, AMZN $947, QS $632, ORCL $1,321 [new], GOOGL $1,321
  [new]; Speculative: SPWR $439, AMPX $1,010, EOSE $1,010) sum to
  **$8,574** — a **$5,580 (39%) shortfall**.

**Eduardo Morales** (target model: Equities 55%, ETF 25%, Crypto 10%,
Commodities 5%, Cash 5%; est/spec split 50/50; total portfolio $32,126):
- Established+Speculative combined bucket target: 55% × 0.5 split × 2 =
  27.5% each × $32,126 = **$8,835 + $8,835 = $17,670**.
- Actual individual moves (Established: NVDA $1,205, ORCL $1,205,
  AMZN $1,205, GOOGL $2,666 [new], NFLX $1,767 [new]; Speculative:
  SPWR $388, EOSE $1,263, AMPX $1,263, ENVX $1,263 — excluding QQQ/TMFC,
  which are ETF-bucket tickers just tagged with an EST/SPEC *tier* label,
  not equity) sum to **$12,225** — a **$5,445 (31%) shortfall**.

Two different owners, two different target models, both showing a
~30-40% shortfall specifically in Established+Speculative, right after
the buckets that don't have this problem got fixed. This needs a real
diagnosis, not another guess from screenshots.

## Three hypotheses — figure out which one is actually true, for each owner

1. **Genuine scarcity** — not enough tickers in Radar/watchlist clear the
   conviction bar to fill the established/speculative headcount
   (`targetEstIndividual`/`targetSpecIndividual`, derived from
   `maxPositions × estSpecRatio` in `server/routes/moves.js`). If this is
   it, you'd expect fewer held+new-open names than the target headcount
   (i.e. actual slot count < target slot count).

2. **Enough names, but each one's individual cap is set low by
   conviction** — every slot is filled, but each ticker's effective
   `hardCapPct` (`Math.min(ticker.capPercent ?? 100, latestAnalysis?.capPercent ?? 100)`
   — see `generateMovesForTicker` in `server/routes/moves.js`) is small
   enough that even every name sitting exactly at its own cap still
   doesn't add up to the bucket target. This would NOT be a bug — it's
   the system correctly reflecting that current analyst conviction
   doesn't support more established/speculative exposure. The right fix
   in this case is a UI one: surface the unused pool explicitly (e.g. an
   "Established (unallocated) — insufficient conviction headroom" line,
   mirroring the ETF/Crypto/Commodities "(unallocated)" bucket-level ADD
   rows), not to force more money into already-capped names.

3. **A real bug** — there IS enough cap headroom (some or all held/new
   names are sized below their own effective `hardCapPct`, not sitting
   at it), but the redistribution math in `computeIndividualModelWeights`
   (and/or `splitBucketTarget` for the fixed-target buckets — check
   whether Eduardo's ETF bucket has the same issue: his ETF target is
   $8,032 [25% × $32,126] but QQQ+TMFC together are only $6,426, with NO
   "ETF (unallocated)" row generated to cover that $1,606 gap, which
   smells like the same bug pattern) simply isn't claiming the available
   room. This traces back to the `denom`/`fairShareSum` fix from
   2026-08-08 (search git log / `small_account_diversification.md` in
   memory if available, or just read the current `allocate()` function
   inside `computeIndividualModelWeights`) — that fix may not fully
   redistribute a clipped ticker's unused pool to the *other* unclipped
   tickers in the same group, or the `remainingEstPoolPct`/
   `remainingSpecPoolPct` formula for new-open sizing may not account for
   headroom freed by capping.

## What to actually check, for Andrea and Eduardo both

1. Confirm total held+new-open headcount per bucket vs. the computed
   `targetEstIndividual`/`targetSpecIndividual` — rules hypothesis 1 in
   or out directly.

2. For every Established and Speculative ticker (held AND any eligible-
   but-unused watchlist candidates), get:
   - `ticker.capPercent` (static Type A/B or configured cap)
   - `latestAnalysis.capPercent` (analyst's most recent recommended cap)
   - the effective `hardCapPct = Math.min(...)` of those two
   - the ACTUAL target weight the engine assigned it (`modelWeightPct` /
     the dollar target shown in Recommended Moves)

   You can get this either by adding temporary logging to
   `computeMovesPayload`/`generateMovesForTicker` and hitting
   `GET /api/moves/:owner` locally against production data, or by
   querying Postgres directly for `Ticker.capPercent` and the latest
   `Analysis.capPercent` per ticker per owner:

   ```bash
   DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-) node -e "
   const { PrismaClient } = require('./server/node_modules/@prisma/client');
   const prisma = new PrismaClient();
   (async () => {
     const owners = ['andrea', 'eduardo']; // adjust to actual owner keys — check via prisma.ownerProfile.findMany() if unsure
     for (const owner of owners) {
       const accounts = await prisma.account.findMany({
         where: { owner },
         include: { positions: { where: { status: 'active' }, include: { ticker: true } } },
       });
       const tickerIds = [...new Set(accounts.flatMap(a => a.positions.map(p => p.tickerId)))];
       for (const tid of tickerIds) {
         const ticker = await prisma.ticker.findUnique({ where: { id: tid } });
         const analysis = await prisma.analysis.findFirst({
           where: { transcript: { tickerId: tid } },
           orderBy: { transcript: { callDate: 'desc' } },
         });
         console.log(owner, ticker.symbol, {
           tickerCapPercent: ticker.capPercent,
           analystCapPercent: analysis?.capPercent ?? null,
           thesisHealth: analysis?.thesisHealth ?? null,
         });
       }
     }
     await prisma.\$disconnect();
   })();
   "
   ```

   (Adjust owner keys / add owner-level cap overrides from
   `OwnerTickerConfig` too if that table has entries for these tickers —
   check `server/routes/moves.js`'s `effectiveCap()` / `ownerCapMap` for
   how those layer on top of `ticker.capPercent`.)

3. Compare: is each ticker's ACTUAL assigned target roughly equal to its
   effective `hardCapPct` (→ hypothesis 2, working as intended) or
   meaningfully below it (→ hypothesis 3, real bug — room is being left
   unused)?

4. Sum each bucket's total available headroom (`Σ min(hardCapPct) × totalPV`
   across all held + eligible-but-unused candidates) and compare to the
   bucket target. If total headroom itself is below the bucket target,
   that's hypothesis 2 (or a genuine mix of 1+2) and no code change is
   warranted — only a UI change to surface the gap honestly. If total
   headroom clears the bucket target but the actual sum assigned doesn't,
   that confirms hypothesis 3.

## If you find a real bug (hypothesis 3)

Only then, fix `computeIndividualModelWeights` (and/or `splitBucketTarget`
+ the fixed-bucket "(unallocated)" shortfall check in
`server/routes/moves.js`) to properly water-fill: clip each ticker at its
effective cap, redistribute the unused remainder across not-yet-clipped
tickers in the same group (iterating until stable), and feed any
still-unused remainder into new-open sizing (`sizeSide`) rather than a
fixed slot-count formula. Verify against Andrea's and Eduardo's real
numbers that individual targets now sum to the bucket total (up to
whatever's genuinely capped-out, per hypothesis 2's honest-shortfall
case).

If you make this change, commit and push it yourself — you have real
local git access and Luis doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "<describe the fix — e.g. water-fill cap-clipped headroom across established/speculative and fixed-target buckets>"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## If it's hypothesis 1 or 2 (no bug)

Don't change the allocation math. Report the honest conclusion — e.g.
"Established headroom across all qualifying names is $X, bucket target
is $Y, the $(Y-X) gap is a legitimate conviction ceiling, not a bug" —
and note it as a candidate follow-up for a UI change (surfacing an
"(unallocated) — insufficient conviction headroom" line) rather than
building anything yourself. Leave that decision to Luis and Cowork.

---

## Reminder: write your wrap-up before you finish

Whatever you find — hypothesis 1, 2, or 3, for either owner — write it
up in `./wrap-ups/recon-established-spec-shortfall-out.md` per the
instructions at the top of this file. Don't end the session without
that file existing; it's how this gets read back into a later Cowork
session.

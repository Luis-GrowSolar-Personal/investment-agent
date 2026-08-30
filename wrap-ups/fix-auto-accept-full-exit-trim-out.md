# Fix: auto-accept a trim when the Schwab target is exactly zero (full exit)

**The fix:** `server/lib/schwabSync.js` now auto-closes every open lot for
a position when Schwab no longer reports that symbol at all (a full
exit) — no more manual "Accept trim → pick lot(s)" click for a case
that never had any real ambiguity (all lots close, always). It first
tries to find the actual Schwab **CLOSING** transaction(s) for that
symbol in the 60-day transaction history (mirroring the buy-side
multi-fill fix, but for `positionEffect === 'CLOSING'` legs) to record
a real sale price/date; if no closing transaction matches, it still
auto-closes (there's no ambiguity about *which* lots close, regardless)
but says so honestly in the lot's `notes`. **Partial trims are
completely untouched** — still go to `positionDiffs` for manual
lot-picker resolution, exactly as before.

## Premise correction — flagging before the "what changed" section

The prompt described this as a change to "`syncAccount()`'s
trim-detection branch... same area involved in the recent multi-fill
fix," implying the fix belongs in the main per-position loop's existing
`// Trim detected — always requires lot-picker` branch
(`schwabSync.js`, now ~line 435). **That's not where a real full exit
ever reaches.** Reading the actual code:

- Line 364: `if (schwabShares <= 0) continue;` — the main loop skips
  a `schwabPos` entry entirely once its Schwab-reported quantity is
  ≤ 0, **before** it ever reaches the trim-detection branch. So that
  branch is only reachable for **partial** trims (`schwabShares > 0`
  but less than local).
- The code's own comment at the second loop (now ~line 543, unchanged
  by this fix) confirms why: *"Schwab drops a position from
  `/accounts?fields=positions` once shares reach zero, so these never
  appear in the loop above."* A true full exit (Andrea's SPWR example:
  `Schwab 0 vs local 1347`) is Schwab **omitting** the symbol from its
  positions response entirely — it's caught by the **separate second
  loop** (`for (const localPos of localPositions)` after the main
  loop), which detects local positions Schwab no longer mentions at
  all.

So the fix was implemented in that **second loop**, not the main
loop's trim branch the prompt pointed at. This is exactly the kind of
premise the standing workflow asks me to verify before implementing —
flagging it here rather than silently "fixing" the wrong branch (which
would have compiled and looked plausible, but would never actually
fire for a real full exit, since `schwabShares <= 0` positions never
reach it).

## What changed — before / after

**`ensureRecentTrades()`** (was: OPENING-legs-only lookup; now: both
OPENING and CLOSING). Refactored its single `Map` return into
`{ opening: Map, closing: Map }`, built in the same single pass over
the transaction feed (no extra Schwab API calls):

```js
// before
if (item.positionEffect !== 'OPENING') continue;
...
recentTrades = new Map();
// after
const map = item.positionEffect === 'OPENING' ? opening
  : item.positionEffect === 'CLOSING' ? closing
  : null;
if (!map) continue;
...
recentTrades = { opening, closing };
```

The one existing call site (buy-side multi-fill matching) was updated
from `trades.get(symbol)` to `trades.opening.get(symbol)` — no other
behavior change there.

**Second loop** (`schwabSync.js`, "Detect local positions that Schwab
no longer reports at all" — full exits):

Before: always pushed to `positionDiffs` for manual resolution —

```js
result.positionDiffs.push({
  symbol: localPos.symbol, schwabShares: 0, localShares: localPos.totalShares,
  status: 'mismatch', diffDirection: 'trim', positionAvgPrice: null,
});
```

After: fetches the position's open `Lot` rows, tries to match the
total shares against summed Schwab CLOSING legs in the 60-day window,
and closes every open lot in one transaction:

```js
const openLots = await prisma.lot.findMany({
  where: { positionId: localPos.positionId, closedDate: null },
});
const trades = await ensureRecentTrades();
const closingLegs = (trades.closing.get(localPos.symbol) ?? []).filter(t => t.price != null);
const closingSum = closingLegs.reduce((sum, t) => sum + t.shares, 0);
const matched = closingLegs.length > 0 && Math.abs(closingSum - localPos.totalShares) / localPos.totalShares < 0.0001;
const closingDate = matched ? new Date(closingLegs[0].tradeDate) : new Date();
const noteSuffix = matched
  ? `Closed ${closingDate.toISOString().slice(0, 10)} — full exit auto-accepted (Schwab reports 0 shares). Matched Schwab closing transaction history: ${closingSum.toFixed(6)} shares across ${closingLegs.length} fill(s) @ ~$${(closingLegs.reduce((s, t) => s + t.shares * t.price, 0) / closingSum).toFixed(4)} avg.`
  : `Closed ${closingDate.toISOString().slice(0, 10)} — full exit auto-accepted (Schwab reports 0 shares). No matching closing transaction found in the last 60 days; closing date is a placeholder (today). Verify actual sale date/price in Schwab's transaction history for accurate LTCG/STCG treatment.`;

await prisma.$transaction(
  openLots.map(lot => prisma.lot.update({
    where: { id: lot.id },
    data: { closedDate: closingDate, notes: (lot.notes ? lot.notes + ' ' : '') + noteSuffix },
  }))
);
result.autoClosedFullExits.push({ symbol: localPos.symbol, lotsClosed: openLots.length, shares: localPos.totalShares, matched });
```

Also added `autoClosedFullExits: []` to the `result` object
initialization (alongside the existing `autoResolvedAdds`), so callers
can surface what was auto-closed in this sync.

## Does `Lot.closedDate` alone suffice, or is a sale price/date field needed elsewhere?

Checked before assuming, per the prompt's instruction:

- `Lot` schema (`server/prisma/schema.prisma:327-338`) has no
  `salePrice`/`proceeds` field — only `closedDate` and free-text
  `notes`.
- Grepped every `closedDate` usage across `server/` and `client/src/`
  (moves.js, dashboard.js, portfolio.js, users.js,
  ownerTickerConfig.js, Portfolio.jsx) — every single one filters
  `.filter(l => !l.closedDate)` to get **open** lots for allocation/
  moves/dashboard math. **Nothing in the app reads a sale price or
  computes realized gain/loss from `Lot` data at all** — grepped for
  `realized`/`salePrice`/`proceeds` and found no such calculation
  anywhere in the codebase.
- The existing manual `acceptTrim()` function
  (`schwabSync.js`, ~line 735) — the human-driven equivalent of what
  this fix now automates for the unambiguous zero-share case — already
  follows exactly this pattern: it sets `closedDate` and appends a
  human-readable summary of what happened to `notes`, with **no**
  separate price field. This fix's new code mirrors that same
  established pattern exactly, rather than inventing a new mechanism.

**Conclusion: `closedDate` + an honest `notes` string is sufficient**
and consistent with how the rest of the app already treats closed
lots — no schema change needed, and none was made.

## Verify

**1–2. Live full-exit case check (read-only) — none currently exists.**
A temporary, throwaway read-only script
(`server/scripts/_recon_full_exits.js`) queried every Schwab-linked
account for positions with manual/import lots that Schwab no longer
reports — the exact shape of a full exit awaiting resolution. **No
matches were found** (the SPWR case Luis mentioned as the motivating
example has evidently already been accepted, consistent with the
prompt's own caveat: *"If SPWR's already been manually accepted... note
that live verification wasn't possible and rely on the dry-run/
unit-level check below instead."*). Per that fallback, verification
was done at the unit level instead (see below). The script was deleted
immediately after confirming no live case exists — nothing left in the
repo.

**Unit-level dry run** (`server/scripts/_dryrun_full_exit_logic.js`,
also deleted after use) — re-implemented the exact matching computation
added to `schwabSync.js` against synthetic transaction data, covering
every branch:

```
--- Case 1: SPWR-style full exit, single clean closing leg matches exactly ---
{ matched: true, closingDate: 2026-08-20, noteSuffix: 'Closed 2026-08-20 — full exit
  auto-accepted (Schwab reports 0 shares). Matched Schwab closing transaction history:
  1347.000000 shares across 1 fill(s) @ ~$2.1500 avg.' }

--- Case 2: full exit split into multiple closing fills, summing exactly ---
{ matched: true, closingDate: 2026-08-20, noteSuffix: '... Matched Schwab closing
  transaction history: 1347.000000 shares across 2 fill(s) @ ~$2.1474 avg.' }

--- Case 3: no closing transaction in 60-day window (predates it) ---
{ matched: false, closingDate: 2026-08-22 (today, placeholder), noteSuffix: '...
  No matching closing transaction found in the last 60 days; closing date is a
  placeholder (today). Verify actual sale date/price ...' }

--- Case 4: closing legs present but don't sum to the local total (ambiguous/unrelated) ---
{ matched: false, ...same placeholder note... }

--- Case 5: closing leg has null price (missing data) — falls to placeholder ---
{ matched: false, ...same placeholder note... }
```

All five cases behave exactly as designed: real-data match → honest
"matched" note with actual price/date; anything else (no data,
mismatched sum, missing price) → still closes (no ambiguity about
which lots) but with an explicit placeholder note, never a fabricated
price.

**3. Partial trims unaffected — confirmed by re-reading the diff.**
`git diff server/lib/schwabSync.js` shows no changes anywhere near the
main loop's `// Trim detected — always requires lot-picker` branch
(~line 435) — grepped for `"Trim detected"` in the diff and got zero
matches. That branch, and the `diffDirection: 'trim'` push it makes to
`positionDiffs`, is byte-for-byte unchanged. Partial trims still
require the manual lot-picker exactly as before.

**4. `verify-allocation-math.sh`** — run for due diligence even though
no real sync occurred (this fix only touches Schwab sync/lot data, and
this task made no writes at all). Result: a handful of pre-existing
`[FAIL]` rows for Luis's and Eduardo's Established/Speculative Equities
buckets — **these are unrelated to this fix**: they exist independent
of any code change made in this task (no sync ran, no `Lot`/`Position`
row was touched by anything in this session), and none of the failing
buckets are downstream of the full-exit code path this fix touches
(that path only fires when `syncAccount()` runs a real sync against an
account with a genuine full-exit diff, which didn't happen here). Not
investigated further — out of scope for this task, flagging for Luis
rather than silently absorbing into this fix's report.

## Verification performed (mechanical)

- `node --check server/lib/schwabSync.js` — passes.
- Re-grepped after editing to confirm `trades.opening.get(symbol)`,
  `trades.closing.get(...)`, and `autoClosedFullExits` all landed as
  written.
- `git diff --stat server/lib/schwabSync.js` — 49 insertions, 20
  deletions, confined to `ensureRecentTrades()`, its one call site, the
  `result` object literal, and the second loop.
- Confirmed the two throwaway scripts were deleted before staging
  (`git status --short` shows neither).

## Deviations from the prompt

1. **Implemented in the second loop, not the main loop's trim branch**
   — see "Premise correction" above. This is a location correction,
   not a scope change: the behavior (auto-close on schwabShares===0)
   is exactly what was asked for; it just lives where full exits
   actually surface in the code.
2. **Live verification (step 1–2) wasn't possible** — no live
   full-exit case currently exists (SPWR already resolved). Used the
   prompt's own explicitly-sanctioned fallback: unit-level dry run
   against synthetic data mirroring the real computation.
3. `git status` showed an unrelated pre-existing modification to
   `client/src/pages/Portfolio.jsx` (not made by this task). Left
   untouched and not staged — only `server/lib/schwabSync.js` was
   committed.

## What was deliberately NOT done

- Did not run a real sync against any account — no `Lot`/`Position`/
  `Account` row was created, updated, or deleted by this task. Both
  throwaway verification scripts were read-only and were deleted
  after use.
- Did not add a `salePrice`/`proceeds` field to the `Lot` schema —
  confirmed unnecessary (see "Does `closedDate` alone suffice" above).
- Did not investigate the pre-existing `verify-allocation-math.sh`
  `[FAIL]` rows for Luis/Eduardo Established/Speculative Equities —
  unrelated to this fix, flagged for Luis to look at separately.
- Did not stage or touch the unrelated pre-existing
  `client/src/pages/Portfolio.jsx` change.

## Follow-up for Luis

1. Next time a position is fully exited on Schwab (or the next real
   sync after this deploy catches one already sitting in that state),
   it should auto-close without a manual click. Check the resulting
   `Lot.notes` to see whether it found the real closing transaction
   ("Matched Schwab closing transaction history...") or fell back to
   the placeholder ("No matching closing transaction found...") — the
   placeholder case means the sale date/price should be verified
   manually for accurate tax treatment.
2. To check the live state of any account for open full-exit
   candidates or, after a sync, what got auto-closed, read-only:
   ```bash
   cd server && export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) && node -e "
   const {PrismaClient}=require('@prisma/client');const p=new PrismaClient();
   (async()=>{
     const lots = await p.lot.findMany({ where: { notes: { contains: 'full exit auto-accepted' } }, include: { position: { include: { ticker: true } } } });
     console.log(lots.map(l => ({ symbol: l.position.ticker.symbol, shares: l.shares, closedDate: l.closedDate, notes: l.notes })));
     await p.\$disconnect();
   })();"
   ```
3. Separately: the pre-existing `verify-allocation-math.sh` failures
   for Luis's and Eduardo's Established/Speculative Equities buckets
   are unrelated to this fix and still open — worth a look when
   convenient.
4. Run `./server/scripts/verify-allocation-math.sh` again after the
   next real sync that exercises this new full-exit path, to confirm
   nothing regressed (expected: no change from this fix specifically,
   since it only touches Schwab sync/lot data, not the moves engine).

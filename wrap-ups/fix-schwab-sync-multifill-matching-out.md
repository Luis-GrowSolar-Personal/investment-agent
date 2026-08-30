# Fix 1 of 2: Schwab sync matcher now sums multiple same-symbol fills

**The fix:** `server/lib/schwabSync.js`, in the `hasManualOrImportLots`
add-diff branch (previously lines 393-408, now ~393-434), when no
single Schwab transaction leg matches the diff exactly, the matcher now
also sums **all** same-symbol OPENING legs already fetched by
`ensureRecentTrades()` in the 60-day window and checks whether that sum
closes the diff (same `0.0001` relative tolerance as the existing
single-leg check). If it does, it creates **one `Lot` row per leg**
(never merged/averaged — each fill keeps its own real price and trade
date, which matters for LTCG/STCG holding period and cost-basis
accuracy). If the sum doesn't close the diff either, behavior is
unchanged: falls through to `positionDiffs` for manual entry, same as
before.

Confirmed against Andrea Morales's real, currently-broken BTC/SIVR case
via a read-only dry run (no sync run, no writes — see verification
section) that the new logic produces exactly the right result: 2 lots
each, summing to 71.9957 (BTC) and 9.876 (SIVR) — precisely the diffs
identified in the prior recon.

## What changed — before / after

**Before** (`server/lib/schwabSync.js:392-408`, single-leg-only):

```js
} else {
  // No single trade in the last 60 days matches the diff exactly. This
  // could mean the purchase predates the 60-day window, OR — just as
  // likely — the diff is the sum of several separate lots (DRIP
  // reinvestments, multiple buys) rather than one trade. We can't tell
  // which from here; surface for manual entry and let the user consult
  // Schwab's own lot detail to enter each real lot.
  result.positionDiffs.push({
    symbol, schwabShares, localShares: localPos.totalShares,
    status: 'mismatch', diffDirection: 'add',
    positionAvgPrice: schwabPos.averagePrice ?? null,
  });
}
```

**After** (same location, now ~393-434):

```js
} else {
  // ...commonly happens when a broker splits one logical buy into
  // multiple fills... Try summing ALL same-symbol OPENING legs...
  const pricedCandidates = candidates.filter(t => t.price != null);
  const legSum = pricedCandidates.reduce((sum, t) => sum + t.shares, 0);
  if (pricedCandidates.length > 1 && Math.abs(legSum - diff) / diff < 0.0001) {
    for (let i = 0; i < pricedCandidates.length; i++) {
      const leg = pricedCandidates[i];
      await prisma.lot.create({
        data: {
          positionId: localPos.positionId,
          shares: leg.shares,
          costBasis: leg.price,
          acquiredDate: new Date(leg.tradeDate),
          source: 'schwab',
          notes: `Auto-resolved from Schwab transaction history (${i + 1} of ${pricedCandidates.length} fills): ${leg.shares.toFixed(6)} shares @ $${leg.price} on ${leg.tradeDate}.`,
        },
      });
      result.autoResolvedAdds.push({ symbol, shares: +leg.shares.toFixed(6), price: leg.price, tradeDate: leg.tradeDate });
    }
  } else {
    // Could mean the purchase predates the window, OR the candidate
    // legs are a mix of unrelated fills we can't safely attribute —
    // don't guess which legs belong together. Surface for manual entry.
    result.positionDiffs.push({
      symbol, schwabShares, localShares: localPos.totalShares,
      status: 'mismatch', diffDirection: 'add',
      positionAvgPrice: schwabPos.averagePrice ?? null,
    });
  }
}
```

Design notes, per the prompt's spec:

- **Cheapest check kept first.** The existing single-leg `candidates.find(...)`
  match (line ~380) is untouched and still runs first — zero behavior
  change for the common case where one trade already matches exactly.
- **Simple sum, not subset-sum.** Sums ALL same-symbol OPENING legs in
  the 60-day window rather than searching combinations. If that
  doesn't close the diff (e.g. some legs belong to an earlier,
  already-resolved diff), it deliberately does **not** attempt
  combinatorial matching — falls through to the existing manual-entry
  path, same as before. This is a known limitation, not a bug: a
  position with two *unrelated* multi-leg diffs open at once (rare,
  but possible for an active lower-liquidity ticker) would still need
  manual entry. Flagging this rather than over-building, per the
  prompt's instruction.
- **`pricedCandidates.length > 1` guard.** If there's only one
  candidate leg, the single-leg check above would already have
  matched it (or it wouldn't equal the diff at all) — so requiring
  `> 1` here just avoids a redundant/no-op path, not a behavior gap.
- **Per-leg price filter.** Legs with a null `price` are excluded from
  the sum (`pricedCandidates`) since a lot needs a real cost basis —
  if a required leg lacks a price, the sum won't include it, `legSum`
  won't match, and the diff correctly falls through to manual entry
  rather than creating a lot with a fabricated price.
- **Notes are honest about what happened**: each created lot says
  `"...(N of M fills): X shares @ $Y on <date>."` — distinct from the
  single-leg `"Auto-resolved from Schwab transaction history: ..."` and
  from the lenient branch's `"Estimated from Schwab sync — ..."` (that
  branch, Fix 2, is untouched by this change).

## Idempotency

Checked whether the existing single-leg path (`autoResolvedAdds`) has
any explicit duplicate guard (e.g. checking for an existing matching
`Lot` before creating one) — it does **not**. Instead it relies on an
implicit guard: `loadLocalPositions()` re-reads live `Lot` rows from
the database at the start of every sync, so once a lot is created for
the matched shares, `localPos.totalShares` on the *next* sync already
includes it, `diff` recomputes to ~0 (well under the `0.0001` absolute
threshold at line 374), and the `if (Math.abs(diff) > 0.0001)` guard
skips the branch entirely — no re-match, no re-create.

This same mechanism protects the new multi-leg path with no extra code
needed: once all N leg-lots are created, the position's `totalShares`
sums to the full Schwab total, so the diff is zero on the next sync and
the branch is skipped. Confirmed this is sufficient rather than adding
a redundant guard, consistent with the prompt's "if the single-leg path
doesn't guard against this either... confirm that and explain why it's
sufficient" instruction.

## Verify — read-only dry run (no real sync, no writes)

Per the constraints, a temporary throwaway script
(`server/scripts/_dryrun_multifill.js`) was written to test the new
logic against Andrea's real Custodial account (id 7) data:
read-only `getTransactions()` call (same one `debug_transactions.js`
uses) for the 60-day transaction feed, plus read-only Prisma
`findMany`/`findUnique` for the current `Lot` rows. **`prisma.lot.create`
was never called** — the script only logged what would be created. The
script was deleted immediately after capturing this output; nothing
was left in the repo.

Dry-run output:

```
Account: Andrea Custodial (id=7)

=== BTC ===
local shares (current Lot rows, read-only): 38
local lots: [ '4sh @ $44.16 (manual)', '34sh @ $37.55 (manual)' ]
candidate OPENING legs in 60-day window: [
  { tradeDate: '2026-08-17T16:52:46+0000', shares: 0.9957, price: 28.335 },
  { tradeDate: '2026-08-17T16:52:46+0000', shares: 71, price: 28.335 }
]
no single-leg match. Sum of 2 priced candidate legs: 71.9957
diff to close: 71.9957, |sum - diff| / diff = 0
MULTI-LEG SUM MATCH — would create 2 lots (prisma.lot.create NOT called, dry run only):
  [would create] shares=0.9957 costBasis=28.335 acquiredDate=2026-08-17T16:52:46+0000 source=schwab
    notes="Auto-resolved from Schwab transaction history (1 of 2 fills): 0.995700 shares @ $28.335 on 2026-08-17T16:52:46+0000."
  [would create] shares=71 costBasis=28.335 acquiredDate=2026-08-17T16:52:46+0000 source=schwab
    notes="Auto-resolved from Schwab transaction history (2 of 2 fills): 71.000000 shares @ $28.335 on 2026-08-17T16:52:46+0000."
  sum of would-create lots: 71.9957 (target diff: 71.9957)

=== SIVR ===
local shares (current Lot rows, read-only): 12
local lots: [ '12sh @ $72.6703 (import)' ]
candidate OPENING legs in 60-day window: [
  { tradeDate: '2026-08-17T04:00:00+0000', shares: 0.876, price: 63.0555 },
  { tradeDate: '2026-08-17T04:00:00+0000', shares: 9, price: 63.0555 }
]
no single-leg match. Sum of 2 priced candidate legs: 9.876
diff to close: 9.876, |sum - diff| / diff = 0
MULTI-LEG SUM MATCH — would create 2 lots (prisma.lot.create NOT called, dry run only):
  [would create] shares=0.876 costBasis=63.0555 acquiredDate=2026-08-17T04:00:00+0000 source=schwab
    notes="Auto-resolved from Schwab transaction history (1 of 2 fills): 0.876000 shares @ $63.0555 on 2026-08-17T04:00:00+0000."
  [would create] shares=9 costBasis=63.0555 acquiredDate=2026-08-17T04:00:00+0000 source=schwab
    notes="Auto-resolved from Schwab transaction history (2 of 2 fills): 9.000000 shares @ $63.0555 on 2026-08-17T04:00:00+0000."
  sum of would-create lots: 9.876 (target diff: 9.876)
```

Both cases: the sum of the fills exactly closes the diff Luis
identified in the recon (71.9957 for BTC, 9.876 for SIVR), and the
per-leg data (real price, real trade date) is what would be written —
confirming the fix resolves the actual, currently-stuck diffs, not a
synthetic example.

**Confirmed unaffected, by re-reading the diff:**
- The single-leg exact-match path (lines ~377-392) is untouched —
  still runs first, still the cheapest/most common case.
- The trim branch (`diffDirection: 'trim'`, ~line 425 area) is
  untouched — still always requires the lot-picker.
- The lenient "only `schwab`-sourced lots" full-replace branch
  (`updatedSchwabLots`, further down in the loop) is untouched — that's
  Fix 2's territory (the "estimated from averagePrice" cost-basis
  accuracy gap), not touched here.

## Verification performed

- `node --check server/lib/schwabSync.js` — passes.
- Dry run against Andrea's real transaction feed and `Lot` rows (above)
  — confirms exact match for both BTC and SIVR.
- `git diff --stat server/lib/schwabSync.js` — confirms only the
  intended block changed (38 insertions, 13 deletions, single
  contiguous hunk).
- Re-grepped after edit to confirm the new `pricedCandidates` /
  `legSum` logic landed in the file as written.

## Deviations from the prompt

None. The premise (root cause, line numbers ~372-408) matched the
current source exactly — no adaptation needed. Followed the "simple
sum, don't over-build subset-sum matching" instruction literally.

## What was deliberately NOT done

- **No real sync was run.** `syncAccount()` was never invoked in this
  task. Andrea's account was not touched — the BTC/SIVR mismatch
  Luis is preserving as evidence remains exactly as it was.
- **No `Lot`/`Position`/`Account` row was created, updated, or
  deleted** — the dry-run script only logged what *would* be created;
  `prisma.lot.create` was never called during this task.
- The throwaway dry-run script (`server/scripts/_dryrun_multifill.js`)
  was deleted after capturing the output above — nothing left in the
  repo.
- Fix 2 (the lenient branch's `averagePrice`-estimated cost basis for
  schwab-only-lot positions) is explicitly out of scope for this task
  and was not touched.
- The known limitation (no subset-sum search when simple full-sum
  doesn't match, e.g. overlapping unrelated diffs) was not built out —
  flagged above per the prompt's instruction to note it rather than
  over-build.

## Commit / push

```
git add -A
git commit -m "Fix Schwab sync matcher to sum multiple same-symbol fills instead of only checking single legs"
git push origin dev
```

Result: staged only `server/lib/schwabSync.js` (the throwaway dry-run
script was deleted before staging, so it was never part of the
commit). Commit created and pushed to `origin/dev` successfully — no
rebase/conflict needed.

## Follow-up for Luis

- When ready, trigger the real sync against Andrea's Custodial account
  (via the normal app flow / Force Sync) to actually create the BTC and
  SIVR lots. Expect: BTC gets 2 new `schwab` lots (0.9957 sh @ $28.335,
  71 sh @ $28.335); SIVR gets 2 new `schwab` lots (0.876 sh @ $63.0555,
  9 sh @ $63.0555) — both tagged with the "(N of M fills)" notes text
  above.
- After that sync, re-check the account summary line for BTC/SIVR —
  the "no matching transaction... enter manually" prompts should be
  gone and share counts should match Schwab exactly (109.9957 for BTC,
  21.876 for SIVR).
- Fix 2 (the averagePrice-estimated cost basis for MSFT/AMD/GOOGL/ORCL)
  is a separate, still-open task.

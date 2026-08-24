# Fix: ADD rows double-count trim proceeds within an account — wrap-up

Date: 2026-08-24 · Branch `dev` · Scope: `server/routes/moves.js` only

## Premise check — confirmed exactly as reported

`annotateAddFunding` built `trimProceedsByAccount` once per run, then for
**every** ADD row recomputed:

```js
const usable   = rows.reduce((s, r) => s + (trimProceedsByAccount.get(r.accountId) ?? 0), 0);
const expected = Math.min(uncovered, usable);
```

Nothing was ever decremented, so N rows routed to the same account each saw
that account's full proceeds. The prompt's numbers reproduce to the cent (see
before/after below). No adaptation needed — the deferred-gap framing from
`7a75576` and the now-decided order from `0021bcc` were both accurate.

## What changed

Two edits, both in `server/routes/moves.js`.

**1. `routeAddsInFundingOrder` (line ~355) — stamp the order.**
The already-sorted `adds` loop became `adds.forEach((m, i) => { m.fundingOrder = i; ... })`.
`annotateAddFunding` has no `tickerMeta`, so it can't re-derive the conviction
ranking; stamping the index avoids duplicating the ranking logic in a second
place (and avoids it drifting).

**2. `annotateAddFunding` (line ~410) — consume a real ledger.**

Before:
```js
for (const m of moves) {
  if (m.moveType !== 'ADD') continue;
  ...
  const usable   = rows.reduce((s, r) => s + (trimProceedsByAccount.get(r.accountId) ?? 0), 0);
  const expected = Math.min(uncovered, usable);
```

After:
```js
const adds = moves.filter(m => m.moveType === 'ADD')
                  .sort((a, b) => (a.fundingOrder ?? Infinity) - (b.fundingOrder ?? Infinity));
for (const m of adds) {
  ...
  let need = uncovered;
  for (const r of rows) {
    if (need <= 0) break;
    const left = trimProceedsByAccount.get(r.accountId) ?? 0;
    if (left <= 0) continue;
    const claim = Math.min(need, left);
    trimProceedsByAccount.set(r.accountId, left - claim);
    need -= claim;
  }
  const expected = uncovered - need;
```

`trimProceedsByAccount` is now a per-run, per-account **ledger** rather than a
lookup table — structurally parallel to `availableCash`/`commitCash` from
`844e3c7`, but tracking net proceeds (`dollarAmount - taxCost`) instead of a
cash balance. It stays a local, parameter-scoped Map for the same reason the
cash ledger does: `computeMovesPayload` awaits mid-run, so module state would
interleave across concurrent requests.

Unclaimed remainder lands in `unbacked` — the existing category and existing
client wording (`PortfolioManager.jsx:238-240`). **No client change was needed
or made**; the fix surfaces through the copy that was already there.

Also updated the doc comment above `annotateAddFunding`, which explicitly
documented the old batch-level-context behavior as deliberate. Leaving that
stale would have been worse than the bug.

## Verification

### 1. Eduardo's freshStart ROTH — before/after (the known-bad case)

ROTH IRA real proceeds in this batch: **$1,920.90** (BTC trim + EOSE exit +
SPWR exit), exactly matching the prompt's $1,920.

| # | ADD row (ROTH-routed) | requested | BEFORE `expectedFromTrims` | AFTER `expectedFromTrims` | AFTER `unbacked` |
|---|---|---|---|---|---|
| 3 | AMD | $1,410 | $1,410 | **$1,410** | $0 |
| 4 | ENVX | $1,663 | $1,663 | **$511** | **$1,152** |
| 5 | AMPX | $1,183 | $1,183 | **$0** | **$1,183** |
| 7 | ETF (unallocated) | $1,533 | $1,533 | **$0** | **$1,533** |
| 8 | Commodities (below min) | $753 | $753 | **$0** | **$753** |
| 9 | Crypto (unallocated) | $1,533 | $1,533 | **$0** | **$1,533** |
| | **total** | **$8,075** | **$8,075 claimed vs $1,920.90 real → over-claim $6,153.34** | **$1,920.90 — exact** | **$6,154** |

The `#` column is the new `fundingOrder`; the division follows the decided
order (Established AMD → Speculative ENVX/AMPX → ETF → Commodities → Crypto).
This reproduces Eduardo's actual behavior: he executed ROTH's three sells plus
one buy against the real ~$1,920, then redirected the rest to Custodial. The
app now says up front that $6,154 of those ROTH rows has no source in the batch.

The harness printed `UNATTRIBUTABLE $…` lines on the pre-fix build for five of
the six rows (totalling $6,153.34) and **none** after.

### 2. Invariant: Σ `expectedFromTrims` per account ≤ account's net proceeds

Checked across **all three owners × both modes** (6 runs, 37 ADD rows).
**Zero violations.** Sample:

```
Eduardo freshStart : ROTH  proceeds $1920.90 | claimed $1920.90   (was $8074.24)
                     Cust  proceeds $11163.34| claimed $3049.99
Eduardo normal     : ROTH  proceeds $1990.93 | claimed $1990.93
                     Cust  proceeds $8861.03 | claimed $1158.58
Andrea  freshStart : Cust  proceeds $7357.13 | claimed $2621.74
                     ROTH  proceeds $1156.25 | claimed $1156.25
Andrea  normal     : ROTH  proceeds $1603.95 | claimed $1603.95
                     Cust  proceeds $10410.25| claimed $3736.74
Luis    freshStart : ROTH  proceeds $7025.14 | claimed $6674.93
Luis    normal     : ROTH  proceeds $4342.96 | claimed $4342.96
```

Several accounts now bind exactly at their proceeds ceiling — which is the
point: that ceiling was previously unenforced.

### 3. Split arithmetic `fromCash + expectedFromTrims + unbacked == requested`

**0 failures / 37 ADD rows** across all 6 runs (tolerance $0.02 for the
`toFixed(2)` rounding, same as prior checks in this chain).

### 4. Double-count vs. genuine self-funding shortfall — both present, distinguishable

They are distinguishable arithmetically, and no third category is needed:

- **Resolved double-count** — account total proceeds ≥ Σ uncovered on its rows,
  but a *later* row is short because an earlier one legitimately claimed first.
  Live example: **Luis, normal mode, ETF (unallocated)** — ROTH proceeds
  $4,342.96, NVDA (order 0) took $2,635, ETF (order 1) got the remaining
  $1,708 and shows **$49 unbacked**. Nothing structural; it's the last $49 of a
  fully-spent, sufficient pool.
- **Genuine self-funding shortfall** — account total proceeds < Σ uncovered
  across its rows, so it was never coverable at any division. Live example:
  **Eduardo, freshStart, ROTH** — $8,075 of uncovered ADD demand against
  $1,920.90 of proceeds: **$6,154 is structural**, because ROTH holds different
  tickers than what's newly recommended there. Also **Andrea, freshStart,
  Crypto (unallocated) $1,758** — ROTH's $1,156.25 was fully consumed by QS and
  wouldn't have covered both regardless.

Both render identically to the owner (`unbacked` → "needs a deposit"), which is
correct: in both cases the money has to come from somewhere else. I did **not**
add a third category. If you later want the UI to distinguish them, the signal
is available without new plumbing — compare an account's total proceeds against
the sum of `uncovered` on its rows — but I'd argue against it: the owner's next
action is the same either way, and the distinction is diagnostic, not actionable.

### 5. Static checks

- `node --check server/routes/moves.js` → clean
- `npx vite build` → clean, `✓ built in 791ms` (only the pre-existing
  chunk-size advisory)
- Re-grepped to confirm both edits landed.

### 6. `./server/scripts/verify-allocation-math.sh`

Ran pre-fix and post-fix and diffed: **byte-identical**. Same tracked task-#50
baseline (the known Established/Speculative reconstruction FAILs and exit code
1, unchanged from `0021bcc`'s wrap-up). Expected — this change touches only the
`expectedFromTrims`/`unbacked` split, never sizing or targets. **No writes**;
`computeMovesPayload` is read-only.

## Deviations from the prompt

1. **Staged specific files instead of `git add -A`.** The prompt's commit block
   says `git add -A`, but the tree has ~35 unrelated untracked files including
   an untracked `client/dist/` build output. `git add -A` would have committed
   all of it. Staged `server/routes/moves.js` and this wrap-up only, per the
   project's standing "never `git add .`" convention. Flagging because it
   contradicts the prompt's literal text.
2. **Doc comment rewritten**, slightly beyond "the `expectedFromTrims`/`unbacked`
   split" as scoped — but the old comment asserted the buggy behavior was
   intentional and named the (now-resolved) blocker, so it had to change.

## Not done / left for you

- No client changes — existing `unbacked` wording reused as instructed.
- No gating, no sizing changes, no cross-account funding, idle-cash ledger and
  priority order untouched.
- Not promoted to prod. Pushed to `dev` only.
- A temporary read-only verification script was used and **deleted**; nothing
  diagnostic remains in the tree.

## Follow-up commands

```bash
# Confirm the change is live on dev after deploy, then eyeball Eduardo's Full Reset:
#   ROTH rows AMPX / ETF / Commodities / Crypto should now read
#   "not covered by idle cash or any trim in this batch — needs a deposit"
#   and ENVX should show a $511 / $1,152 split.

# Re-run the tracked baseline (expects the same task-#50 FAILs, exit 1):
./server/scripts/verify-allocation-math.sh

node --check server/routes/moves.js
cd client && npx vite build
```

Note: Eduardo's Full Reset is a frozen 24-hour snapshot (`2853f91`). If his
current snapshot predates this deploy it will keep showing the old numbers —
regenerate the reset to see the fix.

# Fix: show account routing for out-of-scope bucket-level ADD rows

**Commit `ce1e725`, pushed to `origin/dev`.** Two files:
`server/routes/moves.js`, `client/src/pages/PortfolioManager.jsx`.

Bucket-level rows now carry account routing. **Two findings need your
attention** before this is considered closed — one is a premise
correction, the other is a pre-existing cash-accounting behaviour that
is directly relevant to the mis-execution that motivated this fix. Both
are below.

## Premise checks

**Correction 1 — six push sites, not three.** The prompt says "three
near-identical blocks" and item 1 says "at each of the three bucket-level
ADD push sites." The three *blocks* it names are right, but **each block
contains two push sites**: an "(unallocated)"/scarcity-gap row and a
"(below minimum)" row. Six in total:

| Line | Row | Flags |
|---|---|---|
| 1135 | fixed bucket (unallocated) | — |
| 1158 | fixed bucket (below minimum) | `isBelowFloor` |
| 1329 | freshStart scarcity gap | `isScarcityGap` |
| 1341 | freshStart below minimum | `isBelowFloor` |
| 1646 | normal-path scarcity gap | `isScarcityGap` |
| 1666 | normal-path below minimum | `isBelowFloor` |

I applied the change to all six, since item 3 explicitly directs
including "(below minimum)" rows, and the same "don't hide routing"
reasoning applies to the scarcity-gap rows.

**Correction 2 — the frontend instruction doesn't apply as written.**
Item 2 says the collapsed-row logic should "fall through to the normal
routing-summary rendering when accounts are populated." That cell is the
**Decision column**, not a routing column — for normal rows it holds the
Accept/Decline buttons. Falling through would give ticker-less rows an
Accept button, and `handleAccept` POSTs `symbol: move.symbol`, which is
`null` on these rows. That would write junk decisions.

What I did instead is covered under "Frontend" below.

**Everything else verified as described.** `buildNewPositionRouting` at
line 402 takes `(accounts, dollarAmount)`, needs no ticker or price,
sorts roth → ira → taxable → custodial, splits by `cashBalance`, and has
an `insufficientCash` fallback. `accounts` is fetched at line 928, well
before all six sites. The dollar variable really is `shortfall` at all
six — checked individually rather than assumed.

## What changed

### Server

All six sites, mechanically identical:

```diff
-accounts: [], requires48h: false, isBucketLevel: true
+accounts: buildNewPositionRouting(accounts, shortfall), requires48h: false, isBucketLevel: true
```

Rationale added to `buildNewPositionRouting`'s docblock — one place
rather than six duplicated comments — recording that it now also serves
ticker-less bucket rows and that ticker selection stays out of scope.

### Frontend

`AddRoutingDetail` is gated only by `hasAccts`, so the full BUY ROUTING
panel now renders for these rows automatically. **No change needed
there**, exactly as the prompt predicted.

For the collapsed Decision cell, instead of the (inapplicable)
fall-through, each bucket branch keeps its explanatory badge and gains a
compact `BucketFundingHint`:

```jsx
<span title={`Funding source if you choose to act — ${tip}`}>
  from {label}{needsFunding ? ' ⚠' : ''}
</span>
```

It shows the account name (or "N accounts"), a per-account dollar
breakdown in the tooltip, and an amber ⚠ when any account is flagged
`insufficientCash`. So the funding source is visible **without
expanding** — which is what the motivating incident actually needed.

I also reworded the third branch from **"Outside agent scope"** to
**"Ticker: your pick"**, with the tooltip: *"The agent doesn't pick the
specific ETF/crypto/commodity ticker — that's outside its Circle of
Competence. The funding account(s) below are still calculated for you."*
The old wording read as "there is nothing for you here," which is now
false — routing exists. The out-of-scope caveat is still stated plainly
(verify item 3).

## ⚠ Finding: routing double-counts cash across rows

Not introduced by this change, but this change makes it visible, and it
bears directly on the incident that prompted the task.

`buildNewPositionRouting` is **stateless per row** — each call sees the
full cash balance, with no awareness of other rows claiming the same
dollars. Live data, Andrea Morales (freshStart):

```
Andrea accounts: ROTH IRA $0.03 · Custodial $1,479.28   (total cash $1,479.31)

ETF (unallocated)          gap $3,922.35  ->  routed $1,479.28 from Andrea Custodial
Crypto (unallocated)       gap $1,624.56  ->  routed $1,479.28 from Andrea Custodial
Commodities (below min)    gap   $136.28  ->  routed   $136.28 from Andrea Custodial
```

Two distinct issues:

1. **The same $1,479.28 is claimed by three rows.** Acting on all of
   them needs ~$3,095; she has $1,479. Each row is individually truthful
   and collectively they are not.
2. **Partial coverage is silent.** The ETF row routes $1,479 against a
   $3,922 gap and sets no flag — `insufficientCash` only fires when *no*
   account has ≥$1, so a row that covers 38% of its gap looks the same
   as one that covers 100%. My ⚠ hint therefore does **not** fire here.
   (It does fire for Luis, whose ROTH has no cash at all — all four of
   his rows correctly show INSUFFICIENT.)

**I did not fix either.** Both are properties of shared logic used
identically at the two pre-existing call sites (watchlist/freshStart
candidate rows), so changing it would alter behaviour beyond this task's
scope, and a correct fix is a design decision: routing would need to be
computed globally against a shared, decrementing cash pool across all
rows, rather than per-row. Given the motivating incident was *precisely*
a cash-availability surprise, I'd treat this as the higher-value
follow-up of the two.

## Verification — all 6 items

1. **All bucket rows now route** ✔ — computed live for all three owners,
   both modes:
   ```
   Andrea  [freshStart]: ETF $3922.35 -> 1 acct · Crypto $1624.56 -> 1 acct · Commodities $136.28 -> 1 acct
   Luis    [freshStart]: ETF $1722.65 · Spec $861.32 · Crypto $689.06 · Commodities $689.06 -> all 1 acct, all INSUFFICIENT
   Eduardo [freshStart]: ETF $1530.48 · Crypto $1530.48 · Commodities $744.60 -> all 1 acct
   ```
   (No owner currently has bucket rows in *normal* mode — they only
   appear under freshStart right now, so that's the mode exercised.)
2. **Splits sensibly by tax treatment / cash** ✔ — Luis routes to ROTH
   IRA (`roth`, tax-sheltered, priority 0) and correctly flags
   `insufficientCash`; Andrea and Eduardo route to their Custodial
   (`taxable`) accounts, their only ones with cash. Consistent with the
   two existing call sites. See the caveat above re: partial coverage.
3. **Out-of-scope language still present** ✔ — every row's `reason`
   still matches out-of-scope / Layer-3-sourcing / below-minimum
   phrasing (asserted programmatically), and the Decision cell states it
   plus a tooltip. The agent still never picks a ticker: `symbol` is
   `null` on all six rows, unchanged.
4. **No regression at the two original call sites** ✔ — ticker-scoped
   ADD rows still route: Eduardo `QS, ENVX, AMPX, MSFT, AVGO, GOOGL,
   AMD` each with 1 account; Luis `NVDA`; Andrea `QS`. Same function,
   more callers, identical behaviour at the originals.
5. **`node --check server/routes/moves.js`** ✔ and **`npx vite build`**
   ✔ clean (112 modules).
6. **No writes made** ✔ — `computeMovesPayload` is pure compute; my
   scripts never called `upsert`. `verify-allocation-math.sh` shows the
   same tracked baseline pattern (task #50): the same seven bucket
   failures across the same three owners. Absolute figures differ from
   yesterday's run because prices and targets moved (Andrea is mid-Full-
   Reset as of today 13:49), not because of this change — which touches
   no allocation math at all.

## What was deliberately NOT done

- **No ticker selection** for ETF/crypto/commodity buckets — unchanged
  and still explicitly out of scope.
- **`buildAddRouting`** (held-ticker version) and all ticker-specific
  ADD/TRIM routing — untouched.
- **Manual trade-sequencing / insufficient-funds problem** — untouched,
  still backlogged.
- **The cash double-counting above** — reported, not fixed (shared
  logic, needs a design decision).
- **No visual verification** — Chrome tools still not connected (fifth
  session). Everything above is source- and data-verified; the rendered
  appearance of the new hint is not.

## Follow-up for Luis

1. **Check the three rows render as expected** — each should show its
   badge plus `from Andrea Custodial` (hover for the per-account
   breakdown), and the full BUY ROUTING panel when expanded.
2. **Decide on the double-counting.** Worth a dedicated task: compute
   routing across all rows against one decrementing cash pool, and flag
   rows whose gap exceeds available cash. This is the closest thing here
   to the original mis-execution's root cause that is actually fixable
   in the display layer.
3. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect ce1e725...
   ```
4. Note bucket rows currently only appear under Full Reset for all three
   owners — if you want to see them in everyday mode you'd need a normal
   -mode gap, which none of the three has right now.

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.

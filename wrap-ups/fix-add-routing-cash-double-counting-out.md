# Fix: ADD routing double-counts cash across rows in the same run

**Commit `844e3c7`, pushed to `origin/dev`.** Two files:
`server/routes/moves.js`, `client/src/pages/PortfolioManager.jsx`.

The double-counting is fixed and the invariant now holds for every owner
in both modes. **The ordering question (item 3) produced two findings
that need a product decision from you** — reported here, not acted on,
per the prompt's instruction not to reorder unilaterally.

## Premise check — accurate throughout

Everything the prompt described was confirmed against current code:

- `buildAddRouting` (line 299) read `pos.account?.cashBalance` directly
  in its allocation loop, with no accumulator.
- `buildNewPositionRouting` (line 411) did the same with
  `acct.cashBalance`.
- `insufficientCash` was set only in the `rows.length === 0` fallback —
  so it genuinely meant "no account had any room", never "partially
  covered".
- `accounts` is a single per-run snapshot (`prisma.account.findMany`,
  line 937), reused unmodified.

One useful detail the prompt didn't mention: **`pos.account` and the
`accounts` array are the same objects.** Line 975 does
`byTicker.get(...).positions.push({ ...pos, account: acct })`, so both
routing functions ultimately read one shared account graph. That made a
tempting shortcut available — mutate `acct.cashBalance` as rows consume
it — which I rejected: `totalCash` and `capitalFlow` also read those
fields, so depleting them in place would corrupt unrelated figures.

## What changed

### A per-run ledger, passed explicitly

```js
const committedCash = new Map();   // accountId -> dollars already promised this run

function availableCash(committed, accountId, cashBalance) {
  return Math.max(0, (cashBalance ?? 0) - (committed?.get(accountId) ?? 0));
}
function commitCash(committed, accountId, amount) { /* accumulate */ }
```

Both routing loops now compute room as
`availableCash(committed, id, cashBalance)` instead of raw
`cashBalance`, and call `commitCash(...)` after pushing each row.

**Threaded as a parameter, deliberately not module-level state.**
`computeMovesPayload` awaits mid-run, so two concurrent requests would
interleave and corrupt a shared module-scoped ledger — a subtle bug that
would only appear under simultaneous use. Threading touches four
signatures (`buildAddRouting`, `buildNewPositionRouting`, `makeAddMove`,
`generateMovesForTicker`, the last two with defaults so nothing breaks
if omitted) and ten call sites.

### Partial-coverage flag (item 4)

```js
function flagPartialFunding(rows, requested, routed) {
  const unfunded = +(requested - routed).toFixed(2);
  if (unfunded <= 0.01) return rows;
  for (const r of rows) { r.partiallyFunded = true; r.unfundedAmount = unfunded; }
  return rows;
}
```

Kept **distinct** from `insufficientCash` rather than overloading it —
"partially covered" and "no account has any room" are different
situations and the UI should be able to say which. Surfaced in
`AddRoutingDetail` (an amber "⚠ $X of this add isn't covered by
available cash" line) and folded into the bucket-row funding hint's ⚠
and tooltip.

---

## ⚠ Item 3 — the ordering findings (product decisions, not fixed)

Because the ledger depletes as it goes, generation order now determines
who gets real cash. I traced the actual order from live results rather
than reading it off the file, since the payload's `moves` array is
priority-sorted at the end and does **not** reflect generation order.

### Finding 1: bucket-level rows are funded *before* ticker-specific ones

This is the one I'd flag hardest. Andrea, freshStart — she has
**$1,479.28** total cash:

```
ETF (unallocated)            gap $3,922.35 -> routed $1,479.28   PARTIAL (unfunded $2,443.07)
Crypto (unallocated)         gap $1,624.56 -> INSUFFICIENT
QS                           gap $1,162.44 -> INSUFFICIENT
Commodities (below minimum)  gap   $136.28 -> INSUFFICIENT
```

**"ETF (unallocated)" consumed 100% of her available cash** — and that
is a row where the agent explicitly declines to pick a ticker ("outside
the Circle of Competence, your pick"). It starved `QS`, a real,
conviction-scored, agent-selected ADD.

Eduardo, freshStart, is the same shape at larger scale: ETF + Crypto took
$3,060.96 of his $3,238.33, Commodities took the $177.37 remainder, and
**all seven ticker ADDs** (QS, ENVX, AMPX, MSFT, AVGO, GOOGL, AMD) came
back INSUFFICIENT.

So the current order funds the agent's *least* specific recommendations
first, at the expense of its most specific ones. I don't think that's
what you want, but reordering is a product call and the prompt was
explicit that I shouldn't make it.

### Finding 2: among ticker ADDs, the order is database iteration order

Eduardo, normal mode:

```
QS     gap   $446.76 -> $446.76   funded
MSFT   gap $1,316    -> $1,316    funded
AVGO   gap $1,316    -> $1,316    funded
GOOGL  gap $1,316    -> $159.57   PARTIAL (unfunded $1,156.43)
AMD    gap $1,316    -> INSUFFICIENT
```

That sequence isn't by conviction, priority, or size — the smallest gap
(QS) went first and the four equal-sized ones split arbitrarily. It comes
from `byTicker`'s Map insertion order, built by iterating `accounts` and
then `acct.positions` (line 975) — i.e. **database row order**. GOOGL and
AMD lose out to MSFT and AVGO for no investment reason at all.

### What I'd suggest (your call)

Fund in priority order: ticker-specific ADDs before bucket-level gaps,
and within tickers, by the same ranking the engine already computes
(`priority`, or conviction/rank score) rather than DB order. Both are
one-line-ish sort changes at the generation sites, but they change which
recommendations look fundable — squarely a product decision.

*Also noticed, pre-existing and unchanged:* the "no cash anywhere"
fallback names `managed[0]` — the highest-priority account by type — so
Andrea's Crypto row now says "Andrea ROTH IRA", an account with $0.03,
rather than her Custodial. Harmless but slightly odd, and more visible
now that more rows hit the fallback.

---

## Verification — all 6 items

**1. Invariant: per-account routed total never exceeds actual cash** ✔ —
computed live for all three owners in both modes:

```
Andrea  [normal]  PASS Custodial: routed $1,067.00 vs cash $1,479.28
Andrea  [fresh]   PASS Custodial: routed $1,479.28 vs cash $1,479.28
Luis    [both]    (no real claims — ROTH has $0.03, all rows are fallbacks)
Eduardo [normal]  PASS Custodial: routed $3,238.33 vs cash $3,238.33
Eduardo [fresh]   PASS Custodial: routed $3,238.33 vs cash $3,238.33
=> INVARIANT HOLDS in every case
```

Note the two exact-match cases: the ledger allocates right up to the
balance and then stops, which is the intended behaviour.

**2. Partial coverage now visibly flagged** ✔ — the Andrea ETF case the
prompt named specifically: `gap $3,922.35 -> routed $1,479.28 PARTIAL
(unfunded $2,443.07)`. Previously silent. Also caught Eduardo's GOOGL
($159.57 of $1,316) and his Commodities row ($177.37 of $744.60).

**3. Ordering reported** ✔ — two findings above, with concrete examples,
neither acted on.

**4. No regression on non-competing rows** ✔ — captured full routing
output before and after via `git stash`, diffed:
**14 of 26 ADD rows byte-identical; 12 changed.** Every one of the 12 is
a row that had been competing for an account another row already
claimed. No row that had an account to itself moved.

**5.** `node --check server/routes/moves.js` ✔ · `npx vite build` clean
at 112 modules ✔.

**6. `verify-allocation-math.sh`** ✔ — identical to the pre-change run
earlier today: same seven failures, same figures (Andrea `$736.69` /
`-$350.06` / `-$140.61`, Luis `$1,766.07`, Eduardo `$5.28` / `$30.45` /
`$30.61`). This is the tracked task-#50 baseline and this change touches
no allocation math. **No writes made** — `computeMovesPayload` is pure
compute and none of my scripts called `upsert`.

## What was deliberately NOT done

- **No reordering of move generation** — findings 1 and 2 reported for
  your decision, per the prompt's explicit instruction.
- **No change to which tickers/buckets get recommendations, or for how
  much** — scoped strictly to the routing layer.
- **Nothing touching manual execution sequencing** — still backlogged.
- **Did not mutate `acct.cashBalance` in place** despite the aliasing
  making it easy; `totalCash`/`capitalFlow` read those same fields.
- **No visual verification** — Chrome tools still not connected (sixth
  session). The new amber partial-funding line and the ⚠ in the bucket
  hint are source-verified only.

## Follow-up for Luis

1. **Decide the funding order** (findings 1 and 2). The Andrea case is
   the clearest illustration: an "unallocated ETF" row you'd likely act
   on last is currently first in line for cash, ahead of a specific QS
   recommendation.
2. **Expect more INSUFFICIENT / PARTIAL flags than before.** That isn't
   a regression — it's the previously-hidden truth that your cash
   doesn't cover every recommendation simultaneously. Andrea's four
   freshStart ADDs total ~$6,845 against $1,479 of cash.
3. Eyeball the new amber line in an expanded ADD row's BUY ROUTING panel
   (Eduardo → GOOGL in normal mode is a live example right now).
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 844e3c7...
   ```

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.

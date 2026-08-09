# Recon: Established/Speculative bucket shortfall — findings

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)
Commit: `<see git log — "Fix fixed-target-bucket unallocated shortfall to use per-ticker capped targets, not raw current value">`

## Conclusion, per owner

**The headline "$5,580 / $5,445 shortfall" in the recon prompt was mostly a
measurement artifact, not an engine bug.** The prompt's manual tally summed
only the tickers shown in the "Action Required" (TRIM/ADD) table and missed
tickers that were already at/near target and therefore showing under "No
action needed" — those still count toward the bucket total.

- **Andrea Morales — Established**: balances correctly. AMD+NVDA+AMZN+QS+
  ORCL(new)+GOOGL(new) = $6,114.56; adding AVGO's target (~$962.66, held,
  "no action needed" so it never appeared in the prompt's tally) brings the
  total to ~$7,077.2 — matches the bucket target ($7,077.22) almost exactly.
  **Not a bug.**

- **Andrea Morales — Speculative**: genuinely short, but this is
  **hypothesis 1 (genuine scarcity)**, confirmed directly — not a
  redistribution bug. SPWR+AMPX+EOSE only total $2,458.75 against a
  $7,077.22 target, a real ~$4,618 gap, and there are **zero eligible new
  speculative watchlist candidates** to fill it: every watchlist ticker
  tagged or eligible for the speculative side either has `finalAction`
  `Unknown` (GLD) or `Exit` (RUN) — both fail the `['Add','Hold']`
  eligibility filter in `computeMovesPayload`'s watchlist-candidate loop
  (moves.js ~line 1103-1105). `sizeSide()` correctly returns `[]` for an
  empty candidate list. **Not a bug** — a legitimate coverage gap in the
  Radar/watchlist, not the allocator leaving money on the table.

- **Eduardo Morales — Established**: balances correctly once QS's held
  target (~$803, "no action needed", omitted from the prompt's tally) is
  included: NVDA+ORCL+AMZN+GOOGL(new)+NFLX(new)+QS ≈ $8,850 vs. an $8,834.72
  target. **Not a bug.**

- **Eduardo Morales — Speculative**: also balances once SIVR, BTC, and
  BYDDY (all held, all "no action needed," all omitted from the prompt's
  tally) are included: EOSE+AMPX+ENVX+SPWR+SIVR+BTC+BYDDY ≈ $8,651 vs. an
  $8,834.72 target — within ~$184, effectively converged. **Not a bug.**

## Ruling out hypothesis 3 for the individual-stock engine

Pulled every Established/Speculative move directly from
`computeMovesPayload('<owner>', { bypassWinnerProtection: true })` (that
function is exported from `server/routes/moves.js` — ran it against
production data via a one-off Node script, no HTTP/auth needed) and compared
each ticker's assigned `targetPct` to its `hardCapPct`:

| Owner | Symbol | targetPct | hardCapPct |
|---|---|---|---|
| Andrea | AMD | 3.01% | 50% |
| Andrea | NVDA | 3.01% | 45% |
| Andrea | AMPX | 3.21% | 35% |
| Eduardo | NVDA | 3.75% | 45% |
| Eduardo | ORCL | 3.75% | 45% |

**No individual stock is anywhere near its cap.** `computeIndividualModelWeights`'s
`Math.min(raw * scale, hardCapPct)` clip in the `allocate()` function
(moves.js ~line 223) is never actually binding for either owner's held
equities — so the water-filling/redistribution concern in hypothesis 3
(clipped tickers' unused pool not flowing to others) doesn't apply here.
**No code change made to `computeIndividualModelWeights`.**

## A real bug found and fixed — fixed-target bucket "(unallocated)" check

While checking the recon prompt's secondary "smell" (Eduardo's ETF bucket:
target $8,031.56 vs. QQQ+TMFC $6,426, no "ETF (unallocated)" row), found a
genuine bug in `splitBucketTarget`'s companion shortfall check in
`computeMovesPayload` (moves.js, the `fixedBuckets` loop around line 971,
prior to this session's fix):

```js
const currentValue = b.groups.reduce((s, g) => s + positionMetrics(...).mktValue, 0);
const targetValue  = totalPortfolioValue * (b.targetPct / 100);
const shortfall    = targetValue - currentValue;   // ← bug
```

The shortfall was computed against **raw current market value**, not
against what the held tickers can actually reach at their own per-ticker
caps. Eduardo's QQQ and TMFC are each capped at 10% individually (an
`OwnerTickerConfig`/`Ticker.capPercent` override), so `splitBucketTarget`
correctly clips each to 10% (an even split would have been 12.5% each from
a 25% bucket target ÷ 2 tickers) — meaning the bucket can only ever reach
20% (10%+10%) from currently-held tickers, 5 points short of the 25%
target. But because QQQ (11.62%) and TMFC (11.06%) were *currently*
overweight (above their own caps, both getting trimmed down), their
pre-trim market value happened to sit close to the bucket target in dollar
terms — so the old check saw "current ≈ target" and never fired, even
though after both trims execute the bucket will genuinely sit at ~$6,425
against an $8,032 target, a real $1,606 gap that was going undetected.

This is exactly the same shape as hypothesis 3 (capped headroom silently
left unclaimed) but in the fixed-target-bucket code path, not the
individual-stock barbell path the prompt's hypotheses were framed around.

**Fix applied**: compare `targetValue` against `achievableValue` — the sum
of each held ticker's own capped target (`fixedTargetMap`, already computed
by `splitBucketTarget` a few lines above) — instead of raw current value.
This makes the "(unallocated)" check reflect genuine cap-driven headroom
regardless of whether the held tickers happen to be over- or under-weight
today.

**Verified post-fix** (re-ran `computeMovesPayload` against production data):
- Eduardo now gets `ETF (unallocated): $1,606.31` (was: no row at all).
- Andrea's `Crypto (unallocated)` changed from $2,052.59 → $1,572.72,
  because BTC itself is capped at 5% (not 10%) — the old number was
  actually wrong in the other direction, implicitly suggesting someone buy
  BTC up to the full 10% bucket target when BTC's own cap only allows 5%.
  The new number correctly reflects "BTC can reach $1,572.72 (its own cap);
  the remaining $1,572.72 of bucket room needs a different crypto ticker."
- No double-counting: BTC's own move target (5%, i.e. $1,572.72) plus the
  new `Crypto (unallocated)` row (5%, $1,572.72) sum to exactly the 10%
  bucket target — confirmed directly from the payload.

## What wasn't checked

- Did not audit every owner (only Andrea and Eduardo, per the prompt) — Luis
  Morales's profile exists too and wasn't examined.
- Did not add a UI treatment for genuinely-scarce buckets (Andrea's
  Speculative — hypothesis 1, no code change warranted per the prompt's own
  instructions). Flagging as a candidate follow-up: an explicit
  "Speculative (unallocated) — insufficient conviction headroom" style row,
  mirroring the fixed-bucket unallocated pattern, so a genuine watchlist gap
  reads as "nothing qualifies" rather than the bucket target silently not
  being reconcilable from the UI alone.
- Did not re-verify `sizeSide`'s Type A/B rescale logic or the
  `remainingEstPoolPct`/`remainingSpecPoolPct` formula beyond confirming
  they produced `[]` correctly when the candidate list was empty — no
  candidates existed to exercise the non-trivial branches of `sizeSide` for
  either owner in this session.

## Files touched

- `server/routes/moves.js` (one function: the `fixedBuckets` shortfall
  check inside `computeMovesPayload`)

No schema/migration changes. No client changes — the corrected
"(unallocated)" dollar amounts flow through to the Allocation tab and
re-baseline modal automatically since both already render whatever
`computeMovesPayload` returns.

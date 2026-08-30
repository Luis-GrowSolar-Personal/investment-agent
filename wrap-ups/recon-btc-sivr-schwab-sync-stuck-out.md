# Recon: why BTC/SIVR stay permanently out-of-sync after a re-baseline execution

**Bottom line — root cause: multi-fill-not-summed bug.** The re-baseline
buys for BTC and SIVR were each executed at Schwab as **two separate
same-day fills** (common for these lower-liquidity ETFs). The sync
matcher in `ensureRecentTrades()` only checks whether a *single* trade
leg matches the diff exactly — it never sums multiple same-day fills
for the same symbol. Since neither individual BTC fill (71 sh, 0.9957
sh) nor either SIVR fill (9 sh, 0.876 sh) equals the full diff on its
own, no match is ever found, and because both positions already carry
pre-existing `manual`/`import` lots, there is **no fallback** — the
diff just parks in `positionDiffs` for manual entry, indefinitely. This
is not a symbol-mismatch issue (Schwab's transaction feed uses the
exact same symbol, `BTC`, in both the transaction and position feeds)
and not a missing-data issue (the trades are fully present in the
90-day feed, with real prices, correct type, and correct
`positionEffect`).

Separately, the "cost basis prompts went away after a few days" report
for MSFT/GOOGL/ORCL/AMD/etc. is a **different code path that always
"succeeds" but doesn't get the real cost basis** — those positions had
only `source: 'schwab'` lots, so they hit the lenient full-replace
branch, which always resolves using the position-level `averagePrice`
rather than the real per-lot Schwab cost basis. They look resolved but
are not accurate; see "Question 4" below for why this matters for tax
calculations.

**No writes were made during this recon.** No `Lot`, `Position`, or
`Account` rows were created, updated, or deleted. Only read-only Prisma
queries (`findMany`/`findUnique`) and the existing read-only
`debug_transactions.js` script (`getTransactions` only) were run.
Andrea's account remains untouched, in its current out-of-sync state.

---

## 1. Code path: why BTC/SIVR differ from the equities

`server/lib/schwabSync.js`, in the per-position sync loop (current
lines ~359–439):

- Line 371: `const hasManualOrImportLots = localPos.lotSources.some(s => s !== 'schwab');`
- If true (BTC has two `manual` lots; SIVR has one `import` lot), the
  diff goes through the **strict branch** (lines 372–423):
  - For a positive diff (an add), it calls `ensureRecentTrades()`
    (lines 326–357), which pulls the last 60 days of `TRADE`
    transactions and builds `symbol → [OPENING legs]`.
  - Line 380: `const match = candidates.find(t => Math.abs(t.shares - diff) / diff < 0.0001);`
    — this looks for **one single leg** whose share count matches the
    diff within 0.01%. It never sums multiple legs for the same
    symbol.
  - If no single leg matches, lines 400–407 push the diff into
    `result.positionDiffs` with `status: 'mismatch'` and no further
    resolution attempt is ever made on subsequent syncs — the app
    keeps re-computing the same unmatched diff every sync, which
    reads to the user as "still stuck."
- If `hasManualOrImportLots` is false (MSFT, AMD, GOOGL, ORCL — all
  `source: 'schwab'` only), the code instead takes the **lenient
  branch** (lines 424–438): it deletes the existing `schwab`-sourced
  lot(s) and creates one fresh lot using `schwabPos.averagePrice ??
  0`, tagged `notes: 'Estimated from Schwab sync — ...'`. This branch
  has no failure mode — it always "resolves," just with an estimated,
  not-lot-accurate cost basis.

Confirmed directly against current `Lot` rows for Andrea's Custodial
account (id 7, read-only query):

```
=== BTC (positionId 80) ===
  shares=34 costBasis=37.55  source=manual acquiredDate=2024-11-11 notes=null
  shares=4  costBasis=44.16  source=manual acquiredDate=2024-11-22 notes=null

=== SIVR (positionId 74) ===
  shares=12 costBasis=72.6703 source=import acquiredDate=2026-02-02 notes=null

=== MSFT (positionId 115) ===
  shares=2.9889 costBasis=479.775168122052 source=schwab acquiredDate=2026-08-22
  notes=Estimated from Schwab sync — acquisition date is a placeholder ...

=== AMD (positionId 114) ===
  shares=2.8067 costBasis=525.709908433391 source=schwab acquiredDate=2026-08-22
  notes=Estimated from Schwab sync — acquisition date is a placeholder ...

=== GOOGL (positionId 116) ===
  shares=4.1774 costBasis=343.270934073826 source=schwab acquiredDate=2026-08-22
  notes=Estimated from Schwab sync — acquisition date is a placeholder ...

=== ORCL (positionId 117) ===
  shares=9.6963 costBasis=147.891463754216 source=schwab acquiredDate=2026-08-22
  notes=Estimated from Schwab sync — acquisition date is a placeholder ...
```

This confirms the theory exactly: BTC and SIVR still show only their
pre-existing `manual`/`import` lots — the 71.9957-share BTC buy and the
9.876-share SIVR buy from the re-baseline never made it into the `Lot`
table at all. MSFT/AMD/GOOGL/ORCL each have exactly one `schwab`-sourced
lot dated today (the day of this recon, i.e. refreshed on a later sync
after the re-baseline), carrying the "Estimated from Schwab sync" note
— confirming they took the always-succeeds branch, not the
transaction-history-matched branch.

## 2. Raw Schwab transaction data (last 90 days, Andrea Custodial, account id 7)

Pulled via `node server/scripts/debug_transactions.js 7 90` (read-only,
`getTransactions` only — no writes). Relevant legs, quoted directly:

**BTC — two separate OPENING fills, same trade date:**

```
type:           TRADE
tradeDate:      2026-08-17T16:53:xx+0000  (fee-only legs precede this one)
├─ instrument: {"assetType":"COLLECTIVE_INVESTMENT","status":"ACTIVE","symbol":"BTC",
                "uniformSymbol":"BTC","description":"GRAYSCALE BITCOIN MINI TR ETF",
                "instrumentId":226848413,"closingPrice":34.08,"type":"EXCHANGE_TRADED_FUND"}
├─ amount:          0.9957
├─ price:           28.335
├─ cost:            -28.21
├─ positionEffect:  OPENING

type:           TRADE
tradeDate:      2026-08-17T16:52:46+0000
├─ instrument: {"assetType":"COLLECTIVE_INVESTMENT","status":"ACTIVE","symbol":"BTC", ...}
├─ amount:          71
├─ price:           28.335
├─ cost:            -2011.79
├─ positionEffect:  OPENING
```

`0.9957 + 71 = 71.9957` — exactly matching the missing local diff
(Schwab 109.9957 − local 38 = 71.9957). Both legs are `type: 'TRADE'`,
`positionEffect: 'OPENING'`, `instrument.symbol: 'BTC'` (exact match to
the position-level symbol), and both have a populated `price`
(28.335). Neither leg alone (`0.9957` or `71`) is within 0.01% of
`71.9957`, so `candidates.find(...)` (line 380) never matches either
one, and the sum is never attempted.

**SIVR — same pattern, two OPENING fills:**

```
type:           TRADE
├─ instrument: {"assetType":"COLLECTIVE_INVESTMENT","status":"ACTIVE","symbol":"SIVR",
                "uniformSymbol":"SIVR","description":"abrdn Physical Silver Shares ETF",
                "instrumentId":76223216,"closingPrice":65.9,"type":"EXCHANGE_TRADED_FUND"}
├─ amount:          0.876
├─ price:           63.0555
├─ cost:            -55.24
├─ positionEffect:  OPENING

type:           TRADE
├─ instrument: {"assetType":"COLLECTIVE_INVESTMENT","status":"ACTIVE","symbol":"SIVR", ...}
├─ amount:          9
├─ price:           63.0555
├─ cost:            -567.5
├─ positionEffect:  OPENING
```

`0.876 + 9 = 9.876` — exactly matching the reported SIVR diff (Schwab
21.876 − local 12 = 9.876). Same story: both legs are valid `TRADE` /
`OPENING` fills with the correct symbol and a populated price, but
individually neither matches the full diff.

## 3. Definitive answer

This is a **multi-fill-not-summed bug**, not a symbol-matching bug and
not a missing-data issue:

- **Symbol matching is correct.** `item.instrument?.symbol` is exactly
  `'BTC'` and `'SIVR'` in the transaction feed — identical to the
  position-level symbol used elsewhere in the sync. No CUSIP/alt-symbol
  discrepancy exists for this Grayscale Bitcoin Mini Trust ETF.
- **The data is present and well-formed.** Both trades show up well
  within the 60-day window the matcher actually queries (they're 5
  days old as of this recon), `txn.type === 'TRADE'`,
  `item.positionEffect === 'OPENING'`, and `item.price` is populated
  and non-null for every relevant leg.
- **The actual defect:** Schwab split each re-baseline buy into two
  separate fills (likely a partial fill followed by a fractional-share
  completion, common for these lower-liquidity ETFs), and
  `ensureRecentTrades()`'s matcher (`schwabSync.js:378-380`) only ever
  checks single legs against the diff — it has no logic to sum same-day
  (or any) multiple fills for a symbol before comparing to the diff.
  Because BTC/SIVR both carry pre-existing manual/import lots, there is
  also no lenient fallback available (line 372's branch has none) — so
  the diff parks in `positionDiffs` forever, surviving every subsequent
  sync unchanged.

## 4. Why the equity cost-basis prompts "resolved themselves"

Checked via the `notes` field on the current `Lot` rows (see table in
section 1): MSFT, AMD, GOOGL, and ORCL all show
`notes: "Estimated from Schwab sync — acquisition date is a
placeholder ..."`, **not** `"Auto-resolved from Schwab transaction
history: ..."`.

That means these positions did **not** get a real, transaction-matched
cost basis — they simply had only `schwab`-sourced lots to begin with
(no manual/import lots blocking them), so on a later sync they fell
into the lenient full-replace branch (`schwabSync.js:424-438`), which
always succeeds by using `schwabPos.averagePrice` as a stand-in cost
basis with today's date as a placeholder acquisition date. The manual
cost-basis prompt disappeared because the app now has *a* number to
show, not because it recovered the *real* per-lot cost basis from the
transaction history. This directly affects Principle 5 (every trim
needs an accurate tax cost calculation): for these four tickers, any
trim recommendation today would compute LTCG/STCG using an estimated
average price and a fabricated "acquired today" date rather than the
real lot-level cost basis and holding period — worth flagging before
relying on the tax-cost math for these four positions specifically.

## What was NOT done (deliberately, per scope)

- No sync, reconcile, match, or Force Sync call was made.
- No `Lot`/`Position`/`Account` row was created, updated, or deleted.
- No code changes were made — the two ad hoc read-only query scripts
  used to pull the `Lot` table snapshot were deleted after use; no
  script or code diff remains in the working tree.
- No commit, no push.

## Suggested follow-up (not implemented — flagging only, per scope)

- A real fix would need `ensureRecentTrades()` / the matcher at
  `schwabSync.js:378-380` to sum same-day (or same-symbol, within-window)
  OPENING legs and compare the sum to the diff, not just check single
  legs.
- Separately, worth deciding whether the lenient branch's
  `averagePrice`-estimated lots (MSFT/AMD/GOOGL/ORCL) should later be
  reconciled against real transaction history too, so their cost basis
  isn't left permanently approximate.
- The one-day date discrepancy Luis flagged (local manual lots dated
  Nov 21/22 2024 & Nov 10/11 2024 vs. Schwab's Nov 22/2024 & Nov
  11/2024) was not investigated further — out of scope for this recon
  and likely a timezone/off-by-one artifact from how the original
  manual entries were made, unrelated to the sync-stuck root cause.

## Verification commands used (read-only)

```bash
node server/scripts/debug_transactions.js 7 90
```

(Prisma `findMany`/`findUnique` queries against `Ticker`, `Position`,
`Lot`, and `Account` tables were also run via ad hoc, since-deleted
scripts — no writes.)

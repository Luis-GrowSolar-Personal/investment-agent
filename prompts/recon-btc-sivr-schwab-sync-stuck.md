# Recon: why BTC/SIVR stay permanently out-of-sync after a re-baseline execution

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-btc-sivr-schwab-sync-stuck-out.md`. This is recon
only — **do not sync, reconcile, or write anything to the database.**
Luis is deliberately preserving Andrea's account in its current
out-of-sync state as evidence and does not want it touched. State the
root cause up front, then back it with the raw transaction data and the
exact code path. Write for someone reading cold later.

## Context

Luis ran a re-baseline on Andrea Morales's Custodial (taxable) account
last week. After executing the recommended trades at Schwab, two
problems showed up and one of them is still unresolved:

1. Several equity tickers (MSFT, GOOGL, ORCL, ENVX, AMPX, AMZN, NVDA,
   AMD) initially prompted for manual cost-basis entry, then a few days
   later this resolved itself — the app started showing "Refreshed
   Schwab-estimated lot... share count differs (review required)"
   instead of blocking on manual entry.
2. Two positions — **BTC** (Grayscale Bitcoin Mini Trust ETF) and
   **SIVR** — are still stuck, days later, showing "no matching
   transaction in the last 60 days; may be one lot or several, enter
   manually."

Confirmed directly from the Schwab UI (screenshots) and the app's local
lot table for BTC:

- **Schwab** shows 3 lots for BTC: 71.9957 sh opened 08/17/2026 @
  $28.34/share (cost basis $2,040.00 — this is presumably the
  re-baseline-triggered buy), plus two older lots (4 sh, 34 sh) dated
  11/22/2024 and 11/11/2024. Total 109.9957 shares.
- **Local (the app)** only knows about the two older lots — 4 sh and 34
  sh, both tagged **source: MANUAL**, dated Nov 21/22 2024 and Nov
  10/11 2024 (note: local dates are one day earlier than Schwab's —
  worth noting but probably not the main issue, flag it separately if
  it turns out to matter). Total 38 shares. The 71.9957-share lot from
  the re-baseline execution never made it into the local `Lot` table at
  all.
- The account summary line for SIVR shows the same pattern: Schwab
  21.876 vs local 12, diff +9.876, same "no matching transaction"
  message.

Luis's questions, verbatim: "Shouldn't the API be able to pull those
[cost bases] in?" and "Not sure how these are getting out of sync,"
plus a broader concern: re-baseline execution shouldn't require this
much manual reconciliation afterward.

## What to check (all read-only)

1. Read `server/lib/schwabSync.js` around the diff-resolution logic
   (`hasManualOrImportLots` branch vs. the schwab-only-lots branch —
   roughly lines 359-440 as of this session, confirm current line
   numbers). Explain in plain terms, for Luis, why BTC/SIVR are
   following a **different, stricter code path** than the equity
   tickers that self-resolved: BTC/SIVR each have pre-existing
   `source: 'manual'` lots (the original 4sh/34sh entries, presumably
   entered before Schwab sync existed for this account), which routes
   any new diff through the `hasManualOrImportLots` branch — this
   branch REQUIRES an exact single-transaction match from Schwab's
   transaction history (`ensureRecentTrades()` /
   `candidates.find(t => Math.abs(t.shares - diff) / diff < 0.0001)`)
   and has **no fallback** if no exact match is found; it just parks
   the diff in `positionDiffs` for manual entry, indefinitely. The
   equity tickers, by contrast, apparently have only `source: 'schwab'`
   lots, which routes them through the more lenient "full-replace with
   an estimated cost basis, flagged for review" branch — this ALWAYS
   resolves (using `schwabPos.averagePrice`), it just may need a manual
   review/correction afterward. Confirm this theory directly by
   querying the current `Lot` rows for BTC, SIVR, and 2-3 of the
   equity tickers Luis mentioned (MSFT, AMD) — check their `source`
   field and `notes` to see which code path actually produced them.
2. **Use the existing `server/scripts/debug_transactions.js` script**
   (confirmed read-only — it only calls `getTransactions`, no writes)
   to pull Andrea Custodial's raw Schwab transaction history for the
   last 90 days:
   `node server/scripts/debug_transactions.js <Andrea's Custodial accountId> 90`
   Find the BTC and SIVR opening trades in the raw output and check:
   - Does Schwab's transaction feed actually contain the 71.9957-share
     BTC trade (and the SIVR one) at all within the window?
   - What is `txn.type` for that transaction — is it `'TRADE'` (the only
     type `ensureRecentTrades()` looks at)?
   - What is `item.positionEffect` for the relevant transfer item — is
     it exactly `'OPENING'` (the only value the matching code accepts)?
   - What is `item.instrument?.symbol` for that leg — does it match the
     position-level `symbol` (`'BTC'`) exactly, or could this
     particular Grayscale Bitcoin Mini Trust ETF report under a
     different symbol/CUSIP in the transaction feed than in the
     positions feed? This is the single most likely culprit — check it
     carefully and quote the actual raw value.
   - Is `item.price` populated (non-null) for this transaction?
   - Was the 71.9957-share buy possibly executed as multiple separate
     fills/legs at Schwab (common for less-liquid ETFs) rather than one
     trade — meaning no SINGLE trade would ever match the full diff,
     even though the data is present? Sum the relevant legs and check.
3. Based on what's actually in the raw transaction data, give a
   definitive answer: is this a **symbol-matching bug** (transaction
   feed uses a different symbol string than the positions feed),
   a **multi-fill-not-summed bug** (the matcher only checks single
   trades, never sums multiple same-day fills), a **missing-fallback
   design gap** (working as coded, but the "no fallback for
   manual-lot positions" behavior is simply worse UX than the
   schwab-only-lot path), or something else entirely (e.g., the
   transaction genuinely isn't in Schwab's feed for some account/API
   reason). Don't guess — ground the answer in the actual data pulled
   in step 2.
4. Explain the "cost basis prompts went away after a few days" part of
   Luis's report too: did the equity tickers actually get their diffs
   correctly `autoResolvedAdds`-matched on a later sync (once
   settlement caught up), or did they just fall into the always-succeeds
   "estimated lot, flagged for review" branch and LOOK resolved without
   ever getting the real Schwab cost basis? Check the `notes` field on
   those Lot rows — `"Auto-resolved from Schwab transaction history..."`
   means real data; `"Estimated from Schwab sync..."` means it's a
   guess using `averagePrice`, not the real per-lot cost basis. This
   matters for Luis's tax-cost-accuracy concerns (Principle 5 —
   every trim needs an accurate tax cost calculation, which depends on
   accurate cost basis).

## Constraints — read carefully

- **Do not call `syncAccount`, the `/api/schwab/reconcile` or
  `/api/schwab/match` endpoints, Force Sync, or any other route/script
  that writes to `Position`, `Lot`, or `Account` rows for Andrea's
  account (or any account).**
- `debug_transactions.js` is confirmed read-only (only calls
  `getTransactions`) — safe to run as-is.
- If you need to inspect current `Lot`/`Position` data, use a read-only
  Prisma query (`findMany`/`findFirst`) — never `create`/`update`/
  `delete`/`upsert`.
- Do not commit or push anything — there should be no code changes from
  this task at all, purely investigation and a report.
- In the wrap-up, explicitly confirm no writes were made (e.g., "no
  Lot/Position rows were created, updated, or deleted during this
  recon" — state it plainly so Luis can trust the evidence is intact).

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-btc-sivr-schwab-sync-stuck-out.md` existing, with the
raw transaction data for BTC/SIVR quoted directly, the definitive root
cause, and the explicit no-writes-made confirmation.

# Recon: MSFT's bucket override doesn't persist — always reverts to ETF

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-msft-bucket-override-not-persisting-out.md`. This is
recon — find the definitive mechanism before proposing any fix. If the
fix is obvious and low-risk once you've found the cause, you may
implement it (state that up front in the wrap-up and follow the normal
commit/push convention); if it's more involved, stop and report instead.
Write for someone reading cold later.

## Context

MSFT (Microsoft, a plain equity) is misfiled under the "ETFs" tab in
Andrea Custodial's local portfolio view, alongside QQQ and TMFC.
Schwab correctly shows it under Equities.

**Why it was originally misfiled — already understood, not the
question here.** `smartDefaultBucket()` (`server/lib/portfolioImport.js`)
only recognizes the ticker as an equity if the asset type string is
exactly `'Equity'`; anything else (including an unrecognized or
unnormalized Schwab asset-type value) silently falls through to the
`'etf'` default. MSFT's `Ticker` row apparently got `bucketOverride`
backfilled to `'etf'` this way when it was promoted from watchlist to
portfolio status (`server/lib/schwabSync.js`, the
`ticker.status === 'watchlist'` branch, ~line 489-505 as of this
session) — the backfill is guarded by `if (ticker.bucketOverride ==
null)`, so this only fires once, when `bucketOverride` is still unset.

**The actual question:** Luis opened the bucket picker (`BucketPill` in
`client/src/pages/Portfolio.jsx`) and selected a different bucket for
MSFT — this calls `handleBucketChange` → `PATCH
/api/portfolio/tickers/:id/bucket` → `server/routes/portfolio.js`'s
handler, which does a plain, unconditional
`prisma.ticker.update({ where: { id }, data: { bucketOverride: bucket } })`.
On the surface this looks correct and unconditional — there's no
obvious guard that should prevent it from sticking. But after making the
change, MSFT reverts to (or never leaves) the ETF bucket.

## What to check — don't guess, trace the actual live behavior

1. **Does the PATCH request actually succeed and write the right row?**
   Manually exercise `PATCH /api/portfolio/tickers/:id/bucket` for
   MSFT's actual ticker ID against the live/dev environment (confirm
   which `id` MSFT actually has first via a read-only query) and check
   the HTTP response and the resulting DB row immediately after
   (read-only Prisma query). Does `bucketOverride` actually change in
   the database?
2. **If it DOES change and persist in the DB, but the UI still shows
   ETF** — this is a display/caching issue, not a persistence issue.
   Check how the Portfolio page loads position data (`GET
   /api/portfolio/...` — find the actual route) and whether
   `effectiveBucket` is computed fresh on every load or whether
   something (a cached response, a stale client-side state update,
   `onRefresh()` firing before the PATCH's transaction is visible, etc.)
   could show pre-update data. Also check whether there might be TWO
   `Ticker` rows for symbol `MSFT` (there shouldn't be — `Ticker.symbol`
   is `@unique` — but confirm directly rather than assuming the schema
   constraint was never violated by some earlier import path).
3. **If it DOES persist correctly and the UI does read it correctly**,
   check whether something runs AFTER the user's change and resets it —
   most likely a subsequent Schwab sync. Re-read the
   `ticker.status === 'watchlist'` backfill guard
   (`if (ticker.bucketOverride == null)`) very carefully — confirm it
   really is `== null` and not something that could evaluate true again
   after a user sets an override (e.g., if `bucket: null` is ever
   accidentally written back somewhere, resetting the guard condition).
   Also check the "brand-new position" ticker-creation path (~line
   466-488) — this only runs when the ticker doesn't exist yet, so
   shouldn't refire for an existing MSFT ticker, but confirm there isn't
   a different code path (CSV import, a "resync tickers" admin action,
   anything else that writes `bucketOverride`) that could still be
   firing unconditionally somewhere else in the codebase. Search the
   whole repo for `bucketOverride` writes, not just `schwabSync.js`.
4. **Reproduce end-to-end**: set MSFT's bucket to `equity` via the PATCH
   route directly, confirm it's correct in the DB, then trigger a real
   Force Sync on Andrea's Custodial account and check whether the
   override survives that sync. This isolates whether the sync itself
   is the culprit versus something else.

## Constraints

- Prefer read-only checks first. If reproducing requires triggering a
  real sync (step 4), that's expected and fine — writing to `Ticker`
  rows for bucket classification is low-risk (doesn't touch `Lot`/tax
  data), but say clearly in the wrap-up what was written and confirm the
  end state.
- If you find the cause and it's a simple, obvious, low-risk fix (e.g.,
  a stray unconditional write, or a caching bug with a clear fix), go
  ahead and fix it — say so plainly in the wrap-up. If it's more
  involved or ambiguous, stop and report instead of guessing.

## Commit and push (only if you made a fix)

```bash
git add -A
git commit -m "Fix MSFT-style bucket override not persisting across sync/reload"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-msft-bucket-override-not-persisting-out.md` existing,
with the definitive mechanism (not a guess) and whatever fix (if any)
was applied.

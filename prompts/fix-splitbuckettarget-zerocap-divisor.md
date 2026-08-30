# Fix: splitBucketTarget divides by zero-cap ticker count, stranding target %

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-splitbuckettarget-zerocap-divisor-out.md`.

## Context

Confirmed via two independent recon passes and a live, hands-on
experiment (2026-08-25) — this is not a hypothesis, it's a proven bug.

`splitBucketTarget` (`server/routes/moves.js` ~lines 1224-1238) divides
a fixed bucket's target percentage (ETF 25%, Crypto 10%, Commodities 5%
in the accounts tested) by `groups.length` — the count of every
currently-held ticker whose `getBucket()` resolves to that bucket —
with **no filter for tickers that can't actually claim any of the
target** (zero effective cap, and/or `inScope: false`).

**Proven live:** Andrea Morales's account picked up two new,
unclassified tickers (QGRW, SOLZ — both `capPercent: 0`) via a Schwab
sync after a Full Reset. Both landed in the ETF bucket alongside her two
real ETF holdings, QQQ and TMFC. The divisor became 4 instead of 2,
cutting QQQ and TMFC's fair target from a true ~10% each down to 8.33%
each, generating large, unwarranted TRIM recommendations on both —
confirmed via `server/scripts/dumpMovesForOwner.js` before Luis manually
capped QGRW/SOLZ (`tgt=8.33%`/`tgt=8.30%` on QQQ/TMFC) and the expected
correct values after manually assigning real caps to QGRW/SOLZ
(`tgt=8.30%` on all three ETF-bucket members once QGRW became a
legitimate 3rd member — a *different*, correct scenario from the
zero-cap case this fix addresses). Full detail in
`wrap-ups/recon-andrea-eduardo-fullreset-divergence-out.md` and this
session's live-verification exchange.

**Important: Andrea and Eduardo's accounts will NOT visibly change
after this fix**, because Luis already manually gave QGRW and SOLZ real
caps on both accounts as a workaround. This fix is protective against
the *next* occurrence — any future Schwab sync that creates a new,
unclassified ticker in a fixed-target bucket (ETF, Crypto, or
Commodities) should no longer be able to dilute the targets of
unrelated, already-classified tickers in that same bucket.

## What to build

In `splitBucketTarget` (and confirm the same fix applies identically at
all three call sites — ETF, Crypto, Commodities, per the earlier recon's
note that "the same function is used for the crypto and commodity
buckets"):

1. Exclude tickers with **zero effective cap** (resolve the cap the same
   way the rest of this function already does — check `ownerCapMap`
   first, fall back to `ticker.capPercent`, same pattern as the existing
   `configuredCap` line) from `groups.length` before computing
   `evenShare`.
2. Also consider whether `inScope: false` tickers should be excluded
   independently of cap (a ticker could theoretically have a nonzero
   cap but still be explicitly out of scope) — check how `inScope` is
   used elsewhere in this file for consistency (e.g. the eligibility
   gates fixed in tasks #39/#40) and apply the same standard here. If
   the two conditions (zero cap vs. `inScope: false`) can diverge in
   practice, exclude on **either** condition being true, and say so
   explicitly in the wrap-up.
3. **Excluded tickers still get their own target computed and still
   generate their own move** (their target should still correctly
   resolve to their own — now-excluded-from-the-divisor — cap, which
   for a genuinely-zero-cap ticker is still $0, i.e. still a full-exit
   recommendation). This fix changes the **divisor**, not whether an
   excluded ticker gets its own row. Do not suppress or hide moves for
   excluded tickers.

## What NOT to do

- Do not touch the ticker classifier / `smartDefaultBucket()` — there's
  a separate, already-flagged issue where SOLZ-like tickers silently
  default to 'etf' instead of 'crypto' (noted in
  `recon-andrea-eduardo-fullreset-divergence-out.md`'s sibling
  investigation this session). Out of scope here; note it in the
  wrap-up as still-open if you want, but don't fix it.
- Do not touch anything related to task #77 (the freshStart-vs-normal-
  mode sizing-formula divergence) — a separate, deeper, not-yet-decided
  design question. This fix is scoped strictly to the divisor bug.
- Do not change QQQ/TMFC/QGRW/SOLZ's actual current caps/classifications
  on Andrea or Eduardo's accounts — Luis already fixed those by hand;
  this is a code fix for future occurrences, not a data cleanup task.
- Do not touch `annotateAddFunding`, the cash/trim-proceeds ledgers, or
  anything in the ADD-routing chain from earlier this project — unrelated
  layer.

## Verify

1. **Reproduce the bug first, on a scenario where it still applies.**
   Andrea/Eduardo no longer exhibit it (both zero-cap tickers were
   manually fixed), so construct a fresh, read-only-safe repro: either
   find or temporarily seed (and restore afterward, same discipline as
   prior sessions' throwaway-script pattern) a ticker with `capPercent:
   0` newly held in a bucket alongside real, classified holdings, and
   confirm — using `server/scripts/dumpMovesForOwner.js` — that the real
   holdings' targets are currently understated by the divisor bug.
2. Apply the fix, re-run the same script, and confirm the real holdings'
   targets return to their correct, undiluted value, while the
   zero-cap ticker still generates its own (correctly $0) move.
3. **Regression-check Andrea and Eduardo specifically** — since they no
   longer have any zero-cap tickers in their buckets, confirm
   `dumpMovesForOwner.js` output for both is **byte-identical before and
   after** this fix (QQQ/TMFC/QGRW/SOLZ/BTC targets unchanged). This is
   the key "did I break the now-correct case" check.
4. Confirm the fix applies identically to the Crypto and Commodities
   buckets, not just ETF — construct or find a comparable scenario for
   at least one of the other two buckets if possible; if not reproducible
   live, confirm by code inspection that the same exclusion logic is
   shared/applied consistently across all three call sites.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` — confirm output
   matches the tracked task-#50 baseline (this fix should not change
   the pre-existing, unrelated baseline failures).

## Commit and push

```bash
git add -A
git commit -m "Exclude zero-cap/out-of-scope tickers from splitBucketTarget's divisor"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-splitbuckettarget-zerocap-divisor-out.md` existing, with
the before/after repro from item 1-2 shown explicitly, and item 3's
Andrea/Eduardo no-regression check confirmed.

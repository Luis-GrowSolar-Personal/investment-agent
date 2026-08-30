# Fix: fund ADD rows in a fixed priority order, not generation order

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-add-routing-funding-priority-order-out.md`.

## Context

`fix-add-routing-cash-double-counting` (commit `844e3c7`) added a
per-run, per-account cash ledger (`availableCash`/`commitCash` in
`server/routes/moves.js`) so ADD rows stop overlap-claiming the same
idle cash. That fix deliberately did NOT decide funding order — it
reported, as a finding, that the *current* order (an artifact of
generation sequence: fixed buckets, then individual tickers, then
freshStart/scarcity-gap blocks) funds bucket-level "unallocated"
rows (ETF/Crypto/Commodities — rows where the agent doesn't even pick a
ticker) **before** real, conviction-scored ticker ADDs, and that among
ticker ADDs, order is arbitrary database row order rather than
conviction/priority.

`fix-add-routing-honest-funding-note` (commit `7a75576`) built an
honest display split (`fromCash`/`expectedFromTrims`/`unbacked`) on top
of whatever the ledger already decided, but did not change the ledger's
commit order either.

**Luis has now decided the order.** This task implements it:

> Highest-conviction Established → highest-conviction Speculative → ETF
> (unallocated) → Commodities (below minimum) → Crypto (unallocated)

## What to build

1. **Find the existing conviction/ranking signal for held-ticker ADD
   candidates.** `844e3c7`'s wrap-up referenced "the same ranking the
   engine already computes (`priority`, or conviction/rank score)" —
   confirm the actual field/computation used to rank Established and
   Speculative ADD candidates against each other today (search
   `generateMovesForTicker`, `individualGroups`, and wherever
   candidates are scored/sorted for freshStart selection — that scoring
   already exists somewhere in this file for choosing *which* tickers
   become ADD candidates in the first place). Use that same signal for
   ordering — don't invent a second, different ranking. If genuinely no
   such signal exists for one of the buckets, stop and report rather
   than guessing at a proxy.
2. **Restructure so cash-ledger commits happen in the priority order
   above, decoupled from move-generation order.** The ledger commit
   (`commitCash`, inside `buildAddRouting`/`buildNewPositionRouting`)
   currently fires interleaved with generation, in generation's own
   order. The likely shape: separate "decide what ADD is needed and for
   how much" (sizing — can stay in existing generation order, unchanged)
   from "commit against the shared cash ledger" (routing — needs to run
   as an explicit ordered pass over all ADD-needing rows, sorted per the
   priority above, after sizing is complete for the whole run). This is
   the same kind of post-pass structure `annotateAddFunding` already
   uses in `7a75576` — read that function first, it may be a template
   for how to sequence a second pass cleanly. Confirm with a trace
   whether sizing and routing are cleanly separable in the current code,
   or tangled — report if tangled rather than forcing a fragile split.
3. **Within Established and within Speculative, sort by the conviction
   signal from item 1, descending** (highest conviction gets first claim
   on idle cash).
4. **Bucket-level rows (ETF, Commodities, Crypto) are NOT ranked against
   each other by conviction** — Luis's order fixes their relative
   sequence explicitly (ETF, then Commodities, then Crypto), regardless
   of dollar size or any other signal.
5. Confirm `annotateAddFunding`'s `fromCash`/`expectedFromTrims`/
   `unbacked` split (from `7a75576`) still computes correctly once the
   ledger commit order changes — it should, since it consumes whatever
   `fromCash` the ledger produced, but verify rather than assume.

## What NOT to do

- Do not change which tickers/buckets get ADD recommendations, or the
  dollar amounts — this is scoped entirely to the order in which
  existing recommendations claim available cash.
- Do not change the final display order of moves in the payload (the
  prompt for `844e3c7` noted the payload is priority-sorted at the end,
  separately from generation order — that display sort is unaffected
  unless you find a reason it must change; if so, report it, don't
  silently alter it).
- Do not add gating/disabled buttons — unrelated to this task, already
  explicitly rejected in the prior two fixes.
- Do not touch `annotateAddFunding`'s trim-proceeds limitation (the
  known issue where `expectedFromTrims` can be cited by more than one
  row) — separate, already-documented, out of scope here.

## Verify

1. Live-data check for Andrea (or whichever owner currently best
   illustrates it) confirming the new order: Established ADDs get first
   claim on idle cash, then Speculative, then ETF/Commodities/Crypto in
   that fixed sequence — show the actual before/after routing for a
   scenario where multiple rows compete for the same account's cash
   (Andrea's freshStart ETF/Crypto/QS collision from `844e3c7`'s wrap-up
   is a known example, if still reproducible).
2. Confirm within-bucket ordering (Established-vs-Established,
   Spec-vs-Spec) matches the conviction signal found in item 1 — show
   the actual values for at least one multi-candidate case.
3. Confirm the cash-ledger invariant from `844e3c7` still holds (no
   account's total routed cash exceeds its real balance) — this should
   be unaffected by reordering, but re-verify, don't assume.
4. Confirm `annotateAddFunding`'s split arithmetic (`fromCash +
   expectedFromTrims + unbacked == requested`) still holds for all ADD
   rows across all three owners, both modes — same check `7a75576`'s
   wrap-up already ran, rerun it here.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` — display/routing
   -order-only change, no writes expected; confirm output matches the
   tracked task-#50 baseline.

## Commit and push

```bash
git add -A
git commit -m "Fund ADD rows in priority order: Established -> Speculative -> ETF -> Commodities -> Crypto"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-add-routing-funding-priority-order-out.md` existing,
with the conviction-signal source (item 1) explicitly named and cited.

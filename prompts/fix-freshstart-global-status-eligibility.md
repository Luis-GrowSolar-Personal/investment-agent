# Fix: `freshStart` candidate eligibility incorrectly gated by global `Ticker.status`

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-freshstart-global-status-eligibility-out.md`. State the
fix up front, then show a live before/after run of `freshStart` for
Andrea Morales and Eduardo Morales confirming ENVX now appears in
Andrea's candidate pool and AMD/AVGO now appear in Eduardo's. Also
include the separate QS tier-classification investigation (section 3
below) — that part is recon only, not a fix. Write for someone reading
cold later.

## Context

Confirmed via `wrap-ups/recon-freshstart-candidate-pool-divergence-out.md`:
Luis equalized Andrea's and Eduardo's `OwnerProfile` settings exactly
(same equities/ETF/crypto/commodities/cash split, same estSpecRatio, same
caps, same domains — verified with `server/scripts/compareOwnerProfiles.js`)
and ran `freshStart` re-baseline on both, expecting near-identical
holdings scaled by their ~1.2% portfolio-size difference. Instead, ENVX
never appeared anywhere in Andrea's candidate pool, and AMD/AVGO never
appeared in Eduardo's — not ranked, not rejected, just absent.

Root cause, already diagnosed and quoted in the recon wrap-up:
`Ticker.status` (`'watchlist'` | `'portfolio'`) is a single global column
per ticker, not per-owner. Once ANY owner holds a ticker, its status
flips to `'portfolio'` everywhere. `freshStart`'s non-held candidate
pool is sourced from `prisma.ticker.findMany({ where: { status:
'watchlist', ... } })` — so a `'portfolio'`-status ticker is invisible to
every owner who doesn't happen to hold it themselves (their own
`byTicker`-driven held-loop doesn't cover it either, since they don't
hold it). This directly contradicts the `freshStart` design intent,
quoted in the code's own comment: "Held equities compete on equal
footing with watchlist candidates — no preference to what's currently
held (Luis, confirmed)."

Read the actual current source in `server/routes/moves.js` around the
`freshStart` branch (`fsWatchlistTickers`, `fsUniverse`, `fsEligible`,
`individualGroups`/`byTicker`) before changing anything — this describes
intent based on the recon's quotes, confirm the real current shape first,
since this file has been touched by several sessions.

## Fix 1 (primary): stop using `Ticker.status` to gate freshStart eligibility

`freshStart`'s candidate universe should be: every `inScope` ticker with
a qualifying `Analysis` (`fsEligible`), period — split only by "does THIS
owner already hold it" (→ held-loop, sourced from `byTicker`) vs "does
this owner not hold it" (→ needs-sourcing loop). `Ticker.status` describes
a promotion-workflow state (has *some* owner's Schwab sync promoted this
ticker out of pure-watchlist), not eligibility, and should play no role
in who can consider it as a fresh-build candidate.

Concretely: change the non-held candidate query from
`prisma.ticker.findMany({ where: { status: 'watchlist', inScope: { not: false } } })`
to something that pulls ALL `inScope` tickers (regardless of `status`),
then filters to `!byTicker.has(t.id)` (this owner doesn't already hold
it — which the code already does downstream) so a ticker held by some
other owner is now correctly available as a "new-open" candidate for an
owner who doesn't hold it. Read the exact current query and filtering
chain before editing — confirm there isn't a reason `status` was checked
there that the recon didn't catch (e.g. performance, or excluding a
different kind of row) before removing it.

**Important scope note:** only change this for the `freshStart` path.
The NORMAL (non-freshStart) watchlist-candidate path may have its own
reasons to filter by `status: 'watchlist'` (e.g. it might be intentional
there that a `'portfolio'`-status ticker isn't re-suggested as a fresh
"new open" in the everyday incremental flow, since Principle 9 already
prioritizes existing holdings over new opens and a portfolio-status
ticker not held by this owner is a genuinely different situation there).
Don't touch the normal path's query unless investigation shows it has
the identical bug — if so, flag it in the wrap-up rather than silently
also fixing it, since that's a separate decision.

## Fix 2 (secondary): `inScope` isn't checked for held tickers

Also confirmed in the recon: the held-loop (tickers this owner already
holds) doesn't check `inScope` at all, while the non-held/watchlist loop
does. This means an out-of-scope ticker (e.g. BYDDY, `inScope: false`)
still competes for a `freshStart` slot if the owner happens to hold it,
while being correctly excluded for every other owner. This is a real
inconsistency and arguably violates `CLAUDE.md`'s explicit "Never Do:
Recommend positions outside the circle of competence" — a held ticker
that's fallen out of scope shouldn't get a fair shot at a fresh-build
slot just because it's already owned; it should be treated like any
other now-out-of-scope position (a candidate for exit, not for
re-selection). Add the same `inScope` check to the held-loop's
eligibility gate. Confirm this doesn't change any OTHER currently-in-scope
held ticker's treatment — this should only affect tickers with
`inScope: false`.

## Verify

1. Rerun `computeMovesPayload('Andrea Morales', { bypassWinnerProtection: true, freshStart: true })`
   and the same for Eduardo, directly (no HTTP). Confirm ENVX now appears
   in Andrea's `fsUniverse` (ranked, whether or not it wins a slot) and
   AMD/AVGO now appear in Eduardo's. Paste the new ranked candidate
   tables, same format as the recon wrap-up, for both owners.
2. Confirm BYDDY (held by Eduardo, `inScope: false`) no longer competes
   for a slot in Eduardo's `fsUniverse` after Fix 2 — it should still end
   up EXITed (same visible outcome as before), but now because it's
   correctly gated out from the start, not because it lost a fair
   ranking it should never have had.
3. Run `./server/scripts/verify-allocation-math.sh` before and after —
   confirm no regressions on the normal (non-freshStart) reconciliation
   pattern for any owner, and confirm the freshStart pass still
   reconciles the same way it did in `wrap-ups/build-rebaseline-full-reset-mode-out.md`
   (bucket totals, not ticker selection, should be unaffected by this fix
   — this changes WHICH tickers compete, not how much money each bucket
   targets).
4. Sanity-check one more owner (Luis Morales) to confirm the fix doesn't
   introduce anything unexpected for a three-way candidate pool (a
   ticker held by two of three owners, etc.).

## Commit and push

```bash
git add -A
git commit -m "Fix freshStart candidate eligibility: stop gating on global Ticker.status, add inScope check to held-ticker loop"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## 3. Separate investigation (recon only, no change without Luis's go-ahead): why is QS classified 'established'?

Luis's read: QS (QuantumScape) is pre-revenue, a bet on unproven
solid-state battery tech reaching commercial scale — that's about as
textbook "speculative" as a thesis gets, not "established." He wants to
understand why RADAR classifies it `tier: 'established'`.

Look up QS's `Ticker` row: is `tierOverride` set (a user override), or
is it falling back to the latest `Analysis.tier`/`tierMechanical` (the
3-axis mechanical classifier's output, per `analysis/trend_analyst.py`
and the `tierMechanical` field described in the Prisma schema)? Report:

- The current effective tier and where it's coming from (override vs
  mechanical).
- If mechanical: what the three axes are and what specifically about
  QS's data pushed it toward "established" rather than "speculative" —
  quote the classifier logic, don't just describe it in general terms.
- Whether `tierRationale` (the user's own reasoning field, if ever set)
  has anything relevant already recorded.

**Do not change QS's classification.** This is purely to explain the
current state so Luis can decide whether to set `tierOverride` manually
(the existing mechanism for exactly this kind of manual correction) — a
classification change is his call, not something to silently correct as
part of this fix.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-freshstart-global-status-eligibility-out.md` existing,
with both the fix verification and the QS tier explanation included.

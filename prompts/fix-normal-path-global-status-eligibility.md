# Fix: normal (non-freshStart) watchlist-candidate eligibility has the same global-`Ticker.status` bug

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-normal-path-global-status-eligibility-out.md`. State the
fix up front, then show before/after evidence that a ticker held by one
owner but not another is now a correctly eligible new-open candidate for
the non-holding owner in the everyday (non-freshStart) recommended-moves
flow. Write for someone reading cold later.

## Context

`wrap-ups/fix-freshstart-global-status-eligibility-out.md` fixed this
exact bug for `freshStart` mode: the non-held candidate query filtered on
`status: 'watchlist'`, but `Ticker.status` is a single global column —
once ANY owner holds a ticker, it flips to `'portfolio'` everywhere,
silently making it ineligible as a "new open" candidate for every OTHER
owner who doesn't hold it, even though nothing about their own situation
changed. That wrap-up flagged (but explicitly did not fix, per its own
scope) that the identical `status: 'watchlist'` filter also exists in the
normal, everyday (non-freshStart) watchlist-candidate query — around
`server/routes/moves.js` line ~1432 as of that session.

Luis has now confirmed: this should be fixed the same way in the normal
path too. His reasoning, verbatim: "The non-freshStart should not block
selecting certain equities 'because they are in someone else's bucket' —
if the same thing we just fixed for Reset is happening in re-baseline, we
need to fix it." A ticker being held by Andrea should never be the
reason Eduardo can't be shown it as a legitimate new-open candidate, in
ANY mode — incremental re-baseline or full reset.

Read the actual current source in `server/routes/moves.js` before editing
— confirm the line number and exact query shape (the freshStart fix
session already touched this file; the normal path's query may or may
not have shifted).

## The fix

Apply the same change made for `freshStart`: change the normal-path
non-held candidate query from filtering on `status: 'watchlist'` to
pulling all `inScope` tickers, then relying on the existing
`!byTicker.has(...)`-style filter (whatever the normal path's equivalent
is) to scope by "does this owner already hold it."

**Important — this is NOT the same as removing Principle 9.** Principle
9 (existing positions before new — `docs/architecture/DESIGN_PRINCIPLES.md`)
governs FUNDING PRIORITY: when there's freed capital to deploy, an
existing underweight position gets funded before a brand-new open, even
if the new one scores higher. That's a separate mechanism
(`buildCapitalFlow`'s `addUses` before `promUses`) from ELIGIBILITY
(which tickers are even considered as candidates in the first place).
This fix only widens the second thing — it does not change funding
order. Confirm this distinction holds in the actual code: the eligibility
query feeds into which tickers exist in the candidate list at all;
`buildCapitalFlow`'s ordering is a separate downstream step that still
runs unchanged. If touching the eligibility query turns out to also
require touching `buildCapitalFlow` for the fix to behave sensibly, stop
and report that rather than guessing — it would mean the two are more
coupled than this prompt assumes.

Also check: does the normal path's held-ticker loop have the same missing
`inScope` check that Fix 2 addressed for `freshStart`? If so, apply the
same fix there too (an out-of-scope held ticker shouldn't get funding
priority via Principle 9 either). If the normal path already checks
`inScope` on held tickers, just confirm and note that in the wrap-up —
don't add a redundant check.

## Verify

1. Pick a concrete case: a ticker held by one owner (e.g. AMD, held by
   Andrea) and not by another (Eduardo). Run the NORMAL (non-freshStart)
   moves computation for Eduardo before the fix — confirm AMD does not
   appear anywhere in his candidate list (same absence pattern as the
   freshStart bug). After the fix, confirm AMD is now a real, ranked
   candidate for Eduardo in the normal flow (whether or not it actually
   wins funding — that's Principle 9's call, not this fix's).
2. Run `./server/scripts/verify-allocation-math.sh` before and after for
   all three owners. The **normal** (non-freshStart) reconciliation rows
   are the ones this fix could plausibly move — confirm nothing
   regresses, and note if any previously-passing bucket's numbers shift
   (that's expected here, since the eligible pool just got bigger for
   some owners — explain any shift, don't just report it as a bare
   diff).
3. Confirm the `freshStart` reconciliation rows are completely unaffected
   by this change (this fix only touches the normal path's query).
4. Re-verify BYDDY-style out-of-scope-but-held cases still behave
   correctly in the normal path (same check as Fix 2 did for freshStart,
   if applicable here).

## Commit and push

```bash
git add -A
git commit -m "Fix normal (non-freshStart) candidate eligibility: same global Ticker.status bug fixed for freshStart"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-normal-path-global-status-eligibility-out.md` existing,
with the before/after evidence for the concrete AMD/Eduardo-style case
and the full reconciliation script output.

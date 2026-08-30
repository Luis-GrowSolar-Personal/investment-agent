# Recon: "Remove" doesn't actually remove a position (29415C127 example)

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-position-remove-not-working-out.md`. Find the
definitive mechanism before proposing a fix. If it's an obvious,
low-risk fix once found, implement it (say so up front, follow the
commit/push convention below); if not, stop and report. Write for
someone reading cold later.

## Context

Andrea Custodial has a position, symbol `29415C127` — a CUSIP-style
placeholder representing a rights offering to purchase EOSE shares at a
set price, which Luis never exercised. It's no longer in his Schwab
account at all (confirmed: the reconcile view lists it under "Local-only
(not in Schwab)"). Its one lot: 902 shares, `$0.00` cost basis,
`source: 'schwab'`, acquired "Aug 4, 2026", notes say "Estimated from
Schwab sync..." — so this was created by a past sync at some point when
Schwab still reported it.

Luis clicked the "Remove" button (🗙) on this position in the Portfolio
page's Equities tab, confirmed the "Remove 29415C127 from tracking?
This does not generate a taxable event" dialog — and the row is still
there afterward.

## What's already understood, not the question here

`DELETE /api/portfolio/positions/:id` (`server/routes/portfolio.js`,
~line 409) is a soft delete: `prisma.position.update({ data: { status:
'closed', closedAt: new Date() } })`. The list route, `GET
/api/portfolio/accounts/:id/positions` (~line 247), filters `where: {
accountId, status: 'active' }` — so on paper, a successful soft-delete
should make the row disappear from this exact list. The mismatch between
"this should work" and "it doesn't" is the actual question.

## What to check, in order — trace the live behavior, don't guess

1. **Does the DELETE request actually fire and succeed?** Find
   29415C127's real `Position.id` for Andrea Custodial (read-only
   query), then call `DELETE /api/portfolio/positions/:id` directly
   against it (or watch it happen via the UI if that's easier) and check
   the HTTP response and the resulting DB row immediately after. Does
   `status` actually become `'closed'`?
2. **If the DELETE succeeds and the DB shows `status: 'closed'`, but the
   row still shows in the UI** — this points at either a stale client
   fetch (`onRefresh()` not actually refetching, or a race), or
   something ELSE flipping the status back to `'active'` shortly after.
   Check whether any sync path could reactivate a `'closed'` position —
   grep for every place `Position` gets `update`d with
   `status: 'active'` (there's at least one in `schwabSync.js`'s
   position-creation/promotion logic, and the recent full-exit fix
   touched a related area — confirm neither of those (or anything else)
   could fire for a `'closed'`, Schwab-absent position and flip it back).
3. **If the DELETE call never fires at all**, check the frontend —
   `handleDeletePosition` in `client/src/pages/Portfolio.jsx` and
   whatever renders the confirmation dialog and its "Remove" button —
   for a wiring bug (wrong id passed, event not bound, silent fetch
   failure not surfaced to the user because the response isn't checked
   for `res.ok`).
4. **Consider whether "local-only, source: schwab" positions like this
   one deserve different handling than a manual soft-delete at all** —
   given the full-exit auto-accept fix from earlier this session
   (`wrap-ups/fix-auto-accept-full-exit-trim-out.md`) already handles
   "Schwab no longer reports this symbol" for positions with real share
   counts by auto-closing lots. Check whether that same code path
   should also apply here (it currently only fires for the *live sync*
   detecting a NEW absence, not for a position already sitting
   local-only) — but don't conflate the two without evidence; first find
   out why the plain manual "Remove" button itself isn't working, since
   that's the immediate complaint.

## Constraints

- Prefer read-only checks first (query current state, don't write).
- If reproducing requires actually calling DELETE against this real
  position to observe behavior, that's fine and expected — it's exactly
  what Luis is trying to do (remove a position that's already gone from
  Schwab, doesn't generate a taxable event per the app's own confirmation
  text). Confirm the end state clearly in the wrap-up.
- If you find and fix a simple, obvious bug (e.g., a stale-refresh issue,
  a reactivation bug, a frontend wiring bug), fix it and verify
  29415C127 actually disappears from Andrea Custodial's Equities tab
  data (read-only query of the live DB, or ask Luis to confirm in the
  UI) before calling it done.

## Commit and push (only if you made a fix)

```bash
git add -A
git commit -m "Fix position Remove button not actually removing the position"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-position-remove-not-working-out.md` existing, with the
definitive mechanism and whatever fix (if any) was applied.

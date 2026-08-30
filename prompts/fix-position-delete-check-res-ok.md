# Fix: handleDeletePosition doesn't check res.ok before refreshing

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-position-delete-check-res-ok-out.md`. This is a small,
low-risk fix — implement it directly. Write for someone reading cold
later.

## Context

Flagged during `recon-position-remove-not-working` (see
`wrap-ups/recon-position-remove-not-working-out.md`): the "Remove"
button's handler in `client/src/pages/Portfolio.jsx`
(`AccountPanel.handleDeletePosition`, ~line 449-455) fires the DELETE
and unconditionally calls `onRefresh()` afterward, regardless of
whether the request actually succeeded:

```js
async function handleDeletePosition(positionId) {
  await fetch(`${API}/api/portfolio/positions/${positionId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  onRefresh();
}
```

That recon found no live bug — the DELETE had actually succeeded — but
if a DELETE ever genuinely fails (e.g. a 500), the current code gives
no error signal: `onRefresh()` still fires, the row still correctly
shows (since nothing was actually closed), and to the user this looks
identical to "Remove doesn't work," with no indication of why. This
fix closes that diagnostic gap for next time.

## The fix

In `handleDeletePosition`, check `res.ok` (or catch a thrown error) and
surface a visible failure to the user (toast/alert — match whatever
error-surfacing pattern already exists elsewhere in this file, don't
invent a new one) instead of silently calling `onRefresh()` as if it
succeeded. On success, behavior is unchanged.

Read the current file before editing — don't assume the line numbers
above are still accurate.

## Verify

- Confirm the success path is unchanged (successful delete still
  refreshes normally).
- Confirm a simulated failure (e.g. temporarily point at a bad id, or
  reason through the code path) now surfaces an error to the user
  instead of silently refreshing.
- No backend changes needed — this is frontend-only.

## Commit and push

```bash
git add -A
git commit -m "Surface DELETE failure instead of silently refreshing when removing a position"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-position-delete-check-res-ok-out.md` existing.

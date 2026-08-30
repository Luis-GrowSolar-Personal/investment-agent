# Verify: Moves banner, mandatory decline reason, pending-execution badge (visual pass)

## Report your findings

Write a wrap-up to
`./wrap-ups/verify-moves-banner-badge-visual-out.md`. This is a
**verification-only task — no code changes.** Report defects clearly
rather than fixing them. Write for someone reading cold later.

## Context

`wrap-ups/build-moves-banner-reason-badge-out.md` (commit `02c7c78`,
which includes the earlier `9ac0c20` movesCache fix) built three things
with **zero visual verification** — Chrome wasn't connected in that
session. Source-level verification was thorough (diffs, DB queries,
build checks), but the following were never actually seen rendered:

1. The everyday-mode banner's appearance and copy.
2. The amber pending-execution badge next to an accepted move.
3. That the Radar `StaleTranscriptBadge` refactor is a true visual no-op.

This task closes that gap.

## Before testing — confirm fresh deploy, not a cached view

1. Check `investment-agent-DEV`'s deployed commit matches `02c7c78` (or
   a later commit that includes it — check `git log` if unsure which is
   current HEAD):
   ```
   railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(n['node']['serviceName'], (((n['node'].get('latestDeployment') or {}).get('meta') or {}).get('commitHash') or '')[:8]) for e in d['environments']['edges'] for n in e['node']['serviceInstances']['edges']]"
   ```
   If it doesn't match or isn't a descendant of `02c7c78`, stop and
   report rather than testing stale code.
2. **Hard-refresh before testing.** Navigate with a cache-busting query
   param (e.g. `/?_=<timestamp>`) rather than a plain reload, and
   confirm the loaded JS bundle's content-hashed filename differs from
   whatever was loaded pre-fix (check
   `[...document.querySelectorAll('script[src]')].map(s => s.src)` in
   console, same technique used in prior verifications this session).

## What to check

**1. Banner (everyday mode).**
- Navigate to an owner's Moves/Action Required view where the account
  is in normal (non-Full-Reset) mode and has at least one open move.
- Confirm a banner renders above the move list reading exactly: "These
  are today's recommended trades to bring your allocation back toward
  target, based on current prices. Declining any trade requires a
  logged reason."
- Confirm it does NOT render when there are zero open moves (find or
  check an owner/bucket view with no action required, if one exists).

**2. Pending-execution badge.**
- Find (or create, read-only-safely if needed — do not execute a real
  trade) a move that is currently `Accepted` and still showing (i.e.
  its diff hasn't resolved).
- Confirm an amber circled "!" badge appears beside the `✓ Accepted $X`
  text in the Decision cell.
- Hover it and confirm the tooltip text is sensible and non-alarmist —
  expect wording along the lines of "still listed because the position
  hasn't reached target yet; if you've already placed this trade it
  will drop off once a broker sync reflects it," citing the historical
  accepted amount and date. Report the exact tooltip text you see.

**3. Radar regression check.**
- Navigate to Radar, find a ticker with a stale-transcript badge (the
  existing yellow/red circled "!" for overdue earnings calls).
- Confirm it looks and behaves identically to before — same color
  logic, same tooltip content, no visual change from the shared-
  component extraction.

**4. No suppression sanity check.**
- Confirm a move whose underlying diff has resolved (position back at/
  under target) does not show at all — not greyed out, not present in
  a collapsed state, just absent. This isn't expected to have changed,
  but it's cheap to confirm and worth ruling out given how much this
  file has changed recently.

**5. Mandatory decline reason (quick visual sanity, already source-
verified).**
- Attempt to decline a move with an empty reason field — confirm the
  confirm button is disabled/greyed and cannot be submitted.
- Enter a reason and confirm it submits normally.
- If a previously-declined move is available, click "change" on it and
  confirm the reason field is prefilled with the previous text
  (editable).

## What NOT to do

- Do not accept, decline, or otherwise change any real move or position
  as a permanent action beyond what's needed to observe existing state
  — if you must interact to test, prefer moves/state already present
  over creating new ones, and use the same capture-phase-detector or
  cancel-before-submit techniques used in prior verifications this
  session where applicable.
- Do not trigger a Force Sync or any Schwab API call.

## Report format

For each of the 5 checks, state **PASS**, **FAIL**, or **COULD NOT
TEST** (with why), plus what was actually observed (exact copy/tooltip
text where relevant). If anything fails, describe it precisely enough
that a fix prompt could be scoped without re-investigating from scratch.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/verify-moves-banner-badge-visual-out.md` existing, with a
clear verdict for each of the 5 checks.

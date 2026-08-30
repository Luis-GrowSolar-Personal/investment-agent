# Recon: scope unifying individual-ticker sizing across Full Reset and normal mode

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-unify-individual-sizing-allocator-out.md`. **This is
recon/scoping only — do not write the unified allocator, do not change
`moves.js` behavior.** The goal is a precise map of what exists today,
so a build can be scoped correctly next. Explicit instruction from
Luis: do all the recon needed here, don't start building until this
comes back and a design is agreed.

## Context — the design decision this feeds

Confirmed this session (task #77, still open) that Full Reset and
normal mode use different formulas to size the same individual
Established/Speculative ticker, and can disagree meaningfully even with
zero thesis change and perfect trade execution:

- **Normal mode, currently-held positions**
  (`computeIndividualModelWeights.allocate`, `server/routes/moves.js`
  ~lines 193-227): `denom = Math.max(group.length, targetSpecIndividual)`
  — always divides by *at least* the configured target slot count, so
  existing holdings never expand to fill unclaimed future slots. This
  is deliberate headroom: it reserves room for positions that don't
  exist yet, so opening a new position later doesn't force a shrink-and-
  rebalance across everything already held.
- **Both Full Reset AND normal mode's *new/watchlist candidate* sizing**
  (`sizeSide`, ~lines 1363-1399): `poolCount = min(targetCount,
  active.length)` — divides by whichever is *smaller*: the target slot
  count, or however many real candidates currently qualify. When fewer
  candidates exist than target slots, this fully deploys the available
  pool across them (bigger individual shares), with nothing reserved.

**The point discovered in discussion, not yet confirmed against live
code — confirm it here:** these two formulas *already coexist within
normal mode itself*, on the same side of the same portfolio, depending
on whether a ticker is currently held (headroom formula) or being
newly considered for an open slot (full-deploy formula). If true, this
is a second, independent inconsistency — a currently-held position and
a brand-new candidate on the same side can be sized by genuinely
different rules *today*, with no Full Reset involved at all.

## Direction being considered (report feasibility, don't build it)

Luis's proposed frame: **Full Reset is a special case of normal mode
where every asset happens to be cash.** Instead of two independently-
maintained formulas, there should be **one allocator**, used by both
modes, parameterized by an explicit deploy-vs-reserve choice — surfaced
in the Full Reset flow as a checkbox (working name: "Deploy only into
strongest positions" ON by default = reserve headroom per target slot
count / OFF = fully deploy available cash across only genuinely
qualifying candidates, respecting the cash-reserve preference either
way).

## What to trace and report

1. **Every call site of `computeIndividualModelWeights` and
   `sizeSide`** in `server/routes/moves.js` — confirm the line numbers
   above (they may have drifted from other work this session) and find
   any other call sites not yet accounted for.
2. **Confirm or refute the held-vs-new-candidate inconsistency within
   normal mode itself**, independent of Full Reset. Construct a concrete
   example if you can find or build one (read-only-safe, same
   discipline as this session's other live checks): a side where the
   owner holds fewer positions than their target slot count, and at
   least one genuinely new candidate exists that would fill an open
   slot. Show the actual formula each gets sized by and confirm whether
   they diverge the way this document describes.
3. **Every other place the two formulas' outputs differ beyond the
   headroom-vs-full-deploy question** — the earlier ADD-routing work
   this session found funding-order and cash-ledger issues layered on
   top of sizing; confirm those are cleanly separable from sizing itself
   (they should be, per this session's work, but verify) so a sizing
   unification doesn't accidentally need to also touch routing.
4. **What consumes `targetSpecIndividual`/`targetCount` today** — where
   does this configured slot-count number actually come from
   (`OwnerProfile.maxPositions`/`estSpecRatio`, confirmed earlier this
   session — re-verify), and confirm both formulas read the *same*
   source for it (no drift there either).
5. **What a single unified formula would need to accept as a parameter**
   to reproduce both existing behaviors correctly — sketch (don't
   implement) the shape: something like `allocate(pool, heldCount,
   activeQualifyingCount, targetSlotCount, reserveHeadroom: boolean)`,
   and show, with the numbers from this session's own Established-slot
   example (target=6, held=4, qualifying=4), that your sketch reproduces
   both `pool/6` (reserve) and `pool/4` (full-deploy) correctly.
6. **Any other current behavior that implicitly depends on today's
   two-formula split** and would need to be preserved or explicitly
   redesigned — e.g., does the "Strengthening exception" / winner-
   protection logic, or the funding-priority-order work from earlier
   today, assume anything about which formula ran? Flag anything you
   find; don't assume "no" without checking.
7. **UI-side scope for the proposed checkbox** — where would it live in
   the `RebaselineModal` (confirm current structure per
   `recon-rebaseline-modal-choices-out.md` from earlier this project),
   and what would need to change in `moves.js`'s request handling to
   accept and honor the new parameter.

## What NOT to do

- Do not write the unified allocator function.
- Do not change `computeIndividualModelWeights`, `sizeSide`, or any
  call site.
- Do not add the checkbox to `RebaselineModal`.
- Do not touch task #75's fix (already shipped) or anything in the
  ADD-routing/funding chain from earlier this session.

## Report format

A precise map: every call site of both formulas with line numbers, a
confirmed (or refuted, with evidence) answer on the held-vs-new-
candidate inconsistency within normal mode, the sketch from item 5
verified against real numbers, and an explicit list of what a build
prompt would need to cover. If anything in the proposed direction looks
like it would break an existing, intentional behavior, say so clearly
rather than glossing over it — this is exactly the kind of thing that
needs to surface now, before a design gets locked in.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-unify-individual-sizing-allocator-out.md` existing.

# Fix: scarcity-gap row shows contradictory numbers and a blank Target column

## Report your findings

When done, write a wrap-up to `./wrap-ups/fix-scarcity-row-framing-out.md`.
State the root cause and the fix up front, then show the corrected row's
actual rendered numbers (from production data) for at least Andrea's
Speculative bucket so it's obvious the contradiction is gone. Write for
someone reading cold in a later session.

## The bug, as observed in the running app

Andrea Morales's "Speculative Equities (unallocated)" row (added by the
previous fix — see `wrap-ups/fix-no-qualifying-candidates-message-out.md`)
renders like this:

```
ADD  Speculative Equities (unallocated)   $9,345   —   $2,831   $0 tax   [NO QUALIFYING CANDIDATES]
     Speculative Equities at 29.7% — below target of 18.0%, but no speculative
     watchlist candidate currently clears the conviction bar to fill the gap...
     29.7% current / 18.0% model
```

Two problems:

1. **Target column shows "—" instead of a dollar figure.** `MoveRow`
   (`client/src/pages/PortfolioManager.jsx`) renders `money(move.targetValue)`,
   and `money()` returns `'—'` for `null`/`undefined`. The scarcity-row
   object built in `computeMovesPayload` (`server/routes/moves.js`) never
   sets `targetValue` — only `targetPct` and `dollarAmount`. Same gap likely
   exists on the pre-existing ETF/Crypto/Commodity "(unallocated)" rows —
   check whether those show a real Target $ in the running app or have the
   same dash; if they show a real number, find out how (there may be a
   generic post-processing step downstream — search moves.js for wherever
   "before/after dollar values" or similar are derived generically from
   `currentMktValue`/`dollarAmount` — and work out why it doesn't produce a
   sane number for this row even if it runs).

2. **The message is self-contradictory, and this one matters more.** It
   says "at 29.7% — below target of 18.0%" — but 29.7% is *above* 18.0%,
   not below it. The bucket is genuinely overweight in raw dollar terms
   (SPWR is drastically overweight and is being trimmed via a separate
   `TRIM_CAP` row shown elsewhere in the same Recommended Moves list —
   that trim is correct and unrelated to this row). What the scarcity row
   is actually reporting is a *different* concept: model-weight capacity
   reserved for a hypothetical new open (`denom = max(group.length,
   targetCount)` in `computeIndividualModelWeights.allocate()`, moves.js
   ~line 1199-1214) that no current watchlist candidate can fill. That
   reserved capacity can be real and nonzero *even while* the bucket's
   current aggregate dollar value sits above the target — because the
   held ticker(s) are overweight and heading toward a much smaller
   individual target, not because the bucket needs new money. Comparing
   that reserved-capacity gap against the bucket's *current* value/%
   (as if it were a normal ADD move telling you to deploy more cash) is
   actively misleading in this case.

## What to fix

### 1. Make the Target column show a real number

Explicitly set `targetValue` on the scarcity-row object (and check/fix
the same for the ETF/Crypto/Commodity unallocated rows if they have the
same gap) — don't rely on generic derivation. Decide what number
actually belongs there given the reframing below (likely the full bucket
target in dollars, i.e. `estPoolPct`/`specPoolPct` × total portfolio
value — NOT `currentMktValue + dollarAmount`, which would produce a
nonsensical number here since `dollarAmount` isn't "how much more to add
to reach this row's own target," it's "how much reserved capacity is
unclaimed").

### 2. Reframe the row so it can't contradict itself

The row needs to stop implying "this bucket needs more money right now"
and instead communicate "once other recommended trims/holds in this
bucket execute, there's still X% of model weight nothing currently
qualifies to fill." Concretely:

- Don't compare against the bucket's raw current %/$ in the headline
  reason text — that's the number that made this read backwards. Compare
  against the "achievable" position instead: `heldTargetSum + newOpenSum`
  (the same figures the previous fix already computes to derive the
  shortfall) expressed as a % of total portfolio.
- Reword the reason string to something like: *"Speculative Equities:
  once recommended trims/holds are applied, held positions plus any new
  opens account for {achievablePct}% against an {targetPct}% target — the
  remaining {shortfallPct}% has no watchlist candidate that currently
  clears the conviction bar. Needs new names sourced (Layer 3 /
  Opportunity Scanner), not a bigger allocation to what's already held."*
- Reconsider the `currentMktValue`/`currentPct` fields on this row too —
  showing the bucket's raw current value next to a target that isn't
  directly comparable to it is part of what made this confusing. Decide
  whether to show the achievable value there instead, or omit/relabel
  that column for this row type specifically (`isScarcityGap` is already
  a distinct flag — use it in `MoveRow` to render this row's columns
  differently if a straight reuse of the normal ADD-row layout can't be
  made to read sensibly). Use your judgment on the cleanest fix, but the
  end result must not let "current" and "target" numbers coexist in a way
  that reads as contradictory to someone glancing at the row.

## Open design question — flag it, don't guess silently

Is it even correct for this row to fire while the bucket is aggregate
*overweight* (current $ > target $), as in Andrea's case? An argument
could be made that the scarcity message should only surface once the
bucket's *other* recommended moves (the SPWR trim, etc.) would bring it
to/below target and there's *still* unclaimed capacity — i.e., suppress
it while there's an unrelated overweight problem being solved elsewhere,
and only show it once that's the sole remaining issue. If you have a
clear opinion after tracing the logic, implement it and explain your
reasoning in the wrap-up. If it's genuinely ambiguous, implement the
reframing (which is unambiguously needed either way) but leave the
"should it even fire here" question explicitly open in the wrap-up for
Luis and Cowork to decide, rather than picking silently.

## Verify against production data

Re-run `computeMovesPayload(owner, { bypassWinnerProtection: true })` for
Andrea and Eduardo and confirm the rendered row (or its underlying data,
if you can't render the actual React component headlessly) no longer
contains a self-contradictory current-vs-target comparison, and that the
Target column has a real dollar figure.

## Commit and push

You have real local git access — commit and push this yourself, Luis
doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "Fix contradictory current-vs-target framing and missing Target $ on scarcity-gap rows"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

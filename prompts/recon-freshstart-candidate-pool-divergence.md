# Recon: why do Andrea's and Eduardo's `freshStart` picks diverge despite identical settings?

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-freshstart-candidate-pool-divergence-out.md`. This is a
recon task — **do not change any code**, just investigate and report.
State the answer up front in one or two sentences, then back it with the
actual ranked candidate lists and the exact code responsible. Write for
someone reading cold later.

## Context

Luis spent this session equalizing Andrea Morales's and Eduardo Morales's
`OwnerProfile` settings — confirmed via `server/scripts/compareOwnerProfiles.js`
that every top-level field now matches exactly (equities/ETF/crypto/
commodities/cash split 55/25/10/5/5, estSpecRatio 0.5, minPositionDollar
$1,000, domainsOfInterest identical, etc.) and every per-ticker cap
override matches for any ticker either owner holds. Their portfolio
values are close (~$31,571 vs ~$31,935, about 1.2% apart).

He then ran `freshStart: true` re-baseline (the "Full reset" mode built
last session — see `wrap-ups/build-rebaseline-full-reset-mode-out.md`)
for both. Full reset is designed to rank ALL eligible candidates by
conviction with **zero preference for what's currently held** — Luis
was explicit about this when the feature was speced. His expectation:
with identical settings and comparable portfolio size, the two accounts
should end up recommending essentially the same holdings, scaled by the
~1.2% size difference.

That's not quite what happened. Observed results (from the live UI,
confirmed current as of this session):

**Andrea (established, 5 slots, each sized to $1,736):** TRIM AMD, TRIM
NVDA, ADD AVGO, ADD ORCL (new), ADD GOOGL (new).
**Andrea (speculative):** ADD AMPX only, sized to the ENTIRE speculative
pool ($8,682) — no second candidate.
**Andrea exits:** EOSE, AMZN, QS, SPWR, 29415C127.

**Eduardo (established, 5 slots): TRIM NVDA ($2,012), TRIM ORCL ($2,012),
ADD GOOGL (new, $2,012), ADD QS ($1,341), ADD NFLX (new, $1,341).**
Note the established slots are NOT uniformly sized for Eduardo — $2,012
for three, $1,341 for two (ratio ≈ 2/3).
**Eduardo (speculative):** ADD AMPX ($4,407) AND ADD ENVX ($4,407) — the
pool is split across two candidates, not one.
**Eduardo exits:** AMZN, EOSE, SPWR, BYDDY, 29415C127, EOS ENERGY ENTERP
(matured).

Two things need explaining:

1. **ENVX never appears anywhere in Andrea's move list** — not added,
   not declined, not mentioned. If candidate eligibility is genuinely
   ticker-level (not owner-scoped), ENVX should have at least been *in
   the ranked pool* for Andrea, even if it lost out to AMPX on
   conviction. Same question for BYDDY (Eduardo exits it, meaning it WAS
   a candidate that got evaluated and rejected for him — but does it
   even appear as a candidate for Andrea?). And in reverse: AMD and AVGO
   appear in Andrea's established build but nowhere in Eduardo's — did
   they lose a ranking, or were they never considered for him?
2. **Eduardo's established slots aren't uniformly sized ($2,012 vs
   $1,341) while Andrea's are (all $1,736).** Work out whether this is
   `sizeSide()` (or whatever function actually does the slot-fill)
   weighting individual slot size by each candidate's own Type A/B cap
   (e.g. Type A/35%-cap candidates like QS/NFLX get a smaller slot than
   Type B/50%-cap candidates like NVDA/ORCL/GOOGL), and if so, confirm
   this is pre-existing, intentional behavior — not something `freshStart`
   introduced — that just happens to be invisible in Andrea's result
   because her top-5 established picks all happen to be the same type.

## What to actually check

1. Read the real current source of whatever function builds the
   candidate list for `freshStart` mode (per
   `wrap-ups/build-rebaseline-full-reset-mode-out.md`, this reuses the
   existing new-open candidate ranking/eligibility gate — likely inside
   `sizeSide()` or wherever `computeMovesPayload` sources ADD candidates
   for a side, in `server/routes/moves.js`). Quote the exact eligibility
   filter condition(s) — domain check, `recommendation`/`finalAction`
   check, Type A/B classification requirement, anything else.
2. Confirm directly whether that filter references anything owner- or
   holding-specific (e.g. `OwnerDecision`, current `Position` rows, a
   per-owner watchlist flag) as opposed to being purely global
   (Ticker + latest Analysis, independent of who holds what). Quote the
   exact line(s).
3. Call `computeMovesPayload('Andrea Morales', { bypassWinnerProtection: true, freshStart: true })`
   and `computeMovesPayload('Eduardo Morales', { bypassWinnerProtection: true, freshStart: true })`
   directly (no HTTP), confirm the results match what's described above
   (screenshots could be stale — verify against a live call), and if
   possible, log the FULL ranked candidate list (ticker, score/conviction
   basis, Type A/B, cap%) that gets passed into the slot-filling step for
   Established and Speculative on each side, for both owners, before any
   greedy-fill truncation. Print both owners' ranked lists side by side.
4. Directly answer: is ENVX in Andrea's ranked candidate list at all
   (regardless of whether it made the cut)? Is BYDDY? Is AMD in Eduardo's?
   Is AVGO? If any of these is unexpectedly absent from one owner's list,
   find and quote the exact code responsible and explain the mechanism
   — don't just report the symptom.
5. For the established slot-sizing question: quote the exact sizing
   formula used, confirm whether it's cap-weighted or conviction-weighted
   or something else, and confirm it behaves identically for both owners
   given the same inputs (i.e. this is a general property of the sizing
   function, not something owner-specific).

## What NOT to do

Do not change any code. Do not commit or push anything. This is purely
investigative — the goal is to give Luis a clear, code-grounded answer
to "why do two accounts with identical settings get different holdings
recommended," not to fix anything yet. If you find something that looks
like an actual bug (e.g. eligibility genuinely is owner-scoped when it
shouldn't be per the `freshStart` design intent), say so clearly and
explain the mechanism — Luis will decide whether and how to fix it in a
follow-up prompt.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-freshstart-candidate-pool-divergence-out.md` existing,
with the side-by-side ranked candidate lists and the exact quoted code
for both the eligibility filter and the slot-sizing formula.

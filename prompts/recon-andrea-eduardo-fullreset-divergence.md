# Recon: do Andrea's and Eduardo's Full Reset candidate pools diverge for a real reason?

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-andrea-eduardo-fullreset-divergence-out.md`. This is
investigation only — do not change code unless you find something
trivially and unambiguously wrong (in which case, stop and report it
rather than fixing it, per usual practice for recon tasks).

## Context

Andrea and Eduardo each ran a Full Reset a few days apart (2026-08-24,
close together). Luis noticed strong overlap in the resulting
candidate picks (AVGO, AMPX, QS all ADD in both; BTC/QQQ trimmed in
both; AMZN/EOSE fully exited in both) but also real differences:
Eduardo's reset recommends GOOGL, AMD, and MSFT as brand-new
Established ADD positions, plus ENVX as a new Speculative ADD — none of
which appear as ADDs for Andrea. The working hypothesis, from screenshot
comparison only, is that this is fully explained by different starting
holdings: Andrea already holds GOOGL/AMD/MSFT/NVDA/ORCL/TMFC near target
(they show in her "No action needed" list), so her reset has nothing to
add there, while Eduardo doesn't yet hold them. Her ENVX shows as a TRIM
(already held above target) rather than a fresh ADD.

**This exact class of question has a history of hiding real bugs.**
`recon-freshstart-candidate-pool-divergence-out.md` (task #38, earlier
this project) investigated a similar Andrea/Eduardo candidate-pool
divergence and found two genuine bugs — a global `Ticker.status`/
`inScope` eligibility gate wrongly filtering the candidate pool on both
the freshStart and normal paths (fixed in tasks #39/#40, commits
tracked in that era's wrap-ups). So "looks explainable by different
holdings" is not sufficient on its own here — it needs to actually check
out against the data, not just look plausible from screenshots.

## What to check

1. **Confirm the conviction/candidate-scoring inputs are actually
   shared and current for both owners.** Pull the `Analysis` records (or
   whatever backs `scoreCandidate`/`thesisHealth`/`trajectory`) for
   GOOGL, AMD, MSFT, ENVX, AVGO, AMPX, QS, BTC, QQQ, AMZN, EOSE as of
   each owner's actual Full Reset `computedAt` timestamp. Confirm both
   resets are scoring against the *same* underlying analysis snapshot
   for each ticker (not different transcript/analysis data due to
   something being ingested in the gap between the two resets) — if the
   data genuinely differs by date, that's a legitimate, non-buggy
   explanation for any scoring differences and should be reported as
   such.
2. **Confirm the "already held near target" explanation actually holds
   for every ticker in the divergence, not just some of them.** For
   each of GOOGL, AMD, MSFT, ENVX: check Andrea's actual current
   position (shares, dollar value, % of portfolio) at the time of her
   reset, and confirm it was genuinely at/near target weight (which is
   why no ADD was generated) — don't just trust that it appeared in her
   "No action needed" list; verify the underlying weight-vs-target
   numbers directly.
3. **Check the same global-eligibility gate that caused the bug in
   task #38/#39/#40 hasn't regressed or reappeared in a different
   form** — re-read those wrap-ups first to know exactly what was fixed,
   then confirm the current code still behaves that way for both
   owners' full-reset candidate selection.
4. **Check the reverse direction too**, not just "why does Eduardo have
   ADDs Andrea doesn't" — are there any tickers Andrea's reset
   recommends (ADD, TRIM, or EXIT) that Eduardo's reset doesn't touch at
   all, where the same "different starting holdings" explanation does
   NOT cleanly account for the difference? Report any such case
   explicitly; don't only look for confirming evidence of the working
   hypothesis.
5. **Confirm the funding-priority-order and trim-proceeds-routing
   changes from earlier today (commits `0021bcc` and whatever lands from
   `fix-add-routing-trim-proceeds-double-counting`, if it's landed by
   the time you run this) haven't altered which tickers get selected as
   candidates** — those changes were scoped to routing/funding only, not
   candidate selection, but this recon is a good place to double-check
   that boundary actually held.

## What NOT to do

- Do not change any candidate-selection or scoring logic, even if you
  find something that looks wrong — report it precisely enough that a
  fix prompt could be scoped without re-investigating, per this
  project's usual recon-then-fix-prompt discipline.
- Do not assume the working hypothesis (different holdings explains
  everything) is correct going in — verify it against the data.

## Report format

For each ticker in the divergence (GOOGL, AMD, MSFT, ENVX), state
whether the "already held near target" explanation is confirmed by
actual position data, or whether something else is going on. Explicitly
answer: is there any unexplained divergence between Andrea's and
Eduardo's Full Reset candidate pools, or does everything check out
against real differences in current holdings and/or analysis-data
timing? If anything is unexplained, describe it precisely enough to
scope a fix without re-investigating.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-andrea-eduardo-fullreset-divergence-out.md` existing,
with an explicit yes/no verdict on unexplained divergence.

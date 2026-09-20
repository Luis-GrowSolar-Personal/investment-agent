# R4b findings (append-only)

## PRE-REGISTRATION -- written and committed before any cell was computed (2026-09-20)

From prompts/R4b-short-horizon-and-tradeable-entry.md section 5, plus definitions fixed here before computing.

- Primary: arm A minus arm B (bearish edge) is large at 1-5 days, moderate at 30 days, near zero at 182 days.
- Consequence if primary holds: R4's short-horizon train result is substantially an artifact of the entry price; +23.2 at 30d shrinks materially in arm B.
- Secondary: +13.3 at 182d is largely clean; A and B agree within their ranges.
- Falsified if: A and B agree at short horizons too, OR differ materially at 182d.
- Not predicted: whether arm B keeps any edge at 1-5 days (post-announcement drift).
- Train discovers, tune confirms. Every cell reported.

Definitions fixed before computing (mine, not the prompt's):
- Arm B start price: close on the first trading day strictly after the call date (price_on_or_after(call_date + 1 day)); benchmark same rule. End price identical in both arms, so B's window is one trading day shorter. NOT corrected.
- Consequence to be reported: at a 1-day horizon arm B is (near) zero-length, since its start and end price are usually the same close.
- "Materially differ": paired ticker-block bootstrap range of (edge_A - edge_B) excludes zero AND the point difference is at least 5 points. "Agree": otherwise.
- Timing threshold: gap on D if |move on D| >= 2 x |move on D+1| and >= 2% absolute; gap on D+1 the reverse; else ambiguous. Moves are benchmark-relative (stock minus SPY). Sensitivity reported at min-abs 1% and 4%, and ratio 1x and 4x.
- Gate: arm A at 182/30/60/90 must reproduce R4 cell matrices exactly (stricter than the prompt's rounded figures). Failure = stop.
- Version guard skipped: no scoring calls.

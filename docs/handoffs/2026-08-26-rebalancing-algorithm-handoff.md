# Handoff: Rebalancing algorithm — where we are, and the actual north star

**Date:** 2026-08-26
**For:** A new Cowork session, scoped narrowly to the rebalancing/allocator algorithm (task #77 and related). The prior session accumulated a lot of code-forensics noise (routing fixes, a divisor bug fix, live-DB diagnostics) that isn't needed here — this doc distills what actually matters for the design question.

**Read this first, don't re-derive it.** Then read `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` and `docs/architecture/BACKTEST_SIMULATOR.md` in full before proposing anything.

---

## 1. The problem, stated plainly

The production allocator in `server/routes/moves.js` sizes an individual Established/Speculative ticker with **two different formulas**, depending on whether the ticker is currently held or newly being considered:

- **`computeIndividualModelWeights.allocate`** (moves.js ~183-229) sizes *currently held* positions. It divides the pool by `Math.max(heldCount, targetSlotCount)` — i.e., it always reserves headroom for slots that aren't filled yet, even if there's currently no candidate to fill them.
- **`sizeSide`** (moves.js ~1384-1420) sizes *new/candidate* positions — used by both Full Reset and normal mode's "remaining open slots" logic. It divides the pool by `min(targetSlotCount, qualifyingCandidateCount)` — i.e., it fully deploys the pool across however many real candidates exist right now, with nothing held back.

These two rules can disagree sharply on the same portfolio, same day, zero thesis change. Confirmed live on Luis's own account: a new candidate (NVDA) was sized at 37.5% of the Established pool — the *entire* pool — because it was the only ticker that currently qualified against 11 target slots, while a held position on the same side would have been sized around 3.4% for the identical dollar pool. An 11x difference, with no Full Reset involved.

This is not a single bug. It's what happens when two formulas evolve independently across sessions without ever being checked against a written spec of what the allocator is *supposed* to do. Task #77 tracks the open design question; several adjacent tasks (#50, #56/#58/#59/#60, #67/#78/#79) are related but should not be conflated with this core question.

**The trap to avoid:** the temptation is to patch the discrepancy in code — pick one formula, or add a parameter, or write a unifying function — without first checking whether either formula matches the thing that was actually validated to work. That's the point of section 3 below.

---

## 2. Current state of the investigation (prior session)

A recon (`wrap-ups/recon-unify-individual-sizing-allocator-out.md`) confirmed:

- Both formulas draw from the *same* candidate universe (global `Ticker`/`Analysis` tables, no per-owner watchlist) — the divergence is a sizing-math artifact, not a data-scoping one.
- Normal mode is coherent at the *pool* level (held-slice + new-slice always sum to the full bucket target — a guard added 2026-08-08 specifically for this). The disagreement is per-position, triggered specifically when qualifying candidates < remaining slots.
- A proposed unification (`allocateUnified(pool, heldCount, qualifyingCount, targetSlotCount, reserveHeadroom: boolean)`) was sketched and verified against known numbers, but surfaced real open questions before it can be built:
  1. **A third, independent divergence**: `allocate` (held positions) ignores per-owner cap overrides (`OwnerTickerConfig`); `sizeSide` (new candidates) respects them. Possibly its own bug, independent of headroom-vs-deploy.
  2. `sizeSide` has a `minPositionDollar` floor-and-drop loop (discard worst-ranked candidate, re-divide, repeat) with no equivalent in `allocate`. Should a unified allocator ever drop an *existing holding* this way?
  3. The "(unallocated)" scarcity-gap rows in re-baseline mode structurally depend on the two formulas disagreeing — under a deploy-mode-only allocator, the shortfall those rows report would silently collapse to ~0.
  4. Winner-protection logic could silently drop some TRIM recommendations if unification raises held positions' model weights.
  5. Full Reset's real distinguishing behavior isn't just a deploy/reserve flag — it also reclassifies held tickers into the *same candidate pool* as new opens, a separate mechanism that has to be preserved deliberately.
  6. Any new mode flag must be persisted into the cached `MovesCache` payload (same pattern as `isFreshStart`/`isRebaseline`) or it silently reverts on refresh — this bit the project once already (task #63).

None of this has been decided or built. Luis's last framing before this handoff: *"Full Reset is a special case of normal mode where every asset happens to be cash — there should be one allocator, with a checkbox for deploy-vs-reserve behavior."* That's a reasonable product hypothesis, but it was proposed from first principles, in the middle of a code-archaeology session — not checked against what was actually backtested to work. That check hasn't happened yet, and it should happen before this design gets built.

---

## 3. The actual north star — and a discrepancy worth resolving first

Luis described the north star as: replicate, to the extent possible, the results of a portfolio-management approach modeled by consuming roughly five years of earnings calls of the top 20 S&P 500 equities.

That approach **is written down** — it's not folklore. `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` and `docs/architecture/BACKTEST_SIMULATOR.md` are the two documents that define it.

**Universe composition, confirmed by Luis (2026-08-26) — do not re-litigate this, it's settled:** the backtest universe is deliberately mixed, not a single clean cohort:

1. Real-money positions that saw significant appreciation followed by large drawdowns — ENPH, TTD.
2. Recently-initiated positions that have since appreciated — AMPX.
3. Domain-scoped candidates that were considered but not necessarily held — RUN.
4. Top-20 S&P 500 members **as of 5 years prior to the backtest window** (not top-20-today) — the remaining names, e.g. GOOGL, JNJ, DIS, etc. This is the broad-market comparison cohort, not a domain-scoped pick.

The 17-ticker and "top-20-2021" universes named in `PORTFOLIO_ANALYST_SPEC.md`'s changelog are this same mixed cohort, not a contradiction to resolve — the doc's mixed-cap ticker list (AAPL, JNJ, MA, V alongside TTD, RUN, AMPX, ENPH) matches this composition exactly. **Any ticker currently in RADAR or WATCHLIST is part of the backtest universe — that inclusion is definitionally how it got there.** Treat `type_classifications.json` and the live RADAR/WATCHLIST tables as the current source of truth for universe membership; don't go looking for a separate "top 20 S&P 500" list elsewhere.

Setting that open question aside, here is what the two docs **do** specify, precisely, as the validated allocator behavior (`BACKTEST_SIMULATOR.md`, "Allocator decision rules (Phase 1)"):

- **Add**: `target_pct = min(recommended_size, type_cap)` where `type_cap` is 35% (Type A / Pure-play) or 50% (Type B / Platform) — a single flat cap per classification, not a headroom-reserved or pool-scarcity-dependent number. Buy the delta between target and current, capped by available cash.
- **Trim**: sell a flat 25% of current shares — not a scarcity-aware recalculation of everyone else's slice.
- **Exit**: sell all shares.
- **Hold**: no-op.
- Type A/B caps are tier-refined in production per the 2×2 matrix in `PORTFOLIO_ANALYST_SPEC.md` (Speculative Pure-play 15%, Established Pure-play 35%, both Platform tiers 50%), and the 25% profit-take rule is what actually binds concentration in practice — the Type B cap was empirically shown to be near-vestigial once profit-take is in effect ("Variable cap experiment, retired," 2026-05-17).

**The important observation for task #77**: this validated methodology sizes each position against its *own* cap and its *own* recommended size — full stop. There is no `pool / min(target, qualifying)` full-deploy math and no `pool / max(held, target)` headroom-reserve math anywhere in the backtested rules. Both `allocate` and `sizeSide` in production `moves.js` are **pool-splitting** formulas — a layer that was added later, in production, to handle the practical problem of *multiple simultaneous candidates competing for a shared target-bucket percentage*. That layer doesn't appear to have ever been validated against the backtest; it was built to solve a real UI/allocation problem (how do you size five simultaneous "Add" candidates against one Established bucket target) that the Phase 1 backtest's event-driven, one-decision-at-a-time model didn't need to solve, because the backtest processes one call at a time and re-marks-to-market daily.

This reframes the design question. It's not "which of the two existing formulas is right" — it may be that **neither is a faithful implementation of the modeled approach**, and the real fix is checking whether pool-splitting should exist at all in its current form, versus sizing each Add against its own tier/type cap directly (per spec) and using a different, explicit mechanism (e.g., sequencing, or a stated cash-reserve preference) to handle the case of multiple simultaneous candidates. That's a hypothesis to test in the new session, not a conclusion — but it's the right first question, and it wasn't asked in the prior session because the prior session was heads-down in code, not the spec.

---

## 4. Recommended first steps for the new session

1. **Re-read `PORTFOLIO_ANALYST_SPEC.md` and `BACKTEST_SIMULATOR.md` in full** (both already read in full to produce this handoff; re-read fresh rather than trusting this summary for anything load-bearing). Universe composition is already confirmed (section 3) — don't reopen it.
2. **Check whether the backtest simulator (`analysis/simulator/`, if built — confirm against `BUILD_STATE.md`) has ever been run against real production data**, or whether it remains a Phase 1 design doc that was never executed. This matters: "beat SPY/QQQ/TMFC" is the actual success criterion in the spec, and if that comparison has never been run, there's no empirical baseline to check `allocate`/`sizeSide` against yet regardless of which formula wins the internal argument.
3. **Only then** return to task #77 with a sharper question: not "how do we unify these two formulas" but "does either formula match the spec's Add/Trim/Exit rules, and if the production system needs pool-splitting logic that the spec doesn't have, what should that logic's *design goal* be" (faithfulness to the backtest, or a deliberately different production concession — and if the latter, that should be written into `PORTFOLIO_ANALYST_SPEC.md` as an explicit, acknowledged deviation, not left as implicit code drift).

---

## 5. Standing rules to carry into the new session (from `CLAUDE.md`)

- Read `docs/architecture/DESIGN_PRINCIPLES.md` and `docs/architecture/DOMAIN.md` before touching anything that reaches the analyst, allocator, concentration rules, or backtest integrity — this task touches all four.
- Analyst/allocator firewall: analyst never receives portfolio data; allocator never receives transcripts.
- Never suggest proportional redeployment of trim proceeds without first checking Layer 3 for a higher-conviction alternative.
- Scripts must be `python3`/`pip3`, zsh-compatible, no `--break-system-packages`, no Linux-only assumptions.
- Handoff docs only when explicitly requested (this one was) — don't proliferate more of these mid-session; this project's working rhythm is prompts (`prompts/*.md`) in, wrap-ups (`wrap-ups/*-out.md`) out, via a separate Claude Code CLI session with live DB access. Cowork sessions here don't have DB access.
- Complex terminal commands/SQL go in fenced code blocks in chat, not separate files.

## 6. Related open tasks (don't lose track of these, but don't let them derail the core question)

- **#75** (splitBucketTarget zero-cap divisor) — wrap-up says fixed and verified; tracker currently shows it as pending. Worth a 30-second reconciliation at the start of the new session (check git log for the commit, don't just trust either source blindly).
- **#77** — this handoff's subject.
- **#50** — pre-existing Established Equities reconciliation gap (Andrea/Luis/Eduardo) — may or may not be related to the same root cause; check once #77's design is settled.
- **#67 / #78 / #79** — trade-ticket-modal backlog, classification-at-entry requirement, unclassified-ticker sync notification — downstream of execution work (CLAUDE.md Step 8), not blocking #77, but keep them off the plate for this session's scope.
- **#56 / #58 / #59 / #60** — Moves-grid UI/scroll follow-ups — unrelated to sizing math, explicitly out of scope for this thread.

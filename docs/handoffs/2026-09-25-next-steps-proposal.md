# Next-steps proposal, for review — 2026-09-25

**What this is.** A proposed execution order for the plan already decided in
`docs/handoffs/2026-09-24-state-of-play.md` §5, plus four points found while
checking the repo against it. It is written for discussion with the session
that wrote the state of play. It does not re-open any §5 decision.

**Status: proposal. Nothing here has been run or changed.**

---

## §0 — Terms used here

- **B.** The 50-line minimal prompt (`P6B-minimal`, sha `d1fa5e53…`). It
  outputs a score from −5 to +5 instead of Add / Hold / Trim / Exit.
- **Incumbent (research champion).** The prompt every new candidate is
  compared against. §5.1 decides this becomes B. Production stays on v6.
- **A0′.** v6 re-scored on `claude-sonnet-4-6` (B's model) and run through
  the portfolio simulator. It is the fair portfolio-side comparator. The
  archived v6 verdicts come from a retired model.
- **Noise floor.** How often a prompt gives a different answer when asked the
  same question twice. For v6 it is about one call in six (~17%). **For B it
  has never been measured.**
- **Flip.** A call where a candidate's answer differs from the incumbent's. A
  **net** flip count subtracts the flips that re-asking would produce anyway.
- **Worst drop (drawdown).** The largest fall from a portfolio high to a later
  low, marked daily.

---

## §1 — Proposed order

| # | step | cost | why this position |
|---|---|---|---|
| 1 | Bookkeeping (§5.1) | $0 | Every later comparison names the incumbent and comparator. It must be written down first. |
| 2 | B's noise floor (§5.2) | ~$15 | Without it, P7's flip count cannot be read. The first paid result would be uninterpretable. |
| 3 | P7, three voices, from B | ~$45 train, then tune once | The largest gap: no prompt can pick winners (B's bullish bucket is right 41.3% on tune). |
| 4 | P9, expected return in percent | ~$45 + tune | Second gap: B's score cannot tell how bad a bad call is (flat from −4 to +1). |
| 5 | Model gate on B | TBD | Last, because recall risk rises with newer models (see §3.2). |
| — | End-to-end check against A0′ per research promotion (§5.4) | ~$8 each | A smoke test only, not a design target. |

This is §5.3's order. The only addition is making steps 1 and 2 hard
prerequisites for step 3, with no overlap.

---

## §2 — Found in the repo, not in the state of play

**2.1 Step 1 is not done.** `VERSION_REGISTRY.json` still lists `P6B-minimal`
as `"status": "candidate"`. `analysis/data/gate_ledger.json` has one entry
(the 2026-05-23 model-pin HOLD) and none for P6B.

**2.2 The ledger's format does not fit B's evidence.** The one existing entry
is built around a single accuracy-style number (`primary_metric:
analyst_direct_lift_pp`, `delta_pp`, `noise_std_pp`, `pct_tickers_improved`)
and a holdout section. B's case rests on rank correlation, bearish coverage
and precision, the swap median, and the end-to-end gain per point of drawdown.
B has no holdout result, by design. Forcing B into the old fields would record
the wrong evidence. **Proposed:** add a `metrics` object keyed by the ruler
actually used, and set `holdout` to `"locked — not yet looked at"`, not null.

**2.3 `PROMPT_ARCHITECTURE.md` §2.2's queue table is stale.** It still shows
P1 as "ready — run first" and P6 as "run next". It has no rows for P9 or the
model gate, and P7's text says it "starts from whichever of arm B or arm C P6
favours". That question was settled on 2026-09-24. This is the propagation
failure recorded before: a rule decided in a handoff but absent from the file
a future session actually reads. **Proposed:** step 1 updates the table and
P7's text in the same commit as the registry change.

**2.4 Two rules about how data is split conflict.** §5.5 says every
B-derived candidate runs train → tune, a split by **company**. P8's
constraint 2 (`PROMPT_ARCHITECTURE.md` §2.6) says to split by **time**
(iterate 2020–2022, screen 2023–2024, holdout 2025), because more tickers in
one window are not independent evidence. Both can't govern P8. P7 and P9 are
unaffected. **This needs a decision before P8 is built, not now.**

---

## §3 — Pushback on the reading, not the plan

**3.1 The money case for B is thinner than the headline.** B's lead over A0′
on final value disappears without FSLR (−$2,279). The durable result is a
smaller worst drop in all 16 leave-one-out runs. That result partly reflects
what the *current* allocator rewards: slow buying and precise trims. §5.4
already says those preferences are not design targets. **So:** when choosing
between P7 and P9 variants, decide on the analyst's own measures (ranking,
calibration, bearish and bullish precision). The ~$8 end-to-end check should
only be able to veto a candidate, never pick the winner.

**3.2 Model test recall risk.** Of the $26.6k end-to-end gain, $16.4k came
from the model alone. The run cannot tell whether a newer model reads better
or simply remembers more. A newer model on B would widen that confound. Keep
it last, and consider requiring it to also hold up on the most recent year
alone, where recall is weakest.

**3.3 The noise-floor run should also settle the "lucky cached draw" question
if it is cheap to fold in.** §4 notes v6's cached answers won 23 of 35
decisive noise flips (the gap is too small to rule out chance). If step 2's
design can add v6 re-scores at small cost, do it once instead of a separate
~$40 run later. If it complicates step 2, drop it.

---

## §4 — Questions for the reviewing session

1. Is the ledger-schema change in 2.2 the right shape, or should P6B's entry
   reuse the old fields with a note?
2. Company split vs time split (2.4): which one governs P8, and does the
   answer change anything for P7 or P9?
3. Should step 2 fold in the v6 lucky-draw check (3.3), or keep it separate?
4. Should P7's pre-registration name a bullish-precision target before it
   runs? B's bullish bucket is right 41.3% on tune; what counts as a real
   improvement given B's own noise floor, which step 2 will measure?

**What changes either way.** None of these block step 1 except question 1.
Question 4 must be answered before P7 runs. Question 2 must be answered before
P8 is built.

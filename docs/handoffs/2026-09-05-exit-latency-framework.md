# Exit-Latency Framework — design discussion handoff

**Date:** 2026-09-05 · **Branch at time of writing:** `sweep/db-corpus-baseline`
**Status:** Design agreed in conversation, nothing built, nothing measured beyond §2.1's price-cache table.
**Read with:** `docs/handoffs/2026-09-05-state-of-play.md` (§1, §4, §5.2), `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §0/§5, `docs/architecture/PROMOTION_GATE.md` §2.1/§7/§10 rule 4, `docs/architecture/TREND_LAYER.md`.

This document records a design conversation, not results. Every prediction in
§6 is written down so it can be wrong in public. Nothing here is a decision
under `PROMOTION_GATE.md`; everything here is a candidate that must clear it.

---

## 1. The problem, restated

Luis's observation: the methodology beats SPY/QQQ/TMFC on the settled
configuration but is "not deft at exiting or trimming losers fast enough."

Two corrections to the framing, both from evidence already in the repo:

1. **The allocator weights; it does not select.** 15 of 16 ALL16 names were
   held from Q1 2023 onward; SPWR's absence was a funding failure, not a
   rejection (09-05 state of play §5.2). Test 1 showed the analyst's entire
   $59,145 contribution is sizing. "Exit faster" therefore means "size down
   faster," and three separate mechanisms throttle sizing down — only one of
   them is the analyst.
2. **Exit speed is throttled by construction before the analyst gets a vote.**
   For a 15% position whose thesis breaks:
   - *Detection latency:* the analyst sees the name only at its own call —
     mean ~45 days from event to call, plus up to K=30 days to the session.
   - *Rule latency:* ratchet tranche 1 ("trim to cap") is a **no-op** in this
     corpus because caps never bound (largest position ever 24% vs 35% cap).
     First real money out is tranche 2, a quarter later (40% of 15% = 6pp);
     tranche 3 to 3% another quarter on; tranche 4 exit. Four quarters from
     first Weakening to flat.
   - *Execution latency:* `X`=2.5pp applies to trims as well as adds, so a 6pp
     trim takes three monthly sessions.
   A perfectly-timed analyst still leaves the name meaningfully held at
   month 12–15.

**Consequence for ordering:** measure how the loss splits across those three
lags *before* adding any new signal. If rule/execution lag dominates, the
first fix is a §2.1 allocator sweep (faster ratchet on positions already
under cap), free, no new data.

## 2. Evidence gathered this session

### 2.1 Where the loss actually happens (price cache, backtest window)

For each name's worst peak-to-trough between 2022-01-01 and 2024-06-12:
`worst1%`/`worst5%` = share of total log decline on the single/five worst
days; `after-20%` = share of the decline occurring *after* the stock was
already 20% below peak.

```
tkr         peak     trough  decline  worst5%  worst1%  days  after-20%
SPWR  2023-06-29 2024-04-17    97.6%      51%      19%   201       91%
RUN   2022-09-12 2023-10-27    77.1%      44%      12%   284       85%
QS    2022-01-03 2023-11-01    78.1%      57%      15%   460       83%
EOSE  2022-01-03 2024-05-08    91.5%      61%      16%   589       90%
ENVX  2022-01-03 2024-04-25    78.5%     102%      35%   580       84%
AMPX  2022-09-23 2024-06-12    90.1%      58%      14%   431       87%
TSLA  2022-01-03 2023-01-03    73.0%      46%      10%   251       82%
FSLR  2023-05-12 2023-11-09    42.8%      47%      11%   125       59%
ENPH  2022-12-02 2023-11-09    77.5%      55%      20%   235       85%
TTD   2022-01-03 2022-11-09    55.7%      88%      25%   215       71%
NVDA  2022-01-03 2022-10-14    62.7%      46%      10%   197       74%
AMD   2022-01-03 2022-10-14    62.8%      54%      15%   197       76%
```

Readings:
- The announcement-day gap is unavoidable (public information is
  simultaneous) and is 10–20% of the decline. **80–91% of the loss on the
  speculatives came after the name was already down 20%.** "The damage is
  done" is wrong by roughly a factor of ten on SPWR.
- Distress is a sequence (late filing → going concern → dilutive raise →
  delisting notice → Chapter 11), each step its own gap-down. Catching step 1
  at day 4 instead of next call + four-quarter ratchet skips steps 2–5.
- **The controls show the same shape.** NVDA/AMD/TSLA: 74–82% of decline after
  −20%, then the buy of the decade. A price-only brake cannot tell SPWR from
  NVDA in Oct 2022. Filing-based evidence can (NVDA never filed NT 10-Q, never
  carried going-concern language, never raised dilutively). **Filings are the
  discrimination tool; price is the latency tool. Build filings first so the
  fast brake doesn't cost NVDA.** Test 1's `optimistic ≈ $0 / pessimistic ≈
  −$42.7k` asymmetry is the same warning.

Script to regenerate: inline Python over `analysis/data/price_cache.json`
(see the session transcript; ~30 lines; should be committed as
`analysis/decline_decomposition.py` when work resumes).

### 2.2 Things noticed while reading the repo (not part of the framework)

- `docs/handoffs/2026-09-05-state-of-play.md`, `prompts/resolve-open-four.md`,
  and `analysis/data/run_state/test4-analyst-noise-floor/` are **untracked**;
  nothing committed since `3c689a7`. Test 3's wrap-up reports a stale
  `.git/index.lock` — check it cleared. `CLAUDE.md` still points at the 09-03
  state of play.
- The v6 prompt rollback (`c514ae1`) is on `dev` only. `sweep/db-corpus-baseline`
  (93 ahead / 1 behind) still carries **v10+auto1** in
  `docs/EVALUATION_PROMPT.md`. Test 4 reads that file and says so — its noise
  floor describes v10+auto1, not production v6.
- `allocator_v4.py` is **not** the current allocator; it is the consensus-
  modifier experiment on v3. The session harness imports `allocator_v3`. Its
  result was not located in wrap-ups — check before re-proposing any
  consensus/valuation modifier (CLAUDE.md rule).
- `server/routes/evaluate.js` still uses `max_tokens: 4096`; the v9 postmortem
  identified 4096 as marginal (structured block truncated). Fix was applied
  only to `backtest_runner.py` (8192).
- `analyst_direct_scorer.py` benchmarks every ticker against SPY; gate §3.1
  specifies sector ETFs (TAN etc.). Solar names are graded against the S&P.
- `versions.js` pins `claude-sonnet-4-6`, a bare alias, against gate §8.
- Test 4 paused at 11/50 transcripts (all megacap so far), ~1.07M tokens,
  resumable via `python3 test4_noise_floor.py score`.

## 3. Proposed signal framework

Two constraints decide whether a source can ship: (a) **point-in-time
reconstructable** — otherwise it cannot be backtested, so it cannot clear the
gate; (b) enters as a **document or number about the company** (firewall
forbids portfolio data, not non-transcript data). This is a specification of
BUILD_STATE Step 5 (Alerts: "press release / 8-K classification →
thesis-positive / thesis-negative / noise"), not a new layer.

| # | Signal | Latency gain | Discriminates SPWR from NVDA? | Point-in-time | Cost | Entry point |
|---|---|---|---|---|---|---|
| 1 | **8-K item codes + NT 10-Q/10-K** (5.02 officer departure, 3.02 unregistered equity, 4.02 restatement, 2.04 debt acceleration, 4.01 auditor change, 1.03 bankruptcy; S-3/424B raises) | quarter → ≤4 days | **yes** | EDGAR, free | low, mechanical, no LLM | allocator hard trigger; may open an **out-of-cycle single-ticker session** (bounded exception to `new_calls_only`) where the analyst reads the filing text against the stored thesis |
| 2 | **Runway / dilution** (cash ÷ quarterly burn; burn acceleration; debt maturities vs cash; ATM usage; dilution % = new shares / existing) | *leads* 2–4 quarters | yes (speculatives) | XBRL + 10-Q text | low | allocator cap modifier + analyst fact sheet |
| 3 | **Post-call price reaction** (1–3 day return after the call; PEAD) | none, adds a dissenting vote | partial | price cache, have it | ~zero | allocator sizing modifier (same slot `allocator_v4` used) — reaction is known at session time under K=30, no look-ahead |
| 4 | **Peer read-through** (cohort members report on different dates; extract shared-market statements; attach as context to next cohort member's eval) | weeks; 3–4 looks/quarter at the market instead of 1 | depends on cohort granularity | transcripts, have them | LLM calls | analyst context; uses DOMAIN.md cohorts — the one source that is uniquely Luis's edge |
| 5 | **Guidance / thesis ledger** (persist the analyst's own "measurable condition that would change this recommendation" and management's forward numbers; score next call against them → feeds stumble test 1 mechanically) | detection, not cadence | n/a | transcripts | LLM | analyst; **no new knob** — routes into the existing categorical decision matrix |
| 6 | **Financial-statement fact sheet** (§4) | detection, not cadence (fires on filing date ≈ call date) | yes | XBRL, free | low | analyst context + a few hard triggers |
| 7 | Form 4 insider clusters (asymmetric: buys informative, sells weakly) ; FINRA short interest ; shares-outstanding growth | days | weak | free | low | second tier |
| — | Social media, 13F, analyst ratings/estimate revisions, options IV, CDS | — | — | not PIT / expensive / redundant | — | **skip** (credit and options genuinely lead in distress; hold for later on cost) |

**Thesis-reset rule (from Luis's business-thesis idea).** The analyst already
authors a falsifiable thesis every quarter (RECOMMENDATION section's watch
condition; §8 intake evaluation) and it is discarded. Persist it; Luis edits
in RADAR like Type A/B (solves scaling). On a declined Trim, **one** thesis
reset per position, dated, with a measurable condition and a deadline
quarter; a miss on the reset thesis makes the next Trim non-declinable;
TRACK_RECORD reports "reset theses met: n of m." Without the bound this is
the §8 capitulation model formalized. Backtest hazard: human theses carry
look-ahead — in the simulator, theses must be analyst-generated from the
prior transcript only; human theses apply forward from the day written.

**Valuation ratios (P/E, P/S vs peers).** Belong allocator-side as a sizing
modifier, but address the *profit-take* side (executing well, priced for
it), not the loser side — losers get cheaper as they fall. Needs point-in-
time fundamentals (XBRL by filing date) and a peer table. Lowest priority for
this problem.

**Technicals.** Chart patterns: no. Cross-sectional momentum and trend-
following exits have held up; for this problem the latter is a **daily
circuit breaker in a quarterly-information system**, exit-only never entry.
Spec already has the tripwires (±20% in 5d, 15% DD from 60d peak) as
notifications. Prior: passes on speculatives, fails on established (Test 1
asymmetry; no-average-down makes a stop a permanent exit for speculatives).
Must be evaluated behind the filings layer, not instead of it.

## 4. Fact sheet design (signal #6)

Not raw statements. **A dozen ratios as an eight-quarter series plus a
"metric dropped since last quarter" flag**, judged against the company's own
trailing distribution (z-score), so NVDA's inventory build is compared to
NVDA's own DSI variance and AMPX's to AMPX's. No cohort thresholds tuned on
16 names (§2.1 overfitting trap); cohort comparison is a second pass using
the same cohorts as read-through.

**Two templates, chosen by tier** (design decision, not a fit):

- *Established:* DSI and DSO vs revenue growth (inventory +60% on revenue +10%
  → DSI 60→87 days, guidance cut typically the following quarter); accruals
  (NI − CFO)/assets (Sloan); non-GAAP–GAAP gap and SBC as % of revenue; gross
  margin vs guided; capex vs D&A against the growth narrative; deferred
  revenue / RPO for software.
- *Speculative / pre-revenue:* runway and burn acceleration; backlog,
  book-to-bill, backlog→revenue conversion; customer concentration footnote;
  dilution and ATM usage; milestone delivery vs stated timeline (= thesis
  ledger). Inventory ratios are undefined/meaningless here.

**Tier-invariant hard triggers** (allocator, mechanical): going-concern
language; NT 10-Q/10-K; material weakness (Item 9A — strongest predictor of
restatement); auditor change; DTA valuation allowance (management's own
internal forecast turning negative); runway below threshold with no announced
financing.

**Corroboration is the discriminator.** "Inventory grew ahead of demand" is
a claim; NVDA's filing corroborates it (customer prepayments, deferred
revenue, purchase-commitments footnote moving with inventory); AMPX's does
not, so the claim rests on credibility alone → prompt's mitigation test
scores it "unproven," blind spot #5 applies. Same ratio, two answers,
separated by corroborating lines. NVDA's own 2022 build preceded inventory
charges; its 2023 build was right. The fact sheet supplies evidence or its
absence; the analyst integrates by industry/stage (what it is good at when
given facts, bad at when it must recall them).

Why the CFO question doesn't matter: not misstatement (rare, illegal) but
selection/framing, non-answers in a Q&A run by access-dependent sell-side
with one question each and thin coverage on small caps — and more
importantly, **a single-transcript evaluator has no denominators**.
"Inventory was $180M" carries no information without eight quarters and the
revenue line. That is the v6-changelog gap ("needs cross-transcript
context").

## 5. Test plan

### Test 7 — lag decomposition (run first; simulator only, $0)

For each loser in ALL16 (RUN, QS, EOSE, ENVX, AMPX, SPWR, TSLA 2022–23), from
existing transaction + verdict logs: (a) peak → first bearish verdict
(detection lag, analyst), (b) first bearish verdict → first sell (rule lag,
ratchet), (c) first sell → flat (execution lag, `X`). Price each in dollars.
Same shape as Test 1. Output decides whether the first fix is a §2.1 ratchet
sweep or a new signal.

### Test 8a — ENPH design case (2018→2025)

ENPH is the **design** case, not the validation: v6 was tuned on ENPH+TTD,
both Step 0 runs were ENPH-only, four trend-layer flips are ENPH, and Luis
knows the ending. Use it to learn *what fires and when*, then **freeze the
rules before touching Test 8b**.

Steps: pull XBRL company-facts for ENPH; compute §4 established-template
ratios quarterly by filing date; pull 8-K item history; compute post-call
reactions from price cache; build cohort read-through from SEDG/RUN/SPWR/
FSLR/distributor transcripts already in the corpus (check which exist);
line all of it up against ENPH's stored v6 verdict history (first
Weakening/Trim date from `Analysis`) and price path. Corpus caveats: ENPH is
not in ALL16 (dollar attribution from prices, not simulator); transcripts
start ~2020 (21 calls) — 2018–19 would need loading, but that period mainly
tests non-firing, which the controls cover better.

### Test 8b — eight-name discrimination test (the validation)

Selected **by rule before looking**, fire set vs control set. Metric is
**discrimination, not recall**: a brake that gains two quarters on ENPH with
zero control fires is a result; one that gains three and fires on NVDA is a
failed experiment (Test 1 already priced that failure).

- **Fire set:** ENPH, SPWR, RUN (solar cohort — also exercises read-through),
  + one pre-revenue name (EOSE or QS) for the speculative template.
- **Control set:** NVDA, AMD, TSLA (2022 — established, drew down 60–73%,
  recovered), **FSLR 2023** (same cohort as ENPH, −43%, thesis intact — the
  sharpest control; if read-through fires on FSLR like ENPH it is reading
  "solar is bad" not "resi solar demand is bad").

Pre-registered outputs: per fire-set name, *quarters gained* = first bearish
date from new signals vs first bearish stored verdict; per control, whether
any brake fired and the cost from false exit to recovery. Report established/
speculative split and 2022 separately (§10 rules 4–5). Binomial honesty:
n=8, this is a design screen, not a gate run; anything adopted still goes
through §2.1/§2.2a with the recent holdout intact.

### Build order after the tests

1. Test 7 decomposition. 2. Thesis + guidance ledger (transcript-only, PIT-safe,
repairs a signal already generated and discarded). 3. 8-K/NT poll + runway
triggers (mechanical, free, covers 3 of Luis's 4 examples directly).
4. Post-call reaction modifier (free). 5. Peer read-through. 6. Fact sheet.
7. Exit-only price circuit breaker sweep (behind filings). 8. Valuation
modifier last.

## 6. Predictions baked into this conversation

Written so they can be checked.

1. **Test 7:** rule + execution lag will dominate detection lag for the
   speculatives; the analyst's first bearish verdict will typically precede the
   first sell by ≥2 quarters. If so, a ratchet that skips the no-op tranche 1
   when the position is already under cap is the cheapest win in the project.
2. **ENPH (8a):** the financial-statement fact sheet leads the stored verdict
   by **≤1 quarter** (ENPH's problem was distributor channel inventory — on
   *their* balance sheets — plus rates and NEM 3.0, not its own statements).
   Peer read-through leads more. The regulatory event (CPUC NEM 3.0 decision,
   Dec 2022, at the peak) leads most and is **not in the proposed set** —
   Layer 3 territory. Expect ENPH to tell us which signal to build first, not
   to vindicate the fact sheet.
3. **Controls (8b):** a price-only brake fires on all four controls. The
   filings layer fires on **none** of NVDA/AMD/TSLA (no NT filings, going
   concern, dilutive raise, auditor change in 2022). FSLR is the coin-flip
   and the real test of read-through granularity.
4. **Runway** is the single most predictive number for EOSE/QS/AMPX/ENVX and
   leads the dilutive raise by 2–4 quarters.
5. **Post-call reaction** will show measurable disagreement with the analyst
   on Add verdicts (analyst Add, stock −15% or worse on the call) and those
   disagreements will underperform over the following 60 days.
6. **Valuation modifiers** will be roughly neutral on returns (priced in;
   `allocator_v4`'s own docstring said so) and will not help the loser side.
7. **Exit-only price stop:** passes on speculatives, fails on established.
8. Each 1pp of analyst-direct lift is worth ~$5,825 (Test 1 gradient, fragile,
   three-event basis) — the yardstick for whether detection improvements pay.

## 7. Commands to start with on return

```zsh
# state of the tree first — three untracked items and a possible stale lock
cd "$HOME/.../investment-agent"
ls -la .git/index.lock 2>/dev/null
git status --short
git pull origin dev   # per parallel-development rule; expect the c514ae1 prompt rollback

# ENPH's stored verdict history (baseline dates for Test 8a)
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  psql "$DATABASE_URL" -c "
SELECT t.\"callDate\"::date, a.\"thesisHealth\", a.recommendation,
       a.\"recommendedSize\", a.\"freshMoneyAllocation\", a.\"createdAt\"::date
FROM \"Analysis\" a JOIN \"Transcript\" t ON a.\"transcriptId\"=t.id
JOIN \"Ticker\" k ON t.\"tickerId\"=k.id
WHERE k.symbol='ENPH' ORDER BY t.\"callDate\";"
```

XBRL: `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
(User-Agent header required; free; each fact carries `filed` and `end`
dates — use `filed` as the point-in-time key, never `end`).

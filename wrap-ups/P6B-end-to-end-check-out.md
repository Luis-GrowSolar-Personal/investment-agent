# P6B end-to-end check: does the minimal prompt's score translate to portfolio dollars? Wrap-up

**Run ID:** `p6b-end-to-end-check`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial:** the reference reproduced, all five cells ran at all three phases, and the seed check ran.
**Real spend: $7.75** (arm B on 195 transcripts $4.19; noise arm on 100 transcripts $3.56) against the $15 cap. Everything after scoring is simulator-only and cost $0.
**Reading version (renders correctly anywhere, phone included):** https://claude.ai/artifact/H7JEpgz4AzTCV3HKEC5aii
**Scope boundary: report, do not decide.** Nothing is promoted. `promoted_version` is untouched, the trend layer is untouched, and no mapping cell beyond the two pre-registered ones was run.

---

## §0. Defined terms

**In plain English first.** The portfolio simulator is a fixed set of rules that turn an analyst's verdict on each earnings call into buys and sells, starting from $100,000 in 16 stocks between January 2022 and June 2024. Once a month it looks at the calls that just came in. It puts new money only into names that just reported. It pays for a buy by trimming something else. It never moves one position by more than 2.5 points of the portfolio in a single month. This run swaps the analyst feeding those rules, and asks whether the portfolio does at least as well.

**The six settings that define the settled configuration** (unchanged from the 2026-09-05 reference, `docs/handoffs/2026-09-05-state-of-play.md` §5.1):

- `swap_funding`: a buy is paid for by trimming a holding, not from a cash reserve.
- `K` = 30: trade once every 30 days.
- `new_calls_only`: money goes only into names that reported that month.
- `X` = 2.5pp: **a per-position, per-session speed limit in points of portfolio, not a budget for new tickers and not a cap on position size.** Worked example: a 5% position may end the month anywhere between 2.5% and 7.5%, and no further, however strong the verdict.
- `pooled`: within a session all sells execute first, then the cash is pooled and spent in rank order.
- `per_event_date`: how much of a donor holding may be trimmed to fund a buy is counted per calendar date; at a 30-day cadence this equals counting it per session.

**Other terms.**

- **Two rulers.** *Session-sampled* drawdown looks at the portfolio only on the monthly trading dates. *Daily-marked* drawdown values it every day. **Every drawdown in this report names its ruler**, and the daily ruler is the one compared, because the session ruler understates the fall (reference: 17.32% session-sampled against 23.46% daily-marked).
- **Phase-averaged.** The 30-day schedule can start on day 0, 10 or 20. Every figure is the average of the three phase runs. The three phases differ by a few thousand dollars, which is the noise band here.
- **Overlay.** The rules were built to read v6's verdict fields. Arm B emits only a score, so a small translation layer (`analysis/p6b_overlay.py`) builds each event's fields from the score. It is fixed in advance in the prompt's §4 and touches nothing in the simulator.
- **Trend-layer bypass.** Normally a second layer adjusts v6's verdict using its history (for example turning a Hold into a Trim). B has none of the inputs that layer needs, so in every overlaid cell the final action simply equals the per-call verdict. The A0 cell measures what that costs on v6's own calls.
- **The mapping** (pre-registered, not tuned): score ≤ −2 becomes **Trim**, score ≥ +3 becomes **Add**, anything else **Hold**. The one sensitivity cell moves the Add cut to +2.
- **No-regress.** The gate's own test (`PROMOTION_GATE.md` §4): the portfolio must not do worse than the incumbent. Pre-registered: B3's phase-averaged final value inside A0's phase range, and its daily drawdown not worse than A0's by more than A0's own phase spread.
- **Deployment rate.** How fast the $100,000 gets invested: days until cash falls below 5% of the portfolio, and average cash share across the monthly sessions.
- **Cells.** **R**: v6 as the reference ran it. **A0**: v6's own per-call verdicts fed through the same overlay B gets (the fair comparator). **B3**: B's score at the pre-registered mapping. **B2**: B with the Add cut at +2. **N**: A0 with 100 events replaced by a fresh v6 re-score.

**Corpus.** 195 events across 16 stocks up to 2024-06-12, as `load_events_dedup_on()` returns them. Event-list sha256 `724bba09…85dd` (`repro.json` → `event_list_sha256`). Prices `analysis/data/price_cache.json` (the simulator's own cache, frozen, not refreshed).

---

## Headline

> On the ALL16 window the settled configuration ends at **$184,819** with v6 (R), **$183,780** with v6 stripped to its per-call verdicts (A0), and **$210,351** with the minimal prompt's score at the pre-registered mapping (B3); daily-marked drawdowns **23.46%** / **23.91%** / **16.97%**. B3 is **above** A0's phase range of **$175,269 to $192,981**. On the pre-registered reading, B **exceeds** the end-to-end check.

The pre-registered rule for "above" says: **a finding worth its own document; do not promote on it here** (one window, one seed family, one analyst-model change). This report follows that rule.

**Plain reading.** B not only did not regress the portfolio; on this window it beat v6 by about $26,600 (14% higher) and cut the worst daily fall from 23.9% to 17.0%. It did so while investing more slowly (61 funded Adds against 96), because its 45 Trims landed on stocks that then fell a median 24% and its Adds landed on stocks that then rose a median 18%. Three caveats travel with that, and they are in §"What this does not show": the analyst model changed between the v6 archive and B, the window is a famous one for these names, and it is one window.

---

## Step 0. The reference reproduces, bit-exactly

Settled configuration, seed 0, phases 0/10/20, events from `load_events_dedup_on()`:

| figure | reproduced | reference | source |
|---|---|---|---|
| phase-averaged final value | **$184,819.42** | $184,819 (±$1) | `docs/handoffs/2026-09-05-state-of-play.md` §5.1; `resolve-open-four/cells.jsonl` |
| phase-averaged drawdown, session-sampled | **17.32%** (17.324) | 17.32% (±0.02) | same |
| phase-averaged drawdown, daily-marked | **23.46%** (23.458) | 23.46% (±0.02) | same |
| per-phase finals | $179,944.91 / $189,914.19 / $184,599.16 | $179,945 / $189,914 / $184,599 | cells `1a-phase0`, `1a-phase10`, `1a-phase20` → `results.final` |

All three per-phase finals, session drawdowns and daily drawdowns equal the reference cells to within 1e-6. The trade-logging wrappers used for the decision-stream diff were active during this reproduction and change nothing (`repro.json`, `manifest_repro.json`).

## Results, five cells (phase-averaged, seed 0)

| cell | final value | phase finals (0 / 10 / 20) | phase spread | drawdown, session-sampled | drawdown, **daily-marked** |
|---|---|---|---|---|---|
| R: v6, reference | $184,819 | 179,945 / 189,914 / 184,599 | $9,969 | 17.32% | **23.46%** |
| A0: v6 through the overlay | $183,780 | 183,091 / 192,981 / 175,269 | $17,712 | 17.26% | **23.91%** |
| **B3: score, Add at ≥ +3** | **$210,351** | 214,227 / 209,330 / 207,495 | $6,733 | 11.26% | **16.97%** |
| B2: score, Add at ≥ +2 | $242,415 | 240,270 / 249,799 / 237,175 | $12,624 | 12.60% | **19.77%** |
| N: A0 with 100 events re-scored by v6 | $186,045 | 186,700 / 194,538 / 176,897 | $17,640 | 15.36% | **21.89%** |

Daily-marked drawdown by phase: A0 22.82% / 24.72% / 24.18%; B3 17.54% / 16.82% / 16.56%. **B3's daily drawdown is lower than A0's in every phase.** B3's lowest phase ($207,495) is **$14,514 above** A0's highest ($192,981).

**Seeds.** Seeds 1 and 2 on B3 and A0 give phase finals identical to seed 0 (largest difference $6e-11). The draw spread at X = 2.5pp is zero, as the 2026-09-05 document found, so the band is the phase spread, as pre-registered.

**Events dropped for no B score: 0 of 195** (gate: 3%). B's structured block parsed on all 195 calls; none stopped at `max_tokens`.

---

## The pre-registered reading

- **Pass (no-regress):** final within A0's phase range and drawdown not worse by more than A0's phase spread. Not the outcome: B3 is above the range.
- **Above:** B3's final exceeds A0's phase range with drawdown not worse. **This is the outcome.** B3 $210,351 against a range topping out at $192,981; daily drawdown 16.97% against 23.91%.
- **Below:** did not occur.

## The five predictions, held or not

1. **A0 lands below R by $5k to $20k. Did not hold.** A0 is $1,039 below R ($183,780 vs $184,819), well inside R's own $9,969 phase spread. The trend layer's contribution on this corpus is indistinguishable from zero.
2. **B3 lands at or above A0. Held.** B3 is $26,571 above A0 ($210,351 vs $183,780).
3. **B3's daily drawdown is not better than A0's. Did not hold.** B3's is 6.9 points better (16.97% vs 23.91%). The deployment half of the prediction held: B3 invests more slowly (see below), but slower deployment did not cost it final value.
4. **B2 deploys faster and ends higher than B3, with worse drawdown. Held on all three.** Days to cash below 5%: 450 vs 630. Final $242,415 vs $210,351. Daily drawdown 19.77% vs 16.97%.
5. **The four carrying names end at similar weights under B3 and A0. Held in aggregate, not within it.** AVGO, NVDA, ORCL and TTD together are 71.1% of the book under B3 and 73.4% under A0. Inside that group B3 holds $21.8k more NVDA and $12.0k more AVGO and $13.9k less ORCL and $5.2k less TTD. The extra Trims do land on speculatives (35 of B's 45 Trims).

---

## Diagnostics, B3 against A0 first

Phase-averaged, seed 0. Deployment definitions: **days to cash below 5%** counts calendar days from 2022-01-01 to the first monthly session where cash is under 5% of the portfolio; **average cash** is the mean cash share over the monthly sessions; **turnover** is buys plus sells over average portfolio value.

| diagnostic | R | A0 | **B3** | B2 | N |
|---|---|---|---|---|---|
| events fed: Add / Hold / Trim | 136 / 33 / 26 | 136 / 33 / 26 | **71 / 79 / 45** | 116 / 34 / 45 | 125 / 52 / 18 |
| funded Adds (log entries) | 97.7 | 96.7 | **60.7** | 91.0 | 91.3 |
| …fully / partly / not funded | 1 / 65 / 32 | 0.3 / 67 / 29 | 1.7 / 57 / **2.3** | 2 / 66 / 23 | 0.3 / 62 / 29 |
| sessions where cash bound | 11 | 12 | **3.7** | 12 | 11 |
| swap displacements | 76 | 79 | 61 | 100 | 80 |
| days until cash below 5% | 510 | 500 | **630** | 450 | 510 |
| days until cash below 10% | 490 | 460 | 610 | 440 | 500 |
| average cash share, monthly sessions | 24.6% | 23.7% | **34.5%** | 23.0% | 25.2% |
| buy / sell trades | 85.7 / 102 | 84.7 / 102 | 69 / 99.7 | 91.3 / 143.3 | 79 / 97.7 |
| turnover | 1.73 | 1.81 | 1.87 | 1.75 | 1.61 |
| realized gains | −$7,356 | −$1,744 | **+$18,404** | +$9,364 | −$5,067 |
| distinct stocks held at the end | 15 | 15 | 16 | 15.3 | 15 |

**Deployment.** B3 is slower: 630 days to get under 5% cash against 500, and 34.5% average cash against 23.7%. It also issues far fewer Adds (61 funded log entries against 97), and almost none go unfunded (2.3 against A0's 29.3). What bound each Add (`funding_log` → `binding`, per phase): the session speed limit bound about the same number in both (A0 54 to 57 of 97, B3 50 to 53 of 61), but **cash ran out on about 41 of A0's 97 Adds against about 8 of B3's 61**. B3's Trims and fewer Adds left it with cash when it wanted it. The table shows fewer, better-placed Adds, not a bigger deployment.

**Ending value by stock** (phase-averaged, seed 0; dollars):

| stock | R | A0 | N | **B3** | B2 |
|---|---|---|---|---|---|
| NVDA | 43,508 | 38,275 | 40,228 | **60,116** | 70,135 |
| AVGO | 38,627 | 39,167 | 39,629 | **51,154** | 46,299 |
| ORCL | 29,023 | 34,102 | 32,592 | **20,227** | 35,451 |
| TTD | 23,436 | 23,343 | 23,509 | **18,126** | 30,076 |
| FSLR | 5,358 | 7,326 | 16,201 | **23,520** | 34,429 |
| MSFT | 11,637 | 10,197 | 11,075 | **16,117** | 6,086 |
| AMD | 16,378 | 15,401 | 16,310 | 13,310 | 8,663 |
| GOOGL | 7,701 | 9,233 | 2,957 | 5,286 | 6,036 |
| all other (AAPL, AMPX, ENVX, EOSE, QS, RUN, SPWR, TSLA) | 9,153 | 6,739 | 3,547 | 2,493 | 5,238 |
| **carrying four, share of the book** | 72.8% | 73.4% | 73.1% | **71.1%** | 75.1% |
| **speculatives, share of the book** | 6.5% | 6.4% | 10.1% | **12.1%** | 15.1% |

The gap between B3 and A0 is concentrated. NVDA (+$21.8k), FSLR (+$16.2k), AVGO (+$12.0k) and MSFT (+$5.9k) account for it, partly offset by ORCL (−$13.9k) and TTD (−$5.2k). This is one window in which the AI names rose sharply, so the result rests on how B's verdicts landed on a few large positions.

**Why B3 ends higher: the quality of what each analyst said** (182-day raw stock return after the call, from the price cache; a diagnostic only, no cell used forward returns):

| analyst / answer | events | median 182-day return | mean | share of stocks that rose |
|---|---|---|---|---|
| v6 archive, Add | 136 | +9.8% | +10.4% | 59.6% |
| **B3, Add** | 71 | **+17.6%** | +21.2% | 69.0% |
| B2, Add | 116 | +14.7% | +18.2% | 65.5% |
| v6 archive, Trim | 26 | −5.8% | +3.8% | 46.2% |
| **B (both mappings), Trim** | 45 | **−24.4%** | −13.3% | 26.7% |
| v6 archive, Hold | 33 | −8.5% | −1.0% | 33.3% |
| B3, Hold | 79 | +7.3% | +7.3% | 54.4% |

B's Trims fell a median 24% over the following six months, against 6% for v6's Trims. Of B's 45 Trims, 35 were on speculatives (median −29.0% after the call). B's Adds rose a median 18% against v6's 10%. The v6 archive's Adds on speculatives had a median of −13.8% (n=29); B3 made only 7 speculative Adds (median +23.8%). That is the mechanism the pre-registration named ("a Trim on a loser funds an Add elsewhere"), visible in the events themselves.

**Where the two analysts agree** (v6 archive → B3): Add→Add 66, Add→Hold 55, Add→Trim 15, Hold→Add 4, Hold→Hold 17, Hold→Trim 12, Trim→Add 1, Trim→Hold 7, Trim→Trim 18. B3 keeps 66 of v6's 136 Adds, downgrades 70 of them (55 to Hold, 15 to Trim), and turns 12 of v6's 33 Holds into Trims.

---

## Decision-stream diff, B3 against A0 (`PROMOTION_GATE.md` §2.3 form)

Ordered trade list `(session date, ticker, side, shares, account)`, seed 0:

| phase | A0 trades | B3 trades | first divergence | matched before it | first A0 trade there | first B3 trade there |
|---|---|---|---|---|---|---|
| 0 | 188 | 175 | index 14 | 14 | 2022-05-01 sell FSLR 8.96 sh (tax-advantaged) | 2022-05-01 sell TSLA 2.00 sh (tax-advantaged) |
| 10 | 195 | 175 | index 14 | 14 | 2022-05-11 sell FSLR 8.18 sh | 2022-05-11 sell TSLA 2.07 sh |
| 20 | 177 | 156 | index 14 | 14 | 2022-04-21 buy TSLA 7.18 sh | 2022-04-21 sell TSLA 2.19 sh |

The two streams are identical for the first 14 trades in every phase: the starter buys, one per stock at its first event (2022-01-31 through 2022-04-01), which fire regardless of the verdict. They diverge at the first session after the starters. In phases 0 and 10 A0's first differing trade sells FSLR while B3's sells TSLA (in phase 0, A0 then buys AAPL where B3 sells GOOGL). In phase 20 A0 buys TSLA where B3 sells it. Only 18 to 21 trade rows in total appear in both streams; the rest differ, so the two portfolios are built from different decisions and the dollar gap is not a pricing or accounting difference.

## The noise cell

N replaces 100 of A0's 195 v6 verdicts with a fresh re-score by unmodified v6 on `claude-sonnet-4-6`, chosen by fixed seed (`random.Random('p6b-e2e-noise-11')`).

- R → A0: **−$1,039** (−0.6%). A0 → N: **+$2,265** (+1.2%), daily drawdown −2.0 points. N's phase range ($176,897 to $194,538) contains R and A0.
- B3 minus A0 is **$26,571**, about **12 times** the A0-to-N movement, and B3's lowest phase clears N's highest phase by $12,957.

**Caveat on what N is.** The archived v6 verdicts in R and A0 came from the analyst model that was in production from 2026-05-02 to 2026-06-27, not `claude-sonnet-4-6`. N therefore measures "v6 re-rolled **and** moved to the new model" on half the events, not a pure re-roll. N's fed mix (Add 125, Hold 52, Trim 18) shows the new model gives v6 fewer Trims than the archive (26) and more Holds (52 vs 33). The dollar movement is small either way.

---

## What this does not show

1. **The model changed between the v6 archive and B.** R and A0 use archived calls from the older analyst model; B3 and B2 use `claude-sonnet-4-6`. A0 against B3 therefore differs in model as well as prompt. N is the only cell that touches this, and it shows a small move for v6. It cannot separate "the minimal prompt" from "the newer model" for B.
2. **Hindsight exposure.** The window (2022-01 to 2024-06) and these names (NVDA, AVGO, TSLA and their peers) are the most discussed of the period, and `claude-sonnet-4-6` has a January 2026 cutoff. B's prompt tells it to ignore anything it recalls outside the transcript, but this run cannot test whether it did. Both analyst models were trained after the whole window, so this run cannot test recall for either.
3. **One window, 195 events, three phases of one seed family.** The ranges here are phase spreads, not bootstrap ranges. NVDA, FSLR and AVGO carry most of the gap.
4. **The trend layer is bypassed in A0, N and both B cells.** R minus A0 (+$1,039) is the entire measured trend-layer effect on this corpus, and it is inside R's own phase spread.
5. **The mapping is the pre-registered one.** No other threshold was run. B2, the one sensitivity cell, is more profitable and has a worse drawdown than B3; choosing between them is not a decision this report makes.

---

## What this means, three ways (per the pre-registered reading)

- **Pass (no-regress).** B is cleared on the end-to-end check, and promotion becomes a design question (P6D).
- **Above (the outcome).** B3 ends $26,571 above v6 through the same rules with a smaller daily drawdown, and **is a finding worth its own document**; the pre-registration says not to promote on it here. What would turn it into a promotion decision is outside this run: a run on a window that B did not see through recall (or evidence it did not), and the analyst-model confound separated.
- **Below.** Did not occur.

**Design questions this leaves (for the design session, not decided here):**

1. **Which v6 fields the allocator and trend layer actually need (P6D).** This run bypassed the trend layer and set `recommended_size` to none in every overlaid cell, and B3 still did better. The list of fields the allocator "merely receives" may be very short.
2. **Whether the trend layer's contribution is worth carrying into a B-based analyst.** Measured here it is +$1,039 (R minus A0), inside R's own phase spread, and B's score may already contain what the trend layer added. This corpus cannot separate the two.
3. **Deployment.** B3 deploys more slowly and ends higher; B2 deploys faster and ends higher still, with a larger drawdown. The 2026-09-05 finding that deployment rate governs this allocator holds for B2 versus B3, but not for B3 versus A0, where analyst quality dominated.

---

## Premise flags, deviations, and what was not done

**Premise flags (all in `findings.md` at read time):**
1. The 2026-09-24 state of play (§5) says "~660 transcripts, ~$16". The harness returns **195 events**; the prompt's "~150–195" is right. Cost was $7.75.
2. **Model confound**, described above; not in the prompt.
3. The prompt says 147 transcripts are on disk under `analysis/data/transcripts`. **All 195 are.** 194 match the DB text after whitespace normalisation; NVDA 2021-11-18 differs at character level (both 50,290 characters). The DB text is the source, as the prompt requires.
4. The events loader does not carry transcript ids; they were re-queried with the loader's own filters (SELECT only, read-only connection) and the lowest id per (ticker, call date) kept, as the loader does.

**Deviations:**
- The cells were first run once on an earlier driver commit as a smoke check (27 runs, seven seconds). `cells.jsonl` and the logs were deleted and regenerated against the final driver commit, so each committed cell records the driver that produced it. The numbers were identical.
- The clean-tree check for manifests excludes this run's own output directory (results being produced are not dirty code). The driver, overlay and every input were committed before they produced output.
- The realized-turnover, cash-bound and deployment definitions in the diagnostics table are mine, stated above, because the prompt names the diagnostics without defining them.

**Not done:** no promotion, no registry `promoted_version` change, no trend-layer change, no mapping cell beyond B3 and B2, no DB writes (the DB connection was read-only), no cache refresh, no holdout, no leave-one-ticker-out or other robustness cut beyond the ones above.

**Left for the design session:** the three design questions above; whether to run B on a window that pre-dates its recall (or on masked tickers) before treating the $26.6k as real; whether to re-score the ALL16 corpus with v6 on `claude-sonnet-4-6` for all 195 events (about $8) to remove the model confound from A0.

## Provenance and artifacts

Driver `analysis/p6b_e2e.py`, overlay `analysis/p6b_overlay.py` (each committed before it produced output; the driver commit is recorded in `progress.json`). State in `analysis/data/run_state/p6b-end-to-end-check/`: `progress.json`, `findings.md`, `repro.json`, `manifest_repro.json`, `events_manifest.json`, `scores_b_all16.jsonl`, `scores_noise_all16.jsonl`, `cells.jsonl` (27 runs, each with `config_hash`, `driver_commit`, `overlay_sha256`), `logs/` (funding log, target-cap log and trade list per run), `summary.json`. Manifests record the git commit, `git_dirty: false`, the driver file, and sha256 checksums of `type_classifications.json`, `price_cache.json` and `fundamentals_cache.json`. Cell keys: `<cell>-s<seed>-ph<phase>`. Every dollar and drawdown figure is `cells.jsonl` → `results.final` and `results.dd_daily` / `results.dd_session`, averaged over the three phases.

```bash
# reproduce everything from the committed scores ($0)
python3 analysis/p6b_e2e.py repro
python3 analysis/p6b_e2e.py cells
python3 analysis/p6b_e2e.py summary
```

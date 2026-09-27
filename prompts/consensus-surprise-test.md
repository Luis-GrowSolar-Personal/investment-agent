# Consensus surprise — does beating analysts' EPS estimate predict the next six months? One session

**Run ID:** `consensus-surprise`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/consensus-surprise-test-out.md`
**Cost: $0 marginal.** Luis has a **premium** Alpha Vantage key, stored
in `.env` as **`AV_API_KEY_PREMIUM`**. Use it for every request in this
run. **Never print, log or commit its value.** One `EARNINGS` request per
train company not already fetched: about 33, since the screen's 20 are
reused. No Claude API calls, no scoring.

**One session.** The premium key removes the daily cap. Keep the run
resumable anyway (CLAUDE.md "Long CLI runs"): progress is written after
every fetch, and a re-run skips what is saved.

---

## Framing

Every route to finding winners has failed so far:
- reading the call: B, P7, B's own notes;
- peers' calls: P5;
- sector averages;
- the stock's own announcement-day move.

The last is the market's reaction to the report. It showed no drift here
(−0.033, range −0.098 to 0.035;
`wrap-ups/P5-close-sector-and-drift-out.md`). The one documented route
left is **surprise against analyst consensus**: companies that beat what
analysts expected tend to outperform afterwards. That effect was
historically the stronger form of the drift, though it has also faded.

**The data.**
- Alpha Vantage's free `EARNINGS` endpoint returns every quarter's
  reported EPS, estimated EPS and surprise, back to 2019 or earlier.
- A spot-check against coverage from the time (Cowork, 2026-09-27)
  found the estimates match the **pre-report** consensus: JPM Q1 2023
  $3.41 (Refinitiv, CNBC preview the morning of the report); MU fiscal
  Q1 2023 −$0.02; MU fiscal Q2 2023 −$0.88, against previews of −$0.67
  to about −$0.85.
- Three quarters only. Point-in-time status is **likely, not proven**.

**Firewall.** A company's own reported and expected EPS is data about
that company, not portfolio data (`PROMPT_ARCHITECTURE.md` §1.4). This
run tests it as a standalone signal. Whether it enters the analyst or
the allocator is a later decision.

**Read first:** the wrap-up above (Step 3 and Step 4);
`analysis/p5close_av_probe.py` (reuse its request code);
`analysis/p5close_drift.py` (reuse its return and combination code).

---

## Full-test review amendments (binding; they override everything below, including amendments 1–6 below)

Source: `docs/handoffs/2026-09-27-consensus-full-test-review.md`.

**A. One primary reading.**
- Among train calls B scored **0 or higher** (mean of its two draws), the
  **rank correlation of quarter-adjusted surprise with the 182-day return
  vs SPY**. Pass: ticker-block range (2,000 draws, seed 11) above zero.
- Report how many calls enter.
- Every other reading in this prompt (items 1–6, amendments 1–6) is
  **reported only**.
- **Direction check, reported:** top 19% by combined (B and surprise,
  average percentile rank) against top 19% by B alone, within the B ≥ 0
  calls. Paired big-winner share, with range.

**B. Two conditions on a pass. Both are required.**
- **(a) Unscreened check.** Report the primary on all 57 companies
  **and** on the calls from the ~37 companies the screen did not fetch. A
  pass requires the pooled range above zero **and** a **positive point
  estimate** on the unscreened set.
- **(b) Leave-one-year-out.** Recompute the primary with each calendar
  year removed in turn. A pass requires the point estimate to stay
  **positive in every cut**.

**C. The sector label** (not a gate), applied only to a pass:
- the sector-quarter-adjusted primary is also positive → **"company-picking
  signal; candidate for the analyst"**;
- it is flat → **"sector-level signal; allocator input for sector tilt"**.

**D. Point-in-time checks decide finality.**
- Draw the **5 unflagged** spot-check rows from the top and bottom 5% of
  quarter-adjusted surprise **among the B ≥ 0 calls**; keep the 3 flagged
  rows.
- Write the verdict as **"PROVISIONAL — pending 8 point-in-time checks"**.
  The CLI does not record it as final anywhere. Luis or Cowork checks the
  rows and records the final verdict in the state of play.
- State in the wrap-up that the result is conditional on the vendor's
  estimate matching what the market saw.

**E. Tune test, pre-registered now.** At Step 0, **before any return is
computed**, add a row to `PROMPT_ARCHITECTURE.md` §2.2 as its own commit:
- **CS1, consensus-surprise overlay on B's non-bearish calls.**
  - Train primary as A, with conditions B(a) and B(b).
  - If the train pass is **clean** (pooled range lower end more than 0.02
    above zero, both conditions held), the **tune test** is the same
    primary, measure and B ≥ 0 restriction, on the tune companies, using
    B's existing tune scores. Pass: range above zero, and the sign
    positive in every leave-one-year-out cut.
  - **This spends the reserved tune look** (state of play §3.5).
  - A borderline train pass (lower end within 0.02 of zero) does **not**
    spend it.
- Status: "registered 2026-09-27; train running".

**F. Misleading-result guards (report in the wrap-up):**
- If the beat rate is near 75% in both winner and middle groups, say the
  signal is in the **size** of the beat, not the beat itself.
- If the primary passes on the EPS-scale split's "estimate ≥ 1% of
  price" side and fails on the rest, say the failure is about the
  measure, and name a revenue-surprise source as the next question.

**Headline, replacing the report's opening sentence:**

> Among the ___ train calls B did not score bearish, surprise against
> consensus (quarter-adjusted) ranked six-month returns at ___ (range ___
> to ___). On the ___ unscreened companies' calls: ___. With each year left
> out, the lowest figure was ___ (year dropped: ___). **Provisional reading:
> [pass, clean / pass, borderline / pass on (a)/(b) failing, "one year's
> effect" / fail]**; sector label: [company-picking / sector-level / n/a].
> Pending 8 point-in-time checks.

## Review amendments (binding; they override any conflicting text below)

Source: `docs/handoffs/2026-09-27-consensus-screen-review.md` (go, with
three changes). Commit that file at Step 0.

1. **Three groups, not two.**
   - The groups: **big winners** (+20 points or more over 182 days vs
     SPY), **big losers** (−20 or worse), and the **middle**.
   - **Primary reading: winners against the middle.** Median-surprise
     difference, company-block range (2,000 draws, seed 11) above zero →
     "surprise separates winners".
   - Report losers against the middle beside it. "Finds winners" can
     never be earned by the misses.
   - The full test's item 2 uses the same three-way split.
2. **Quarter-adjusted surprise is the primary measure.**
   - For each matched call: **quarter-adjusted SUE_p = SUE_p − the median
     SUE_p of all fetched matched calls reported in the same calendar
     quarter.**
   - Use it for **every** reading. Report raw SUE_p beside it.
   - Report how many calls each quarter's median rests on.
3. **Spot-checks go where the result is decided.**
   - The five point-in-time rows for manual checking come from the **top
     and bottom 5%** of quarter-adjusted SUE_p among matched calls: three
     from the top, two from the bottom. Seed 11 within those bands.
   - Add a diagnostic: by company, the share of matched quarters where
     AV's own `surprisePercentage` exceeds ±100%. **Flag** companies with
     many such rows (likely a GAAP-vs-adjusted basis mismatch). Report the
     main readings with and without flagged companies.
   - The wrap-up states: **if any of the five extreme rows is later found
     revised or mismatched, the reading drops to "can't tell" whatever
     the numbers.**
4. **Closing rule** (review Q4). A negative screen does **not** close the
   lead on its own; the full test runs. **Exception:** if the screen is
   clearly negative **and** quarter-adjusted surprise relates to the
   announcement-day move r0 at **0.5 or stronger** (rank correlation),
   say "lead closed: the market already priced the surprise". The full
   test is then not needed.
5. **EPS scale split** (review Q5, full test only). Split calls where the
   **estimate is at least 1% of the share price** from the rest. Report
   every reading for both groups. If the effect lives only in the first
   group, say "a revenue-surprise source is the next data question".

6. **After the screen (Cowork, 2026-09-27), reported only; the readings
   are unchanged.**
   - **Sector-quarter adjusted surprise.** SUE_p minus the median SUE_p of
     same-**sector-group**, same-calendar-quarter matched calls. Require
     at least 5 calls; otherwise fall back to the quarter median and count
     how often that happens. Report the three-group comparison and the
     rank correlation on this measure beside the primary one. The screen
     showed a within-sector-year rank correlation of −0.001.
   - **Spot-check rows.** List **3** from the flagged companies' extremes
     **and 5** from **unflagged** companies' top and bottom 5% (3 top, 2
     bottom; seed 11). The screen's five were all EOSE and JKS.
   - **Reuse the screen's fetches.** Skip any company whose full `EARNINGS`
     response is already saved under `analysis/data/evals/consensus_av/`
     (the screen's 20, including MU, RUN and JPM). Fetch only the rest.
     Report how many requests were needed.

## Ground rules

1. **Train companies and train calls only.** No tune or holdout returns.
2. Prices from `analysis/data/corpus_v2/scorer_price_cache_v1.json`.
3. **AV etiquette:**
   - at most **30 requests per minute**, well under the premium tier's
     limit;
   - on any `Note` or `Information` rate-limit message, wait 60 seconds
     and retry **once**. If it recurs, stop, report the message, and
     leave the run resumable;
   - raw responses are saved gitignored under
     `analysis/data/evals/consensus_av/`. Commit only the derived table.
4. **Every reading is fixed here, before any return is computed.**
5. An after-the-fact check on train. A pass earns a pre-registered
   candidate; it promotes nothing. Report, do not decide.

## Step −1 / Step 0 — git bookends and resume

State in `analysis/data/run_state/consensus-surprise/`. `progress.json`
first. It records the companies fetched, the requests used today and the
date. Commit, each as its own commit: this prompt; the screen review file;
`docs/handoffs/2026-09-27-consensus-full-test-review-brief.md`; and, if
present, `docs/handoffs/2026-09-27-consensus-full-test-review.md`. **If
that review asks for changes not reflected in this prompt, stop and
report. Do not apply review changes yourself.** Clean
tree. Scripts committed before output.

## Step 1 — fetch (one session)

Fetch the 57 train companies in alphabetical order, one `EARNINGS`
request each, and resume where the last day stopped. Symbol mapping:
- use `TICKER_ALIASES.json` working symbols;
- ANTM → ELV;
- delisted or failed names (FRC, MAXN, SUNW, VIAC/PARA) are tried once
  and recorded if empty. PARA stays excluded for corrupt prices.

When all 57 are done (or recorded empty), go to Step 2 in the same
session.

## Step 2 — match estimates to train calls ($0)

- **Matching.** Match each train call to the AV quarter whose
  `reportedDate` is within **±3 days** of the call date. Report the match
  rate, and list unmatched calls by company.
- **Surprise measure** (fixed now): **SUE_p = (reportedEPS −
  estimatedEPS) ÷ the share price at the last close before the call.**
  Percentage surprise is reported only as a diagnostic, because it
  explodes near zero EPS (RUN shows +1,471%).
- **Also:** beat or miss (sign only), and **surprise persistence**: the
  company beat in both this quarter and the previous one.
- **Point-in-time spot-check,** 5 more quarters. The CLI cannot verify
  these, so list 5 matched quarters (seeded, seed 11, different
  companies) with AV's estimate. Luis or Cowork check them against
  coverage from the time. Do not fetch news.

## Step 3 — the test ($0)

Outcome: the 182-day tradeable-entry return vs SPY, as everywhere.
SUE_p is known at the tradeable entry, since the report precedes the
first close after the call. **Assert no overlap.**

Report, with ticker-block ranges (2,000 draws, seed 11):
1. **Rank correlation** with the 182-day return, for: SUE_p; B's own
   score (mean of two draws); and combined (the average percentile rank
   of SUE_p and B). Also combined minus B.
2. **The winners question.** Top 19% of matched calls by SUE_p (the same
   share as B's 235 of 1,217): the share right (beat by more than 5
   points) and the share **big winners** (+20 or more), with Wilson
   ranges, against 12.6%. The same for the top 19% by combined.
3. **Downside.** Bottom 16% by SUE_p (B's 191 share): hit rate against
   B's 62.3% / 61.3%.
4. **Persistence.** Rank correlation and big-winner share for calls that
   beat two quarters running, against all others.
5. **By year** (2020 separate), and **within sector-year**, pooled as in
   phase 1 Step 1c.
6. **Overlap with the failed announcement-day move.** Rank correlation of
   SUE_p with r0 (from `p5-close-sector-drift/drift.json` inputs). If
   they are strongly related, this is the same signal measured twice.

**Pre-registered readings (each reported separately):**
- **"Surprise drift present"** if SUE_p's rank correlation has its range
  above zero.
- **"Surprise finds winners"** if the top-19% big-winner share's Wilson
  range lies above 12.6%.
- **"Surprise adds to B"** if combined minus B has its range above zero.

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/consensus-surprise-test-out.md`, `.md` only. Open with:

> ___ of ___ train calls were matched to an analyst consensus estimate.
> Surprise against consensus, scaled by share price, ranked six-month
> returns at ___ (range ___ to ___); its top 19% held ___% big winners
> against 12.6% (range ___ to ___); combined with B, ___ (combined minus
> B ___, range ___ to ___). **[Surprise drift present / not] · [finds
> winners / not] · [adds to B / not].** It relates to the announcement-day
> move at ___.

**Close with what it means, both ways.**
- **If any reading holds:** it is the first bullish lead. The next step is
  a pre-registered test on tune companies (54 fetches with the premium
  key).
- **If none holds:** consensus surprise joins the closed leads. The
  machine's role is downside protection.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure. One prompt in, one wrap-up out. **Finish with a commit and
`git push`**, reporting the hash. On failure,
say so and never force.

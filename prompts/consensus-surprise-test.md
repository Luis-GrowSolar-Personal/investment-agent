# Consensus surprise — does beating analysts' EPS estimate predict the next six months? $0, about 3 days

**Run ID:** `consensus-surprise`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/consensus-surprise-test-out.md`
**Cost: $0.** Alpha Vantage free tier (`AV_API_KEY`): **one `EARNINGS`
request per train company, 57 in all, at most 25 per day**, so about 3
days of wall time. No Claude API calls, no scoring.

**This run is multi-day and must be resumable** (CLAUDE.md "Long CLI
runs"). Each day it fetches what the daily limit allows, commits
progress, and stops cleanly with `next_action` set. Re-running the
prompt resumes.

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

## Ground rules

1. **Train companies and train calls only.** No tune or holdout returns.
2. Prices from `analysis/data/corpus_v2/scorer_price_cache_v1.json`.
3. **AV etiquette:**
   - at most 5 requests per minute and 25 per day;
   - stop for the day on any `Note` or `Information` rate-limit message.
     Do not retry that day;
   - raw responses are saved gitignored under
     `analysis/data/evals/consensus_av/`. Commit only the derived table.
4. **Every reading is fixed here, before any return is computed.**
5. An after-the-fact check on train. A pass earns a pre-registered
   candidate; it promotes nothing. Report, do not decide.

## Step −1 / Step 0 — git bookends and resume

State in `analysis/data/run_state/consensus-surprise/`. `progress.json`
first. It records the companies fetched, the requests used today and the
date. Commit this prompt and the review file, each as its own commit, on the
first day only. Clean
tree. Scripts committed before output.

## Step 1 — fetch (day 1–3)

Fetch the 57 train companies in alphabetical order, one `EARNINGS`
request each, and resume where the last day stopped. Symbol mapping:
- use `TICKER_ALIASES.json` working symbols;
- ANTM → ELV;
- delisted or failed names (FRC, MAXN, SUNW, VIAC/PARA) are tried once
  and recorded if empty. PARA stays excluded for corrupt prices.

**Stop and resume** at the daily limit. When all 57 are done (or
recorded empty), go to Step 2 in the same session.

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
  a pre-registered test on tune companies, with fresh fetches of 54 tune
  companies (about 3 days free), before any paid plan.
- **If none holds:** consensus surprise joins the closed leads. The
  machine's role is downside protection.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure. One prompt in, one wrap-up out. **Finish each day's
session with a commit and `git push`**, reporting the hash. On failure,
say so and never force.

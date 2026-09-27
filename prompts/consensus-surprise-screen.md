# Consensus surprise — one-day screen on 22 train companies. $0, under an hour

**Run ID:** `consensus-surprise-screen`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/consensus-surprise-screen-out.md`
**Cost: $0.** Alpha Vantage free tier: **at most 22 `EARNINGS` requests**
(today's allowance of 25, less the 3 used by the probe), at most 5 per
minute. No Claude API calls, no scoring.

## Framing

This is a **screen** for the full test in
`prompts/consensus-surprise-test.md`. **Everything in that prompt applies
unchanged** except what is stated here: the ground rules, the matching,
the SUE_p measure, the Step 3 test items and the report format. Read it
first.

**Why a screen.** 22 companies can only reveal a **large** effect.
State that plainly in the wrap-up:
- **A clear positive** is worth confirming on the full set.
- **Flat means "not a big effect"**, not "no effect". It does not close
  the lead.

The fetched data is **reused** by the full test later (same raw folder,
`analysis/data/evals/consensus_av/`), so nothing here is wasted.

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

As the full prompt, plus:
- If AV returns a rate-limit `Note` or `Information`, stop fetching,
  analyse what arrived, and say so.
- **Reserve 2 requests,** so fetch at most 20 companies, in case of a
  malformed response needing one retry.

## Step −1 / Step 0

State in `analysis/data/run_state/consensus-surprise-screen/`.
`progress.json` first. Commit this prompt,
`prompts/consensus-surprise-test.md`,
`docs/handoffs/2026-09-27-consensus-screen-review-brief.md` and, if
present, `docs/handoffs/2026-09-27-consensus-screen-review.md`, each as its
own commit. **If the review asks for changes not reflected in this prompt,
stop and report. Do not apply review changes yourself.** Clean tree.
Scripts committed before output. Write the fetch and analysis scripts so
the full test can reuse them unchanged.

## Step 1 — choose the 20 companies (fixed before fetching; Luis, 2026-09-27)

**Winner-rich selection, within-company comparison.** From the 57 train
companies, excluding those expected empty (FRC, MAXN, SUNW, VIAC/PARA):
1. For each company, count its train calls that became **big winners**
   (+20 or more over 182 days vs SPY) and its **other** train calls.
2. Keep companies with **at least 2 big-winner calls and at least 6
   other calls**.
3. Take the **20 with the most big-winner calls**. Break ties by total
   calls, then alphabetically.
4. RUN, MU and JPM are included **only if they qualify**. Reuse their
   probe files if they are the full `EARNINGS` response.

Commit `selection.json`, with each company's winner and other counts,
before any request.

**Why this is valid, stated in the wrap-up.** Companies are chosen for
having winners, so the comparison is **inside those companies**: big-
winner calls against the same companies' other calls. That answers "does
surprise separate winners from the rest?" It does **not** answer "how
often does a beat lead to a big winner across the market?" The
market-wide rates in items 2–3 below come from a winner-rich sample, so
they are **inflated by design**. Report them, but label them as such and
do not read them against 12.6%.

## Steps 2–3 — as the full prompt, on the screened calls only

Same matching (±3 days), same SUE_p, same test items 1–6, same
pre-registered readings, on the matched calls from these companies.

**Add the primary screen comparison (Luis's case-control design), fixed
now:**
- Among the matched calls, compare **big-winner calls** with **the same
  companies' other calls** on:
  - (a) **beat rate** (reported EPS above estimate);
  - (b) **median SUE_p**.
- Use a **company-block** bootstrap (2,000 draws, seed 11). Resample
  companies and recompute both groups inside them.
- Also compare **within each company**: the share of companies whose
  winner calls had a higher mean SUE_p than their other calls, against
  the 50% expected by chance.

**Screen reading, primary:** "surprise separates winners" if (b)'s
difference has its range above zero. Report (a) beside it. For scale:
roughly three quarters of large companies beat consensus in a typical
quarter, so the beat rate alone is expected to be high in **both**
groups.

**Add one line to the report:** the **smallest rank correlation this
sample could have detected.** That is roughly the half-width of SUE_p's
ticker-block range, the level below which a true effect would read as
"can't tell".

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/consensus-surprise-screen-out.md`, `.md` only. Open with:

> Inside ___ winner-rich companies, big-winner calls beat consensus ___% of
> the time against ___% for the same companies' middle calls; their median
> quarter-adjusted surprise was ___ against ___ (difference ___, range ___
> to ___): **[surprise separates winners / does not / can't tell]**. Big
> losers against the middle: ___ (range ___ to ___). Surprise relates to
> the announcement-day move at ___. Across
> the ___ matched calls, surprise against consensus
> (scaled by price) ranked six-month returns at ___ (range ___ to ___);
> this sample could detect an effect of about ___ or larger. Its top 19%
> held ___% big winners against 12.6% (range ___ to ___). Combined with
> B: ___ (combined minus B ___, range ___ to ___). **Screen reading: [clear
> positive — confirm on the full set / clear negative / can't tell at
> this size].**

Then items 1–6, the 5 quarters listed for a point-in-time spot-check, and
requests used.

**Close with the decision it sets up:**
- **Clear positive:** run the full test (2 more free days, or one paid
  month).
- **Clear negative:** say how large an effect the screen rules out.
- **Can't tell:** name the two ways to settle it:
  - 2 more free days;
  - about $50 for one month of the paid tier.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure. **Finish with `git push`**, and report the hash; on failure,
say so and never force.

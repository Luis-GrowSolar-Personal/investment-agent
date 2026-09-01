# What autonomy buys — the cadence floor, and the veto sweep

`wrap-ups/close-equivalence-corrected-targets-out.md` closed the equivalence
gate bit-exact and ran the cadence grid. Two results frame this run.

**Cadence buys almost nothing on return, and costs on risk.** Within
`new_calls_only`, K=7 and K=30 are tied ($189,538 vs $189,425, 0.06% apart)
while drawdown falls monotonically as the cadence slows — 25.29% at K=7,
20.58% at K=30, 15.10% at K=90.

**Optimal `X` under `cash_deployment` rises monotonically with the session
interval** — 1.0 / 1.0 / 1.5 / 2.5 / 3.0 pp at K = 7 / 14 / 30 / 60 / 90 —
while `new_calls_only` wants 3pp at every cadence. That is the signature of a
**deployment-rate** constraint: under `new_calls_only` the earnings calendar
caps how often a name can receive, so K does not change the rate; under
`cash_deployment` a name can receive every session, so faster cadence means
faster deployment and X must tighten to compensate. It is §5's land grab
returning through a side door, which is also why all 18 of the grid's Rule 4
drawdown failures are `cash_deployment` cells.

**The question this run exists to answer.** A future agent may ingest
transcripts as they publish and trade on its own schedule, making `K` = 1 —
the floor for this simulator, since transcripts publish intraday and execution
is at the close. Two things change under autonomy, and only one of them is
cadence:

1. **`K` → 1.** Unsampled. The existing curve is flat at its fast end, so this
   is an extrapolation the grid does not support and must be measured.
2. **The veto disappears.** §8's capitulation model exists because a *human*
   declines Trims and Exits, forms attachments to winners at the 25%
   profit-take crossing, and capitulates 30% below the peak. An autonomous
   agent does not. §10 calls the 0%-veto-versus-capitulation gap **"the dollar
   value of discipline… the product's thesis, quantified against Luis's own
   tickers."** It has never been measured.

**The second is very likely where autonomy pays, and this run measures both so
the comparison is like-for-like.**

Read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §8, §9, §10, §10b and
§11 before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, `swap_funding` with the conformant per-date
trim cap, `pooled` execution, `trim_budget_scope = per_event_date`. Work on
`sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/autonomy-cadence-floor-and-veto-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`autonomy-cadence-floor-and-veto`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.

**Write state before reading anything.** Create the directory and an initial
`progress.json` — every step `pending`, `next_action` set to "spec reading not
yet started" — as the **very first action of the session**, before reading the
architecture documents and before Step 0. Update `next_action` once the reading
is done. Then flush `cells.jsonl` after every cell, update `progress.json` after
every step, and append to `findings.md` the moment a finding is established.

Running low on budget is a reason to stop cleanly with a precise `next_action`,
not to rush. **Step 2 is the higher-value half of this run — if budget is
tight, do Step 2 before Step 1.**

## Step 0 — hygiene

Clean tree with a hard stop if `git_dirty` cannot be recorded `false`; driver
committed **before** any manifest, as its own commit, manifests following in a
separate commit. `off` belongs at the **loose** end of any limit axis. Carry the
five gates forward, Invariant #9 per **session**, Invariant #5 conditional.

## Step 1 — the cadence floor

Extend the axis to the fast end:

| Axis | Values |
|---|---|
| **`K`** | **1, 3**, plus 7 and 30 re-run as anchors |
| **Scope** | `new_calls_only`, `cash_deployment` |
| **Limit `X`** | **0.1, 0.25, 0.5**, 1, 1.5, 2, 2.5, 3, 5 pp, and `off` |
| **Phase** | 3 offsets per K (for K=1 phase is degenerate — say so and run one) |
| **Draws** | 7 for the scan; 15 at the top region |

The limit range is extended downward so `cash_deployment`'s optimum stays
**bracketed** at fast cadences — the whole point of Rule 3b's boundary
condition.

**Anchor check:** K=7 and K=30 must reproduce the previous grid's
phase-averaged medians. Report whether they do; a mismatch does not stop the
run but voids the cross-grid comparison, and every affected conclusion must be
flagged.

**Test the rate mechanism explicitly.** Report, per (K, scope): the optimal
`X*`, and `X* × sessions_per_year`. Under the deployment-rate hypothesis `X*`
keeps falling as K falls. Report the product too — if it is roughly constant,
the rate story is clean; if it drifts, say so rather than forcing it.

**Discriminate the competing hypothesis.** The alternative reading is that
trading *near* an earnings call is what produces return, and cash deployed far
from any call is wasted. These make different predictions and one cheap
measurement separates them: **tag every Add with days-since-the-nearest call
for that ticker, and compare outcomes by that distance.** Under the rate story
distance should not matter; under the proximity story near-call Adds should
outperform. Report the comparison whichever way it falls.

## Step 2 — the veto sweep (§8)

**This is the measurement that prices autonomy.** Implement §8's capitulation
model exactly as specified — it is closed, do not re-derive it:

- When a position **first crosses the 25%-of-portfolio profit-take threshold**,
  it becomes a "pet" with probability `p`. The flag is **sticky** for that
  position. `p` is *the fraction of your winners you fall in love with*.
- A pet position **declines all recommended Trims and Exits.** A declined
  `Exit` arms the rule as much as a declined `Trim` — the ENPH shape was a held
  position through a broken thesis, not a skipped trim.
- **Capitulation trigger: −30% from the trailing peak position value** since
  entry. On trigger, **full exit** at that session's close.

§8 also requires this to be run **inside** the cadence sweep, at minimum at the
endpoints — it is path-dependent, and a slower cadence gives a pet position
more room to run before anyone looks.

| Axis | Values |
|---|---|
| **`p`** | **0% (baseline), 10%, 20%, 30%** |
| **`K`** | 1, 7, 30, 90 |
| **Scope / limit** | each cadence's own best cell from Step 1 / the prior grid |
| **Draws** | **15** — pet formation is probabilistic and needs its own variance, separate from the tie-break seed |

Report per cell: final value min / median / max, max drawdown distribution,
number of pets formed, number that capitulated, and realized losses
attributable to capitulation.

## Step 3 — what autonomy is worth

For each cadence, report the **gap between p = 0% and each p > 0%**, in dollars
and percent, with both distributions.

**Pre-declared decision rule, agreed before results are seen:** the value of
removing the veto counts as **real** at a given cadence only if the 0% and
capitulation-`p` **fifteen-draw ranges do not overlap** — Rule 2, unchanged.
Overlapping ranges mean **tied**, reported as tied, never ranked by median.
Report the gap as a range, not a point estimate.

Then state plainly, without recommending anything:

- what an autonomous agent buys by **removing the veto** (Step 3's gap)
- what it buys by **driving `K` to 1** (Step 1's cadence delta at matched
  scope and limit)
- which of the two is larger, and whether either survives Rule 2

## Step 4 — rules

**Rules 1, 2 and 4 unchanged.** Rule 4 scores against the adopted **39.12%**
ceiling on median drawdown across draws plus share-of-draws; robust requires
≥ 2/3. Rule 2: overlapping ranges are **tied**.

**Rule 3** — single clause, `off` at the loose end. Material if `|Δ| ≥` the
smaller of the two adjacent draw ranges; discard immaterial; unimodal if what
remains reads `+…+ −…−`.

**Rule 3b** — plateau within **2.5%** of the peak median, sensitivity at 1% /
2.5% / 5%, never an argmax. Peak at either end of the sampled range means the
optimum is **not bracketed** — which is exactly why Step 1 extends the limit
axis down to 0.1pp.

**When comparing any two numbers, state for each whether it is a forward draw,
a median across draws, or a phase-averaged median.**

## Step 5 — report

Scope boundary: **report, do not decide.** Do not select `K`, a limit, a scope,
a `p`, or a `minPositionPct`; do not amend any spec; do not resolve §12 items.

Open with resume status, then:

> **Cadence floor: `K`=1 best cell [scope]/[X]pp → [return], [DD]; versus
> `K`=30's [return], [DD]. Rate mechanism: `X*` [does / does not] keep falling
> as K falls; `X* × sessions/yr` = [values]. Proximity hypothesis:
> [supported / refuted]. Veto: removing it is worth [range] at `K`=1,
> [range] at `K`=30, [range] at `K`=90 — [separable / tied] under Rule 2 at
> each. Larger effect: [veto / cadence]. Cells passing the 39.12% bar: [list].**

**Two caveats belong in the report, not just in this prompt:** `K`=1 is this
simulator's floor — transcripts publish intraday and execution is at the close,
so "continuous" is not representable — and the backtest models **no slippage,
partial fills or rejections**, the safety scaffolding `CLAUDE.md`'s Step 8(b)
calls for. Any `K`=1 figure is an **upper bound**, not a forecast.

Flag plainly: any gate that fails, any anchor that does not reproduce, any rule
that gives an uncomfortable answer, any previously published number that turns
out to be wrong, and whether anything disturbs the settled decisions in §0.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Do not stage or commit unrelated working-tree changes — stash and pop.
  `testing/` stays gitignored.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.

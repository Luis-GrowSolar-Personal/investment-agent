# Allocator thread — state of play

**Date:** 2026-09-01 (evening)
**Supersedes:** the morning version of this file, and
`docs/handoffs/2026-08-31-allocator-state-of-play.md`. Both remain in git
history; nothing in them is needed to read this.
**Status:** the allocator configuration is **settled**. What remains is a build
decision and a small number of measured-but-undecided parameters.

---

## 1. Where the thread stands

Eight measurement sessions since 2026-08-30. The funding question is closed, the
session model is proven bit-exact against the validated harness, the cadence
axis is bracketed at both ends, and the last major unmeasured axis — the user
veto — has been measured.

**The design is decided. The open items are second-order.**

---

## 2. The settled configuration

| Parameter | Decision | Basis |
|---|---|---|
| **Funding mode** | `swap_funding`, conformant per-date trim cap | measured; +7.5% return for +1.0pp drawdown like-for-like, and §10 rule 4 says this corpus understates it |
| **Cadence `K`** | **30 days** | operational discipline (below), with the return/risk trade understood |
| **Scope** | **`new_calls_only`** — *in this version* | revisit when Layer 3 lands; switching costs a re-tune of `X`, not a redesign |
| **Session change limit `X`** | **2.5pp** | last good marginal step; 3pp is the first bad one |
| **Drawdown ceiling** | **39.12%** | median of four baselines' max drawdowns + 5pp |
| **§11 defect #2** | fix in production | measured; limit-dependent, tied at the historical baseline |
| **Cap restoration** | no mechanism change; wording corrected | caps bind purchases, not realized weight |
| **Cash reserve** | retired — not a knob | cash is a residual |

**Measured performance of the settled cell** (phase-averaged median across 15
draws): **$184,819** final value from $100,000, **17.32%** median drawdown.

Against the same window's benchmarks — all of which are computed **pre-tax
buy-and-hold**, while the strategy figure is **after tax**, so the comparison is
conservative:

| | Final | Max drawdown |
|---|---|---|
| **Settled cell** | **$184,819** | **17.32%** |
| SPY | $113,980 | 25.36% |
| QQQ | $119,178 | 35.25% |
| TMFC | $120,512 | 32.99% |
| Equal-weight of universe | $120,427 | 42.76% |

Beats all four on return by 53–62%, with a lower drawdown than any of them.

### Why `K` = 30 rather than 90

K=90 measures slightly better on both axes ($185,509 at 15.10% versus $184,819
at 17.32%). It was rejected on **operational robustness**, which the backtest
does not model and §10 rule 3 explicitly permits as a structural argument:

- A missed session at K=90 costs 25% of the year's discipline; at K=30 it costs
  8%.
- K=90's phase spread is 7.26% against K=30's 5.39% — the measured fragility to
  *which day you start on* is the same sensitivity, reached independently.
- §2's own table: a K=90 session carries ~17.3 calls (up to 23 in one sitting)
  against ~5.9 at K=30. The rare session is also the heavy one, and heavy
  sessions are the ones that get postponed.

### Why `X` = 2.5pp rather than 3pp

3pp is the grid's peak at every K under `new_calls_only`. 2.5pp was chosen on
marginal value: each step up to 2.5pp buys return at $3,300–$4,800 per point of
drawdown; the step from 2.5 to 3.0 buys it at **$1,413** — the first clearly bad
increment.

---

## 3. What the last two runs established

### The session model is now proven

Gate 1a reproduces the validated harness **bit-exact** — $189,781.58036163618,
seventeen significant figures, diff 0.0. Everything downstream rests on a
harness demonstrated equal to the one behind the settled numbers.

### The cadence axis is bracketed at both ends

`new_calls_only` return by cadence, phase-averaged medians at 3pp:

| K | Final | Drawdown | Staleness |
|---|---|---|---|
| 1 | $200,115 | 26.63% | ~0.5 d |
| 3 | $194,942 | 26.79% | ~1.5 d |
| 7 | $189,538 | 25.29% | 3.3 d |
| 30 | $189,425 | 20.58% | 14.1 d |
| 90 | $185,509 | 15.10% | 42.7 d |

**Return rises monotonically as cadence quickens; drawdown rises with it.** The
whole axis is one trade: roughly 5pp of drawdown per 3–6% of return.

### The veto — §10's "product thesis" — is worth nothing measurable

This is the most consequential negative result in the thread.

| K | gap from removing the veto | Rule 2 |
|---|---|---|
| 1 | −$597 .. +$86 | tied |
| 7 | −$194 .. +$274 | tied |
| 30 | $0 .. +$1,442 | tied |
| 90 | −$4,916 .. $0 | tied |

Tied at every cadence, every range straddling zero.

**The mechanism matters more than the number.** With the pet-formation coin
forced to certainty, only **one position in the entire 2.5-year run** ever
crosses the 25%-of-portfolio profit-take threshold at the settled configuration
(AVGO, peaking at 31.3%). §8's model has almost nothing to attach to, because
**the per-session limit already prevents positions from growing large enough to
fall in love with.** The veto and the limit aim at the same hazard; the limit
gets there first.

Re-run at limit `off`, where positions reach 79% of portfolio, the model bites —
and the result is worse than null, it is **bidirectional**: the best draws under
a 30% veto rate reach $311,697 and $338,070, roughly 1.7–1.9× the disciplined
baseline. In a window ending in a mega-cap melt-up, refusing to trim a winner
was sometimes the best decision available.

Two readings, and this thread does not choose between them: either the limit has
already enforced the discipline, or the corpus cannot see it — sixteen frozen
mega-cap-heavy names over a rising window is close to the worst possible sample
for pricing a refusal to sell. ENPH and TTD are in the universe precisely to
carry this shape and neither produced a capitulation at a viable cell.

### What autonomy is actually worth

**The cadence, not the discipline.** Driving `K` to 1 is worth **+3.41%** at the
settled cell (+$6,296, ranges non-overlapping, separable) for **+5.4pp** of
drawdown. Removing the veto is worth nothing measurable.

Before treating +3.41% as the prize: `K`=1 is this simulator's floor, not
"continuous"; and the backtest models **no slippage, no partial fills, no
rejections**. A daily agent trades roughly 30× as often as K=30 for that gross
edge. Every K=1 figure is an upper bound.

### Two hypotheses resolved

- **Deployment rate** — supported in direction: optimal `X` under
  `cash_deployment` falls 1.5 → 0.5 → 0.25 → ≤0.1pp as K goes 30 → 7 → 3 → 1,
  while `new_calls_only` holds at 3pp everywhere. Not supported in magnitude:
  `X* × sessions/yr` drifts 18.3 → 36.5 rather than holding constant.
- **Call proximity — refuted.** Adds placed 31–90 days from a call returned
  **+102.7%** to hold-to-end against **+51.4%** for Adds within 3 days. Cash
  deployed far from a call is not wasted.

---

## 4. Corrections to the record

Figures published earlier that are wrong or superseded:

| Claim | Status |
|---|---|
| Pooling worth +34.4% at `off` | **Withdrawn.** Re-derived against an exact baseline with cadence pinned: −0.029%, tied at every limit. |
| "Cadence buys almost nothing on return" | **True within K ∈ [7, 90], false below.** K=1 is +5.64% over K=30. The published figures were right; the inference drawn from them was not. |
| Gate target `$190,481.16304357877` | A **median across 15 draws** quoted as a forward draw. The forward draw is `$189,781.58036163618`, in the same manifest. |
| Session-model outputs before commit `a7df857` | **Computed tax-free** — year-end tax ran outside the session loop, after every snapshot. Affects only the two failed cadence attempts, which selected nothing. All settled numbers came from the per-event harness, which always taxed. |
| Displacement gains −$32,679 / −$24,950 | Ticker-filtered, not sale-attributed. Corrected figure: **−$19,924**. |
| 38.0% drawdown ceiling | A three-benchmark artifact. Correct figure **39.12%**. |

---

## 5. What remains open

1. **`minPositionPct`** — measured at one region: 1.0% cuts displacements 44%
   and collapses the stub tail (15 tickers → 10) with drawdown flat. The +2.07%
   return is a Rule 2 tie. Defensible as housekeeping; value not chosen.
2. **Scope revisit when Layer 3 lands** — `new_calls_only` is "in this version."
   Cash-deployment is what makes a newly surfaced candidate fundable before its
   next earnings call.
3. **Re-tune `X` if `K` changes.** The best limit is cadence-dependent.
4. **Speculative drift backstop** — the 15%-cap → 25%-profit-take band leaves
   10pp unpoliced. Never approached in this corpus. Would be a new rule.
5. **Rule 3b's plateau test** — non-overlap returns singletons out of precision
   once draw spreads collapse below 1%. Needs replacing before the next sweep.
6. **§8's capitulation model** — near-inert under the settled limit. Whether to
   amend it is a design question this thread deliberately did not answer.
7. **Speculative ceiling level** — still pending the exposure diagnostic.
8. **Option B** — re-evaluating ALL16's 312 transcripts (~$25–35) to escape a
   148-event corpus. Still the only route past this window's limits.

---

## 6. Next step

**Nothing in the allocator needs another sweep.** The design is settled and the
open items above are parameters, not questions blocking a build.

The build sequence resumes at **Step 8(a): in-app trading** — Accept places the
real order via the Schwab API and re-verifies the account's resulting balance
before the next dependent trade. `CLAUDE.md` calls for recon-first design there,
with explicit confirm, partial-fill and rejection handling, idempotency, and a
paper pass before real money. The autonomy findings sharpen the case: the
measured edge from faster cadence is 3–6% gross, and **none of the slippage,
partial-fill or turnover costs that would eat it are modelled anywhere yet.**

If a measurement session comes first, **Option B** is the highest-value one —
every finding in this document is bounded by a 148-event window.

---

## 7. Backups — and the Dropbox question

**The repository is well protected.** It lives at
`/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent`
— inside Dropbox — and is also pushed to
`github.com/Luis-GrowSolar-Personal/investment-agent`. Local, synced, and
versioned off-machine. **The tier caches are inside the repo**, so
`price_cache.json` and `fundamentals_cache.json` are covered too.

**The corpus dump is not.** It sits at

```
/Users/luismorales/investment-agent-backups/analysis_corpus_20260830.sql   (41 MB)
```

— in the **home directory, outside the Dropbox tree**. Confirmed from the path
recorded in every manifest's `corpus.db_snapshot`. So it exists on one machine
only.

It is the single irreplaceable artifact in this project: the model that produced
those evaluations is retired, so it cannot be regenerated at any price. If it is
lost, `$141,837` joins `$287k` as a number nobody can reproduce.

**Not into git.** A 41 MB blob that changes wholesale cannot be delta-compressed,
so every snapshot would add ~41 MB to the repository permanently; GitHub warns
above 50 MB. §10b also keeps the corpus outside the repo by design. The dump
holds no account or position data (`Analysis` / `Transcript` / `Ticker` only),
but `Transcript.rawText` is third-party earnings-call text, so confirm the
repo's visibility before it goes near GitHub.

**Do this:**

```zsh
gzip -k ~/investment-agent-backups/analysis_corpus_20260830.sql
shasum -a 256 ~/investment-agent-backups/analysis_corpus_20260830.sql.gz
```

Then put the `.gz` (roughly 4–5 MB) somewhere synced — inside the Dropbox tree
is enough — and ideally also attach it to a **GitHub Release** tagged to its
commit, since release assets live outside git history. **Record the checksum:**
every manifest references `corpus.db_snapshot_sha256` and currently points at a
file only one machine has.

One caveat on Dropbox generally: it protects against losing the laptop, not
against a bad write propagating. A `fetch_fundamentals.py` run would overwrite
the frozen tier caches and Dropbox would faithfully sync the damage. §10b's
dated, checksummed archive of those two files is still not done.

---

## 8. Reproducibility state

- Branch `sweep/db-corpus-baseline`, pushed to origin.
- Standing assertion holds: `no_reserve_raw` control = **$141,836.57**, verified
  after every code change on the measurement path.
- Gate 1a bit-exact; all six gates pass in the two most recent runs.
- Cross-grid anchors reproduce to rounding.
- `price_cache.json` / `fundamentals_cache.json` frozen at 2026-05-11 —
  **never refresh them to clear the staleness warning.**
- `testing/` is gitignored and holds real brokerage position exports.
- Run state under `analysis/data/run_state/<run_id>/` is committed; a
  budget-exhausted session resumes rather than restarting.

---

## 9. First action on return

1. **Back up the corpus dump** — §7. Five minutes, and the only item here whose
   cost of being skipped is unbounded.
2. **Then Step 8(a)**, or Option B if you would rather widen the evidence first.

---

## 10. Standing lessons

Kept because they cost real sessions to learn:

- **A gate must test correctness, not the prompt author's expectations.** Five
  runs stopped on design-session drafting errors.
- **Every reference figure in a gate must cite its manifest path and JSON key**,
  and every comparison must state whether each number is a forward draw or a
  median. A bare figure cost two sessions.
- **`off` belongs at the loose end of a limit axis.** Placing it first produced
  three consecutive false "jagged" verdicts.
- **Overlapping ranges are tied.** Rule 2 exists because a median difference
  inside the noise band was twice reported as a result.
- **A number without a manifest is not citable** — and the manifest must name a
  commit that actually contains the driver.
- **Write run state before doing any work.** A session that dies during its
  reading should still leave a checkpoint.

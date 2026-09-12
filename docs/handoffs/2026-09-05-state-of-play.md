# State of Play — 2026-09-05

**Supersedes** `docs/handoffs/2026-09-03-state-of-play.md`. That document's
§0 (terms) still stands and is not repeated here — **read it first**, then this.
Five of its figures and two of its claims are now known wrong; §3 below lists
every one with its replacement.

**Branch:** `sweep/db-corpus-baseline`
**Read first on return:** §1, then §3 (what changed), then §7 (test plan).

---

## 0. One term added to §0

| Term | What it means |
|---|---|
| **ruler** | *How often portfolio value is sampled when computing max drawdown.* **Session-sampled** = one observation per trading session (~31 points at K=30 across the window) — what `report.py:_max_drawdown` sees, because the session harness fills `daily_snapshots` once per session. **Daily-marked** = one observation per calendar day (~894). Session-sampled drawdown is **systematically understated**, by 1.9–8.3pp depending on phase, because the sampling grid steps over troughs. **Every drawdown figure in this project must now name its ruler.** An unlabelled drawdown is not a usable number. |

---

## 1. Where things stand in one paragraph

The settled allocator configuration is unchanged and now rests on better
evidence than before: re-measured on the correct ruler, X=2.5pp is at the
risk-adjusted optimum, where the old ruler had made X=1.0 look 25% better. But
the project's headline risk claim was measurement error — the published 17.32%
portfolio drawdown was session-sampled while the benchmark drawdowns it was
compared against were daily-marked, and on a like-for-like ruler the advantage
over SPY falls from 8.04pp to 1.90pp. The allocator's edge is **return, not
risk**. Test 1 is complete: the analyst is worth $59,145 over a
zero-information floor, degrades gracefully, and the promotion gate that
rejected the current model turns out never to have measured the names that
carry the portfolio. The corpus archive (§8's oldest item) is closed. Test 2 is
written and queued.

## 2. Settled configuration — unchanged

`swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp, `pooled`, `per_event_date`.

**Published figures, corrected and labelled:**

| | value | ruler |
|---|---|---|
| Final value (phase-averaged, seed 0) | **$184,819** | — |
| Max drawdown | 17.32% | **session-sampled** |
| Max drawdown | **23.46%** | **daily-marked** |
| SPY | $113,980 / 25.36% | daily-marked |
| SPY | 21.13% | session-sampled (phase-avg) |
| QQQ | $119,178 / 35.25% | daily-marked |
| TMFC | $120,512 / 32.99% | daily-marked |
| EW | $120,427 / 42.76% | **unknown — never reproduced, do not quote as measured** |

**Advantage over SPY on drawdown:**

| comparison | value |
|---|---|
| As published (SPY daily vs portfolio session — **mismatched**) | 8.04pp |
| Like-for-like, **daily** ruler | **1.90pp** |
| Like-for-like, session ruler | 3.80pp |

**Nothing found disturbs the configuration.** §5.5 records why it survives, and
on the correct ruler the case for X=2.5 is stronger than it was.

## 3. Requote list — every figure and claim this run changes

| # | Was | Now | Where published |
|---|---|---|---|
| 1 | Portfolio 17.32% drawdown quoted beside SPY/QQQ/TMFC as like-for-like | 17.32% is **session-sampled**; the benchmark figures are **daily-marked**. Portfolio daily-marked = **23.46%** | 09-03 §2 |
| 2 | "Advantage over SPY 8.04pp" | Mismatched-ruler artifact. Like-for-like daily = **1.90pp** | 09-03 §2 |
| 3 | §5.2 anomaly #2: 3.5pp phase sensitivity of drawdown, framed as a fact about trade timing | **Sampling artifact.** Session-ruler phase spread 5.69pp vs daily-ruler 1.42pp — the real path barely varies with phase | 09-03 §5.2 |
| 4 | §5.2 anomaly #1: 15 tie-break draws identical, cause unknown | **Understood** — see §5.3. Not a defect | 09-03 §5.2 |
| 5 | §5.1: "the only genuine rejection is SPWR — never held, in any draw, at any point", framed as the most encouraging fact in the table | **Mechanical funding failure, not a rejection** — see §5.2. And it *cost* ~$1,069 inside the window | 09-03 §5.1 |
| 6 | §4.5: "production is pinned to a model a gate rejected" | The gate that rejected it scoped to 7 tickers with **no established names** and **holdout n=0**, never covering the four names that are ~73% of the portfolio — see §5.4 | 09-03 §4.5 |
| 7 | analyst-sensitivity wrap-up: "the corpus has no two events on the same date" | **False** — 36 dates carry 2+ events, 83 events sit in them | `wrap-ups/analyst-sensitivity-out.md` §3 |
| 8 | Review claim (mine): "exact `rank_key` ties never occur"; then "328 tied candidate pairs" | **Both wrong.** The 328 count was an artifact of my own instrumentation — see §5.3 | this session, retracted here |
| 9 | `resolve-open-four` Step 4: "the ruler does not reorder the X axis" | True **only for raw final value**. On risk-adjusted terms the ruler *does* reorder — see §5.5 | `wrap-ups/resolve-open-four-out.md` §4 |

## 4. Test 1 complete — how much analyst quality matters

Source: `wrap-ups/analyst-sensitivity-out.md`, run `analyst-sensitivity`.
All figures **phase 0 only**, medians across 15 corruption seeds unless noted.
Drawdowns below are **session-sampled** (the run predates §5.1).

### 4.1 The zero-information floor

Every score forced to `Hold`/`Intact`: **$120,800 final, 12.72% dd, 16 tickers
held.** That beats SPY and QQQ outright and edges TMFC.

But the number that answers the question asked is the *gap*:
**$184,819 − $120,800 = $59,145.** The analyst is worth **49% over the floor**,
and produces **74% of the total gain** over $100k. The mechanism (universe +
first-call starter + X-throttle) beats the benchmarks on its own; the analyst
roughly triples the gain on top.

The floor holds 16 tickers against the real run's 15 — see §5.2, that gap is
SPWR and is mechanical.

### 4.2 Sensitivity

A **7.44pp lift drop** — the exact regression `gate_ledger.json` entry 1
measured — costs, at the settled cell:

| mode | cost | drawdown |
|---|---|---|
| `adjacent` (the "realistic" degradation) | **$24,886 (13.8%)** | *falls* 4.98pp |
| `pessimistic` | ~$42,700 (23.8%), interpolated | falls |
| `optimistic` | ~$0 — never costs money in this backtest | rises |

**Direction of error dominates magnitude.** The ledger gives magnitude for
`claude-sonnet-4-6` and says nothing about direction, so the cost of the pinned
model spans an ~$18k range on an unknown. §5.4 has what is known.

Gradient near the operating point: **~$5,825 per 1pp of lift** (adjacent,
q=0→0.1). Lift is quantised at 1/195 = **0.513pp per event**, so that gradient
rests on a three-event difference — fragile, do not over-read.

### 4.3 Shape

Drawdown *falls* as the analyst degrades, in every mode but `optimistic`. That
is not a benefit — degraded scores mean fewer Adds, which under `swap_funding`
means more idle cash, and cash lowers drawdown by non-participation.

Risk-adjusted (gain per point of drawdown, session ruler) the picture is a
**plateau then a cliff**, not the "roughly linear" the wrap-up reports:

| cell | gain/dd |
|---|---|
| uncorrupted | 3.83 |
| adjacent q=0.2 | 3.77 |
| adjacent q=0.5 (the −7.44pp point) | 3.47 |
| adjacent q=1.0 | 1.01 |
| zero-information | 1.64 |
| SPY / QQQ / TMFC | 0.64 / 0.57 / 0.65 |

Two readings worth carrying: the 7.44pp shock costs 13.8% of dollars but only
~9% risk-adjusted, so **forced model migration is tolerable**; and **full noise
(1.01) is worse than no analyst at all (1.64)** — a broken analyst is worse than
none, which is the argument for keeping the gate.

### 4.4 Rule 4 has no teeth on this axis

Max drawdown anywhere in the 360-cell grid is 25.09% against a 39.12% ceiling —
**0/360 breaches**. Degrading the analyst pushes drawdown the wrong way for the
rule to catch anything.

## 5. The five questions resolved

Source: `wrap-ups/resolve-open-four-out.md`, run `resolve-open-four`, plus
direct checks this session.

### 5.1 The ruler — the headline

`report.py:_max_drawdown` runs over `daily_snapshots`, which the session harness
fills **once per session** (`sweep_cadence_and_session_model.py:958-959` says so
in its own comment) — for the portfolio *and*, via `compute_summary`, for every
benchmark.

Daily NAV was reconstructed without touching the allocator: share counts are
constant between session dates, so
`nav(d) = cash_at_session + Σ shares × price(d)`.

| phase | final | dd session | dd daily | understated by |
|---|---|---|---|---|
| 0 | $179,945 | 20.85% | 22.78% | 1.93pp |
| 10 | $189,914 | 15.96% | 24.20% | 8.25pp |
| 20 | $184,599 | 15.16% | 23.39% | 8.23pp |
| **phase-avg** | **$184,819** | **17.32%** | **23.46%** | **6.13pp** |

The phase-averaged final and session drawdown reproduce the published headline
**exactly**, which is what identifies it as session-sampled.

**Phase spread: session 5.69pp vs daily 1.42pp.** The real portfolio path barely
cares which day of the month you trade — requote #3.

Two off-session transactions exist, both `forced-liquidation-for-tax` on AAPL.
`2023-12-31` executed at that day's close ($192.53), in-window, **$4.00** — the
reconstruction error it implies is 0.003% and nowhere near the 2022 trough.
`2024-12-31` is priced at **$213.07, the last in-window close**, not that day's
actual $250.42 — a **bookkeeping stamp, not look-ahead**. Note the label will
mislead anyone filtering the transaction log by date.

### 5.2 SPWR — mechanical, not a rejection

One scored event: `2024-05-02`, `Trim`, confidence `unknown`, size 3.0. The
first-call starter **did** queue at the 2024-05-20 session (`target_cap_log`:
starter leg, 5.0%). `funding_log`: `intended_dollars 8062.74`,
`target_buy_dollars 4031.37` (halved by X=2.5pp), `actual_dollars 0`,
**`binding: 'cash available'`** — the portfolio was fully deployed.

**Replacement for §5.1's claim:**

> SPWR was never held because its single Trim event queued a 5% starter leg at
> the 2024-05-20 session and that leg failed to fund (`binding: cash available`,
> $0 against $8,062.74 intended) in a fully-deployed portfolio — a mechanical
> absence, not an analyst rejection.

And the "encouraging" framing fails twice over: SPWR rose **+26.5%** ($1.17 →
$1.48) between that session and window close, so the exclusion **cost ~$1,069**.
The August 2024 bankruptcy is outside the window and invisible to the backtest.

**What this means more broadly:** the starter fires for every name regardless of
score, so the allocator does not select — it *weights*. Combined with §4.1, the
analyst's entire contribution is **sizing**.

### 5.3 The tie-break seed — understood, and two wrong answers retracted

Both prior explanations were wrong:

- "No two events share a call date" — **false**, 36 dates carry 2+ events.
- "Exact `rank_key` ties never occur, so the RNG never binds" (mine) — the
  census reported 328 tied pairs across 13/27 sessions, apparently refuting it.

**The 328 figure was an artifact of my own instrumentation.** `rank_key` has
**three** call sites, not one: line 937 (the candidate sort, which carries the
random 4th key) and **line 678, inside `_fund_candidate`, which sorts *donors*
on every funding attempt**. A session funding 8 candidates evaluates each held
ticker's key 8 times. My recorder counted call sites indiscriminately, so
donor re-rankings were counted as candidate ties. That is the x7/x8
multiplicity.

Consequences: there is **no candidate duplication**, so no structural route for
a ticker to exceed X; donor selection uses `rank_key` with **no** random key and
is deterministic by design; and the original explanation — continuous `gap`
separates distinct candidates so the RNG rarely binds — is back as the likely
account. Not measured further; the question is closed as understood, not as
worth more instrumentation.

**Independently verified this session:** `max_session_pp_change` = **exactly
2.500000pp** at phases 0, 10 and 20. The X limit binds and does not leak.

**Latent defect, recorded not fixed:**
`tie_rng = random.Random((seed or 0) * 7919 + hash(cadence) % 1000)`
(line 423) hashes the **string** `"30"`, and Python randomises string hashing
per process. Same cell, same seed, different process → different stream.
Harmless while the RNG never binds; **not captured by `config_hash`**. Fix:
`int(cadence)`, or pin `PYTHONHASHSEED` and record it in every manifest.

### 5.4 The gate that rejected the model never measured the portfolio

`gate_ledger.json` entry 1 scopes to `ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR` —
seven names, **no established names**, ENPH not in ALL16, `pct_tickers_improved`
28.6% (2 of 7), and **holdout n=0 on both arms**.

Analyst-direct lift, same methodology, by scope:

| scope | lift | n |
|---|---|---|
| ledger entry-1 scope | **+5.17pp** | 58 |
| ALL16 | −3.08pp | 195 |
| ALL16 established | **−6.31pp** | 111 |
| ALL16 speculative | +1.19pp | 84 |
| AVGO/NVDA/ORCL/TTD (~73% of portfolio) | **−3.57pp** | 56 |

The +5.17pp corroborates the ledger's own 4.94pp champion figure, validating the
scope reconstruction.

So the −7.44pp was measured on the **one subpopulation where the analyst has
positive directional lift**, and never on the names that carry the portfolio.

**This also dissolves the −3.08pp paradox.** The lift baseline is *always
predict bullish* — a punishing benchmark for mega-caps in a rising window. The
metric measures **direction-calling**; §4.1 shows the portfolio is paid for
**position-sizing**. Different skills. A negative lift is not evidence the
analyst is useless to a long-only allocator that can only size.

**§4.5 is reframed, not resolved.** The open item is not "pinned to a rejected
model" but "rejected by a gate whose scope was unrepresentative and whose
holdout never ran."

### 5.5 sonnet-4-6's error direction — undetermined

Champion `claude-sonnet-4-20250514`: n=6, **all `Add`**, mean ordinal 0.000.
Challenger `claude-sonnet-4-6`: n=36 (Add 13 / Hold 1 / Trim 18 / Exit 4), mean
ordinal 1.361. **Paired rows: 0.**

With no overlap the comparison is confounded and six all-`Add` rows are not a
baseline. Directional signal only: 61% of challenger calls are Trim or Exit,
which if real is §4.2's `pessimistic` arm (~$42,700) not `adjacent` (~$24,886).
**Hand to Test 4**, which needs paired re-scoring anyway.

### 5.6 The X axis on the correct ruler — the settled configuration survives

`resolve-open-four` Step 4 ranked X on **raw final value**, which is
ruler-invariant by construction and so cannot detect the effect it was asked
about. §5.1 of 09-03 records that X was chosen **for risk-adjusted return**.

Gain over $100k per point of max drawdown, phase-averaged, seed 0:

| X | final | gain | gain/dd **session** | gain/dd **daily** |
|---|---|---|---|---|
| 0.5 | 121,800 | 21,800 | 5,752 | 3,313 |
| **1.0** | 144,149 | 44,149 | **6,140** | 3,566 |
| 1.5 | 160,675 | 60,675 | 5,719 | 3,461 |
| 2.0 | 171,865 | 71,865 | 5,133 | 3,377 |
| **2.5** | 184,819 | 84,819 | 4,897 | **3,615** |
| 3.0 | 189,425 | 89,425 | 4,345 | 3,239 |
| 4.0 | 179,225 | 79,225 | 3,210 | 2,426 |
| 5.0 | 168,497 | 68,497 | 2,544 | 1,961 |
| off | 135,435 | 35,435 | 798 | 733 |

**On the session ruler X=1.0 beats X=2.5 by 25.4% risk-adjusted. On the daily
ruler X=2.5 wins, with X=1.0 1.4% behind — a Rule 2 tie.**

The mechanism: the session ruler flatters tight caps most, because small X means
many small trades and a smooth path a 30-day grid tracks well (gap 2.79pp at
X=0.5), while large X means big single-session moves the grid misses (8.00pp at
X=5.0). A systematically X-dependent bias is exactly what reorders a
risk-adjusted comparison.

**Conclusion: X=2.5pp is at the risk-adjusted optimum on the correct ruler**,
and the apparent 25% advantage for a tighter cap was a measurement artifact. On
raw final value the optimum is X=3.0 ($189,425 vs $184,819), inside the 2.5–3pp
band 09-03 §0.1 already describes — unchanged.

Rule 4 on the daily ruler: only `X=off` breaches (48.37%); no capped cell does,
the closest being X=5.0 at 34.93%. The 39.12% ceiling was itself calibrated on
session-sampled numbers — internally consistent, understated in absolute terms.
**Not re-adopted.**

## 6. Corpus archive — §8's oldest item, closed

Source: `wrap-ups/corpus-archive-out.md` plus direct work this session.

**Archive:** `https://github.com/Luis-GrowSolar-Personal/investment-agent-corpus`
(private). Plain SQL, uncompressed — deliberately, so git can delta rather than
storing every dump whole. Holds the 20260830 and 20260905 dumps, schema files,
checksums, census, and caches.

**Why it matters:** the corpus was scored by `claude-sonnet-4-20250514`, which
is retired. It **cannot be regenerated at any price**, and `PROMOTION_GATE.md`
§2.3 makes it a release dependency for the conformance fixtures.

**Three defects found and fixed:**

1. **`corpus_backup_ro` lacked `SELECT` on the three sequences.**
   `pg_dump --data-only` reads sequence values even in a table-scoped dump; the
   first dump failed outright. Granted.
2. **The schema dump carried `OWNER TO` / `GRANT` statements**, so restoring
   onto a clean Postgres failed on missing roles — the archive was *not*
   restorable independently, which is the entire point of it. `--no-owner
   --no-acl` added; the 20260905 schema has **zero** of either, verified.
3. **Change detection was broken.** `pg_dump` emits a random `\restrict` token
   every run, so the file sha256 differs even for a byte-identical corpus —
   proven: 20260904 and 20260905 differ *only* in that token, and three
   consecutive dumps produced three different raw hashes. Any
   "commit-only-if-changed" gate would have fired every time. Fixed with a
   `content_hash()` that excludes the `\restrict`/`\unrestrict` lines; the raw
   sha256 is still recorded, for verifying a given file transferred intact.
   Verified: the script now reports `UNCHANGED` and writes nothing.

**Verification:** full restore into a scratch Postgres with `ON_ERROR_STOP=1`,
zero errors, row counts 45/709/806 matching live exactly.

**Measured, contradicting an earlier assumption:** git got **no meaningful
delta** on the second dump — 12.96 MiB written for a 43.3 MB file, essentially
zlib alone. The plain-SQL choice still beats gzip (which would defeat delta
permanently), but each dump costs ~13 MiB of history rather than the "small
delta" predicted. Revisit if cadence increases.

### 6.1 Periodic archiving — the remaining build task

**Design settled, not yet built.** GitHub Actions in the **archive** repo, not
the main repo and not the app: a backup taken by the thing being backed up
shares its bugs, and an app with push rights to the archive can also destroy it.
The app declares state, external infrastructure acts on it — the same layering
discipline as the analyst/allocator firewall.

Requirements:

- `.github/workflows/corpus-archive.yml` in `investment-agent-corpus`.
- Weekly `schedule:` cron **and** `workflow_dispatch:`.
- `DATABASE_URL` repo secret — the **`corpus_backup_ro`** credential
  (`CORPUS_BACKUP_DATABASE_URL` in the main repo `.env`), never the read-write
  one.
- Install `postgresql-client-18` via the **PGDG apt repository**;
  `ubuntu-latest` ships an older client and `pg_dump` refuses to dump the live
  **18.6** server. This is the one place `apt` is permitted — CI runner only.
- Run `scripts/dump_corpus.sh` (vendor it into the archive repo, or check out
  the main repo as a second step).
- Commit the corpus **only when the content hash moved**; never
  `push --force`; never rewrite archive history.
- Fail the job on any verification failure so GitHub's failure email fires.
  **A green run that backed nothing up is worse than a red one.**
- **Heartbeat file** — write and commit `LAST_RUN.txt` on *every* run
  (timestamp, row counts, content hash, corpus filename, CHANGED/UNCHANGED),
  ~200 bytes. Justified on its own merits as a freshness record:
  `git log -1 LAST_RUN.txt` answers "is my archive current?" without pulling
  43 MB.
- **Reorder the same-day guard.** It currently fires *before* change detection
  and exits 1, so a manual dispatch on a day the cron already ran fails the job
  spuriously. An unchanged corpus should report `UNCHANGED` and exit 0 first.
- First run should be dispatched manually; a **no-op first run (no corpus
  commit) is the correct result** and proves change detection works.

**Known limitation, verified against GitHub's documented behaviour:** GitHub
disables scheduled workflows after **60 days of inactivity on the default
branch**, per repository. The archive repo will be quiet by design. Whether a
bot-authored heartbeat commit resets that clock is **not established** — the
existence of third-party keepalive actions implies it is not reliable, and their
authors note that gratuitous keepalive commits may breach GitHub's terms. So:

- Do **not** rely on the heartbeat to defeat the timer; keep it for freshness.
- GitHub **notifies the repository owner** when it disables a workflow this way,
  so the failure is loud, and re-enabling is one click or `gh workflow enable`.
- The risk partly self-limits: corpus growth and repo activity are correlated —
  the corpus only grows when transcripts are evaluated, which is when the
  project is active. **Residual risk to name honestly:** a stable app that is
  still scoring calls quarterly, where the schedule could lapse while the corpus
  moves. An external trigger calling `gh workflow run` would close it, at the
  cost of depending on an always-on machine.

Until the workflow exists, run `bash scripts/dump_corpus.sh` by hand and push;
the archive is only as current as the last manual run.

## 7. Test plan — §7 of 09-03, updated

| # | Test | Status |
|---|---|---|
| 1 | Analyst-quality sensitivity | **COMPLETE** — §4 |
| 2 | Hit rate by year | **Prompt written and queued**: `prompts/test2-look-ahead-hit-rate-by-year.md` |
| 3 | Transcript ingestion fidelity (AV vs hand-entered) | not started — blocks 5, 6 |
| 4 | Analyst noise floor | not started — blocked by 3; **also inherits §5.5** |
| 5 | Universe substitution | not started — blocked by 3 |
| 6 | Look-ahead prohibition probe | not started — blocked by 3, 4 |

### Test 2 — three things the prompt encodes that the original missed

1. **Model-version segmentation.** Every version-stamped row has a **2025–26
   call date**, so the recent tail is confounded by the `sonnet-4-6` swap *and*
   v10+auto1 prompt drift on top of any look-ahead signal — three explanations,
   and the model delta alone (−7.44pp) dwarfs any plausible year-over-year
   movement. Primary series is single-model on the unstamped presumed-v6 rows,
   ~2021–2024; the 2025 tail is reported separately and labelled contaminated.
2. **Lift is mechanically capped at (1 − baseline).** With an always-bullish
   baseline near 0.85, a *perfect* analyst can score at most +15pp. 2022 was
   bearish and 2023–24 bullish for these names, so **a declining lift series is
   the null expectation**, not a signal. The prompt requires reporting analyst
   hit rate, baseline, lift, headroom-captured and the ground-truth mix
   separately: **look-ahead predicts the hit rate falls; the baseline confound
   predicts only lift falls.**
3. **A flat result is weak evidence, not strong.** `sonnet-4-20250514`'s cutoff
   sits well past this corpus, so there is no in-window boundary to exploit;
   the gradient is *density of coverage*. The prompt pre-commits to that
   reading so a flat line does not enter this document overstated.

Also cut by established/speculative (7.5pp spread, §5.4) and reported with
binomial CIs, with Rule 2 extended to overlapping intervals.

## 8. Open items

- **Build the archive workflow** (§6.1) — the only thing standing between a
  current archive and a stale one.
- **Model-version decision** (§4.5, reframed by §5.4) plus a retroactive ledger
  entry recording the June change as a forced exception. **Do not resolve on
  the existing −7.44pp alone** — re-run the gate on a representative scope, or
  state explicitly that the decision is being made on unrepresentative evidence.
- **Relabel the 18 August Analysis rows** — stamped `v6`, actually scored by
  v10+auto1. Relabel, do not delete; they are the evidence.
- **Startup hash-check** — server hashes the prompt file it loaded and refuses
  to boot if it does not match `versions.js`. ~5 lines. Makes the 2026-09-03
  drift structurally impossible.
- **Corpus-integrity endpoint** — recorded in `docs/architecture/BUILD_STATE.md`
  as a deferred product item: read-only row counts, `max("createdAt")`, content
  hash of `Analysis`, so external infrastructure can detect change without
  pulling 43 MB. Same family as the startup hash-check.
- **`hash(cadence)` reproducibility defect** (§5.3) — proposed, not applied.
- **`testing/` is untracked rather than gitignored on `dev`** while holding real
  brokerage exports. One line.
- **`CLAUDE.md` hosting line** still describes a prod service last deployed
  2026-04-04, status FAILED.
- **`DESIGN_PRINCIPLES.md` §1** look-ahead claim — narrow to portfolio-aware
  scoring, point at §4.
- **EW benchmark** is unmeasured on either ruler (`baseline.py` computes
  SPY/QQQ/TMFC only). Do not quote 42.76% as measured.
- **Re-measure the rest of the sweep on the daily ruler?** §5.6 did the X axis.
  Every other published drawdown in this project is session-sampled and
  understated. Not urgent — no decision currently rests on them — but any figure
  promoted to a decision must be re-measured first.

## 9. Build sequence — unchanged

1. **Conformance fixtures** (`CONFORMANCE_FIXTURES.md`, `PROMOTION_GATE.md` §9.6)
2. **Headless replay driver** (§9.7)
3. **Step 8(a)** — in-app trading, per `CLAUDE.md`

§7's tests are validation and compete for the same hours. The archive workflow
(§6.1) is small and should not wait behind them.

## 10. Process notes from this session

- **Git identity leak, fixed.** Every commit in this repo before 2026-09-05 is
  authored `l.morales@windmarenergy.com`, on a repo `CLAUDE.md` declares
  personal and separate from Windmar. Cause: a repo-local `user.email` in
  `.git/config`, and `~/bin/code_dev_switch` switching the `gh` push token but
  never the git commit identity — two separate systems. Both fixed; the script
  now exports `GIT_AUTHOR_*`/`GIT_COMMITTER_*` per profile, which outranks
  repo-local config. **History deliberately not rewritten** — those commit SHAs
  are cited as provenance throughout this document, the wrap-ups and the
  manifests. No corpus data ever reached the work account; both repos have a
  single personal remote.
- **`progress.json` drifted from `findings.md`** in two runs, causing a resume
  to redo an expensive dump and restore. Update the step map when a step
  finishes, not at the end.
- **Two of this session's own claims were wrong and are retracted in §3** (rows
  7 and 8). Recorded because a wrong answer written down confidently is worse
  than an open question.

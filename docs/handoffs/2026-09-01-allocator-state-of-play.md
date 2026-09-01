# Allocator thread — state of play

**Date:** 2026-09-01
**Supersedes:** `docs/handoffs/2026-08-31-allocator-state-of-play.md`, which
holds the full measurement evidence and the corrections made along the way.
This document records what was **decided** on top of it.
**For:** Luis, returning after a few days away.

---

## 1. What changed since yesterday

Yesterday's document ended with a bracketed optimum and six open decisions.
**Five are now settled and one was reframed.** The spec has been amended to
match (`ALLOCATOR_OPERATING_MODEL.md` §0, new). The next measurement prompt is
written and waiting.

The allocator question is no longer "what should the design be." It is "what
does the design look like at a realistic operating cadence," which is one sweep
away.

---

## 2. The settled configuration

| Parameter | Decision | Status |
|---|---|---|
| Funding mode | `swap_funding` (conformant per-date trim cap) | settled |
| Per-session change limit `X` | 2.5pp | **provisional** — re-derive with `K` |
| Drawdown ceiling | 39.12% | settled |
| §11 defect #2 (stale cash snapshot) | fix in production | settled |
| Cap restoration | no mechanism change; wording corrected | settled |
| Minimum position size | `minPositionPct` + tradability sub-floor; displacement sells the whole position rather than leaving a stub | form agreed, **value unmeasured** |
| Cash reserve level | retired — not a knob | settled |

### Why swap-funding, despite a worse drawdown at its peak

Against `no_reserve_raw` the gap reads 26.6% vs 21.1%. Most of that is §11
defect #2 flattering the raw baseline. Compared like-for-like — both with the
live-cash rebuild — it is **+7.5% return for +1.0pp drawdown**.

And §10 rule 4 says this corpus structurally understates swap-funding: the
mechanism exists to fund a candidate that appears while you are fully invested,
and no new candidate can appear in a frozen 16-name universe. Its measured
advantage is a floor, not a verdict.

### Why 2.5pp rather than 3pp

3pp is the return optimum; 2.5pp is the better risk-adjusted cell. The marginal
step from 2.5 to 3pp buys **+$6,956 of gain for +3.9pp of drawdown** — roughly
7% more profit for 17% more drawdown.

### Why 39.12% rather than 38.0%

Not a change in risk tolerance — an arithmetic correction. The pre-declared
formula is *median of the four baselines' max drawdowns, +5pp*. Computed with
all four (SPY 25.36%, QQQ 35.25%, TMFC 32.99%, equal-weight 42.76%) the median
is 34.12% and the ceiling is **39.12%**. The 38.0% carried for three sessions
used only three baselines. Adopting the correct figure flips no cell in the
current grid, which is why it was settled now rather than later.

### Why no cap-restoration mechanism

There was never a contradiction — only loose wording. §9 invariant #2 says no
position's **target** may exceed its cap: a decision-time constraint on
purchases. §3 deliberately allows realized weight to drift between calls and
credits that for the Type B result. §5's "caps are inviolable" was written as
though it were a continuous constraint; it now says what it means.

At the settled 2.5pp the entire observed drift is **TTD at 16.4% against a 15%
cap — +1.4pp, on 90 of 894 trading days.** Drift scales with the ceiling
(+8.2pp at 5pp, +12.3pp uncapped) and vanishes at 1pp and below.

---

## 3. What the configuration means, in plain terms

**The per-session change limit is a ceiling on how fast one position may grow —
not an allocation, and not a constraint on how far a winner runs.** Price drift
between calls is unconstrained; the ceiling only throttles buying.

**Cash is a residual, not a reserve.** Nothing is held back on purpose. The
tight ceiling simply cannot deploy fast enough to stay fully invested — about
29% average cash at 2.5pp — and every dollar is available the moment a name
qualifies. Deliberate cash reserves were measured and are retired: they lower
drawdown but cost return, and the ceiling lowers drawdown *further* while
raising return.

**The low drawdowns are diversification, not cash.** At its own worst moment the
portfolio is 72–79% invested. It took the decline; it just wasn't concentrated
in three names when it arrived.

---

## 4. What closed that used to be open

- **"Order is the allocator" is now a bounded claim.** It holds exactly as long
  as cash binds. At 2.5pp the spread across fifteen orderings is 0.9%; at 1pp
  and below all fifteen are identical. The ordering-rule sweep, once queued as
  the next major thread, is now worth a single confirmation run.
- **Cash reserve** — retired as a policy knob.
- **The funding-mode question** — the thing this whole thread was blocked on.

---

## 5. What remains open

1. **`K`, the operating cadence** — and with it the real value of the limit.
   This is the next run.
2. **`minPositionPct`** — form agreed, value unmeasured. Folded into the
   cadence prompt.
3. **A speculative drift backstop** — the 15%-cap → 25%-profit-take band leaves
   10pp of unpoliced room. Never approached in this corpus (max 16.4%). Would be
   a new rule, not a clarification.
4. **Scope** — `new_calls_only` vs `cash_deployment`. §3 specifies
   cash-deployment; it has never actually been implemented. The cadence prompt
   builds it.
5. **Speculative ceiling level** — still pending the exposure diagnostic.
6. **Rule 3b's plateau test** — replaced in the cadence prompt with a
   practical-significance band; the overlap test stopped working once draw
   spreads collapsed below 1%.
7. **Option B** — re-evaluating ALL16's 312 transcripts (~$25–35) to recover
   the full window. Still the only route past a 148-event corpus.
8. **The veto / capitulation sweep** — unblocked now, but deliberately last.

---

## 6. Next step

**Run `prompts/sweep-cadence-and-session-model.md`** (CLI, no API spend).

It is not just another parameter sweep. Every measurement so far ran at
**per-call cadence**, where a position can only receive on its own earnings call
— roughly four times a year. Under §2's session model and §3's cash-deployment
scope, a session happens every `K` days and free cash goes to the best eligible
candidate anywhere. The same 2.5pp then deploys at a completely different rate:
~10pp/year at per-call cadence, up to ~130pp/year at `K`=7.

**So the limit value and the cadence are one measurement, not two.** That is why
2.5pp is provisional.

The prompt implements §3's session model — new machinery, never built — behind a
hard equivalence gate: configured to mimic the old per-call harness it must
reproduce **$190,481** and **$141,836.57** exactly, or the run stops. It then
sweeps `K` × phase × scope × limit, and folds in the `minPositionPct` sweep, the
one-shot ordering confirmation, and the staleness/return frontier that prices
Step 6 (automated transcript ingestion).

---

## 7. Housekeeping — two things worth doing before you step away

**Push the branch.** 29 commits are local-only:

```zsh
cd ~/Dropbox/"My Mac (MacBook-Pro.attlocal.net)"/Desktop/investment-agent
git push origin sweep/db-corpus-baseline
```

Verified safe: `.env` and the `testing/` brokerage CSVs were never committed,
and the only CSVs in history are simulation outputs.

**Get the corpus dump off the laptop. → CARRIED FORWARD AS THE FIRST ACTION OF
THE NEXT SESSION (see §9).** `~/investment-agent-backups/analysis_corpus_20260830.sql`
(41 MB) sits outside Dropbox, so it exists on one machine. It is the single
irreplaceable artifact in this project — the model that produced those
evaluations is retired, so it cannot be regenerated at any price. If it is lost,
`$141,837` joins `$287k` as a number nobody can reproduce.

**Not into git.** A 41 MB blob that changes wholesale cannot be delta-compressed,
so every future snapshot adds ~41 MB to the repository permanently; GitHub warns
above 50 MB and fails at 100 MB. §10b also puts the corpus outside the repo by
design — the corpus is data, the repo is code, and mixing them is what made
`price_cache.json` a hazard. The dump holds no account or position data
(`Analysis` / `Transcript` / `Ticker` only), but `Transcript.rawText` is
third-party earnings-call text, so confirm the repo's visibility before it goes
anywhere near GitHub.

**Do this instead:** gzip it (SQL dumps compress roughly 10:1, so ~4–5 MB) and
put it in Dropbox — instantly offsite, versioned, no new infrastructure. Better
still, also attach the gzip to a **GitHub Release** tagged to the commit it
belongs with: release assets live outside git history, so no repository bloat,
and it is versioned against a SHA, which is exactly what §10b's manifest
contract wants.

```zsh
gzip -k ~/investment-agent-backups/analysis_corpus_20260830.sql
shasum -a 256 ~/investment-agent-backups/analysis_corpus_20260830.sql.gz
```

**Record that checksum.** Every manifest references `corpus.db_snapshot_sha256`
and currently points at a file only one machine has.

**Still not done from §10b:** archiving `price_cache.json` and
`fundamentals_cache.json` to a dated folder with recorded checksums. They are
incidentally Dropbox-synced, but one `fetch_fundamentals.py` run would overwrite
them and Dropbox would faithfully sync the damage.

---

## 8. Reproducibility state

- Branch `sweep/db-corpus-baseline`; spec amendment at `ca29b37`.
- 33 manifests from the final grid, all `git_dirty: false`, each `driver_file`
  verified present in the commit it names.
- Standing assertion holds: `no_reserve` control = **$141,836.57**.
- Cross-grid anchors reproduce to six decimal places.
- `price_cache.json` / `fundamentals_cache.json` frozen at 2026-05-11 —
  **never refresh them to clear the staleness warning.**
- `testing/` is gitignored and must stay that way.

---

## 9. First action on return

**1. Back up the corpus dump before anything else.** Deferred from this session
and carried forward deliberately: gzip
`~/investment-agent-backups/analysis_corpus_20260830.sql`, put it in Dropbox
and/or a GitHub Release tagged to its commit, and record the sha256 — see §7 for
the commands and why not into git. This is five minutes of work protecting the
one artifact in the project that cannot be regenerated at any price. Do it
first, because it is the only item here whose cost of being skipped is
unbounded.

**2. Then run the cadence prompt.** Everything else waits on what `K` does to
the limit value.

If the equivalence gate fails, stop there and read the failure — it means §3's
session model changed behaviour the old harness had, and nothing downstream is
comparable until that is understood.

---

## 10. Standing lessons from this thread

Kept because they cost real time to learn:

- **A gate must test correctness, not the prompt author's expectations.** Four
  runs stopped on design-session drafting errors: a rule with two contradicting
  clauses, a conflation of *target* with *realized weight*, a prediction written
  as a gate, and a gate placed on a defect §11 documents as known and unfixed.
- **`off` belongs at the loose end of a limit axis.** Placing it first produced
  three consecutive false "jagged" verdicts.
- **Rank overlapping ranges as tied.** Rule 2 exists because a median difference
  inside the noise band was twice reported as a result.
- **A number without a manifest is not citable** — and the manifest must name a
  commit that actually contains the driver.

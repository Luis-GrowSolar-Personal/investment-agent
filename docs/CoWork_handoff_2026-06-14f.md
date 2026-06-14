# Investment Agent — CoWork Handoff

**Date:** 2026-06-14 (f)
**Picks up from:** CoWork_handoff_2026-06-14e.md
**Session work:** Wired the trend layer / Maturity classifier into the save
flow (06-14e's next-session priority #2). JS port of the verdict/matrix/
confidence logic + shared parity fixtures + per-ticker recompute in `save.js`.

---

## What shipped this session

### 1. `server/lib/trendAnalyst.js` — JS port

Faithful line-by-line port of `analysis/trend_analyst.py`'s pure functions:
`computeTrendVerdict` (Rules 1-8), `applyMatrix` (§6 allocator matrix),
`computeFinalConfidence` (three-state confidence), plus helpers
(`detectSoftSignals`, `classifyQuarter`, `consecutiveSoft`, `encodeThesis`/
`encodeMitigation`/`encodeCredibility`, `humanizeSignals`, `toFloat`).

- Input history rows use the **same snake_case field names** as
  `trend_analyst.py`'s `_mk()` test schema (`thesis_health`,
  `recommended_size`, `fresh_money_allocation`, `credibility_delta`,
  `mitigation_track_record`, etc.) — this is what lets one fixture file drive
  both languages.
- **Not ported:** `build_tier_function` (3-axis speculative/established
  classifier — needs `price_cache.json`/`fundamentals_cache.json`, laptop-only
  artifacts). `save.js` reads tier from `Ticker` fields instead (see #3).
- Faithfully reproduced the Python walrus-operator truthiness quirk in Rule 7
  (`if prev_size := _to_float(...)`) — a `recommended_size` of exactly `0`
  is treated the same as missing/null on both sides, matching Python's `0`-is-
  falsy behavior. Flagging this only because it's non-obvious from reading the
  JS in isolation; it's intentional parity, not a bug.

### 2. Shared parity fixtures + test runners

- `analysis/data/trend_verdict_fixtures.json` — the 17 self-test cases from
  `trend_analyst.py`'s `run_self_tests()` (verdict cases 1-10c), plus the 13
  `apply_matrix` cases (11-17, including a `verdict: null` passthrough case I
  added for `save.js`'s insufficient-history path), plus 5 new
  `compute_final_confidence` cases (not previously self-tested in Python —
  added here for both-language coverage). **35 cases total.**
- `analysis/test_trend_fixtures.py` — loads the fixtures, runs them through
  `trend_analyst.py`. **Passing: 35/35.**
- `server/lib/trendAnalyst.fixtures.test.js` — loads the same fixtures, runs
  them through `trendAnalyst.js`. **Passing: 35/35.**
- Added `!analysis/data/trend_verdict_fixtures.json` to `.gitignore` (the
  `analysis/data/*` blanket ignore would otherwise hide it, same pattern as
  the existing `type_classifications.json` exception).

**This is the new regression bar.** Any future change to verdict/matrix/
confidence logic in either `trend_analyst.py` or `trendAnalyst.js` must keep
both runners green:
```
python3 analysis/test_trend_fixtures.py
node server/lib/trendAnalyst.fixtures.test.js
```

### 3. `server/routes/save.js` — per-ticker trend recompute

After the new `Analysis` row is created, and before the response is sent:

- Fetches this ticker's latest-per-transcript `Analysis` history (same shape
  as `radar.js`'s history query: `transcript.findMany` with
  `analyses: { orderBy: { createdAt: 'desc' }, take: 1 }`, ordered by
  `callDate asc`).
- **Out-of-order guard:** if the newly-saved transcript is *not* the
  chronologically-latest one for this ticker (i.e. Luis backfilled an older
  quarter), the recompute is **skipped** and a console warning recommends
  running `python3 analysis/sync_trend_to_db.py --ticker <SYMBOL>` to resync
  the full history. Reasoning: `compute_trend_verdict` is backward-looking
  only, so a backfilled older entry doesn't retroactively need a new verdict
  itself, but every *later* entry's verdict technically should be
  recomputed against the now-denser history — that full re-walk is out of
  scope for this event-driven, single-row path.
- **Tier precedence — flagging a discrepancy vs. 06-14e:** the 06-14e handoff
  text said `tierMechanical ?? tierOverride ?? 'established'`. I implemented
  `ticker.tierOverride ?? ticker.tierMechanical ?? 'established'` instead,
  because (a) the `schema.prisma` field comments explicitly say
  `tierOverride` is the user override that should win, and (b)
  `dashboard.js` line 133 already uses this exact precedence
  (`ticker.tierOverride ?? ticker.tierMechanical ?? null`). I believe 06-14e's
  ordering was a typo. **Net effect is the same** in the common case where
  only one of the two is set; it only matters if both are set and disagree.
  Flagging in case this was a deliberate choice I'm not aware of.
- Computes `verdict = computeTrendVerdict(history, tier)`, then
  `[finalAction, trendRationale] = applyMatrix(recommendation, verdict)`, then
  `finalConfidence = computeFinalConfidence(verdict, recommendation, finalAction)`.
- Writes `tier`, `trajectory`, `suggestedOverride`, `finalAction`,
  `finalConfidence`, `trendRationale` onto the new `Analysis` row via
  `prisma.analysis.update`.
- **No nulling of other rows' trend fields.** Unlike
  `sync_trend_to_db.py`'s `null_stale_trend_fields` (which clears trend fields
  on non-latest analyses for the *same transcript*, e.g. when a v6 re-eval
  supersedes an older prompt version), `save.js` only ever creates a brand-new
  `Transcript` + `Analysis` pair — there's no superseded sibling row to null.
  If that assumption changes (e.g. a future "re-evaluate this transcript"
  feature), this will need revisiting.
- **Best-effort:** wrapped in try/catch — a trend-recompute failure logs to
  console and does not block the save response (the evaluation and transcript
  are still saved either way).

### 4. Verification

- `node --check` clean on `save.js` and `trendAnalyst.js`.
- Both fixture runners pass (35/35 each).
- Dry-run script (not committed) simulating `save.js`'s mapping +
  `computeTrendVerdict`/`applyMatrix`/`computeFinalConfidence` against a
  3-quarter "improving" history and a 2-quarter "insufficient history" case —
  both produced expected output (`Hold → Add`, `confident` / `null verdict`,
  `Hold` passthrough, `unknown`).
- **Not tested:** end-to-end against the live Railway DB (no DB access from
  sandbox). Next real transcript save from RADAR will be the first live test —
  worth checking that ticker's `Analysis.trajectory`/`finalAction`/
  `finalConfidence`/`trendRationale` populate correctly.

---

## Deferred (unchanged from 06-14e)

- **Force-resync button (RADAR)** — manual per-ticker trigger of the same
  recompute, for correcting bad transcripts / edge cases.
- **2x/day tier-classifier cron** — re-runs the 3-axis classifier, writes
  `Ticker.tierMechanical`. Still needs the price/fundamentals refresh-path
  decision from 06-14e.
- `/api/moves/:owner` ~8.9s N+1 query fix.
- Phase 3 — Schwab `marketdata` price refresh.

---

## Files changed / created this session

- `server/lib/trendAnalyst.js` (new)
- `server/lib/trendAnalyst.fixtures.test.js` (new)
- `analysis/data/trend_verdict_fixtures.json` (new)
- `analysis/test_trend_fixtures.py` (new)
- `server/routes/save.js` (modified — trend recompute block + import)
- `.gitignore` (modified — fixtures exception)

---

## Action needed from Luis: git push

The sandbox hit the same Dropbox-mount git lock issue as prior sessions
(`.git/index.lock` / `.git/ORIG_HEAD.lock` can't be removed —
`Operation not permitted`). HEAD and `origin/dev` were confirmed in sync
before this session's edits (both at `5e1a5dd2`), so nothing was lost — but
I can't commit/push from here. From your machine:

```bash
cd investment-agent
git pull origin dev   # should be a no-op / fast-forward, just in case
git add .gitignore server/lib/trendAnalyst.js server/lib/trendAnalyst.fixtures.test.js \
        analysis/data/trend_verdict_fixtures.json analysis/test_trend_fixtures.py \
        server/routes/save.js docs/CoWork_handoff_2026-06-14f.md
git status   # docs/CoWork_handoff_2026-06-14e.md is also untracked from last
              # session — add it too if you want it in history
git commit -m "Wire trend layer into save.js: JS port + parity fixtures + per-save recompute"
git push origin dev
```

`client/src/App.jsx` was not touched this session — no conflict expected.

---

## Next session priorities (suggested)

1. **Live verification**: save a new transcript via RADAR for any portfolio
   ticker, confirm the new `Analysis` row gets `trajectory`/`finalAction`/
   `finalConfidence`/`trendRationale` populated and RADAR's TREND badge
   reflects it.
2. Force-resync button (RADAR) — same recompute, manually triggered.
3. 2x/day tier-classifier cron (resolve price/fundamentals refresh path
   first).
4. Then: `/api/moves/:owner` N+1 fix, Phase 3 Schwab marketdata.

---

## Token usage note

This session stayed well under the 85% alert threshold — no alert needed.

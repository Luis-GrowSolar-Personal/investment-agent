# Investment Agent — CoWork Handoff

**Date:** 2026-06-14 (e)
**Picks up from:** CoWork_handoff_2026-06-14d.md
**Session work:** Readiness assessment (5-point check) + trend-layer
operationalization design. No code changes this session — investigation,
one manual DB sync run by Luis, and a build spec for next session.

---

## Why

Luis asked whether the agent is ready to manage real money, against 5
claims (Schwab sync, trim/add recs aligned with the validated model, new-
position ranking, non-equity viewing, per-user caps). `BUILD_STATE.md`
(April 11) is stale and was not used — findings are code-grounded against
the live `server/routes/dashboard.js`, `schwabSync.js`,
`PORTFOLIO_ANALYST_SPEC.md` (2026-05-17), and a live RADAR screenshot.

---

## Findings summary (5-claim assessment)

1. **Schwab sync** — largely true for matched/linked accounts (auto-sync on
   login, 4h staleness, cash + position sync, lot-source preservation).
   Phase 3 (Schwab `marketdata` price refresh) still not done — prices
   remain Polygon-only (15-min delayed). Unchanged from prior sessions.

2. **Trim/Add recs aligned with latest model** — **this was the real gap**,
   see below. Now addressed for this moment in time; needs operationalizing
   so it doesn't regress.

3. **New-position ranking (Layer 3 / Opportunity Scanner)** — confirmed not
   built, explicitly deferred in `PORTFOLIO_ANALYST_SPEC.md`. Luis agrees
   this is additive, not a blocker for managing the current portfolio.

4. **Non-equity viewing** — confirmed working (equity/etf/crypto/commodity/
   cash buckets, `smartDefaultBucket`, manual override, counted in
   `totalPortfolioValue`). CLAUDE.md's risk-role framework (defensive/
   growth/commodity correlation tagging, e.g. "GLD is the only true hedge")
   is not implemented — buckets are asset-class only. Not raised as a
   blocker this session.

5. **Per-user caps** — confirmed live via `OwnerTickerConfig` →
   `ownerCapOverrides` in `dashboard.js`, combined with `Ticker.capPercent`
   and the analyst's per-call `capPercent` (min of the three). Type A/B +
   cap% were corrected via `analysis/apply_type_classifications.js` (run
   2026-05-31) and verified correct against the 2x2 matrix in
   `PORTFOLIO_ANALYST_SPEC.md` (AMPX/ENVX/EOSE/SPWR = A/35%, AAPL/MSFT/TSLA =
   B/50%, TTD = A/35%).

---

## The trend-layer sync gap (claim 2) — root cause and fix

`trajectory`/`finalAction`/`finalConfidence`/`trendRationale`/`tier` are
written only by `analysis/sync_trend_to_db.py`, an offline script. A RADAR
screenshot showed 5 of 8 portfolio tickers (AMPX, ENVX, EOSE, SPWR, TTD) had
never had it run — TREND column showed "—". Without these fields,
`dashboard.js` falls back to `finalAction = recommendation` (the raw
per-call output, not the trend-layer-corrected one). AMPX/ENVX/EOSE are
three of the seven tickers the v2.1 trend layer (44%→54%) was specifically
validated on, so their live "Add" recommendations were running without that
correction.

**Fix applied this session:** Luis ran `sync_trend_to_db.py` for all
tickers. Trend fields should now be populated for all 8 portfolio tickers —
**verify on next RADAR check** that AMPX/ENVX/EOSE "Add" calls still hold
(or were adjusted) and that TREND badges now show values instead of "—".

---

## Agreed design for next session: operationalize the trend sync

Goal: stop depending on a manual laptop script run after every transcript
load. Agreed split (Luis confirmed):

### 1. `save.js` — per-ticker, per-save trend recompute (event-driven)

- On every transcript save, recompute the trend verdict + `finalAction` for
  **that ticker only** — pure in-memory operation over that ticker's
  existing `Analysis` rows (no price/fundamentals fetch, no full-portfolio
  sweep). Should be sub-second to low-seconds even during a multi-transcript
  import.
- Steps: fetch this ticker's Analysis history (latest per transcript, same
  query shape as `sync_trend_to_db.py`'s `fetch_all_analyses` but filtered
  to one ticker), recompute verdict for the new latest via
  `compute_trend_verdict` / `apply_matrix` / `compute_final_confidence`,
  null the previous-latest's trend fields, write the new verdict.
- **Reads `tier` from `Ticker.tierMechanical ?? Ticker.tierOverride ??
  'established'`** — does NOT recompute tier. Tier becomes the cron's job
  (below).
- **Open question for implementation:** `compute_trend_verdict` /
  `apply_matrix` / `compute_final_confidence` currently live in
  `analysis/trend_analyst.py` (Python), and the script's docstring states
  backtest CSV output and live RADAR must be identical "by construction"
  (same source functions). Porting this logic to JS for `save.js` breaks
  that single-source guarantee unless the JS port is kept in sync /
  unit-tested against the same fixtures as `trend_analyst.py`'s
  `if __name__ == "__main__"` test block (lines ~980-1110). Decide:
  port to JS with shared test fixtures, or have Node shell out to a small
  Python helper (less clean on Railway, but preserves single source).

### 2. Force-resync button (RADAR)

- Manual per-ticker trigger of the same save.js-style recompute. Safety net
  for edge cases (correcting a bad transcript, post-cron re-check) — not
  required for normal flow.

### 3. Periodic cron — 2x/day, tier (3-axis) reclassification

- Schedule: ~7:30 AM ET (pre-market) and ~12:30 PM ET (midday) — catches
  volatility-driven tier flips from intraday news. **Mind Railway cron is
  UTC and ET shifts with DST** — compute both UTC times and note which
  daylight-savings assumption was used.
- Re-runs the 3-axis classifier (`analysis/type_classifier.py` /
  `build_tier_function`, vol + market cap + P/E) against fresh price +
  fundamentals data, writes `Ticker.tierMechanical`.
- **Open question:** `price_cache.json` / `fundamentals_cache.json` are
  currently refreshed manually on Luis's laptop via `fetch_prices_*.py` /
  `fetch_fundamentals.py` (live API calls). A Railway cron needs either (a)
  those fetchers ported to run inside the cron job with live API access, or
  (b) a separate scheduled refresh step before the classifier runs.

### 4. RADAR refresh

- No extra wiring needed — `server/routes/radar.js` already reads
  `ticker.tierMechanical` directly (lines ~85, ~241), so refresh
  automatically reflects the cron's latest output once it writes that field.

---

## Open / deferred (unchanged from 2026-06-14d)

- **`/api/moves/:owner` ~8.9s latency** (N+1 query in
  `server/routes/moves.js`, ~line 620) — future session.
- **Phase 3** — Schwab `marketdata` for price refresh, Polygon as fallback
  (see `CoWork_handoff_2026-06-14.md`).
- Schwab CSV/account-history cost-basis correction (claim 5 follow-up) —
  Luis will do this in parallel; current accounts are non-taxable or
  low-tax-exposure, so the placeholder-lot tax-cost approximation in
  `computeTrimTax` is acceptable for now.

---

## Next session priorities (suggested order)

1. Decide the JS-port-vs-Python-helper question for trend verdict logic
   (blocks #2).
2. Build save.js per-ticker trend recompute + Force-resync button.
3. Build 2x/day tier-classifier cron (resolve price/fundamentals refresh
   path first).
4. Then: `/api/moves/:owner` N+1 fix, then Phase 3 Schwab marketdata.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance. This session was investigation +
design only (no code edits); usage was moderate, not near 85%.

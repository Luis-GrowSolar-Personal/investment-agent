#!/usr/bin/env python3
"""
sweep_cadence_and_session_model.py — prompts/sweep-cadence-and-session-model.md

New session-model machinery per ALLOCATOR_OPERATING_MODEL.md §2/§3/§4/§5.
Step 1 is gated: the session model must exactly reproduce the settled
per-call reference numbers before any cadence sweep runs.

In-memory only. No DB writes (loads the frozen v6 corpus from Postgres, a
read, same as every prior session in this thread). No LLM calls.

Usage:
    cd analysis && python3 sweep_cadence_and_session_model.py [--gate-only]
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
START = date(2022, 1, 1)
C = date(2024, 6, 12)
INITIAL = 100_000
EXPECTED_NO_RESERVE = 141_837
CONFIDENCE_RANK = {"confident": 2, "advisory": 1, "unknown": 0, None: 0}


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                           text=True, check=True).stdout.strip()


# Step 0b (prompts/cadence-equivalence-and-pooling.md): _rebuild_buy_leg is
# now IMPORTED from the shared driver, not duplicated. That module's
# git_dirty assertion moved from import time to assert_clean_for_manifest(),
# called only when a manifest is written, so importing it here no longer
# risks failing while docs/wrap-up files for this task are mid-edit.
from analysis.bracket_three_modes_s11_corrected import (
    _rebuild_buy_leg, assert_clean_for_manifest,
)


def fetch_extra_fields(all16, end):
    import psycopg2, psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                       a."freshMoneyAllocation" AS fresh_money_allocation,
                       a."credibilityDelta" AS credibility_delta,
                       a."mitigationCapabilityTrackRecord" AS mitigation_track_record,
                       a."stumbleType" AS stumble_type
                FROM "Analysis" a
                JOIN "Transcript" t ON a."transcriptId" = t.id
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                JOIN (SELECT a2."transcriptId", MAX(a2."createdAt") AS latest
                      FROM "Analysis" a2 GROUP BY a2."transcriptId") latest
                  ON latest."transcriptId" = a."transcriptId" AND latest.latest = a."createdAt"
                WHERE tk.symbol = ANY(%s) AND t."callDate" <= %s
                  AND a."createdAt" >= %s AND a."createdAt" < %s
            """, (all16, end, "2026-05-02 12:33:23-04", "2026-06-27 16:26:16-04"))
            rows = cur.fetchall()
    finally:
        conn.close()
    return {(r["ticker"], r["call_date"]): r for r in rows}


def recompute_trend_layer(events, tier_for_ticker, extra_fields):
    from trend_analyst import compute_trend_verdict, apply_matrix, compute_final_confidence
    by_ticker: dict = {}
    for e in events:
        by_ticker.setdefault(e.ticker, []).append(e)
    for ticker, ticker_events in by_ticker.items():
        ticker_events.sort(key=lambda e: e.call_date)
        tier = (tier_for_ticker(ticker) if tier_for_ticker else "established") or "established"
        for i, ev in enumerate(ticker_events):
            history = []
            for prior in ticker_events[: i + 1]:
                extra = extra_fields.get((prior.ticker, prior.call_date), {})
                history.append({
                    "thesis_health": prior.thesis_health,
                    "recommendation": prior.per_call_rec,
                    "recommended_size": prior.recommended_size,
                    "fresh_money_allocation": extra.get("fresh_money_allocation"),
                    "credibility_delta": extra.get("credibility_delta"),
                    "mitigation_track_record": extra.get("mitigation_track_record"),
                    "stumble_type": extra.get("stumble_type"),
                })
            verdict = compute_trend_verdict(history, tier=tier)
            per_call_rec = ev.per_call_rec or ""
            final_action, _r = apply_matrix(per_call_rec, verdict)
            ev.final_action = final_action
            ev.final_confidence = compute_final_confidence(verdict, per_call_rec, final_action)
            ev.trajectory = (verdict or {}).get("trajectory")


def load_events_dedup_on():
    from analysis.simulator.data import load_call_events
    from trend_analyst import build_tier_function
    from type_classifier import build_type_function, build_driver_count_function
    events_full = load_call_events(tickers=ALL16, end_date=C, dedupe_same_day_calls=True)
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(SCRIPT_DIR / "data" / "price_cache.json",
                                   SCRIPT_DIR / "data" / "fundamentals_cache.json")
    extra_fields = fetch_extra_fields(ALL16, C)
    recompute_trend_layer(events_full, tier_fn, extra_fields)
    return events_full, type_fn, driver_fn, tier_fn


from analysis.simulator.allocator_v3 import (
    decide as decide_v3, STARTER_PCT_SPECULATIVE, STARTER_PCT_ESTABLISHED,
)
from analysis.simulator.allocator_v2 import _type_cap, _build_sell_trades
from analysis.simulator.accounts import Portfolio, Trade, InsufficientCash, InsufficientShares
from analysis.simulator.data import PriceLookup
from analysis.simulator.report import compute_summary, _max_drawdown
from analysis.simulator.baseline import initialize_baselines
from analysis.simulator.simulator import DailySnapshot, SimulationResult

MANIFEST_DIR = SCRIPT_DIR / "data" / "run_manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
DRIVER_FILE = "analysis/sweep_cadence_and_session_model.py"
REF_SWAP_2_5PP = 190_481.0          # median over 15 draws, per prompt
REF_NO_RESERVE_OFF = 141_836.57     # standing assertion, per prompt

QUARTER_ENDS_MONTHS = (3, 6, 9, 12)


# ---------------------------------------------------------------------------
# manifest infra (same shape as the three-mode driver)
# ---------------------------------------------------------------------------

def sha256_file(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(run_id, params, results):
    # Step 0b: the hard stop-gate lives in the shared
    # assert_clean_for_manifest(), called fresh at every manifest write --
    # not an import-time snapshot. This also asserts the shared driver file
    # (bracket_three_modes_s11_corrected.py) is present at HEAD; this
    # driver's own presence is asserted separately below.
    commit, branch, dirty = assert_clean_for_manifest()
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{DRIVER_FILE}"],
        cwd=REPO_ROOT, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"HEAD={commit[:12]} does not contain {DRIVER_FILE} -- commit "
            f"this driver before writing a manifest against it."
        )
    output_sha = hashlib.sha256(json.dumps(results, sort_keys=True, default=str).encode()).hexdigest()
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_branch": branch, "git_dirty": dirty,
        "driver_file": DRIVER_FILE,
        "params": params, "results": results, "output_sha256": output_sha,
    }
    path = MANIFEST_DIR / f"{run_id}-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


# ---------------------------------------------------------------------------
# Session-date generation (§2)
# ---------------------------------------------------------------------------

def per_call_session_dates(events):
    return sorted({e.call_date for e in events if START <= e.call_date <= C})


def fixed_k_session_dates(k_days, phase_offset):
    dates = []
    d = START + timedelta(days=phase_offset)
    while d <= C:
        if d >= START:
            dates.append(d)
        d += timedelta(days=k_days)
    if not dates or dates[-1] < C:
        dates.append(C)
    return sorted(set(dates))


def _quarter_end(dt):
    """Most recent quarter-end on/before dt."""
    q_month = ((dt.month - 1) // 3) * 3 + 3
    if q_month > dt.month:
        q_month -= 3
    if q_month <= 0:
        return date(dt.year - 1, 12, 31)
    year = dt.year
    if q_month == 12:
        return date(year, 12, 31)
    # last day of q_month
    next_month = date(year, q_month + 1, 1)
    return next_month - timedelta(days=1)


def seasonal_session_dates(phase_offset):
    """Weekly during days 15-42 after each quarter-end, monthly otherwise."""
    dates = set()
    d = START + timedelta(days=phase_offset)
    while d <= C:
        qe = _quarter_end(d)
        days_since_qe = (d - qe).days
        if 15 <= days_since_qe <= 42:
            step = 7
        else:
            step = 30
        dates.add(d)
        d += timedelta(days=step)
    dates.add(C)
    return sorted(x for x in dates if START <= x <= C)


def session_dates_for(cadence, phase_offset, events):
    if cadence in ("per_call", "single_event", "per_call_bundled"):
        return per_call_session_dates(events)
    if cadence == "seasonal":
        return seasonal_session_dates(phase_offset)
    return fixed_k_session_dates(int(cadence), phase_offset)


def build_sessions(cadence, phase_offset, events, events_all):
    """Return an ordered list of (session_key, session_date, [events]).

    session_key is a distinct identifier per session (needed because
    'single_event' mode can emit several sessions sharing the same
    session_date -- one per event -- which a plain dict keyed by date
    would silently collapse).

    - 'single_event' (Step 1a hard gate): each event, in draw order, is
      its own session at session_date = event.call_date. Where several
      calls share a date, they become consecutive single-event sessions
      in draw order, per the prompt's Step 1a spec. In this configuration
      §3's pooling has nothing to pool.
    - every other cadence: events bucket into the session whose date is
      the first session date >= the event's call_date (unchanged from
      the prior driver), preserving draw order within a session.
    """
    if cadence == "single_event":
        sessions = []
        for i, e in enumerate(events):
            if e.call_date < START or e.call_date > C:
                continue
            sessions.append((i, e.call_date, [e]))
        return sessions

    import bisect
    sdates_only = session_dates_for(cadence, phase_offset, events_all)
    events_by_session = {d: [] for d in sdates_only}
    for e in events:
        if e.call_date > sdates_only[-1] or e.call_date < START:
            continue
        pos = bisect.bisect_left(sdates_only, e.call_date)
        target_sd = sdates_only[pos]
        events_by_session[target_sd].append(e)
    return [(sd, sd, events_by_session[sd]) for sd in sdates_only]


# ---------------------------------------------------------------------------
# Rank key (§4): confidence, recency, gap-to-target. Seeded random tie-break.
# ---------------------------------------------------------------------------

def rank_key(ticker, state_entry, portfolio, prices_today, session_date):
    if state_entry is None:
        return (0, -10**9, -1.0)
    conf = CONFIDENCE_RANK.get(state_entry.get("final_confidence"), 0)
    days_since = (session_date - state_entry["call_date"]).days
    recency_score = -days_since
    price = prices_today.get(ticker)
    if price is None:
        gap = -1.0
    else:
        cap_pct = _type_cap(state_entry.get("type_classification"),
                             state_entry.get("tier"), state_entry.get("driver_count"))
        rsp = state_entry.get("recommended_size_pct")
        target_pct = min(rsp, cap_pct) if rsp else cap_pct
        portfolio_value = portfolio.total_value(prices_today)
        target_dollars = (target_pct / 100.0) * portfolio_value if portfolio_value > 0 else 0
        current_dollars = portfolio.position_value(ticker, price)
        gap = (target_dollars - current_dollars) / target_dollars if target_dollars > 0 else -1.0
    return (conf, recency_score, gap)


def eligible_for_cash(ticker, state_entry, portfolio, prices_today, session_date):
    """§4 'Eligible for cash' floor."""
    if state_entry is None:
        return False
    if state_entry.get("final_action") != "Add":
        return False
    if state_entry.get("final_confidence") == "unknown" or state_entry.get("final_confidence") is None:
        return False
    price = prices_today.get(ticker)
    if price is None:
        return False
    cap_pct = _type_cap(state_entry.get("type_classification"),
                         state_entry.get("tier"), state_entry.get("driver_count"))
    portfolio_value = portfolio.total_value(prices_today)
    current_pct = (portfolio.position_value(ticker, price) / portfolio_value * 100
                   if portfolio_value > 0 else 0.0)
    if current_pct >= cap_pct - 1e-9:
        return False  # already at/over tier cap
    # no-average-down rule on speculatives
    if state_entry.get("tier") == "speculative":
        wcb = portfolio.weighted_cost_basis(ticker) if hasattr(portfolio, "weighted_cost_basis") else None
        if wcb is not None and price < wcb:
            return False
    return True


# ---------------------------------------------------------------------------
# Session simulation
# ---------------------------------------------------------------------------

def make_session_decider(funding_mode, limit_pp, scope, min_position_pct=0.0):
    """Returns run_session(...) closure state shared across the whole run."""
    state = {
        "ticker_state": {},       # ticker -> dict
        "seen_event_tickers": set(),
        "funding_log": [],
        "displacement_log": [],
        "target_cap_log": [],
        "staleness_log": [],      # list of days-stale per decision acted-on
        "session_limit_used": {}, # reset per session: ticker -> pp used this session
    }
    return state


def _floor_dollars(min_position_pct, portfolio_value):
    return max(min_position_pct / 100.0 * portfolio_value, 0.0)


def run_session_sweep_cell(events_all, prices, type_fn, driver_fn, tier_fn,
                            cadence, phase_offset, scope, funding_mode, limit_pp,
                            reverse_order=False, seed=None, min_position_pct=0.0,
                            sub_floor_dollars=100.0, execution_order="pooled",
                            trim_budget_scope="per_event_date",
                            veto_p=0.0, veto_seed=0):
    """Run ONE session-model backtest for a given (cadence, phase, scope,
    funding_mode, limit, draw, minPositionPct, execution_order) cell.
    Mirrors run_cell's per-call harness but batches decisions at session
    boundaries and, for scope=cash_deployment, ranks eligible candidates
    anywhere in the universe rather than only today's reporters.

    execution_order (Step 2, prompts/cadence-equivalence-and-pooling.md):
    - 'pooled' (default): §3's specified sequence -- all of this session's
      sells execute, then all cash is pooled and deployed in §4 rank order.
      This is what Step B/C below always did.
    - 'sequential': each event's full trade set (its own sell, then its
      own buy funding) executes before the next event in the session is
      considered -- reproduces the validated per-call harness's ordering
      on a multi-event session. Implemented only for scope='new_calls_only'
      (the only scope Step 2 sweeps it against); with scope='cash_deployment'
      it falls back to 'pooled' behavior, since Step 2 never combines the two
      and defining sequential cross-ticker cash-deployment ordering was out
      of scope for this run.

    veto_p / veto_seed (Step 2, prompts/autonomy-cadence-floor-and-veto.md):
    ALLOCATOR_OPERATING_MODEL.md §8's capitulation model, implemented as
    specified rather than approximated.

    - When a position FIRST crosses the 25%-of-portfolio profit-take
      threshold it becomes a "pet" with probability `veto_p` (a fraction in
      [0,1]). The flag is STICKY for that position. The crossing is observed
      at that ticker's own call -- the only moment §3/§4 evaluate
      profit-take, since held positions are not re-sized between their own
      calls.
    - A pet position DECLINES all recommended Trims and Exits (including the
      profit-take trim itself, which is the mechanism §8 says gets pointed
      the wrong way).
    - Capitulation trigger: -30% from the TRAILING PEAK POSITION VALUE since
      entry, evaluated once per session; on trigger, FULL EXIT at that
      session's close, before that session's decisions, so the proceeds join
      §3 step 2's cash pool.
    - Closing a position clears its pet flag and peak: a later re-entry is a
      new position, and §8's flag is sticky "for that position".
    - Interpretation, flagged in the wrap-up: a pet is also excluded from
      swap-funding DONOR eligibility. §8's text names Trims and Exits; a
      displacement trim is a sell of the beloved position to fund another
      idea, which is exactly the reduction the modelled user refuses.

    veto_seed is deliberately independent of `seed` (the ordering/tie-break
    draw), because pet formation is probabilistic and needs its own variance.
    veto_p = 0.0 disables the model entirely and draws no RNG, so it is
    bit-identical to the pre-existing behaviour.
    """
    events = list(events_all)
    if reverse_order:
        events = list(reversed(events))
    if seed is not None:
        rng = random.Random(seed)
        by_date = {}
        for e in events:
            by_date.setdefault(e.call_date, []).append(e)
        events = []
        for d in sorted(by_date):
            bucket = by_date[d]
            rng.shuffle(bucket)
            events.extend(bucket)
    tie_rng = random.Random((seed or 0) * 7919 + hash(cadence) % 1000)

    sessions_list = build_sessions(cadence, phase_offset, events, events_all)

    taxable_cash = INITIAL / 2
    tax_adv_cash = INITIAL / 2
    portfolio = Portfolio.initialize(taxable_cash=taxable_cash, tax_advantaged_cash=tax_adv_cash)
    baselines = initialize_baselines(INITIAL, START, prices)
    held_tickers: set = set()
    ticker_state: dict = {}
    seen_event_tickers: set = set()
    funding_log, displacement_log, target_cap_log, staleness_log = [], [], [], []
    skipped_events = []
    daily_snapshots = []

    day_start_of_day_value = {}
    day_trimmed_today = {}
    last_calendar_date = None

    # --- §8 capitulation model state (see docstring) ---
    PROFIT_TAKE_PCT = 25.0          # §8 / §5: profit-take threshold, % of portfolio
    CAPITULATION_DRAWDOWN = 0.30    # §8: -30% from the trailing peak position value
    veto_rng = random.Random(veto_seed * 104729 + 17)
    pet_flags: set = set()          # tickers currently flagged as pets (sticky)
    pet_decided: set = set()        # tickers whose 25% crossing coin has been flipped
    pos_peak_value: dict = {}       # ticker -> trailing peak position value since entry
    pet_log = []                    # every pet formation
    capitulation_log = []           # every capitulation exit
    declined_log = []               # every Trim/Exit declined by a pet

    # Per-ticker sorted call dates, for Step 1's call-proximity tagging.
    calls_by_ticker: dict = {}
    for _e in events_all:
        calls_by_ticker.setdefault(_e.ticker, []).append(_e.call_date)
    for _t in calls_by_ticker:
        calls_by_ticker[_t].sort()

    def _days_since_nearest_call(ticker, when):
        """Days from `when` back to the most recent call for `ticker` on or
        before `when`. None when the ticker has no such call yet."""
        import bisect as _bisect
        ds = calls_by_ticker.get(ticker)
        if not ds:
            return None
        pos = _bisect.bisect_right(ds, when)
        if pos == 0:
            return None
        return (when - ds[pos - 1]).days

    def _clear_position_veto_state(ticker):
        pet_flags.discard(ticker)
        pos_peak_value.pop(ticker, None)

    def rebuild_helper(ticker, target_buy_dollars, day_price, trade_date, raised_by_account, reason):
        return _rebuild_buy_leg(ticker, target_buy_dollars, portfolio, day_price, trade_date,
                                 raised_by_account, reason=reason)

    # --- Year-end tax, applied INSIDE the session loop (fifth-bug fix, Step 2
    # of prompts/close-equivalence-corrected-targets.md).
    #
    # This used to be a post-loop pass over `session_dates_seq`, which meant
    # every year's forced-liquidation-for-tax executed against the FINAL
    # portfolio state, after the last `daily_snapshots.append(...)`. Two
    # consequences, both wrong: (a) the tax hit never appeared in ANY
    # snapshot, and `compute_summary` takes final_portfolio_value from
    # `snaps[-1].total_value` (analysis/simulator/report.py:134), so the
    # headline number was entirely tax-free; (b) the shares sold to pay the
    # tax kept compounding for the rest of the run instead of being gone.
    # The reference (analysis/simulator/simulator.py:207-227) walks every
    # calendar day and settles tax at step 2 -- after that day's trades,
    # BEFORE that day's mark-to-market -- on Dec 31 of each year, plus a
    # partial-year settlement on the final day when it is not Dec 31.
    #
    # Mapped onto session dates: no trades occur between sessions, so
    # settling year Y at the first session on/after Jan 1 of Y+1 leaves the
    # portfolio in the same state as settling it on Dec 31 -- provided the
    # liquidation PRICES are still anchored to the literal Dec 31 (the
    # fourth-bug fix, commit cbba37e, preserved here).
    from analysis.simulator.tax import compute_year_end_tax
    year_end_taxes = []
    loss_carryforward = 0.0
    taxed_years: set = set()

    def _settle_year_end_tax(year, price_anchor_date):
        nonlocal loss_carryforward
        anchor_prices = prices.all_prices_on(list(held_tickers), price_anchor_date)
        tax_result = compute_year_end_tax(portfolio, year=year,
                                           loss_carryforward_in=loss_carryforward,
                                           prices_for_liquidation=anchor_prices)
        year_end_taxes.append(tax_result)
        loss_carryforward = tax_result.loss_carryforward_out
        taxed_years.add(year)

    n_sessions_total = len(sessions_list)

    for _sess_i, (skey, sd, in_scope) in enumerate(sessions_list):
        # Settle any Dec 31 that has passed since the previous session, before
        # this session's decisions see the portfolio (the reference has
        # already taken the hit by then).
        for _y in range(START.year, sd.year):
            if _y not in taxed_years and date(_y, 12, 31) < sd:
                _settle_year_end_tax(_y, date(_y, 12, 31))
        prices_needed = held_tickers | {e.ticker for e in in_scope} | set(ticker_state.keys())
        prices_today = prices.all_prices_on(list(prices_needed), sd)
        portfolio_value_before_session = portfolio.total_value(prices_today)

        # --- §8: trailing-peak maintenance and the capitulation trigger.
        # Runs once per session, BEFORE this session's decisions, so a
        # capitulation exit's proceeds join §3 step 2's cash pool. Peaks are
        # refreshed first, so a position making a new high this session
        # cannot trigger on its own new peak.
        if veto_p > 0.0:
            for _t in list(pos_peak_value.keys()):
                if portfolio.position_shares(_t) <= 1e-9:
                    _clear_position_veto_state(_t)
            for _t in list(ticker_state.keys()):
                if portfolio.position_shares(_t) <= 1e-9:
                    continue
                _px = prices_today.get(_t)
                if _px is None:
                    continue
                _val = portfolio.position_value(_t, _px)
                if _val <= 1e-9:
                    continue
                if _val > pos_peak_value.get(_t, 0.0):
                    pos_peak_value[_t] = _val
                if _t not in pet_flags:
                    continue
                _peak = pos_peak_value.get(_t, _val)
                if _peak > 0 and _val <= (1.0 - CAPITULATION_DRAWDOWN) * _peak + 1e-12:
                    _shares = portfolio.position_shares(_t)
                    _exit_trades = _build_sell_trades(
                        _t, _shares, portfolio, _px, sd, reason="capitulation-full-exit")
                    _proceeds = 0.0
                    _rs_before = len(portfolio.realized_sales)
                    for _tr in _exit_trades:
                        try:
                            portfolio.execute_sell(_tr)
                            _proceeds += _tr.shares * _tr.price
                        except InsufficientShares:
                            skipped_events.append((sd, _t, "insufficient shares (capitulation)"))
                    capitulation_log.append({
                        "date": sd, "ticker": _t, "peak_value": _peak,
                        "exit_value": _val, "proceeds": _proceeds,
                        "loss_from_peak": _peak - _val,
                        "realized_gain": sum(
                            rs.realized_gain
                            for rs in portfolio.realized_sales[_rs_before:]),
                    })
                    _clear_position_veto_state(_t)

        # The 25%-of-start-of-day-value donor trim cap resets on a CALENDAR
        # DATE change, not on every session -- matching make_funding_decide_fn's
        # day_state, which keys off `trade_date` and persists across every
        # event/call on the same date. This matters specifically for
        # 'single_event' cadence, where several calls sharing one calendar
        # date become several consecutive sessions: resetting per-session
        # there would let each same-date session re-claim a fresh 25% of the
        # donor instead of sharing one day's budget, diverging from the
        # reference the equivalence gate must reproduce exactly.
        # trim_budget_scope (Step 3, prompts/close-equivalence-corrected-targets.md):
        #   'per_event_date' -- what the reference does, described above.
        #   'per_session'    -- spec-faithful (§5 denominates the donor trim
        #                       budget in SESSIONS, not calendar dates), so
        #                       every session re-claims a fresh 25%. These two
        #                       can only differ where a calendar date carries
        #                       more than one session, i.e. 'single_event' /
        #                       'per_call' cadence; at any fixed-K or seasonal
        #                       cadence one session IS one date and the two
        #                       are identical by construction.
        if trim_budget_scope == "per_session" or sd != last_calendar_date:
            day_start_of_day_value = {
                t: portfolio.position_value(t, prices_today.get(t, 0.0))
                for t in ticker_state if portfolio.position_shares(t) > 1e-9
            }
            day_trimmed_today = {}
            last_calendar_date = sd
        session_limit_used = {}  # ticker -> pp already consumed this session

        def _fund_candidate(cand):
            """Deploy cash to ONE candidate, subject to §5's per-session
            limit. Shared by the 'pooled' Step C loop (called once per
            candidate, after the whole session's pool is ranked) and the
            'sequential' execution order (called immediately, once per
            event, from Step A below -- so 'remaining' cash for the next
            event already reflects this one's trades)."""
            ticker = cand["ticker"]
            day_price = cand["day_price"]
            portfolio_value_before = portfolio.total_value(prices_today)
            already_used_pp = session_limit_used.get(ticker, 0.0)
            target_buy_dollars = cand["intended"]
            if limit_pp is not None and portfolio_value_before > 0:
                remaining_pp = max(limit_pp - already_used_pp, 0.0)
                limit_dollars = (remaining_pp / 100.0) * portfolio_value_before
                target_buy_dollars = min(target_buy_dollars, limit_dollars)
            if target_buy_dollars <= 1e-6:
                funding_log.append({
                    "date": sd, "ticker": ticker, "intended_dollars": cand["intended"],
                    "target_buy_dollars": 0.0, "actual_dollars": 0.0,
                    "shortfall": cand["intended"], "binding": "session limit", "pp_change": 0.0,
                    "days_since_call": _days_since_nearest_call(ticker, sd),
                    "buy_price": day_price,
                })
                return

            if funding_mode == "no_reserve_raw":
                # Today's baseline: decide_v3's own natural buy trades,
                # passed through unmodified whenever they already fit under
                # the (limit-capped) target; scaled down proportionally
                # otherwise. Carries §11 defect #2 unmodified -- this is the
                # comparability anchor / standing assertion.
                natural_trades = cand.get("natural_buy_trades", [])
                natural_buy_dollars = sum(t.shares * t.price for t in natural_trades)
                cap = target_buy_dollars
                if natural_buy_dollars <= cap + 1e-6:
                    actual = natural_buy_dollars
                    final_trades = natural_trades
                else:
                    scale = cap / natural_buy_dollars if natural_buy_dollars > 0 else 0.0
                    final_trades = []
                    for t in natural_trades:
                        scaled_shares = t.shares * scale
                        if scaled_shares > 1e-9:
                            final_trades.append(Trade(
                                account=t.account, ticker=t.ticker, side="buy",
                                shares=scaled_shares, price=t.price,
                                trade_date=t.trade_date, reason=t.reason + "-capped",
                            ))
                    actual = sum(t.shares * t.price for t in final_trades)
            elif funding_mode == "no_reserve_s11fixed":
                raised_by_account = {"tax_advantaged": 0.0, "taxable": 0.0}
                new_buy_trades, actual = rebuild_helper(
                    ticker, target_buy_dollars, day_price, sd, raised_by_account,
                    reason="session-add-to-target")
                final_trades = new_buy_trades
            elif funding_mode == "swap_funding":
                natural_trades = cand.get("natural_buy_trades", [])
                natural_buy_dollars = sum(t.shares * t.price for t in natural_trades)
                shortfall = target_buy_dollars - natural_buy_dollars
                raised_by_account = {"tax_advantaged": 0.0, "taxable": 0.0}
                sell_trades = []
                if shortfall > 1e-6:
                    donors = []
                    for other, st in ticker_state.items():
                        if other == ticker:
                            continue
                        if portfolio.position_shares(other) <= 1e-9:
                            continue
                        if st.get("final_action") not in ("Hold", "Trim", "Exit"):
                            continue
                        if other in pet_flags:
                            # §8 interpretation (see docstring): a pet also
                            # refuses to be displaced to fund someone else.
                            continue
                        donors.append(other)
                    donors.sort(key=lambda t: rank_key(t, ticker_state.get(t), portfolio, prices_today, sd))
                    remaining = shortfall
                    for donor in donors:
                        if remaining <= 1e-6:
                            break
                        donor_price = prices_today.get(donor) or prices.price_on(donor, sd)
                        if donor_price is None:
                            continue
                        donor_value_now = portfolio.position_value(donor, donor_price)
                        if donor_value_now <= 1e-6:
                            continue
                        sod_value = day_start_of_day_value.get(donor, donor_value_now)
                        already_trimmed = day_trimmed_today.get(donor, 0.0)
                        floor_dollars = 0.0
                        if min_position_pct and min_position_pct > 0:
                            floor_dollars = max(_floor_dollars(min_position_pct, portfolio_value_before),
                                                 sub_floor_dollars)
                        cap_today = max(0.0, 0.25 * sod_value - already_trimmed)
                        max_trim_dollars = min(cap_today, donor_value_now)
                        raise_amount = min(max_trim_dollars, remaining)
                        # minPositionPct stub rule: if the trim would leave the
                        # donor below the floor, sell the whole position instead.
                        if floor_dollars > 0 and (donor_value_now - raise_amount) < floor_dollars:
                            raise_amount = donor_value_now
                        shares_to_sell = raise_amount / donor_price
                        if shares_to_sell < 1e-9:
                            continue
                        donor_sells = _build_sell_trades(
                            donor, shares_to_sell, portfolio, donor_price, sd,
                            reason="swap-funding-displacement")
                        actually_raised = sum(st_.shares * st_.price for st_ in donor_sells)
                        for st_ in donor_sells:
                            raised_by_account[st_.account] += st_.shares * st_.price
                        sell_trades.extend(donor_sells)
                        remaining -= actually_raised
                        day_trimmed_today[donor] = already_trimmed + actually_raised
                        donor_pct_after = ((donor_value_now - actually_raised) / portfolio_value_before * 100
                                            if portfolio_value_before > 0 else 0.0)
                        displacement_log.append({
                            "date": sd, "donor": donor, "candidate": ticker,
                            "raised": actually_raised,
                            "donor_final_action": ticker_state.get(donor, {}).get("final_action"),
                            "donor_pct_after": donor_pct_after,
                        })
                # Compute the buy leg BEFORE executing this event's own donor
                # sells -- matching the reference exactly: _rebuild_buy_leg's
                # avail = portfolio.accounts[acct].cash + raised_by_account
                # assumes cash does NOT yet reflect these sells (the
                # reference never executes trades inside decide_fn; it
                # returns them for the caller to execute afterward). Selling
                # first here would double-count the proceeds (once via the
                # now-higher live cash balance, once via raised_by_account).
                new_buy_trades, actual = rebuild_helper(
                    ticker, target_buy_dollars, day_price, sd, raised_by_account,
                    reason="session-add-to-target-swap-funded")
                for t in sell_trades:
                    try:
                        portfolio.execute_sell(t)
                    except InsufficientShares:
                        skipped_events.append((sd, t.ticker, "insufficient shares (donor)"))
                final_trades = new_buy_trades
            else:
                raise ValueError(f"unknown funding_mode {funding_mode!r}")

            for t in final_trades:
                try:
                    portfolio.execute_buy(t)
                    held_tickers.add(t.ticker)
                except InsufficientCash:
                    skipped_events.append((sd, t.ticker, "insufficient cash"))

            eps = 1.0
            if actual >= target_buy_dollars - eps:
                binding = "target gap" if target_buy_dollars >= cand["intended"] - eps else "session limit"
            else:
                binding = "cash available"

            pp_change = (actual / portfolio_value_before * 100) if portfolio_value_before > 0 else 0.0
            session_limit_used[ticker] = already_used_pp + pp_change

            funding_log.append({
                "date": sd, "ticker": ticker, "intended_dollars": cand["intended"],
                "target_buy_dollars": target_buy_dollars, "actual_dollars": actual,
                "shortfall": max(cand["intended"] - actual, 0.0),
                "binding": binding, "pp_change": pp_change,
                # Step 1 proximity test: days from this Add back to the most
                # recent call for this ticker.
                "days_since_call": _days_since_nearest_call(ticker, sd),
                "buy_price": day_price,
            })

        pending_adds = []  # dicts: ticker, intended, day_price

        # --- Step A: profit-take then recommended action, per in-session event ---
        for event in in_scope:
            price = prices.price_on(event.ticker, sd)
            if price is None:
                skipped_events.append((sd, event.ticker, "no price near session_date"))
                continue
            is_first_call = event.ticker not in seen_event_tickers
            seen_event_tickers.add(event.ticker)
            effective_type = type_fn(event.ticker)
            tier = tier_fn(event.ticker) if tier_fn else None
            driver_count = driver_fn(event.ticker) if driver_fn else None
            final_action = event.final_action or event.per_call_rec or "Hold"

            # Snapshot BEFORE this event's own trades are generated or
            # executed -- matching make_funding_decide_fn exactly, which
            # reads portfolio_value_before / current_dollars_before ahead
            # of calling decide_v3 and never re-reads them after this
            # event's own sell leg executes (decide_fn returns trades for
            # the caller to execute afterward; it does not execute them
            # itself). The session driver previously executed this event's
            # sells before taking this snapshot, which is an equivalence
            # bug on any event whose own trade set includes a sell.
            portfolio_value_before = portfolio.total_value(prices_today)
            current_dollars_before = portfolio.position_value(event.ticker, price)
            had_position = portfolio.position_shares(event.ticker) > 1e-9

            # --- §8: pet formation. The profit-take threshold (25% of
            # portfolio) is evaluated at this ticker's own call, which is the
            # only place §3/§4 evaluate it. The coin is flipped exactly once
            # per position, the FIRST time it is observed across the
            # threshold, and the resulting flag is sticky until the position
            # closes.
            if veto_p > 0.0 and had_position and portfolio_value_before > 0:
                _pos_pct = 100.0 * current_dollars_before / portfolio_value_before
                if _pos_pct >= PROFIT_TAKE_PCT - 1e-12 and event.ticker not in pet_decided:
                    pet_decided.add(event.ticker)
                    if veto_rng.random() < veto_p:
                        pet_flags.add(event.ticker)
                        pos_peak_value[event.ticker] = max(
                            pos_peak_value.get(event.ticker, 0.0), current_dollars_before)
                        pet_log.append({"date": sd, "ticker": event.ticker,
                                        "position_pct": _pos_pct,
                                        "position_value": current_dollars_before})

            trades = decide_v3(
                ticker=event.ticker, final_action=final_action,
                recommended_size_pct=event.recommended_size,
                type_classification=effective_type, portfolio=portfolio,
                day_price=price, trade_date=sd, prices_today=prices_today,
                tier=tier, is_first_call=is_first_call, driver_count=driver_count,
            )
            # Execute everything except buy trades now (profit-take/exit).
            # §8: a pet declines ALL recommended Trims and Exits -- the
            # profit-take trim included, since that is precisely the sale the
            # modelled user refuses to make near the peak.
            _is_pet = event.ticker in pet_flags
            for t in trades:
                if t.side == "sell":
                    if _is_pet and t.ticker == event.ticker:
                        declined_log.append({
                            "date": sd, "ticker": t.ticker,
                            "declined_dollars": t.shares * t.price,
                            "final_action": final_action, "reason": t.reason,
                        })
                        continue
                    try:
                        portfolio.execute_sell(t)
                        held_tickers.add(t.ticker)
                    except InsufficientShares:
                        skipped_events.append((sd, t.ticker, "insufficient shares"))

            ticker_state[event.ticker] = {
                "final_action": final_action, "call_date": event.call_date,
                "session_date": sd,
                "recommended_size_pct": event.recommended_size,
                "type_classification": effective_type, "tier": tier,
                "driver_count": driver_count,
                "final_confidence": event.final_confidence,
            }
            staleness_log.append((sd - event.call_date).days)

            starter_fired = is_first_call and not had_position
            cap_pct_this_ticker = _type_cap(effective_type, tier, driver_count)
            intended = 0.0
            if starter_fired:
                starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                               else STARTER_PCT_ESTABLISHED)
                target_cap_log.append({
                    "date": sd, "ticker": event.ticker, "leg": "starter",
                    "target_pct": starter_pct, "cap_pct": cap_pct_this_ticker,
                    "excess": starter_pct - cap_pct_this_ticker,
                })
                if portfolio_value_before > 0:
                    intended += (starter_pct / 100.0) * portfolio_value_before
            v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
            if v2_leg_applies and final_action == "Add" and portfolio_value_before > 0:
                target_pct = min(event.recommended_size, cap_pct_this_ticker) if event.recommended_size else cap_pct_this_ticker
                target_cap_log.append({
                    "date": sd, "ticker": event.ticker, "leg": "add",
                    "target_pct": target_pct, "cap_pct": cap_pct_this_ticker,
                    "excess": target_pct - cap_pct_this_ticker,
                    "known_s11_concatenation": starter_fired,
                })
                target_dollars = (target_pct / 100.0) * portfolio_value_before
                delta = target_dollars - current_dollars_before
                if delta > 0:
                    intended += delta
            if intended > 1e-6:
                natural_buy_trades = [t for t in trades if t.side == "buy"]
                cand = {
                    "ticker": event.ticker, "intended": intended, "day_price": price,
                    "trade_date": sd, "natural_buy_trades": natural_buy_trades,
                }
                if execution_order == "sequential" and scope == "new_calls_only":
                    # Fund THIS event's own buy right now, before the next
                    # event in the session is even looked at -- reproduces
                    # the validated per-call harness's ordering exactly.
                    _fund_candidate(cand)
                else:
                    pending_adds.append(cand)

        # --- Step B: build eligible candidate pool (§4) ---
        if scope == "new_calls_only":
            candidates = list(pending_adds)
        elif scope == "cash_deployment":
            candidates = list(pending_adds)
            pending_tickers = {c["ticker"] for c in candidates}
            for t, st in ticker_state.items():
                if t in pending_tickers:
                    continue
                price_t = prices_today.get(t)
                if price_t is None:
                    price_t = prices.price_on(t, sd)
                if price_t is None:
                    continue
                if not eligible_for_cash(t, st, portfolio, {**prices_today, t: price_t}, sd):
                    continue
                cap_pct = _type_cap(st.get("type_classification"), st.get("tier"), st.get("driver_count"))
                rsp = st.get("recommended_size_pct")
                target_pct = min(rsp, cap_pct) if rsp else cap_pct
                pv = portfolio.total_value(prices_today)
                target_dollars = (target_pct / 100.0) * pv if pv > 0 else 0
                current_dollars = portfolio.position_value(t, price_t)
                delta = target_dollars - current_dollars
                if delta > 1e-6:
                    candidates.append({"ticker": t, "intended": delta, "day_price": price_t,
                                        "trade_date": sd, "natural_buy_trades": []})
        else:
            raise ValueError(f"unknown scope {scope!r}")

        # §4 rank order applies when the session model does real batching.
        # At 'single_event' cadence every session is exactly one event by
        # construction -- candidates has at most one entry, so ranking is a
        # no-op there regardless. At per-call cadence a "session" degenerates
        # to (usually) one event; on the rare same-call-date multi-ticker
        # session, the validated per-call harness has no ranking step at all
        # -- it just executes decide_fn sequentially in draw order. The
        # equivalence gate requires reproducing THAT behavior exactly, so
        # ranking is skipped for cadence in ('per_call', 'single_event') and
        # applied for every real cadence.
        # 'per_call_bundled' (Step 1b) uses the SAME session dates as
        # 'per_call' (one session per distinct call date) but, unlike the
        # equivalence-only 'per_call', DOES apply §4 ranking within a
        # multi-event session -- that's the entire thing Step 1b measures.
        if cadence not in ("per_call", "single_event"):
            def _key(c):
                base = rank_key(c["ticker"], ticker_state.get(c["ticker"]), portfolio, prices_today, sd)
                return (base[0], base[1], base[2], tie_rng.random())
            candidates.sort(key=_key, reverse=True)

        # --- Step C: deploy cash, subject to §5 limit. 'pooled' (default,
        # §3's specified sequence) ranks the WHOLE session's candidate pool
        # then deploys via _fund_candidate; 'sequential' new_calls_only
        # already funded each candidate inline in Step A above, so
        # `candidates` is empty here in that case. ---
        for cand in candidates:
            _fund_candidate(cand)

        # Mirror the reference's step 2: on Dec 31 itself, and on the final
        # day when it is not Dec 31 (partial-year settlement), tax settles
        # AFTER this session's trades and BEFORE the mark-to-market.
        _is_dec31 = (sd.month == 12 and sd.day == 31)
        _is_last_session = (_sess_i == n_sessions_total - 1)
        if sd.year not in taxed_years and (_is_dec31 or _is_last_session):
            _settle_year_end_tax(sd.year, date(sd.year, 12, 31) if _is_dec31 else sd)

        # --- daily mark-to-market: only recorded AT session dates for this
        # lightweight session harness (sufficient for final value / drawdown
        # on session boundaries; see wrap-up note on drawdown granularity). ---
        mark_prices = prices.all_prices_on(list(held_tickers), sd)
        taxable_acc = portfolio.accounts["taxable"]
        tax_adv_acc = portfolio.accounts["tax_advantaged"]
        taxable_value = taxable_acc.cash + sum(
            sum(l.shares * mark_prices.get(t, l.cost_basis_per_share) for l in lots)
            for t, lots in taxable_acc.lots.items())
        tax_adv_value = tax_adv_acc.cash + sum(
            sum(l.shares * mark_prices.get(t, l.cost_basis_per_share) for l in lots)
            for t, lots in tax_adv_acc.lots.items())
        n_positions = len({t for acc in portfolio.accounts.values() for t, lots in acc.lots.items()
                            if any(l.shares > 1e-9 for l in lots)})
        baseline_values = {t: b.value_on(prices, sd) for t, b in baselines.items()}
        position_values = {t: sum(l.shares * mark_prices.get(t, l.cost_basis_per_share)
                                   for acc in portfolio.accounts.values() for l in acc.lots.get(t, []))
                            for t in held_tickers}
        daily_snapshots.append(DailySnapshot(
            date=sd, total_value=taxable_value + tax_adv_value, taxable_value=taxable_value,
            tax_advantaged_value=tax_adv_value, cash_total=taxable_acc.cash + tax_adv_acc.cash,
            n_positions=n_positions, baseline_values=baseline_values,
            cash_taxable=taxable_acc.cash, cash_tax_advantaged=tax_adv_acc.cash,
            position_values=position_values,
        ))
        # year-end tax at Dec 31 boundaries falling on/after this session and
        # before the next: apply once per calendar year at the session that
        # crosses or lands on it (approximation: apply at year's LAST session).

    r = SimulationResult(
        start_date=START, end_date=C, initial_capital=INITIAL,
        daily_snapshots=daily_snapshots, portfolio=portfolio, baselines=baselines,
        year_end_taxes=year_end_taxes, universe_tickers=sorted({e.ticker for e in events_all}),
        skipped_events=skipped_events,
    )
    s = compute_summary(r)
    total = len(funding_log)
    fully_funded = sum(1 for f in funding_log if f["shortfall"] < 1.0)
    unfunded = sum(1 for f in funding_log if f["actual_dollars"] < 1.0 and f["intended_dollars"] >= 1.0)
    partial = total - fully_funded - unfunded
    below_1pct = sum(1 for snap in r.daily_snapshots
                      if snap.total_value > 0 and snap.cash_total / snap.total_value < 0.01)
    distinct_tickers = len({t for acc in r.portfolio.accounts.values() for t in acc.lots
                             if any(l.shares > 1e-9 for l in acc.lots[t])})

    staleness_pairs = []
    for _, sd, in_scope_events in sessions_list:
        for event in in_scope_events:
            staleness_pairs.append((event.ticker, (sd - event.call_date).days))
    per_ticker_stale: dict = {}
    for t, d in staleness_pairs:
        per_ticker_stale.setdefault(t, []).append(d)
    per_ticker_mean_staleness = {t: statistics.mean(ds) for t, ds in per_ticker_stale.items()}
    mean_staleness_all = statistics.mean([d for _, d in staleness_pairs]) if staleness_pairs else 0.0

    # --- Step 1 proximity test: dollar-weighted forward return of each funded
    # Add, bucketed by days-since-that-ticker's-nearest-call. Horizons: 90
    # calendar days, and hold-to-window-end. Adds with no forward price are
    # dropped from the bucket rather than imputed.
    prox_buckets: dict = {}
    for f in funding_log:
        if f.get("actual_dollars", 0.0) <= 1.0:
            continue
        dsc = f.get("days_since_call")
        if dsc is None:
            continue
        p0 = f.get("buy_price")
        if not p0:
            continue
        bucket = ("0-3d" if dsc <= 3 else "4-7d" if dsc <= 7 else
                  "8-30d" if dsc <= 30 else "31-90d" if dsc <= 90 else "90d+")
        for horizon, when in (("h90", min(f["date"] + timedelta(days=90), C)),
                              ("end", C)):
            p1 = prices.price_on(f["ticker"], when)
            if p1 is None or p1 <= 0:
                continue
            b = prox_buckets.setdefault((bucket, horizon),
                                        {"n": 0, "dollars": 0.0, "wret": 0.0})
            b["n"] += 1
            b["dollars"] += f["actual_dollars"]
            b["wret"] += f["actual_dollars"] * (p1 / p0 - 1.0)
    add_proximity = {}
    for (bucket, horizon), b in prox_buckets.items():
        add_proximity[f"{bucket}|{horizon}"] = {
            "n": b["n"], "dollars": b["dollars"],
            "dollar_weighted_return": (b["wret"] / b["dollars"]) if b["dollars"] else None,
        }

    max_pp_change_per_session: dict = {}
    for f in funding_log:
        key = (f["date"], f["ticker"])
        max_pp_change_per_session[key] = max_pp_change_per_session.get(key, 0.0) + f["pp_change"]
    max_session_pp = max(max_pp_change_per_session.values()) if max_pp_change_per_session else 0.0

    return {
        "final_value": s.final_portfolio_value, "max_dd": s.max_drawdown_pct,
        "baseline_finals": s.baseline_finals, "baseline_drawdowns": s.baseline_drawdowns,
        "add_total": total, "fully_funded": fully_funded, "partial": partial, "unfunded": unfunded,
        "total_shortfall": sum(f["shortfall"] for f in funding_log),
        "distinct_tickers": distinct_tickers, "n_days": len(r.daily_snapshots),
        "below_1pct_days": below_1pct,
        "pct_below_1pct": 100 * below_1pct / len(r.daily_snapshots) if r.daily_snapshots else 0,
        "n_displacements": len(displacement_log),
        "displacement_log": displacement_log,
        "n_events": len(events), "n_sessions": len(sessions_list),
        "funding_log": funding_log, "daily_snapshots": r.daily_snapshots,
        "skipped_events": r.skipped_events, "portfolio": r.portfolio,
        "target_cap_log": target_cap_log,
        "mean_staleness": mean_staleness_all,
        "per_ticker_mean_staleness": per_ticker_mean_staleness,
        "max_session_pp_change": max_session_pp,
        "realized_gains": sum(rs.realized_gain for rs in r.portfolio.realized_sales),
        # --- §8 capitulation model diagnostics ---
        "n_pets": len(pet_log),
        "n_capitulations": len(capitulation_log),
        "n_declined": len(declined_log),
        "declined_dollars": sum(d["declined_dollars"] for d in declined_log),
        "capitulation_loss_from_peak": sum(c["loss_from_peak"] for c in capitulation_log),
        "capitulation_realized_gain": sum(c["realized_gain"] for c in capitulation_log),
        "pet_log": pet_log,
        "capitulation_log": capitulation_log,
        # --- Step 1 call-proximity test ---
        "add_proximity": add_proximity,
    }


def independent_max_drawdown(daily_snapshots):
    values = [s.total_value for s in daily_snapshots]
    worst_dd = 0.0
    running_peak = float("-inf")
    for v in values:
        if v > running_peak:
            running_peak = v
        if running_peak > 0:
            dd = (running_peak - v) / running_peak
            if dd > worst_dd:
                worst_dd = dd
    return worst_dd

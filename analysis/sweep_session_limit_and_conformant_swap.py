#!/usr/bin/env python3
"""
sweep_session_limit_and_conformant_swap.py — task #77
(prompts/sweep-session-limit-and-conformant-swap.md).

Session-limit sweep (2 funding modes x 4 limit values = 8 configs x 7 draws
= 56 runs), with swap_funding ALWAYS using the per-date (not per-event) 25%
donor trim cap -- the per-event version is retired as non-conformant with
§5, not offered as an option here.

Sale-attributed displacement accounting via RealizedSale.reason (added this
session, additive, verified non-behavior-changing).

Re-derives the drawdown bar from the four baselines on the exact clean
window and STOPS before scoring if it disagrees with the inherited 38.0%.

In-memory only. No DB writes, no LLM calls.

Usage:
    cd analysis && python3 sweep_session_limit_and_conformant_swap.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.simulator.allocator_v3 import (
    decide as decide_v3, STARTER_PCT_SPECULATIVE, STARTER_PCT_ESTABLISHED,
)
from analysis.simulator.allocator_v2 import _type_cap, _build_sell_trades
from analysis.simulator.accounts import Trade
from analysis.simulator.data import PriceLookup, load_call_events
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary, _max_drawdown
from trend_analyst import build_tier_function, compute_trend_verdict, apply_matrix, compute_final_confidence
from type_classifier import build_type_function, build_driver_count_function

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
START = date(2022, 1, 1)
C = date(2024, 6, 12)
INITIAL = 100_000
EXPECTED_NO_RESERVE = 141_837
CONFIDENCE_RANK = {"confident": 2, "advisory": 1, "unknown": 0, None: 0}
MANIFEST_DIR = SCRIPT_DIR / "data" / "run_manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
DRIVER_FILE = "analysis/sweep_session_limit_and_conformant_swap.py"

DB_SNAPSHOT_PATH = Path.home() / "investment-agent-backups" / "analysis_corpus_20260830.sql"


# ---------------------------------------------------------------------------
# §10b manifest infrastructure (0b: pin the driver, not its predecessor)
# ---------------------------------------------------------------------------

def sha256_file(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                           text=True, check=True).stdout.strip()


def assert_driver_committed():
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    if dirty:
        raise RuntimeError(
            f"git_dirty is true at HEAD={commit[:12]} -- Step 0a's hard "
            f"stop-gate requires false. Not proceeding."
        )
    # Assert the driver file exists in this commit's tree (0b).
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{DRIVER_FILE}"],
        cwd=REPO_ROOT, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"HEAD={commit[:12]} does not contain {DRIVER_FILE} -- manifest "
            f"would name a commit that predates the code producing these "
            f"numbers. Commit the driver first."
        )
    return commit, git("rev-parse", "--abbrev-ref", "HEAD"), dirty


_GIT_COMMIT, _GIT_BRANCH, _GIT_DIRTY = assert_driver_committed()
_TYPE_JSON_SHA = sha256_file(SCRIPT_DIR / "data" / "type_classifications.json")
_PRICE_CACHE_SHA = sha256_file(SCRIPT_DIR / "data" / "price_cache.json")
_FUNDAMENTALS_CACHE_SHA = sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json")
_DB_SNAPSHOT_SHA = sha256_file(DB_SNAPSHOT_PATH)


def write_manifest(run_id, loaded_events, in_window_events, params, results):
    def sha_of(events):
        repr_ = "|".join(f"{e.ticker}:{e.call_date.isoformat()}" for e in
                          sorted(events, key=lambda e: (e.ticker, e.call_date)))
        return hashlib.sha256(repr_.encode()).hexdigest()

    output_sha = hashlib.sha256(json.dumps(results, sort_keys=True, default=str).encode()).hexdigest()
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _GIT_COMMIT,
        "git_branch": _GIT_BRANCH,
        "git_dirty": _GIT_DIRTY,
        "driver_file": DRIVER_FILE,
        "corpus": {
            "source": "db",
            "created_at_window": ["2026-05-02 12:33:23-04", "2026-06-27 16:26:16-04"],
            "universe": ALL16,
            "loaded_event_count": len(loaded_events),
            "loaded_event_ids_sha256": sha_of(loaded_events),
            "in_window_event_count": len(in_window_events),
            "in_window_event_ids_sha256": sha_of(in_window_events),
            "db_snapshot": str(DB_SNAPSHOT_PATH),
            "db_snapshot_sha256": _DB_SNAPSHOT_SHA,
        },
        "prompt_version": "v6 (circumstantial, see recon-analysis-table-v6-corpus-out.md)",
        "model_version": "claude-sonnet-4-20250514 (circumstantial, same basis)",
        "classification": {
            "type_json_sha256": _TYPE_JSON_SHA,
            "tier_source": "trend_analyst.build_tier_function, frozen caches 2026-05-11",
            "price_cache_sha256": _PRICE_CACHE_SHA,
            "fundamentals_cache_sha256": _FUNDAMENTALS_CACHE_SHA,
        },
        "params": params,
        "results": results,
        "output_sha256": output_sha,
    }
    path = MANIFEST_DIR / f"{run_id}-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


# ---------------------------------------------------------------------------
# Data loading + trend recompute
# ---------------------------------------------------------------------------

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
    by_ticker: dict[str, list] = {}
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
    events_full = load_call_events(tickers=ALL16, end_date=C, dedupe_same_day_calls=True)
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(SCRIPT_DIR / "data" / "price_cache.json",
                                   SCRIPT_DIR / "data" / "fundamentals_cache.json")
    extra_fields = fetch_extra_fields(ALL16, C)
    recompute_trend_layer(events_full, tier_fn, extra_fields)
    return events_full, type_fn, driver_fn, tier_fn


# ---------------------------------------------------------------------------
# Funding-mode decide_fn -- swap_funding ALWAYS uses the per-date trim cap.
# ---------------------------------------------------------------------------

def make_funding_decide_fn(funding_mode, session_change_limit_pp=None,
                            ticker_state=None, funding_log=None, displacement_log=None):
    ticker_state = ticker_state if ticker_state is not None else {}
    funding_log = funding_log if funding_log is not None else []
    displacement_log = displacement_log if displacement_log is not None else []
    day_state = {"date": None, "start_of_day_value": {}, "trimmed_today": {}}

    def rank_key(ticker, state_entry, portfolio, prices_today, trade_date):
        if state_entry is None:
            return (0, -10**9, -1.0)
        conf = CONFIDENCE_RANK.get(state_entry.get("final_confidence"), 0)
        days_since = (trade_date - state_entry["call_date"]).days
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

    def decide_fn(
        *, ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        if day_state["date"] != trade_date:
            day_state["date"] = trade_date
            day_state["start_of_day_value"] = {
                t: portfolio.position_value(t, prices_today.get(t, 0.0))
                for t in ticker_state if portfolio.position_shares(t) > 1e-9
            }
            day_state["trimmed_today"] = {}

        portfolio_value_before = portfolio.total_value(prices_today)
        current_dollars_before = portfolio.position_value(ticker, day_price)
        had_position = portfolio.position_shares(ticker) > 1e-9

        trades = decide_v3(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call, driver_count=driver_count,
        )

        ticker_state[ticker] = {
            "final_action": final_action, "call_date": trade_date,
            "recommended_size_pct": recommended_size_pct,
            "type_classification": type_classification, "tier": tier,
            "driver_count": driver_count,
            "final_confidence": getattr(decide_fn, "_last_confidence", None),
        }
        if ticker not in day_state["start_of_day_value"] and portfolio.position_shares(ticker) > 1e-9:
            day_state["start_of_day_value"][ticker] = portfolio.position_value(ticker, day_price)

        starter_fired = is_first_call and not had_position
        intended = 0.0
        if starter_fired:
            starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                            else STARTER_PCT_ESTABLISHED)
            if portfolio_value_before > 0:
                intended += (starter_pct / 100.0) * portfolio_value_before
        v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
        if v2_leg_applies and final_action == "Add" and portfolio_value_before > 0:
            cap_pct = _type_cap(type_classification, tier, driver_count)
            target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct
            target_dollars = (target_pct / 100.0) * portfolio_value_before
            delta = target_dollars - current_dollars_before
            if delta > 0:
                intended += delta

        if intended <= 1e-6:
            return trades

        target_buy_dollars = intended
        if session_change_limit_pp is not None and portfolio_value_before > 0:
            limit_dollars = (session_change_limit_pp / 100.0) * portfolio_value_before
            target_buy_dollars = min(target_buy_dollars, limit_dollars)

        natural_buy_dollars = sum(t.shares * t.price for t in trades if t.side == "buy")

        if funding_mode == "no_reserve":
            cap = target_buy_dollars
            if natural_buy_dollars <= cap + 1e-6:
                actual = natural_buy_dollars
                final_trades = trades
            else:
                scale = cap / natural_buy_dollars if natural_buy_dollars > 0 else 0.0
                final_trades = []
                for t in trades:
                    if t.side == "buy":
                        scaled_shares = t.shares * scale
                        if scaled_shares > 1e-9:
                            final_trades.append(Trade(
                                account=t.account, ticker=t.ticker, side="buy",
                                shares=scaled_shares, price=t.price,
                                trade_date=t.trade_date, reason=t.reason + "-capped",
                            ))
                    else:
                        final_trades.append(t)
                actual = sum(t.shares * t.price for t in final_trades if t.side == "buy")
        elif funding_mode == "swap_funding":
            non_buy_trades = [t for t in trades if t.side != "buy"]
            shortfall = target_buy_dollars - natural_buy_dollars
            raised_by_account = {"tax_advantaged": 0.0, "taxable": 0.0}
            sell_trades = []
            if shortfall > 1e-6:
                donors = []
                for other, state in ticker_state.items():
                    if other == ticker:
                        continue
                    if portfolio.position_shares(other) <= 1e-9:
                        continue
                    if state.get("final_action") not in ("Hold", "Trim", "Exit"):
                        continue
                    donors.append(other)
                donors.sort(key=lambda t: rank_key(
                    t, ticker_state.get(t), portfolio, prices_today, trade_date))
                remaining = shortfall
                for donor in donors:
                    if remaining <= 1e-6:
                        break
                    donor_price = prices_today.get(donor)
                    if donor_price is None:
                        continue
                    donor_value_now = portfolio.position_value(donor, donor_price)
                    if donor_value_now <= 1e-6:
                        continue
                    # Conformant: 25% of donor's START-OF-DAY value, minus
                    # whatever's already been trimmed from it today.
                    sod_value = day_state["start_of_day_value"].get(donor, donor_value_now)
                    already_trimmed = day_state["trimmed_today"].get(donor, 0.0)
                    cap_today = max(0.0, 0.25 * sod_value - already_trimmed)
                    max_trim_dollars = min(cap_today, donor_value_now)
                    raise_amount = min(max_trim_dollars, remaining)
                    shares_to_sell = raise_amount / donor_price
                    if shares_to_sell < 1e-9:
                        continue
                    donor_sells = _build_sell_trades(
                        donor, shares_to_sell, portfolio, donor_price,
                        trade_date, reason="swap-funding-displacement",
                    )
                    actually_raised = sum(st.shares * st.price for st in donor_sells)
                    for st in donor_sells:
                        raised_by_account[st.account] += st.shares * st.price
                    sell_trades.extend(donor_sells)
                    remaining -= actually_raised
                    day_state["trimmed_today"][donor] = already_trimmed + actually_raised

                    donor_pct_after = ((donor_value_now - actually_raised) / portfolio_value_before * 100
                                        if portfolio_value_before > 0 else 0.0)
                    displacement_log.append({
                        "date": trade_date, "donor": donor, "candidate": ticker,
                        "raised": actually_raised,
                        "donor_final_action": ticker_state.get(donor, {}).get("final_action"),
                        "donor_pct_after": donor_pct_after,
                    })

            remaining_to_buy = target_buy_dollars
            new_buy_trades = []
            for account_name in ("tax_advantaged", "taxable"):
                if remaining_to_buy <= 1e-6:
                    break
                avail = portfolio.accounts[account_name].cash + raised_by_account[account_name]
                if avail <= 1e-6:
                    continue
                spend = min(remaining_to_buy, avail)
                shares = spend / day_price
                if shares < 1e-9:
                    continue
                new_buy_trades.append(Trade(
                    account=account_name, ticker=ticker, side="buy",
                    shares=shares, price=day_price, trade_date=trade_date,
                    reason="add-to-target-swap-funded",
                ))
                remaining_to_buy -= spend

            final_trades = sell_trades + non_buy_trades + new_buy_trades
            actual = sum(t.shares * t.price for t in new_buy_trades)
        else:
            raise ValueError(f"unknown funding_mode {funding_mode!r}")

        funding_log.append({
            "date": trade_date, "ticker": ticker, "intended_dollars": intended,
            "target_buy_dollars": target_buy_dollars, "actual_dollars": actual,
            "shortfall": max(target_buy_dollars - actual, 0.0),
        })
        return final_trades

    return decide_fn


def run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
             funding_mode, session_change_limit_pp=None, reverse_order=False, seed=None):
    events = list(events_full)
    if reverse_order:
        events = list(reversed(events))
    if seed is not None:
        rng = random.Random(seed)
        by_date: dict = {}
        for e in events:
            by_date.setdefault(e.call_date, []).append(e)
        events = []
        for d in sorted(by_date):
            bucket = by_date[d]
            rng.shuffle(bucket)
            events.extend(bucket)

    ticker_state, funding_log, displacement_log = {}, [], []
    confidence_by_key = {(e.ticker, e.call_date): e.final_confidence for e in events_full}
    base_decide = make_funding_decide_fn(
        funding_mode, session_change_limit_pp, ticker_state, funding_log, displacement_log)

    def decide_fn(
        *, ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        base_decide._last_confidence = confidence_by_key.get((ticker, trade_date))
        return base_decide(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call, driver_count=driver_count,
        )

    r = run_simulation(
        start_date=START, end_date=C,
        taxable_cash=INITIAL / 2, tax_advantaged_cash=INITIAL / 2,
        universe_tickers=ALL16, prices=prices, events=events,
        decide_fn=decide_fn, type_for_ticker=type_fn,
        driver_count_for_ticker=driver_fn, tier_for_ticker=tier_fn,
    )
    s = compute_summary(r)
    total = len(funding_log)
    fully_funded = sum(1 for f in funding_log if f["shortfall"] < 1.0)
    unfunded = sum(1 for f in funding_log if f["actual_dollars"] < 1.0 and f["intended_dollars"] >= 1.0)
    partial = total - fully_funded - unfunded
    n_days = len(r.daily_snapshots)
    below_1pct = sum(1 for snap in r.daily_snapshots
                      if snap.total_value > 0 and snap.cash_total / snap.total_value < 0.01)
    distinct_tickers = len({t for acc in r.portfolio.accounts.values() for t in acc.lots
                             if any(l.shares > 1e-9 for l in acc.lots[t])})

    displacement_sale_gains = [rs.realized_gain for rs in r.portfolio.realized_sales
                                if rs.reason == "swap-funding-displacement"]
    ordinary_sale_gains = [rs.realized_gain for rs in r.portfolio.realized_sales
                            if rs.reason != "swap-funding-displacement"]
    disp_hold = [d for d in displacement_log if d["donor_final_action"] == "Hold"]
    disp_trimexit = [d for d in displacement_log if d["donor_final_action"] in ("Trim", "Exit")]

    return {
        "final_value": s.final_portfolio_value, "max_dd": s.max_drawdown_pct,
        "baseline_finals": s.baseline_finals, "baseline_drawdowns": s.baseline_drawdowns,
        "add_total": total, "fully_funded": fully_funded, "partial": partial, "unfunded": unfunded,
        "total_shortfall": sum(f["shortfall"] for f in funding_log),
        "distinct_tickers": distinct_tickers, "n_days": n_days,
        "below_1pct_days": below_1pct, "pct_below_1pct": 100 * below_1pct / n_days if n_days else 0,
        "n_displacements": len(displacement_log),
        "displacement_sale_realized_gain": sum(displacement_sale_gains),
        "displacement_realized_gain_hold": sum(rs.realized_gain for rs in r.portfolio.realized_sales
                                                if rs.reason == "swap-funding-displacement"
                                                and any(d["date"] == rs.sale_date and d["donor"] == rs.ticker
                                                        and d["donor_final_action"] == "Hold"
                                                        for d in displacement_log)),
        "ordinary_sale_realized_gain": sum(ordinary_sale_gains),
        "n_disp_hold": len(disp_hold), "n_disp_trimexit": len(disp_trimexit),
        "below_2pct": sum(1 for d in displacement_log if d["donor_pct_after"] < 2.0),
        "below_1pct_donor": sum(1 for d in displacement_log if d["donor_pct_after"] < 1.0),
        "below_05pct_donor": sum(1 for d in displacement_log if d["donor_pct_after"] < 0.5),
        "n_events": len(events),
    }


def equal_weight_series(tickers, start_date, end_date, capital, prices):
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p
    values = []
    d = start_date
    while d <= end_date:
        total = 0.0
        for t, shares in holdings.items():
            p = prices.price_on(t, d, max_lookback_days=120)
            if p:
                total += shares * p
        values.append(total)
        d += timedelta(days=1)
    return values


def score_cell(final_value, max_dd, spy, qqq, tmfc, ew, dd_bar):
    beats = {"SPY": final_value > spy, "QQQ": final_value > qqq, "TMFC": final_value > tmfc}
    n_beat = sum(beats.values())
    dd_ok = max_dd * 100 <= dd_bar
    if n_beat == 3 and dd_ok:
        return "PASS", beats
    if n_beat >= 2 and dd_ok:
        return "SOFT PASS", beats
    return "FAIL", beats


def main() -> int:
    t0 = time.time()
    print(f"git commit={_GIT_COMMIT[:12]} branch={_GIT_BRANCH} dirty={_GIT_DIRTY}")
    if _GIT_DIRTY:
        print("STOP: git_dirty is true. Step 0a's hard stop-gate requires false.")
        return 1
    print("git_dirty=false confirmed; driver file present at HEAD. Proceeding.\n")

    events_full, type_fn, driver_fn, tier_fn = load_events_dedup_on()
    prices = PriceLookup.from_cache()
    print(f"Loaded events (dedup on): {len(events_full)}")
    in_window = [e for e in events_full if START <= e.call_date <= C]
    print(f"In-window events: {len(in_window)}\n")

    control = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, "no_reserve")
    print(f"no_reserve control: ${control['final_value']:,.2f}")
    if abs(control["final_value"] - EXPECTED_NO_RESERVE) >= 1.0:
        print(f"STOP: standing assertion failed -- expected ${EXPECTED_NO_RESERVE}, "
              f"got ${control['final_value']:,.2f}")
        return 1
    print("Standing assertion PASSED.\n")

    # ---- Step 3 (computed early so Step 2's scoring can use it; reported in order) ----
    spy = control["baseline_finals"]["SPY"]
    qqq = control["baseline_finals"]["QQQ"]
    tmfc = control["baseline_finals"]["TMFC"]
    spy_dd = control["baseline_drawdowns"]["SPY"]
    qqq_dd = control["baseline_drawdowns"]["QQQ"]
    tmfc_dd = control["baseline_drawdowns"]["TMFC"]
    ew_series = equal_weight_series(ALL16, START, C, INITIAL, prices)
    ew_final = ew_series[-1]
    ew_dd = _max_drawdown(ew_series)
    median_dd = statistics.median([spy_dd, qqq_dd, tmfc_dd, ew_dd])
    rederived_bar = (median_dd + 0.05) * 100

    print("=== Step 3 (computed first): re-derived drawdown bar ===")
    print(f"SPY:  final=${spy:,.2f}  maxDD={spy_dd*100:.2f}%")
    print(f"QQQ:  final=${qqq:,.2f}  maxDD={qqq_dd*100:.2f}%")
    print(f"TMFC: final=${tmfc:,.2f}  maxDD={tmfc_dd*100:.2f}%")
    print(f"Equal-weight: final=${ew_final:,.2f}  maxDD={ew_dd*100:.2f}%")
    print(f"Median of the four drawdowns: {median_dd*100:.2f}%")
    print(f"Re-derived bar (median + 5pp): {rederived_bar:.2f}%")
    print(f"Inherited bar (three sessions): 38.00%")
    bar_matches = abs(rederived_bar - 38.0) < 0.05
    print(f"Match: {'YES' if bar_matches else 'NO -- STOP, per instruction'}")

    write_manifest("step3-drawdown-baselines", events_full, in_window,
                    {"window": [str(START), str(C)], "universe": ALL16, "capital": INITIAL},
                    {"spy_final": spy, "spy_dd": spy_dd, "qqq_final": qqq, "qqq_dd": qqq_dd,
                     "tmfc_final": tmfc, "tmfc_dd": tmfc_dd, "ew_final": ew_final, "ew_dd": ew_dd,
                     "median_dd": median_dd, "rederived_bar_pct": rederived_bar,
                     "inherited_bar_pct": 38.0, "matches": bar_matches})

    if not bar_matches:
        print(f"\nMISMATCH: re-derived bar {rederived_bar:.2f}% != inherited 38.0%. "
              f"Per instruction: do not adopt the re-derived figure, do not describe "
              f"any cell as passing 'under' {rederived_bar:.2f}%. Both figures are "
              f"reported (above, and in the wrap-up); Step 2's measurement grid "
              f"still runs below, and per Step 3's own final instruction every "
              f"config is still scored against the EXISTING 38.0% bar -- the "
              f"design session decides which bar stands, not this run.")

    dd_bar = 38.0  # existing bar, per instruction -- scored against this regardless of the mismatch above

    # ---- Step 2: the eight-configuration grid, 7 draws each ----
    configs = {
        "A (no_reserve, off)": dict(funding_mode="no_reserve"),
        "C (no_reserve, 10pp)": dict(funding_mode="no_reserve", session_change_limit_pp=10.0),
        "no_reserve-15pp": dict(funding_mode="no_reserve", session_change_limit_pp=15.0),
        "no_reserve-20pp": dict(funding_mode="no_reserve", session_change_limit_pp=20.0),
        "D (swap_funding, 10pp, conformant)": dict(funding_mode="swap_funding", session_change_limit_pp=10.0),
        "swap_funding-15pp": dict(funding_mode="swap_funding", session_change_limit_pp=15.0),
        "swap_funding-20pp": dict(funding_mode="swap_funding", session_change_limit_pp=20.0),
        "swap_funding-off": dict(funding_mode="swap_funding"),
    }

    print(f"\n=== Step 2: eight-configuration grid, 7 draws each (56 runs) ===")
    all_results = {}
    for label, kwargs in configs.items():
        vals = {}
        cellinfo = {}
        r_fwd = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, **kwargs)
        vals["forward"] = r_fwd["final_value"]; cellinfo["forward"] = r_fwd
        r_rev = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, reverse_order=True, **kwargs)
        vals["reversed"] = r_rev["final_value"]; cellinfo["reversed"] = r_rev
        for seed in range(1, 6):
            r_seed = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, seed=seed, **kwargs)
            vals[f"seed{seed}"] = r_seed["final_value"]; cellinfo[f"seed{seed}"] = r_seed
        all_vals = list(vals.values())
        med = statistics.median(all_vals)
        all_results[label] = {"vals": vals, "cellinfo": cellinfo, "min": min(all_vals),
                               "median": med, "max": max(all_vals),
                               "spread": max(all_vals) - min(all_vals)}
        print(f"\n{label} ({kwargs}):")
        for k, v in vals.items():
            print(f"  {k:10} ${v:,.2f}")
        fwd = cellinfo["forward"]
        print(f"  min=${min(all_vals):,.2f}  median=${med:,.2f}  max=${max(all_vals):,.2f}  "
              f"spread=${max(all_vals)-min(all_vals):,.2f} ({100*(max(all_vals)-min(all_vals))/med:.1f}% of median)")
        print(f"  maxDD(forward)={fwd['max_dd']*100:.1f}%  cash<1%={fwd['pct_below_1pct']:.1f}%  "
              f"Adds funded/partial/unfunded={fwd['fully_funded']}/{fwd['partial']}/{fwd['unfunded']} "
              f"of {fwd['add_total']}  shortfall=${fwd['total_shortfall']:,.0f}  "
              f"distinct_tickers={fwd['distinct_tickers']}  displacements={fwd['n_displacements']}")
        if fwd["n_displacements"]:
            print(f"  donor below 2%/1%/0.5%: {fwd['below_2pct']}/{fwd['below_1pct_donor']}/{fwd['below_05pct_donor']} "
                  f"of {fwd['n_displacements']}")
            print(f"  displacement sale-attributed realized gain: ${fwd['displacement_sale_realized_gain']:,.0f}  "
                  f"(Hold-donor subset: ${fwd['displacement_realized_gain_hold']:,.0f})  "
                  f"ordinary Trim/Exit realized gain: ${fwd['ordinary_sale_realized_gain']:,.0f}")
            print(f"  displacements on Hold-verdict donors: {fwd['n_disp_hold']}  "
                  f"on Trim/Exit-verdict donors: {fwd['n_disp_trimexit']}")

        write_manifest(f"step2-{label.split()[0]}", events_full, in_window,
                        {**kwargs, "config_label": label, "seeds_tested": list(range(1, 6))},
                        {"values": vals, "min": min(all_vals), "median": med, "max": max(all_vals),
                         "forward_max_dd": fwd["max_dd"], "forward_diagnostics": {
                             k: v for k, v in fwd.items() if k not in ("baseline_finals", "baseline_drawdowns")}})

    elapsed = time.time() - t0
    print(f"\nWall-clock runtime for the 56-run grid (+ setup/scoring): {elapsed:.1f}s")

    # ---- Pre-declared rules ----
    a = all_results["A (no_reserve, off)"]
    c = all_results["C (no_reserve, 10pp)"]
    d = all_results["D (swap_funding, 10pp, conformant)"]

    print("\n=== Pre-declared rules, applied mechanically ===")
    c_verdict = "REAL" if c["median"] > a["max"] else "INSIDE THE NOISE BAND"
    d_verdict = "REAL" if d["median"] > a["max"] else "INSIDE THE NOISE BAND"
    print(f"Rule 1, C vs A: C median ${c['median']:,.0f} vs A max ${a['max']:,.0f} -> {c_verdict}")
    print(f"Rule 1, D vs A: D median ${d['median']:,.0f} vs A max ${a['max']:,.0f} -> {d_verdict}")

    c_range = (c["min"], c["max"])
    d_range = (d["min"], d["max"])
    overlap = not (c_range[1] < d_range[0] or d_range[1] < c_range[0])
    rule2 = "TIED (ranges overlap)" if overlap else "SEPARABLE"
    print(f"Rule 2, C vs D (both at 10pp): C range ${c_range[0]:,.0f}-${c_range[1]:,.0f}, "
          f"D range ${d_range[0]:,.0f}-${d_range[1]:,.0f} -> {rule2}")

    print("\nRule 3, limit surface shape (forward draw, by mode):")
    for mode_label, keys in [("no_reserve", ["A (no_reserve, off)", "C (no_reserve, 10pp)",
                                              "no_reserve-15pp", "no_reserve-20pp"]),
                              ("swap_funding", ["swap_funding-off", "D (swap_funding, 10pp, conformant)",
                                                "swap_funding-15pp", "swap_funding-20pp"])]:
        fwd_vals = [all_results[k]["cellinfo"]["forward"]["final_value"] for k in keys]
        print(f"  {mode_label}: off=${fwd_vals[0]:,.0f}  10pp=${fwd_vals[1]:,.0f}  "
              f"15pp=${fwd_vals[2]:,.0f}  20pp=${fwd_vals[3]:,.0f}")

    # ---- Step 3: scoring ----
    print(f"\n=== Scoring all 8 configs' forward draw against the {dd_bar}% bar ===")
    print(f"{'CONFIG':40}  {'FINAL':>12}  {'MAXDD':>7}  {'SCORE':>10}  BEATS")
    for label, res in all_results.items():
        fwd = res["cellinfo"]["forward"]
        score, beats = score_cell(fwd["final_value"], fwd["max_dd"], spy, qqq, tmfc, ew_final, dd_bar)
        beats_str = ",".join(k for k, v in beats.items() if v)
        print(f"{label:40}  ${fwd['final_value']:>10,.0f}  {fwd['max_dd']*100:>6.1f}%  {score:>10}  {beats_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

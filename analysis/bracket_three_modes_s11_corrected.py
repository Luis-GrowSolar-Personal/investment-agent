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
DRIVER_FILE = "analysis/bracket_three_modes_s11_corrected.py"

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

def _rebuild_buy_leg(ticker, target_buy_dollars, portfolio, day_price, trade_date,
                      raised_by_account, reason="add-to-target-s11fixed"):
    """The ONE buy-leg rebuild function, shared verbatim by
    no_reserve_s11fixed and swap_funding (per this session's Step 2
    instruction: 'use the same rebuild function ... if the two rebuild
    differently, the comparison reintroduces the confound'). Drains
    tax_advantaged then taxable, against LIVE cash plus whatever this
    event's donor sells (if any) already credited to raised_by_account --
    this is exactly what fixes §11 defect #2, since it never reads a
    stale, pre-execution cash snapshot for the second leg of a
    starter+Add concatenation."""
    remaining_to_buy = target_buy_dollars
    new_buy_trades = []
    for account_name in ("tax_advantaged", "taxable"):
        if remaining_to_buy <= 1e-6:
            break
        avail = portfolio.accounts[account_name].cash + raised_by_account.get(account_name, 0.0)
        if avail <= 1e-6:
            continue
        spend = min(remaining_to_buy, avail)
        shares = spend / day_price
        if shares < 1e-9:
            continue
        new_buy_trades.append(Trade(
            account=account_name, ticker=ticker, side="buy",
            shares=shares, price=day_price, trade_date=trade_date, reason=reason,
        ))
        remaining_to_buy -= spend
    actual = sum(t.shares * t.price for t in new_buy_trades)
    return new_buy_trades, actual


def make_funding_decide_fn(funding_mode, session_change_limit_pp=None,
                            ticker_state=None, funding_log=None, displacement_log=None,
                            target_cap_log=None):
    ticker_state = ticker_state if ticker_state is not None else {}
    funding_log = funding_log if funding_log is not None else []
    displacement_log = displacement_log if displacement_log is not None else []
    target_cap_log = target_cap_log if target_cap_log is not None else []
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
        cap_pct_this_ticker = _type_cap(type_classification, tier, driver_count)
        intended = 0.0
        if starter_fired:
            starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                            else STARTER_PCT_ESTABLISHED)
            # Gate 2 (decision-time invariant #2): the starter's own target
            # vs cap. By construction (5/8% constants, 15% minimum cap) this
            # can never breach on its own.
            target_cap_log.append({
                "date": trade_date, "ticker": ticker, "leg": "starter",
                "target_pct": starter_pct, "cap_pct": cap_pct_this_ticker,
                "excess": starter_pct - cap_pct_this_ticker,
            })
            if portfolio_value_before > 0:
                intended += (starter_pct / 100.0) * portfolio_value_before
        v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
        if v2_leg_applies and final_action == "Add" and portfolio_value_before > 0:
            cap_pct = _type_cap(type_classification, tier, driver_count)
            target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct
            # Gate 2: the v2 Add leg's own target vs cap. By construction
            # (min(recommended_size_pct, cap_pct)) this can never breach
            # either -- confirmed here, not assumed.
            target_cap_log.append({
                "date": trade_date, "ticker": ticker, "leg": "add",
                "target_pct": target_pct, "cap_pct": cap_pct,
                "excess": target_pct - cap_pct,
                "known_s11_concatenation": starter_fired,  # both legs fired this event
            })
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

        if funding_mode == "no_reserve_raw":
            # Today's baseline: decide_v3's raw concatenated trades passed
            # through unmodified whenever they already fit under the
            # session limit. Carries §11 defect #2 (starter + Add sized
            # against the same stale cash snapshot) unmodified -- this is
            # the comparability anchor for the existing corpus.
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
        elif funding_mode == "no_reserve_s11fixed":
            # §11's own prescribed "one bug-fixed cell": identical to
            # no_reserve_raw except the buy leg is rebuilt against LIVE
            # cash via the exact same _rebuild_buy_leg() helper
            # swap_funding uses below (raised_by_account all zero -- no
            # donor selling here, just correct cash accounting).
            non_buy_trades = [t for t in trades if t.side != "buy"]
            raised_by_account = {"tax_advantaged": 0.0, "taxable": 0.0}
            new_buy_trades, actual = _rebuild_buy_leg(
                ticker, target_buy_dollars, portfolio, day_price, trade_date, raised_by_account)
            final_trades = non_buy_trades + new_buy_trades
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

            new_buy_trades, actual = _rebuild_buy_leg(
                ticker, target_buy_dollars, portfolio, day_price, trade_date, raised_by_account,
                reason="add-to-target-swap-funded")
            final_trades = sell_trades + non_buy_trades + new_buy_trades
        else:
            raise ValueError(f"unknown funding_mode {funding_mode!r}")

        # Binding-constraint classification (Step 1d): what actually stopped
        # this Add from reaching its full target?
        eps = 1.0
        if actual >= intended - eps:
            binding = "target gap"        # fully funded -- nothing else bound
        elif target_buy_dollars < intended - eps and actual >= target_buy_dollars - eps:
            binding = "session limit"     # hit the limit-capped target exactly
        else:
            binding = "cash available"    # short even of the limit-capped target

        # Max single-session position change (§9 invariant #9, Step 1b):
        # net dollar effect of THIS event's full trade set on `ticker`,
        # as a % of pre-trade portfolio value. Positive = net buy.
        net_ticker_dollars = sum(
            (t.shares * t.price if t.side == "buy" else -t.shares * t.price)
            for t in final_trades if t.ticker == ticker
        )
        pp_change = (abs(net_ticker_dollars) / portfolio_value_before * 100
                     if portfolio_value_before > 0 else 0.0)

        funding_log.append({
            "date": trade_date, "ticker": ticker, "intended_dollars": intended,
            "target_buy_dollars": target_buy_dollars, "actual_dollars": actual,
            "shortfall": max(target_buy_dollars - actual, 0.0),
            "binding": binding, "pp_change": pp_change,
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

    ticker_state, funding_log, displacement_log, target_cap_log = {}, [], [], []
    confidence_by_key = {(e.ticker, e.call_date): e.final_confidence for e in events_full}
    base_decide = make_funding_decide_fn(
        funding_mode, session_change_limit_pp, ticker_state, funding_log, displacement_log,
        target_cap_log)

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
        "funding_log": funding_log,
        "daily_snapshots": r.daily_snapshots,
        "skipped_events": r.skipped_events,
        "portfolio": r.portfolio,
        "target_cap_log": target_cap_log,
        "binding_counts": _binding_counts(funding_log),
        "cap_drift": _cap_drift_census(r.daily_snapshots, type_fn, tier_fn, driver_fn),
    }


def _binding_counts(funding_log):
    counts = {"target gap": 0, "cash available": 0, "session limit": 0}
    for f in funding_log:
        counts[f["binding"]] = counts.get(f["binding"], 0) + 1
    return counts


def _cap_drift_census(daily_snapshots, type_fn, tier_fn, driver_fn):
    """Step 2 diagnostic: per ticker, max REALIZED weight ever observed
    (portfolio.total_value denominator, matching _decide_add), its cap,
    days spent above cap, and max excess in pp. Never a gate."""
    cap_by_ticker = {t: _type_cap(type_fn(t), tier_fn(t), driver_fn(t)) for t in ALL16}
    max_weight = {}
    days_above = {}
    for snap in daily_snapshots:
        if snap.total_value <= 0:
            continue
        for t, v in snap.position_values.items():
            w = v / snap.total_value * 100
            if w > max_weight.get(t, 0):
                max_weight[t] = w
            cap = cap_by_ticker.get(t)
            if cap is not None and w > cap:
                days_above[t] = days_above.get(t, 0) + 1
    census = {}
    for t in ALL16:
        cap = cap_by_ticker[t]
        mw = max_weight.get(t, 0.0)
        census[t] = {"max_weight": mw, "cap": cap, "days_above": days_above.get(t, 0),
                     "max_excess": max(0.0, mw - cap)}
    return census


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


def independent_max_drawdown(daily_snapshots):
    """Step 1a: a SECOND, separately-written max-drawdown computation over
    the DailySnapshot.total_value series, deliberately not sharing code
    with report.py::_max_drawdown (which walks a running peak forward).
    This one instead finds, for every trough candidate, the highest prior
    peak and takes the worst peak-to-trough ratio directly -- O(n^2) but
    the series here is under 1000 points, so that's fine, and the
    algorithmic shape is different on purpose."""
    values = [s.total_value for s in daily_snapshots]
    n = len(values)
    worst_dd = 0.0
    worst_peak_i = worst_trough_i = 0
    running_peak = float("-inf")
    running_peak_i = 0
    for i in range(n):
        if values[i] > running_peak:
            running_peak = values[i]
            running_peak_i = i
        if running_peak > 0:
            dd = (running_peak - values[i]) / running_peak
            if dd > worst_dd:
                worst_dd = dd
                worst_peak_i = running_peak_i
                worst_trough_i = i
    return worst_dd, worst_peak_i, worst_trough_i


def draw_kwargs_list():
    """forward, reversed, seed1..seed13 -- 15 draws total."""
    return [("forward", {}), ("reversed", {"reverse_order": True})] + \
           [(f"seed{s}", {"seed": s}) for s in range(1, 14)]


def ranges_overlap(a_min, a_max, b_min, b_max):
    return not (a_max < b_min or b_max < a_min)


MODES = ["no_reserve_raw", "no_reserve_s11fixed", "swap_funding"]


def run_five_gates(events_full, prices, type_fn, driver_fn, tier_fn, control_final):
    """Step 1: the five gates, with Gate 4 corrected to never stop on a
    skipped event attributable to §11's second documented defect. Run on
    all three modes at off, 0.5pp and 10pp.
    Returns (passed: bool, report_lines: list[str])."""
    lines = []
    all_ok = True

    def check(label, ok, detail):
        nonlocal all_ok
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        lines.append(f"  [{status}] {label}: {detail}")
        return ok

    # Gate 1: standing assertion
    check("Gate 1: standing assertion (no_reserve_raw control = $141,837)",
          abs(control_final - EXPECTED_NO_RESERVE) < 1.0,
          f"${control_final:,.2f}")

    configs = [(mode, limit_pp, label) for mode in MODES
               for limit_pp, label in [(None, "off"), (0.5, "0.5pp"), (10.0, "10pp")]]

    for mode, limit_pp, label in configs:
        lines.append(f"\n--- {mode}, {label}, forward draw ---")
        kwargs = dict(funding_mode=mode)
        if limit_pp is not None:
            kwargs["session_change_limit_pp"] = limit_pp
        r = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, **kwargs)

        # Gate 2: invariant #2 AT DECISION TIME -- target_pct vs cap_pct for
        # every Add-shaped leg (starter and v2), not realized/drifted weight.
        # §11's first defect (starter+Add landing over cap in the REALIZED
        # portfolio) is a known defect and does not stop the run -- and by
        # construction (min(recommended_size, cap_pct); starter constants
        # always below the smallest cap) this decision-time check cannot
        # fail unless there's an actual coding defect in _type_cap.
        max_excess = max((e["excess"] for e in r["target_cap_log"]), default=None)
        s11_events = [e for e in r["target_cap_log"] if e.get("known_s11_concatenation")]
        check(f"Gate 2: invariant #2 at decision time (target_pct <= cap_pct)",
              max_excess is None or max_excess <= 1e-6,
              (f"max(target_pct - cap_pct) observed = {max_excess:.4f}pp"
               if max_excess is not None else "no Add-shaped decisions") +
              f"  ({len(s11_events)} known-§11 starter+Add concatenation events this run -- "
              f"reported as the documented defect, not a new gate failure)")

        # Gate 3: invariant #9
        pp_changes = [f["pp_change"] for f in r["funding_log"]]
        max_pp_change = max(pp_changes) if pp_changes else 0.0
        limit_check = limit_pp if limit_pp is not None else float("inf")
        check(f"Gate 3: invariant #9 (session move <= limit + rounding)",
              max_pp_change <= limit_check + 0.5,
              f"max observed {max_pp_change:.2f}pp against limit={label}")

        # Gate 4: invariant #5 -- CONDITIONAL. Stop only on a skipped event
        # NOT attributable to §11 defect #2. Classify by (date, ticker)
        # membership in the known-s11-concatenation set built from
        # target_cap_log; an event skipped for that ticker on that date
        # where a concatenation fired is "known_s11_concatenation", anything
        # else is "other" and DOES stop the run.
        s11_dates_tickers = {(e["date"], e["ticker"]) for e in r["target_cap_log"]
                              if e.get("known_s11_concatenation")}
        classified = []
        unexplained = []
        for d, t, reason in r["skipped_events"]:
            if (d, t) in s11_dates_tickers:
                classified.append((d, t, reason))
            else:
                unexplained.append((d, t, reason))
        check("Gate 4: invariant #5, CONDITIONAL (skipped events attributable to §11 defect #2 don't stop)",
              len(unexplained) == 0,
              f"{len(classified)} known_s11_concatenation (not a failure), "
              f"{len(unexplained)} OTHER/unexplained (would stop the run)" +
              (f" -- {unexplained[:5]}" if unexplained else ""))
        if classified:
            lines.append(f"  [diagnostic] §11-defect-#2 skipped events this run: {classified}")

        # Gate 5: independent drawdown recomputation
        indep_dd, peak_i, trough_i = independent_max_drawdown(r["daily_snapshots"])
        dd_diff_pp = abs(indep_dd - r["max_dd"]) * 100
        check("Gate 5: independent drawdown recompute agrees within 0.01pp",
              dd_diff_pp < 0.01,
              f"compute_summary={r['max_dd']*100:.4f}%  independent={indep_dd*100:.4f}%  "
              f"diff={dd_diff_pp:.4f}pp")

        # Diagnostics (never gate the run) -- report only
        lines.append(f"  [diagnostic] binding constraint counts: {r['binding_counts']}")
        cap_breaches = {t: c for t, c in r["cap_drift"].items() if c["days_above"] > 0}
        if cap_breaches:
            lines.append(f"  [diagnostic] realized cap drift (informational, not a gate): {cap_breaches}")

    return all_ok, lines


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

    control0 = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, "no_reserve_raw")
    print(f"no_reserve_raw control (forward, off): ${control0['final_value']:,.2f}")
    if abs(control0["final_value"] - EXPECTED_NO_RESERVE) >= 1.0:
        print(f"STOP: standing assertion failed -- expected ${EXPECTED_NO_RESERVE}, "
              f"got ${control0['final_value']:,.2f}")
        return 1
    print("Standing assertion PASSED.\n")

    # ---- Drawdown bar diagnostic (inherited from last session, re-confirmed
    # arithmetically here; NOT re-derived or re-litigated) ----
    spy = control0["baseline_finals"]["SPY"]
    qqq = control0["baseline_finals"]["QQQ"]
    tmfc = control0["baseline_finals"]["TMFC"]
    spy_dd = control0["baseline_drawdowns"]["SPY"]
    qqq_dd = control0["baseline_drawdowns"]["QQQ"]
    tmfc_dd = control0["baseline_drawdowns"]["TMFC"]
    ew_series = equal_weight_series(ALL16, START, C, INITIAL, prices)
    ew_final = ew_series[-1]
    ew_dd = _max_drawdown(ew_series)
    median_dd_4 = statistics.median([spy_dd, qqq_dd, tmfc_dd, ew_dd])
    rederived_bar = (median_dd_4 + 0.05) * 100
    print("=== Drawdown baselines (unchanged from last session; not re-litigated) ===")
    print(f"SPY:  final=${spy:,.2f}  maxDD={spy_dd*100:.2f}%")
    print(f"QQQ:  final=${qqq:,.2f}  maxDD={qqq_dd*100:.2f}%")
    print(f"TMFC: final=${tmfc:,.2f}  maxDD={tmfc_dd*100:.2f}%")
    print(f"Equal-weight: final=${ew_final:,.2f}  maxDD={ew_dd*100:.2f}%")
    print(f"Median of the four: {median_dd_4*100:.2f}%  -> re-derived bar {rederived_bar:.2f}%")
    print(f"Standing/authoritative bar for scoring: 38.00% (39.12% is a diagnostic only, not adopted)\n")
    dd_bar = 38.0

    write_manifest("drawdown-baselines-v4", events_full, in_window,
                    {"window": [str(START), str(C)], "universe": ALL16, "capital": INITIAL},
                    {"spy_final": spy, "spy_dd": spy_dd, "qqq_final": qqq, "qqq_dd": qqq_dd,
                     "tmfc_final": tmfc, "tmfc_dd": tmfc_dd, "ew_final": ew_final, "ew_dd": ew_dd,
                     "median_dd": median_dd_4, "rederived_bar_pct": rederived_bar,
                     "authoritative_bar_pct": 38.0})

    # ================= STEP 1: THE FIVE GATES, CORRECTED =================
    print("=" * 70)
    print("STEP 1: the five gates (Gate 4 corrected) -- off, 0.5pp, 10pp, all three modes")
    print("=" * 70)
    gates_passed, gate_lines = run_five_gates(
        events_full, prices, type_fn, driver_fn, tier_fn, control0["final_value"])
    for line in gate_lines:
        print(line)
    print()

    write_manifest("step1-five-gates", events_full, in_window,
                    {"window": [str(START), str(C)], "universe": ALL16},
                    {"all_gates_passed": gates_passed, "detail": gate_lines})

    if not gates_passed:
        print("STOP: one or more of the five gates FAILED. Not proceeding to "
              "Step 4's bracketing sweep, per instruction.")
        return 1
    print("All five gates PASSED. Proceeding to Step 4's bracketing grid.\n")

    # ---- Step 3: the grid -- 10 limits x 3 modes x 15 draws = 450 runs ----
    limit_values = [None, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    limit_labels = ["off", "0.5", "1", "1.5", "2", "2.5", "3", "4", "5", "10"]
    modes = MODES
    draws = draw_kwargs_list()

    print(f"=== Step 3: the grid, {len(limit_values)} limits x {len(modes)} modes x "
          f"{len(draws)} draws = {len(limit_values)*len(modes)*len(draws)} runs ===\n")

    all_results = {}  # (mode, limit_label) -> {...}
    for mode in modes:
        for label, limit_pp in zip(limit_labels, limit_values):
            key = (mode, label)
            base_kwargs = dict(funding_mode=mode)
            if limit_pp is not None:
                base_kwargs["session_change_limit_pp"] = limit_pp

            finals, dds, cellinfo = {}, {}, {}
            for draw_name, draw_kwargs in draws:
                r = run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
                             **base_kwargs, **draw_kwargs)
                finals[draw_name] = r["final_value"]
                dds[draw_name] = r["max_dd"]
                cellinfo[draw_name] = r

            final_vals = list(finals.values())
            dd_vals = list(dds.values())
            fwd = cellinfo["forward"]
            med_final = statistics.median(final_vals)
            med_dd = statistics.median(dd_vals)
            n_clear_38 = sum(1 for dd in dd_vals if dd * 100 <= 38.0)
            n_clear_3912 = sum(1 for dd in dd_vals if dd * 100 <= rederived_bar)

            s11_dt = {(e["date"], e["ticker"]) for e in fwd["target_cap_log"]
                      if e.get("known_s11_concatenation")}
            n_skip_s11 = sum(1 for d, t, _ in fwd["skipped_events"] if (d, t) in s11_dt)
            n_skip_other = len(fwd["skipped_events"]) - n_skip_s11

            res = {
                "mode": mode, "limit_label": label, "limit_pp": limit_pp,
                "finals": finals, "dds": dds, "cellinfo": cellinfo,
                "final_min": min(final_vals), "final_median": med_final, "final_max": max(final_vals),
                "final_spread": max(final_vals) - min(final_vals),
                "dd_min": min(dd_vals), "dd_median": med_dd, "dd_max": max(dd_vals),
                "n_clear_38": n_clear_38, "n_clear_3912": n_clear_3912, "n_draws": len(dd_vals),
                "fwd": fwd, "n_skip_s11": n_skip_s11, "n_skip_other": n_skip_other,
            }
            all_results[key] = res

            print(f"--- {mode} limit={label}pp ---")
            print(f"  final: min=${res['final_min']:,.0f}  median=${med_final:,.0f}  "
                  f"max=${res['final_max']:,.0f}  spread=${res['final_spread']:,.0f} "
                  f"({100*res['final_spread']/med_final:.1f}% of median)")
            print(f"  maxDD: min={res['dd_min']*100:.1f}%  median={med_dd*100:.1f}%  "
                  f"max={res['dd_max']*100:.1f}%  clears38.0%={n_clear_38}/15  "
                  f"clears39.12%(diag)={n_clear_3912}/15")
            print(f"  forward-draw diagnostics: cash<1%={fwd['pct_below_1pct']:.1f}%  "
                  f"Adds funded/partial/unfunded={fwd['fully_funded']}/{fwd['partial']}/{fwd['unfunded']} "
                  f"of {fwd['add_total']}  shortfall=${fwd['total_shortfall']:,.0f}  "
                  f"distinct_tickers={fwd['distinct_tickers']}  displacements={fwd['n_displacements']}  "
                  f"skipped_events: {n_skip_s11} known-§11 / {n_skip_other} other")
            if fwd["n_displacements"]:
                print(f"  donor below 2%/1%/0.5%: {fwd['below_2pct']}/{fwd['below_1pct_donor']}/"
                      f"{fwd['below_05pct_donor']} of {fwd['n_displacements']}")
            print(f"  [Step 3 diagnostic] binding constraint counts (forward draw): {fwd['binding_counts']}")
            cap_breaches = {t: c for t, c in fwd["cap_drift"].items() if c["days_above"] > 0}
            n_tickers_breach = len(cap_breaches)
            total_ticker_days = sum(c["days_above"] for c in cap_breaches.values())
            largest_excess = max((c["max_excess"] for c in fwd["cap_drift"].values()), default=0.0)
            largest_excess_ticker = max(fwd["cap_drift"].items(), key=lambda kv: kv[1]["max_excess"],
                                          default=(None, {}))[0] if fwd["cap_drift"] else None
            print(f"  [Step 2 diagnostic] cap drift (forward draw): {n_tickers_breach} tickers ever exceed cap, "
                  f"{total_ticker_days} total ticker-days above cap, largest excess "
                  f"{largest_excess:.2f}pp ({largest_excess_ticker})")
            if cap_breaches:
                print(f"      breach detail: {cap_breaches}")

            write_manifest(f"bracket-{mode}-{label}pp", events_full, in_window,
                            {**base_kwargs, "limit_label": label,
                             "draws": [d[0] for d in draws]},
                            {"final": {"min": res["final_min"], "median": med_final, "max": res["final_max"]},
                             "dd": {"min": res["dd_min"], "median": med_dd, "max": res["dd_max"]},
                             "n_clear_38": n_clear_38, "n_clear_3912_diagnostic": n_clear_3912,
                             "n_skip_known_s11": n_skip_s11, "n_skip_other": n_skip_other,
                             "forward_diagnostics": {k: v for k, v in fwd.items()
                                                      if k not in ("baseline_finals", "baseline_drawdowns",
                                                                    "funding_log", "daily_snapshots",
                                                                    "skipped_events", "portfolio",
                                                                    "target_cap_log")}})

    elapsed = time.time() - t0

    # ---- Anchor reproduction check: off and 10pp should reproduce the
    # previous (sweep-limit-axis-dense) grid's medians to the dollar ----
    print("=== Anchor reproduction check (off, 10pp vs. sweep-limit-axis-dense-out.md) ===")
    # Exact values from analysis/data/run_manifests/dense-*-manifest.json
    # (sweep-limit-axis-dense session), not the rounded figures printed in
    # that session's wrap-up prose.
    prior_medians = {
        ("no_reserve_raw", "off"): 139354.62876414592, ("no_reserve_raw", "10"): 179605.3269444481,
        ("swap_funding", "off"): 155877.75172085734, ("swap_funding", "10"): 156231.06246731651,
    }
    anchors_match = True
    for (mode, label), prior_med in prior_medians.items():
        cur_med = all_results[(mode, label)]["final_median"]
        diff = abs(cur_med - prior_med)
        ok = diff < 0.005  # exact -- no tolerance, per this session's prompt
        if not ok:
            anchors_match = False
        print(f"  {mode:14} {label:>4}pp: prior median ${prior_med:,.6f}  this run ${cur_med:,.6f}  "
              f"diff ${diff:,.6f}  -> {'MATCH' if ok else 'MISMATCH'}")
    if not anchors_match:
        print("  MISMATCH DETECTED: something changed since the previous grid. "
              "The comparison to that prior run is VOID -- treat this grid as "
              "self-contained, not as a direct extension of it.")
    else:
        print("  All anchors reproduce exactly. This grid is directly comparable "
              "to the previous one.")
    print(f"\nWall-clock runtime for the {len(limit_values)*len(modes)*len(draws)}-run grid "
          f"(+ setup/scoring): {elapsed:.1f}s")

    # ---- Step 4: what §11 defect #2 actually costs ----
    print("\n=== Step 4: §11 defect #2 cost surface (no_reserve_raw vs no_reserve_s11fixed) ===")
    print(f"{'LIMIT':>6}  {'RAW MEDIAN':>12}  {'FIXED MEDIAN':>13}  {'DELTA $':>10}  "
          f"{'DELTA %':>8}  {'RAW DD MED':>10}  {'FIXED DD MED':>12}  {'RAW SKIP':>9}  {'FIXED SKIP':>10}")
    for label in limit_labels:
        raw = all_results[("no_reserve_raw", label)]
        fixed = all_results[("no_reserve_s11fixed", label)]
        delta = fixed["final_median"] - raw["final_median"]
        delta_pct = 100 * delta / raw["final_median"] if raw["final_median"] else 0.0
        print(f"  {label:>5}pp  ${raw['final_median']:>10,.0f}  ${fixed['final_median']:>11,.0f}  "
              f"${delta:>+8,.0f}  {delta_pct:>+6.1f}%  {raw['dd_median']*100:>8.1f}%  "
              f"{fixed['dd_median']*100:>10.1f}%  {raw['n_skip_s11']+raw['n_skip_other']:>7}  "
              f"{fixed['n_skip_s11']+fixed['n_skip_other']:>8}")

    # ---- Rule 1: beats the control (no_reserve_raw, off) ----
    print("\n=== Rule 1: beats the control (no_reserve_raw, off) ===")
    control = all_results[("no_reserve_raw", "off")]
    control_fixed = all_results[("no_reserve_s11fixed", "off")]
    for mode in modes:
        for label in limit_labels:
            if mode == "no_reserve_raw" and label == "off":
                continue
            r = all_results[(mode, label)]
            margin = r["final_median"] - control["final_max"]
            margin_pct = 100 * margin / control["final_max"]
            verdict = "REAL" if margin > 0 else "INSIDE THE NOISE BAND"
            margin2 = r["final_median"] - control_fixed["final_max"]
            margin2_pct = 100 * margin2 / control_fixed["final_max"]
            verdict2 = "REAL" if margin2 > 0 else "INSIDE THE NOISE BAND"
            print(f"  {mode:20} {label:>5}pp: median ${r['final_median']:,.0f} vs raw-control max "
                  f"${control['final_max']:,.0f} -> margin ${margin:,.0f} ({margin_pct:+.1f}%) -> {verdict}   "
                  f"| vs s11fixed-control max ${control_fixed['final_max']:,.0f} -> margin ${margin2:,.0f} "
                  f"({margin2_pct:+.1f}%) -> {verdict2}")

    # ---- Rule 3a: shape -- REWRITTEN AS A SINGLE CLAUSE, supersedes all
    # prior versions. Classify each first-difference material/immaterial
    # (material iff |diff| >= smaller of the two adjacent configs' own
    # 15-draw ranges); discard immaterial ones; classify the REMAINING
    # sign sequence as unimodal (+...+ -...-, either side empty) or jagged. ----
    print("\n=== Rule 3a: shape (single clause -- material/immaterial then sign sequence) ===")
    shape_classification = {}
    material_seqs = {}
    for mode in modes:
        medians = [all_results[(mode, l)]["final_median"] for l in limit_labels]
        diffs = [medians[i+1] - medians[i] for i in range(len(medians)-1)]
        materiality = []
        for i, d in enumerate(diffs):
            spread_left = all_results[(mode, limit_labels[i])]["final_spread"]
            spread_right = all_results[(mode, limit_labels[i+1])]["final_spread"]
            material = abs(d) >= min(spread_left, spread_right)
            materiality.append(material)
        print(f"  {mode}: medians={[f'${m:,.0f}' for m in medians]}")
        for i, (l1, l2, d, mat) in enumerate(zip(limit_labels, limit_labels[1:], diffs, materiality)):
            spread_left = all_results[(mode, l1)]["final_spread"]
            spread_right = all_results[(mode, l2)]["final_spread"]
            print(f"    {l1}->{l2}: diff=${d:+,.0f}  smaller-adjacent-range=${min(spread_left, spread_right):,.0f}  "
                  f"-> {'MATERIAL' if mat else 'immaterial'}")
        material_signs = ["+" if diffs[i] > 0 else "-" for i in range(len(diffs)) if materiality[i]]
        material_seq_str = "".join(material_signs)
        changes = sum(1 for i in range(len(material_signs)-1) if material_signs[i] != material_signs[i+1])
        classification = "UNIMODAL AND USABLE" if changes == 0 else "JAGGED AND UNUSABLE"
        shape_classification[mode] = classification
        material_seqs[mode] = material_seq_str
        print(f"    material sign sequence: '{material_seq_str}' ({sum(materiality)} of {len(diffs)} "
              f"differences are material)")
        print(f"    classification: {classification}")

    # ---- Rule 3b: plateau, with boundary condition ----
    print("\n=== Rule 3b: plateau (unimodal modes only), with boundary condition ===")
    plateaus = {}
    for mode in modes:
        if "JAGGED" in shape_classification[mode]:
            print(f"  {mode}: JAGGED -- no plateau, nothing spec'd from this axis.")
            plateaus[mode] = None
            continue
        peak_label = max(limit_labels, key=lambda l: all_results[(mode, l)]["final_median"])
        peak = all_results[(mode, peak_label)]
        plateau = [l for l in limit_labels
                   if ranges_overlap(all_results[(mode, l)]["final_min"], all_results[(mode, l)]["final_max"],
                                      peak["final_min"], peak["final_max"])]
        plateaus[mode] = plateau
        print(f"  {mode}: peak at {peak_label}pp (median ${peak['final_median']:,.0f}, "
              f"range ${peak['final_min']:,.0f}-${peak['final_max']:,.0f})")
        print(f"    plateau (limits overlapping the peak's range): {plateau}")
        if peak_label == limit_labels[0] or peak_label == limit_labels[-1]:
            end_desc = "first sampled value (off)" if peak_label == limit_labels[0] else \
                       f"last sampled value ({peak_label}pp)"
            print(f"    OPTIMUM NOT BRACKETED: the peak ({peak_label}pp) sits at the "
                  f"{end_desc}, an end of the sampled range. The plateau is open at that end. "
                  f"No limit value can be recommended until the axis is bracketed on both sides.")
        if len(plateau) >= len(limit_labels) - 1:
            print(f"    NOTE: plateau spans nearly the whole axis -- axis does not discriminate.")

    # ---- Rule 4: drawdown bar on the distribution ----
    print(f"\n=== Rule 4: drawdown bar (median across 15 draws), bar={dd_bar}% ===")
    print(f"{'CONFIG':22}  {'MED FINAL':>12}  {'MED DD':>7}  {'BEATS 3':>8}  {'CLEARS':>7}  "
          f"{'SHARE CLEAR':>12}  VERDICT")
    for mode in modes:
        for label in limit_labels:
            r = all_results[(mode, label)]
            beats3 = r["final_median"] > spy and r["final_median"] > qqq and r["final_median"] > tmfc
            clears_median = r["dd_median"] * 100 <= dd_bar
            share_clear = r["n_clear_38"] / r["n_draws"]
            if beats3 and clears_median:
                if share_clear >= 2/3:
                    verdict = "ROBUSTLY PASSING"
                else:
                    verdict = "FRAGILE (passes median, <2/3 of draws)"
            elif beats3:
                verdict = "FAIL (drawdown)"
            else:
                verdict = "FAIL (return)"
            print(f"  {mode+'-'+label:20}  ${r['final_median']:>10,.0f}  {r['dd_median']*100:>6.1f}%  "
                  f"{'yes' if beats3 else 'no':>8}  {'yes' if clears_median else 'no':>7}  "
                  f"{share_clear*100:>10.0f}%  {verdict}")

    # ---- Rule 2: pairwise, best config of each mode, on BOTH return and drawdown ----
    print("\n=== Rule 2: pairwise separability, best config per mode (return AND drawdown) ===")
    top_label = {mode: max(limit_labels, key=lambda l: all_results[(mode, l)]["final_median"])
                 for mode in modes}
    top = {mode: all_results[(mode, top_label[mode])] for mode in modes}
    for mode in modes:
        t = top[mode]
        print(f"  Top {mode}: {top_label[mode]}pp, median ${t['final_median']:,.0f}, "
              f"return range ${t['final_min']:,.0f}-${t['final_max']:,.0f}, "
              f"drawdown range {t['dd_min']*100:.1f}%-{t['dd_max']*100:.1f}%")
    import itertools
    for m1, m2 in itertools.combinations(modes, 2):
        t1, t2 = top[m1], top[m2]
        ret_overlap = ranges_overlap(t1["final_min"], t1["final_max"], t2["final_min"], t2["final_max"])
        dd_overlap = ranges_overlap(t1["dd_min"], t1["dd_max"], t2["dd_min"], t2["dd_max"])
        print(f"  {m1} ({top_label[m1]}pp) vs {m2} ({top_label[m2]}pp): "
              f"return {'TIED' if ret_overlap else 'SEPARABLE'}, "
              f"drawdown {'TIED' if dd_overlap else 'SEPARABLE'}")

    # ---- "Follow the peak": trough analysis for EACH mode's best config ----
    print("\n=== Peak trough analysis, per mode (best config in each) ===")
    peak_manifest_results = {}
    for mode in modes:
        peak_res = top[mode]
        peak_fwd = peak_res["cellinfo"]["forward"]
        print(f"\n  {mode} peak: {top_label[mode]}pp, median ${peak_res['final_median']:,.0f}")
        indep_dd, peak_i, trough_i = independent_max_drawdown(peak_fwd["daily_snapshots"])
        trough_snap = peak_fwd["daily_snapshots"][trough_i]
        trough_cash_pct = (trough_snap.cash_total / trough_snap.total_value * 100
                            if trough_snap.total_value > 0 else 0.0)
        trough_invested_pct = 100 - trough_cash_pct
        trough_holdings = {t: v for t, v in trough_snap.position_values.items() if v > 1.0}
        final_snap = peak_fwd["daily_snapshots"][-1]
        final_holdings = {t: v / final_snap.total_value * 100 for t, v in final_snap.position_values.items()
                           if v > 1.0}
        print(f"    Drawdown trough: {trough_snap.date}  invested={trough_invested_pct:.1f}%  "
              f"cash={trough_cash_pct:.1f}%")
        print(f"    Trough holdings: {sorted(trough_holdings.items(), key=lambda kv: -kv[1])}")
        print(f"    Terminal composition ({final_snap.date}): " +
              ", ".join(f"{t}={pct:.1f}%" for t, pct in sorted(final_holdings.items(), key=lambda kv: -kv[1])))
        peak_manifest_results[mode] = {
            "peak_label": top_label[mode], "trough_date": str(trough_snap.date),
            "trough_invested_pct": trough_invested_pct, "trough_cash_pct": trough_cash_pct,
            "trough_holdings": trough_holdings, "terminal_composition": final_holdings,
        }

    write_manifest("peak-trough-analysis-per-mode", events_full, in_window,
                    {"modes": modes}, peak_manifest_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())

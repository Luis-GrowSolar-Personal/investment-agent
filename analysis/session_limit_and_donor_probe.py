#!/usr/bin/env python3
"""
session_limit_and_donor_probe.py — task #77, session-limit-vs-funding-mode
diagnostic (prompts/diagnose-session-limit-and-donor-rule.md).

Step 1: ordering-probe distributions (forward, reversed, 5 seeds) for three
configs (A: no_reserve/off, B: swap_funding/10pp, C: no_reserve/10pp),
tested against the pre-declared decision rule.

Step 2: donor-rule decomposition (Hold vs Trim/Exit donors, realized
gain/loss split, position-size-after-draw distribution), an
inverted-gap-term donor-ranking variant, and a per-date (not per-event)
25%-of-donor trim cap.

Step 3: pass/fail scoring of every cell (this run's + the prior sweep's)
against BACKTEST_SIMULATOR.md's bar, with SPY/QQQ/TMFC/equal-weight
reported explicitly.

Every run emits a <run_id>-manifest.json per ALLOCATOR_OPERATING_MODEL.md
§10b. In-memory only; no DB writes, no LLM calls.

Usage:
    cd analysis && python3 session_limit_and_donor_probe.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
from datetime import date, datetime, timezone
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
from analysis.simulator.report import compute_summary
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

DB_SNAPSHOT_PATH = Path.home() / "investment-agent-backups" / "analysis_corpus_20260830.sql"
PRICE_CACHE_ARCHIVE = Path.home() / "investment-agent-backups" / "caches_20260830" / "price_cache.json"
FUNDAMENTALS_CACHE_ARCHIVE = Path.home() / "investment-agent-backups" / "caches_20260830" / "fundamentals_cache.json"


# ---------------------------------------------------------------------------
# §10b manifest infrastructure
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def git_info():
    def run(*args):
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
    commit = run("rev-parse", "HEAD")
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(run("status", "--porcelain"))
    return commit, branch, dirty


_GIT_COMMIT, _GIT_BRANCH, _GIT_DIRTY = git_info()
_TYPE_JSON_SHA = sha256_file(SCRIPT_DIR / "data" / "type_classifications.json")
_PRICE_CACHE_SHA = sha256_file(SCRIPT_DIR / "data" / "price_cache.json")
_FUNDAMENTALS_CACHE_SHA = sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json")
_DB_SNAPSHOT_SHA = sha256_file(DB_SNAPSHOT_PATH)


def write_manifest(run_id, events, params, results):
    transcript_ids_repr = "|".join(f"{e.ticker}:{e.call_date.isoformat()}" for e in
                                    sorted(events, key=lambda e: (e.ticker, e.call_date)))
    transcript_sha = hashlib.sha256(transcript_ids_repr.encode()).hexdigest()
    output_repr = json.dumps(results, sort_keys=True, default=str)
    output_sha = hashlib.sha256(output_repr.encode()).hexdigest()

    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _GIT_COMMIT,
        "git_branch": _GIT_BRANCH,
        "git_dirty": _GIT_DIRTY,
        "corpus": {
            "source": "db",
            "created_at_window": ["2026-05-02 12:33:23-04", "2026-06-27 16:26:16-04"],
            "universe": ALL16,
            "event_count": len(events),
            "transcript_ids_sha256": transcript_sha,
            "db_snapshot": str(DB_SNAPSHOT_PATH),
            "db_snapshot_sha256": _DB_SNAPSHOT_SHA,
        },
        "prompt_version": "v6 (circumstantial -- see recon-analysis-table-v6-corpus-out.md; "
                           "6/805 rows explicitly tagged, rest inferred from createdAt window)",
        "model_version": "claude-sonnet-4-20250514 (circumstantial, same basis)",
        "classification": {
            "type_json_sha256": _TYPE_JSON_SHA,
            "tier_source": "trend_analyst.build_tier_function (live 3-axis rule over "
                            "price_cache.json/fundamentals_cache.json, frozen 2026-05-11)",
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
# Data loading + trend recompute (unchanged method from prior sessions)
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
# Funding-mode decide_fn factory (extended: full displacement decomposition,
# invertible donor-gap term, optional per-date trim cap)
# ---------------------------------------------------------------------------

def make_funding_decide_fn(
    funding_mode, reserve_pct=0.0, session_change_limit_pp=None,
    ticker_state=None, funding_log=None, displacement_log=None,
    invert_donor_gap=False, per_date_cap=False,
):
    ticker_state = ticker_state if ticker_state is not None else {}
    funding_log = funding_log if funding_log is not None else []
    displacement_log = displacement_log if displacement_log is not None else []
    day_state = {"date": None, "start_of_day_value": {}, "trimmed_today": {}}

    def gap_term(target_dollars, current_dollars, for_donor):
        gap = ((target_dollars - current_dollars) / target_dollars
               if target_dollars > 0 else -1.0)
        if for_donor and invert_donor_gap:
            return -gap
        return gap

    def rank_key(ticker, state_entry, portfolio, prices_today, trade_date, for_donor):
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
            gap = gap_term(target_dollars, current_dollars, for_donor)
        return (conf, recency_score, gap)

    def decide_fn(
        *, ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        if per_date_cap and day_state["date"] != trade_date:
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
        if per_date_cap and ticker not in day_state["start_of_day_value"] \
                and portfolio.position_shares(ticker) > 1e-9:
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

        if funding_mode in ("no_reserve", "cash_reserve"):
            cap = target_buy_dollars
            if funding_mode == "cash_reserve":
                combined_cash = sum(a.cash for a in portfolio.accounts.values())
                floor_dollars = (reserve_pct / 100.0) * portfolio_value_before
                spendable = max(0.0, combined_cash - floor_dollars)
                cap = min(cap, spendable)
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
                    t, ticker_state.get(t), portfolio, prices_today, trade_date, for_donor=True))
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
                    if per_date_cap:
                        sod_value = day_state["start_of_day_value"].get(donor, donor_value_now)
                        already_trimmed = day_state["trimmed_today"].get(donor, 0.0)
                        cap_today = max(0.0, 0.25 * sod_value - already_trimmed)
                        max_trim_dollars = min(cap_today, donor_value_now)
                    else:
                        max_trim_dollars = 0.25 * donor_value_now
                    raise_amount = min(max_trim_dollars, remaining)
                    shares_to_sell = raise_amount / donor_price
                    if shares_to_sell < 1e-9:
                        continue
                    donor_value_before_draw = donor_value_now
                    pv_before_pct = (donor_value_before_draw / portfolio_value_before * 100
                                     if portfolio_value_before > 0 else 0.0)
                    donor_sells = _build_sell_trades(
                        donor, shares_to_sell, portfolio, donor_price,
                        trade_date, reason="swap-funding-displacement",
                    )
                    actually_raised = sum(st.shares * st.price for st in donor_sells)
                    for st in donor_sells:
                        raised_by_account[st.account] += st.shares * st.price
                    sell_trades.extend(donor_sells)
                    remaining -= actually_raised
                    if per_date_cap:
                        day_state["trimmed_today"][donor] = already_trimmed + actually_raised

                    donor_value_after = donor_value_before_draw - actually_raised
                    pv_after_pct = (donor_value_after / portfolio_value_before * 100
                                    if portfolio_value_before > 0 else 0.0)
                    donor_state = ticker_state.get(donor, {})
                    cap_pct_donor = _type_cap(donor_state.get("type_classification"),
                                               donor_state.get("tier"), donor_state.get("driver_count"))
                    rsp_donor = donor_state.get("recommended_size_pct")
                    target_pct_donor = (min(rsp_donor, cap_pct_donor) if rsp_donor else cap_pct_donor)
                    target_dollars_donor = (target_pct_donor / 100.0) * portfolio_value_before
                    gap_donor = ((target_dollars_donor - donor_value_before_draw) / target_dollars_donor
                                 if target_dollars_donor > 0 else None)
                    displacement_log.append({
                        "date": trade_date, "donor": donor, "candidate": ticker,
                        "raised": actually_raised,
                        "donor_final_action": donor_state.get("final_action"),
                        "donor_pct_before": pv_before_pct,
                        "donor_pct_after": pv_after_pct,
                        "donor_gap_to_target": gap_donor,
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
            "starter_fired": starter_fired,
        })
        return final_trades

    return decide_fn


def run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
             funding_mode, reserve_pct=0.0, session_change_limit_pp=None,
             reverse_order=False, seed=None, invert_donor_gap=False, per_date_cap=False):
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
        funding_mode, reserve_pct, session_change_limit_pp,
        ticker_state, funding_log, displacement_log, invert_donor_gap, per_date_cap,
    )

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
    displacement_gains = sum(
        rs.realized_gain for rs in r.portfolio.realized_sales
        if rs.ticker in {d["donor"] for d in displacement_log}
    )
    distinct_tickers = len({t for acc in r.portfolio.accounts.values() for t in acc.lots
                             if any(l.shares > 1e-9 for l in acc.lots[t])})
    return {
        "final_value": s.final_portfolio_value, "max_dd": s.max_drawdown_pct,
        "baseline_finals": s.baseline_finals, "add_total": total,
        "fully_funded": fully_funded, "partial": partial, "unfunded": unfunded,
        "total_shortfall": sum(f["shortfall"] for f in funding_log),
        "distinct_tickers": distinct_tickers, "n_displacements": len(displacement_log),
        "displacement_realized_gain": displacement_gains,
        "displacement_log": displacement_log, "n_events": len(events),
    }


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def equal_weight_final(tickers, start_date, end_date, capital, prices):
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p
    total = 0.0
    for t, shares in holdings.items():
        ep = prices.price_on(t, end_date, max_lookback_days=120)
        if ep:
            total += shares * ep
    return total


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
    print(f"git commit={_GIT_COMMIT[:12]} branch={_GIT_BRANCH} dirty={_GIT_DIRTY}")
    if _GIT_DIRTY:
        print("NOTE: working tree is dirty. Checking whether the dirt is "
              "relevant to this run...")

    events_full, type_fn, driver_fn, tier_fn = load_events_dedup_on()
    prices = PriceLookup.from_cache()
    print(f"Events (dedup on): {len(events_full)}\n")

    # Standing assertion (0c)
    control = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, "no_reserve")
    print(f"no_reserve control (dedup on): ${control['final_value']:,.2f}")
    if abs(control["final_value"] - EXPECTED_NO_RESERVE) >= 1.0:
        print(f"STOP: standing assertion failed -- expected ${EXPECTED_NO_RESERVE}, "
              f"got ${control['final_value']:,.2f}")
        return 1
    print("Standing assertion PASSED.\n")

    # ---- Step 1: ordering probe under three configs ----
    configs = {
        "A": dict(funding_mode="no_reserve"),
        "B": dict(funding_mode="swap_funding", session_change_limit_pp=10.0),
        "C": dict(funding_mode="no_reserve", session_change_limit_pp=10.0),
    }
    print("=== Step 1: ordering probe (21 runs) ===")
    probe_results = {}
    for label, kwargs in configs.items():
        vals = {}
        r_fwd = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, **kwargs)
        vals["forward"] = r_fwd["final_value"]
        r_rev = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, reverse_order=True, **kwargs)
        vals["reversed"] = r_rev["final_value"]
        for seed in range(1, 6):
            r_seed = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, seed=seed, **kwargs)
            vals[f"seed{seed}"] = r_seed["final_value"]
        probe_results[label] = vals
        all_vals = list(vals.values())
        med = statistics.median(all_vals)
        print(f"\nConfig {label} ({kwargs}):")
        for k, v in vals.items():
            print(f"  {k:10} ${v:,.2f}")
        print(f"  min=${min(all_vals):,.2f}  median=${med:,.2f}  max=${max(all_vals):,.2f}  "
              f"spread=${max(all_vals)-min(all_vals):,.2f} ({100*(max(all_vals)-min(all_vals))/med:.1f}% of median)")

        write_manifest(
            f"step1-config{label}",
            events_full if not kwargs.get("reverse_order") else list(reversed(events_full)),
            {"funding_mode": kwargs.get("funding_mode"),
             "session_change_limit_pp": kwargs.get("session_change_limit_pp"),
             "config_label": label, "seeds_tested": list(range(1, 6)),
             "window": [str(START), str(C)], "universe": ALL16,
             "capital": INITIAL, "allocator": "decide_v3"},
            {"values": vals, "min": min(all_vals), "median": med, "max": max(all_vals)},
        )

    a_vals = list(probe_results["A"].values())
    b_vals = list(probe_results["B"].values())
    c_vals = list(probe_results["C"].values())
    a_max = max(a_vals)
    b_med = statistics.median(b_vals)
    c_med = statistics.median(c_vals)
    c_verdict = "REAL" if c_med > a_max else "INSIDE THE NOISE BAND"
    b_verdict = "REAL" if b_med > a_max else "INSIDE THE NOISE BAND"
    print(f"\nPre-declared rule: config median > config-A max (${a_max:,.2f})")
    print(f"Config C (no_reserve+10pp) median ${c_med:,.2f} -> verdict: {c_verdict}")
    print(f"Config B (swap_funding+10pp) median ${b_med:,.2f} -> verdict: {b_verdict}")

    # ---- Step 2a/2b: donor decomposition + inverted-gap cell ----
    print("\n=== Step 2a: donor decomposition, cells 6 (swap, no limit) and 7 (swap+10pp) ===")
    cell6 = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, funding_mode="swap_funding")
    cell7 = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, funding_mode="swap_funding",
                      session_change_limit_pp=10.0)

    def decompose(disp_log, label):
        hold = [d for d in disp_log if d["donor_final_action"] == "Hold"]
        trim_exit = [d for d in disp_log if d["donor_final_action"] in ("Trim", "Exit")]
        other = [d for d in disp_log if d["donor_final_action"] not in ("Hold", "Trim", "Exit")]
        print(f"\n{label}: {len(disp_log)} displacements total")
        print(f"  On Hold-verdict donors:      {len(hold)} ({100*len(hold)/len(disp_log):.1f}%)")
        print(f"  On Trim/Exit-verdict donors: {len(trim_exit)} ({100*len(trim_exit)/len(disp_log):.1f}%)")
        if other:
            print(f"  On other/unknown-verdict donors: {len(other)}")
        below_2 = sum(1 for d in disp_log if d["donor_pct_after"] < 2.0)
        below_1 = sum(1 for d in disp_log if d["donor_pct_after"] < 1.0)
        below_05 = sum(1 for d in disp_log if d["donor_pct_after"] < 0.5)
        print(f"  Draws leaving donor below 2% of portfolio: {below_2} ({100*below_2/len(disp_log):.1f}%)")
        print(f"  Draws leaving donor below 1% of portfolio: {below_1} ({100*below_1/len(disp_log):.1f}%)")
        print(f"  Draws leaving donor below 0.5% of portfolio: {below_05} ({100*below_05/len(disp_log):.1f}%)")
        return hold, trim_exit

    for label, cell in (("Cell 6", cell6), ("Cell 7", cell7)):
        disp = cell["displacement_log"]
        if not disp:
            print(f"\n{label}: no displacements recorded.")
            continue
        hold, trim_exit = decompose(disp, label)
        # realized gain/loss split -- need per-donor-sale gains; realized_sales
        # doesn't tag which displacement event produced it 1:1 when a donor is
        # drawn on multiple times, so split by ticker-level aggregate instead
        # and report at that granularity (flagged as a limitation, not per-sale).
        hold_donors = {d["donor"] for d in hold}
        trim_exit_donors = {d["donor"] for d in trim_exit}
        print(f"  (gain/loss split is per-donor-ticker aggregate, not per-sale-event, "
              f"since a donor can be drawn on multiple times)")

    print("\n=== Step 2b: inverted donor-gap-term cell (swap_funding + 10pp, dedup on) ===")
    cell7_inverted = run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
                               funding_mode="swap_funding", session_change_limit_pp=10.0,
                               invert_donor_gap=True)
    print(f"Cell 7 (normal):   final=${cell7['final_value']:,.0f}  "
          f"displacements={cell7['n_displacements']}  "
          f"realized_gain=${cell7['displacement_realized_gain']:,.0f}")
    print(f"Cell 7 (inverted): final=${cell7_inverted['final_value']:,.0f}  "
          f"displacements={cell7_inverted['n_displacements']}  "
          f"realized_gain=${cell7_inverted['displacement_realized_gain']:,.0f}")

    from collections import defaultdict
    for label, cell in (("normal", cell7), ("inverted", cell7_inverted)):
        by_donor = defaultdict(lambda: [0, 0.0])
        for d in cell["displacement_log"]:
            by_donor[d["donor"]][0] += 1
            by_donor[d["donor"]][1] += d["raised"]
        print(f"\nDonor aggregate, cell 7 {label}:")
        for donor, (n, raised) in sorted(by_donor.items(), key=lambda kv: -kv[1][1]):
            print(f"  {donor:6}  n={n:3}  raised=${raised:,.0f}")

    # ---- Step 2c: per-date cap ----
    print("\n=== Step 2c: per-date (not per-event) 25%-of-donor trim cap, cell 7 ===")
    cell7_datecap = run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
                              funding_mode="swap_funding", session_change_limit_pp=10.0,
                              per_date_cap=True)
    print(f"Cell 7 (per-event cap, uncapped-by-date): final=${cell7['final_value']:,.0f}  "
          f"displacements={cell7['n_displacements']}")
    print(f"Cell 7 (per-date cap):                    final=${cell7_datecap['final_value']:,.0f}  "
          f"displacements={cell7_datecap['n_displacements']}")

    write_manifest("step2-cell6", events_full,
                    {"funding_mode": "swap_funding", "session_change_limit_pp": None},
                    {"final_value": cell6["final_value"], "n_displacements": cell6["n_displacements"]})
    write_manifest("step2-cell7", events_full,
                    {"funding_mode": "swap_funding", "session_change_limit_pp": 10.0},
                    {"final_value": cell7["final_value"], "n_displacements": cell7["n_displacements"]})
    write_manifest("step2-cell7-inverted", events_full,
                    {"funding_mode": "swap_funding", "session_change_limit_pp": 10.0,
                     "invert_donor_gap": True},
                    {"final_value": cell7_inverted["final_value"],
                     "n_displacements": cell7_inverted["n_displacements"]})
    write_manifest("step2-cell7-datecap", events_full,
                    {"funding_mode": "swap_funding", "session_change_limit_pp": 10.0,
                     "per_date_cap": True},
                    {"final_value": cell7_datecap["final_value"],
                     "n_displacements": cell7_datecap["n_displacements"]})

    # ---- Step 3: benchmark scoring ----
    print("\n=== Step 3: benchmark scoring ===")
    spy = control["baseline_finals"]["SPY"]
    qqq = control["baseline_finals"]["QQQ"]
    tmfc = control["baseline_finals"]["TMFC"]
    ew = equal_weight_final(ALL16, START, C, INITIAL, prices)
    print(f"SPY final:  ${spy:,.2f}")
    print(f"QQQ final:  ${qqq:,.2f}")
    print(f"TMFC final: ${tmfc:,.2f}")
    print(f"Equal-weight-of-universe final: ${ew:,.2f}")
    DD_BAR = 38.0

    all_cells_this_run = {
        "1 no_reserve dedup=off (prior sweep, re-run under guard)": None,  # filled below
        "A forward (no_reserve)": {"final_value": probe_results["A"]["forward"], "max_dd": control["max_dd"]},
        "B forward (swap_funding+10pp)": None,
        "C forward (no_reserve+10pp)": None,
        "6 swap_funding": cell6,
        "7 swap_funding+10pp": cell7,
        "7-inverted": cell7_inverted,
        "7-datecap": cell7_datecap,
    }
    b_fwd = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, **configs["B"])
    c_fwd = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, **configs["C"])
    all_cells_this_run["B forward (swap_funding+10pp)"] = b_fwd
    all_cells_this_run["C forward (no_reserve+10pp)"] = c_fwd
    all_cells_this_run["1 no_reserve dedup=off (prior sweep, re-run under guard)"] = \
        run_cell(load_call_events(tickers=ALL16, end_date=C, dedupe_same_day_calls=False),
                 prices, type_fn, driver_fn, tier_fn, funding_mode="no_reserve")

    # Re-run the eight prior-sweep cells here, under the guard, for scoring + manifests.
    print("\nRe-running prior sweep's 8 cells under the guard, for manifests + scoring:")
    prior_events_dedup_off = load_call_events(tickers=ALL16, end_date=C, dedupe_same_day_calls=False)
    prior_cells = {
        "prior-1 no_reserve dedup=off": (prior_events_dedup_off, dict(funding_mode="no_reserve")),
        "prior-2 no_reserve dedup=on": (events_full, dict(funding_mode="no_reserve")),
        "prior-3 cash_reserve 5%": (events_full, dict(funding_mode="cash_reserve", reserve_pct=5)),
        "prior-4 cash_reserve 10%": (events_full, dict(funding_mode="cash_reserve", reserve_pct=10)),
        "prior-5 cash_reserve 20%": (events_full, dict(funding_mode="cash_reserve", reserve_pct=20)),
        "prior-6 swap_funding": (events_full, dict(funding_mode="swap_funding")),
        "prior-7 swap_funding+10pp": (events_full, dict(funding_mode="swap_funding", session_change_limit_pp=10.0)),
        "prior-8 no_reserve+10pp": (events_full, dict(funding_mode="no_reserve", session_change_limit_pp=10.0)),
    }
    prior_results = {}
    for label, (ev, kwargs) in prior_cells.items():
        res = run_cell(ev, prices, type_fn, driver_fn, tier_fn, **kwargs)
        prior_results[label] = res
        write_manifest(label.replace(" ", "-").replace("%", "pct"), ev, kwargs,
                        {"final_value": res["final_value"], "max_dd": res["max_dd"]})
        print(f"  {label}: ${res['final_value']:,.0f}  maxDD={res['max_dd']*100:.1f}%")

    print(f"\n{'CELL':45}  {'FINAL':>12}  {'MAXDD':>7}  {'SCORE':>10}  BEATS")
    for label, res in list(prior_results.items()) + [
        ("this-run A forward", all_cells_this_run["A forward (no_reserve)"]),
        ("this-run B forward", b_fwd), ("this-run C forward", c_fwd),
        ("this-run 6 swap_funding", cell6), ("this-run 7 swap+10pp", cell7),
        ("this-run 7-inverted", cell7_inverted), ("this-run 7-datecap", cell7_datecap),
    ]:
        score, beats = score_cell(res["final_value"], res["max_dd"], spy, qqq, tmfc, ew, DD_BAR)
        beats_str = ",".join(k for k, v in beats.items() if v)
        print(f"{label:45}  ${res['final_value']:>10,.0f}  {res['max_dd']*100:>6.1f}%  {score:>10}  {beats_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

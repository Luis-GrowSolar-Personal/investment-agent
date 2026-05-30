#!/usr/bin/env python3
"""
analyst_direct_scorer.py — Promotion Gate §3.1: Analyst-direct metric.

For a given eval cache version, computes the benchmark-relative 2Q hit-rate
and lift over an always-bullish baseline, broken out by call type.

This is the PRIMARY gate metric for analyst-layer changes (new prompt, new model).
See docs/architecture/PROMOTION_GATE.md §3.1 for full methodology.

Scoring logic:
  - Each eval maps to a direction: bullish (Add), bearish (Trim/Exit), neutral (Hold)
  - Ground truth: benchmark-relative 2Q (~182 day) forward return, ±5% dead-band
    bullish  → stock outperformed benchmark by >+5%
    bearish  → stock underperformed benchmark by >-5%
    neutral  → within ±5% (the dead-band)
  - Hit: predicted direction matches ground truth direction
  - Always-bullish baseline: predicts "bullish" on every call
  - Lift: our hit-rate minus always-bullish hit-rate (overall and per call-type)

Benchmark: SPY for all tickers (sector ETFs not yet in price cache; revisit once
TAN/SOXX/etc. are added for solar/semiconductor tickers).

Usage:
    cd analysis
    python3 analyst_direct_scorer.py --eval-dir data/evals/v6_sonnet-4-20250514
    python3 analyst_direct_scorer.py --eval-dir data/evals/v6_sonnet-4-20250514 --csv out.csv
    python3 analyst_direct_scorer.py --eval-dir data/evals/v6_sonnet-4-20250514 \\
        --tickers ENPH TTD AMPX ENVX EOSE QS SPWR   # original 7-ticker set
    python3 analyst_direct_scorer.py \\
        --eval-dir data/evals/v6_sonnet-4-20250514 \\
        --holdout-start 2025-01-01   # score only calls on/after this date

Pre-reqs:
    - Versioned eval cache exists at --eval-dir (*.txt files, one per call)
    - analysis/data/price_cache.json has prices for all tickers + SPY
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PRICE_CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"

FORWARD_DAYS = 182       # ~2 quarters
DEAD_BAND = 0.05         # ±5% benchmark-relative dead-band
BENCHMARK = "SPY"        # default benchmark; extend with per-ticker ETF map later


# ---------------------------------------------------------------------------
# Price cache
# ---------------------------------------------------------------------------

class PriceCache:
    def __init__(self, path: Path):
        with path.open() as f:
            self._data: dict[str, dict[str, float]] = json.load(f)

    def price_on_or_after(self, ticker: str, target: date) -> tuple[Optional[float], Optional[date]]:
        """Return (price, actual_date) for the first trading day on or after target."""
        days = self._data.get(ticker, {})
        if not days:
            return None, None
        for i in range(30):
            key = (target + timedelta(days=i)).isoformat()
            if key in days:
                return days[key], date.fromisoformat(key)
        return None, None


# ---------------------------------------------------------------------------
# Eval file parsing
# ---------------------------------------------------------------------------

_STRUCTURED_RE = re.compile(
    r"---STRUCTURED---\s*(\{[\s\S]*?\})\s*---END STRUCTURED---"
)

def parse_structured(text: str) -> dict:
    m = _STRUCTURED_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def direction_from_score(score: dict) -> Optional[str]:
    """Map structured score to bullish/bearish/neutral."""
    rec = (score.get("recommendation") or "").strip().lower()
    health = (score.get("thesisHealth") or "").strip().lower()

    if rec in ("add",):
        return "bullish"
    if rec in ("trim", "exit"):
        return "bearish"
    if rec == "hold":
        return "neutral"

    # Fallback: use thesis health if recommendation is missing
    if health in ("strengthening",):
        return "bullish"
    if health in ("weakening", "broken"):
        return "bearish"
    if health in ("intact",):
        return "neutral"

    return None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CallRecord:
    ticker: str
    call_date: date
    predicted: str              # bullish / bearish / neutral
    ground_truth: Optional[str] # bullish / bearish / neutral / None (not yet scoreable)
    benchmark_rel_return: Optional[float]  # stock_return - benchmark_return (raw fraction)
    hit: Optional[bool]         # True/False/None (None = not yet scoreable)
    always_bullish_hit: Optional[bool]


# ---------------------------------------------------------------------------
# Core scorer
# ---------------------------------------------------------------------------

def score_eval_dir(
    eval_dir: Path,
    prices: PriceCache,
    tickers: Optional[list[str]] = None,
    holdout_start: Optional[date] = None,
) -> list[CallRecord]:
    """
    Score all eval files in eval_dir. Returns one CallRecord per scoreable call.
    A call is scoreable if price data exists at both the call date and 2Q forward.
    """
    records: list[CallRecord] = []
    files = sorted(eval_dir.glob("*.txt"))

    for f in files:
        # Filename format: {TICKER}_{YYYY-MM-DD}.txt
        stem = f.stem
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            continue
        ticker, date_str = parts
        try:
            call_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        if tickers and ticker not in tickers:
            continue
        if holdout_start and call_date < holdout_start:
            continue

        text = f.read_text(encoding="utf-8", errors="replace")
        score = parse_structured(text)
        if not score:
            continue

        predicted = direction_from_score(score)
        if predicted is None:
            continue

        # Fetch prices
        p0, _ = prices.price_on_or_after(ticker, call_date)
        b0, _ = prices.price_on_or_after(BENCHMARK, call_date)
        fwd_target = call_date + timedelta(days=FORWARD_DAYS)
        p1, p1_date = prices.price_on_or_after(ticker, fwd_target)
        b1, _       = prices.price_on_or_after(BENCHMARK, fwd_target)

        if not all([p0, b0, p1, b1]):
            # Not yet scoreable (too recent or missing data)
            records.append(CallRecord(
                ticker=ticker, call_date=call_date,
                predicted=predicted, ground_truth=None,
                benchmark_rel_return=None, hit=None,
                always_bullish_hit=None,
            ))
            continue

        stock_ret = (p1 - p0) / p0
        bench_ret = (b1 - b0) / b0
        rel = stock_ret - bench_ret

        if rel > DEAD_BAND:
            ground_truth = "bullish"
        elif rel < -DEAD_BAND:
            ground_truth = "bearish"
        else:
            ground_truth = "neutral"

        hit = (predicted == ground_truth)
        always_bullish_hit = (ground_truth == "bullish")

        records.append(CallRecord(
            ticker=ticker, call_date=call_date,
            predicted=predicted, ground_truth=ground_truth,
            benchmark_rel_return=round(rel, 4),
            hit=hit, always_bullish_hit=always_bullish_hit,
        ))

    return records


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(records: list[CallRecord], eval_dir: Path) -> None:
    scoreable = [r for r in records if r.hit is not None]
    not_yet    = [r for r in records if r.hit is None]

    print("=" * 68)
    print(f"ANALYST-DIRECT SCORER  —  Promotion Gate §3.1")
    print(f"Eval dir: {eval_dir}")
    print(f"Benchmark: {BENCHMARK}  |  Horizon: {FORWARD_DAYS}d (~2Q)")
    print(f"Dead-band: ±{DEAD_BAND*100:.0f}%  (rel. to benchmark)")
    print("=" * 68)
    print(f"Total eval files processed:  {len(records)}")
    print(f"Scoreable (2Q data exists):  {len(scoreable)}")
    print(f"Not yet scoreable (too new): {len(not_yet)}")

    if not scoreable:
        print("\nNo scoreable calls — nothing to report.")
        return

    # --- Overall ---
    our_hits   = sum(1 for r in scoreable if r.hit)
    base_hits  = sum(1 for r in scoreable if r.always_bullish_hit)
    our_rate   = our_hits / len(scoreable)
    base_rate  = base_hits / len(scoreable)
    lift       = our_rate - base_rate

    print(f"\n{'─'*68}")
    print(f"OVERALL  (n={len(scoreable)})")
    print(f"  Our hit-rate:           {our_rate*100:5.1f}%  ({our_hits}/{len(scoreable)})")
    print(f"  Always-bullish baseline:{base_rate*100:5.1f}%  ({base_hits}/{len(scoreable)})")
    print(f"  Lift:                  {lift*100:+5.1f}pp")

    # --- By call type ---
    print(f"\n{'─'*68}")
    print("BY CALL TYPE")
    for ctype in ("bullish", "neutral", "bearish"):
        subset = [r for r in scoreable if r.predicted == ctype]
        if not subset:
            print(f"  {ctype:<8}: no calls")
            continue
        n_hit  = sum(1 for r in subset if r.hit)
        n_base = sum(1 for r in subset if r.always_bullish_hit)
        rate   = n_hit / len(subset)
        blift  = rate - (n_base / len(subset))
        print(f"  {ctype:<8}: {rate*100:5.1f}% hit  ({n_hit}/{len(subset)})  "
              f"lift vs baseline {blift*100:+.1f}pp")

    # --- Ground truth distribution ---
    gt_counts = {"bullish": 0, "neutral": 0, "bearish": 0}
    for r in scoreable:
        gt_counts[r.ground_truth] += 1
    print(f"\n{'─'*68}")
    print("GROUND TRUTH DISTRIBUTION (benchmark-relative 2Q outcomes)")
    for k, v in gt_counts.items():
        print(f"  {k:<8}: {v:>3}  ({v/len(scoreable)*100:.1f}%)")

    # --- Prediction distribution ---
    pred_counts = {"bullish": 0, "neutral": 0, "bearish": 0}
    for r in scoreable:
        pred_counts[r.predicted] += 1
    print(f"\n{'─'*68}")
    print("OUR PREDICTION DISTRIBUTION")
    for k, v in pred_counts.items():
        print(f"  {k:<8}: {v:>3}  ({v/len(scoreable)*100:.1f}%)")

    # --- Confusion-style breakdown ---
    print(f"\n{'─'*68}")
    print("CONFUSION (predicted → actual)  * = hit")
    header = f"  {'predicted':<10} {'actual':>10} {'count':>7}"
    print(header)
    combos: dict[tuple, int] = {}
    for r in scoreable:
        key = (r.predicted, r.ground_truth)
        combos[key] = combos.get(key, 0) + 1
    for (pred, actual), count in sorted(combos.items()):
        mark = "*" if pred == actual else " "
        print(f"  {mark}{pred:<9} → {actual:<9} {count:>5}")

    # --- Per-ticker hit rate ---
    print(f"\n{'─'*68}")
    print("PER-TICKER HIT RATE")
    ticker_groups: dict[str, list[CallRecord]] = {}
    for r in scoreable:
        ticker_groups.setdefault(r.ticker, []).append(r)
    for ticker, rows in sorted(ticker_groups.items()):
        n = len(rows)
        h = sum(1 for r in rows if r.hit)
        print(f"  {ticker:<6}: {h}/{n}  ({h/n*100:.0f}%)")

    print("=" * 68)


def write_csv(records: list[CallRecord], path: Path) -> None:
    scoreable = [r for r in records if r.hit is not None]
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ticker", "call_date", "predicted", "ground_truth",
            "benchmark_rel_return_pct", "hit", "always_bullish_hit",
        ])
        for r in scoreable:
            writer.writerow([
                r.ticker,
                r.call_date.isoformat(),
                r.predicted,
                r.ground_truth,
                f"{r.benchmark_rel_return*100:.2f}" if r.benchmark_rel_return is not None else "",
                "1" if r.hit else "0",
                "1" if r.always_bullish_hit else "0",
            ])
    print(f"CSV written → {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--eval-dir", type=Path, required=True,
        help="Versioned eval cache directory (e.g. data/evals/v6_sonnet-4-20250514)"
    )
    ap.add_argument(
        "--tickers", nargs="*", default=None,
        help="Restrict to these tickers (default: all in eval-dir)"
    )
    ap.add_argument(
        "--holdout-start", type=parse_date, default=None,
        help="Score only calls on/after this date (YYYY-MM-DD) — for holdout mode"
    )
    ap.add_argument(
        "--csv", type=Path, default=None,
        help="Optional: write per-call results to this CSV file"
    )
    args = ap.parse_args()

    eval_dir = args.eval_dir
    if not eval_dir.is_absolute():
        eval_dir = SCRIPT_DIR / eval_dir
    if not eval_dir.exists():
        ap.error(f"eval-dir not found: {eval_dir}")

    if not PRICE_CACHE_PATH.exists():
        ap.error(f"Price cache not found: {PRICE_CACHE_PATH}")

    prices = PriceCache(PRICE_CACHE_PATH)
    records = score_eval_dir(
        eval_dir=eval_dir,
        prices=prices,
        tickers=args.tickers,
        holdout_start=args.holdout_start,
    )

    print_report(records, eval_dir)

    if args.csv:
        write_csv(records, args.csv)


if __name__ == "__main__":
    main()

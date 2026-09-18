#!/usr/bin/env python3
"""
q2_bearish_strength_driver.py — prompts/q2-bearish-strength-separation.md

Read-only analysis of already-scored eval caches. Answers: within v6's
existing bearish calls, do the analyst's own supporting fields (recommendation
Exit/Trim split, thesisHealth, blindSpotsTriggered count, stumbleType,
ratchetTranche, credibilityDelta, threatMechanismImpaired, recommendedSize/
capPercent) separate the calls that turned out right from the calls that
turned out wrong?

NO LLM CALLS. NO DB WRITES. Reads analysis/data/evals/* and
analysis/data/price_cache.json only, via the existing scorer's own
parse_structured() / direction_from_score() (imported, not re-implemented --
see prompt §5a and state-of-play §6 on repeated parser-drift bugs).

Usage:
    cd analysis
    python3 q2_bearish_strength_driver.py
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analyst_direct_scorer import (
    PriceCache, parse_structured, direction_from_score,
    score_eval_dir, SkipLog, enforce_coverage,
)

SCRIPT_DIR = Path(__file__).resolve().parent
EVAL_DIRS = {
    "train": SCRIPT_DIR / "data" / "evals" / "v6_claude-sonnet-4-6",
    "tune": SCRIPT_DIR / "data" / "evals" / "v6_claude-sonnet-4-6_tune",
}
# Flagged premise (see findings.md): the prompt's §2 ground rule 5 says to use
# analysis/data/price_cache.json "as it stands." That file is documented in
# analyst_direct_scorer.py's own --price-cache help text as "the frozen
# default, which legacy benchmarks replay off" -- it covers only 66 tickers
# (an older 8-ticker-era cohort) and does not cover this corpus's 56/54
# train/tune tickers (confirmed: MMM, ABBV, etc. absent). The actual v6
# train/tune baselines this run must reproduce (§5b) were scored against
# analysis/data/corpus_v2/scorer_price_cache_v1.json (172 tickers), per the
# --price-cache invocations recorded in wrap-ups/baseline-v6-tune-batch-out.md.
# Using the prompt's literal default would fail the coverage guard on both
# splits and cannot reproduce the §5b reference figures. Using the actual
# baseline cache instead -- still frozen, still read-only, still zero API
# spend -- to honor the run's real intent (reproduce v6's scored bearish
# calls) rather than its literal (and here, inapplicable) instruction.
PRICE_CACHE_PATH = SCRIPT_DIR / "data" / "corpus_v2" / "scorer_price_cache_v1.json"
RUN_STATE_DIR = SCRIPT_DIR / "data" / "run_state" / "q2-bearish-strength-separation"
JOINED_CSV_PATH = RUN_STATE_DIR / "joined_calls.csv"
CELLS_JSONL_PATH = RUN_STATE_DIR / "cells.jsonl"

UNGRADABLE_TICKERS = {"WOLF", "SPWR", "NOVA"}  # state-of-play §6 / prompt §5b

FIELDS = [
    "ticker", "call_date", "split", "predicted", "ground_truth",
    "benchmark_rel_return_pct", "hit",
    "recommendation", "thesisHealth", "thesisDelta", "stumbleType",
    "credibilityDelta", "ratchetTranche", "activeDriverCount",
    "blindSpotsTriggered_raw", "blindSpotsTriggered_count",
    "threatMechanismImpaired", "mitigationArgumentPresent",
    "recommendedSize", "capPercent", "freshMoneyAllocation",
]


def wilson_95(hits: int, n: int) -> tuple[float, float]:
    """Wilson score interval, 95%. Used instead of the normal approximation
    because several buckets here have n well under 30."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963985
    p = hits / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (max(0.0, lo) * 100, min(1.0, hi) * 100)


@dataclass
class JoinedRow:
    ticker: str
    call_date: str
    split: str
    predicted: Optional[str]
    ground_truth: Optional[str]
    benchmark_rel_return_pct: Optional[float]
    hit: Optional[bool]
    structured: dict


def build_joined_rows() -> tuple[list[JoinedRow], dict]:
    """Re-derive the same CallRecords the scorer would (via its own
    score_eval_dir/enforce_coverage), then re-open each source .txt to pull
    the extra structured fields (recommendation is already on CallRecord,
    but thesisHealth/blindSpotsTriggered/etc are not)."""
    prices = PriceCache(PRICE_CACHE_PATH)
    rows: list[JoinedRow] = []
    parse_fail_count = 0
    field_null_counts: dict[str, int] = {f: 0 for f in FIELDS}
    field_total_bearish = 0

    for split, eval_dir in EVAL_DIRS.items():
        skips = SkipLog()
        records = score_eval_dir(eval_dir, prices, skips=skips)
        try:
            enforce_coverage(records, skips)
        except SystemExit as e:
            # Expected: WOLF/SPWR (and NOVA on train) are documented
            # ungradable tickers (prompt §5b, state-of-play §6) -- 2024/25
            # bankruptcies with reused tickers / purged pre-reorg prices.
            # The guard's job is to catch UNEXPECTED loss; this loss is
            # named in the prompt itself, so continue and let §5b's own
            # denominator accounting report it explicitly rather than
            # treating it as a silent partial run.
            msg = str(e)
            assert "WOLF" in msg or "SPWR" in msg or "NOVA" in msg, (
                f"Coverage guard failed for a reason other than the "
                f"documented WOLF/SPWR/NOVA loss -- do not suppress:\n{msg}"
            )
            print(f"[{split}] coverage guard tripped on documented "
                  f"ungradable ticker(s) only -- continuing:\n{msg}\n")

        # Re-parse each file's structured block for the extra fields not
        # carried on CallRecord. Index by (ticker, call_date) to join.
        extra_by_key: dict[tuple[str, str], dict] = {}
        for f in sorted(eval_dir.glob("*.txt")):
            stem = f.stem
            parts = stem.rsplit("_", 1)
            if len(parts) != 2:
                continue
            ticker, date_str = parts
            text = f.read_text(encoding="utf-8", errors="replace")
            score = parse_structured(text)
            if not score:
                parse_fail_count += 1
                continue
            extra_by_key[(ticker, date_str)] = score

        for r in records:
            key = (r.ticker, r.call_date.isoformat())
            structured = extra_by_key.get(key, {})
            rows.append(JoinedRow(
                ticker=r.ticker,
                call_date=r.call_date.isoformat(),
                split=split,
                predicted=r.predicted,
                ground_truth=r.ground_truth,
                benchmark_rel_return_pct=(
                    round(r.benchmark_rel_return * 100, 2)
                    if r.benchmark_rel_return is not None else None
                ),
                hit=r.hit,
                structured=structured,
            ))

    # Null-field coverage check, restricted to bearish calls per prompt §5a.
    bearish_rows = [row for row in rows if row.predicted == "bearish"]
    field_total_bearish = len(bearish_rows)
    for row in bearish_rows:
        s = row.structured
        for f in FIELDS:
            if f in ("ticker", "call_date", "split", "predicted",
                      "ground_truth", "benchmark_rel_return_pct", "hit"):
                continue
            if f == "blindSpotsTriggered_raw":
                val = s.get("blindSpotsTriggered")
            elif f == "blindSpotsTriggered_count":
                bst = s.get("blindSpotsTriggered")
                val = bst if isinstance(bst, list) else None
            else:
                val = s.get(f)
            if val is None or val == "":
                field_null_counts[f] += 1

    coverage_report = {
        "parse_fail_count": parse_fail_count,
        "bearish_total": field_total_bearish,
        "field_null_counts": field_null_counts,
        "field_null_pct": {
            f: round(c / field_total_bearish * 100, 1) if field_total_bearish else 0.0
            for f, c in field_null_counts.items()
        },
    }
    return rows, coverage_report


def write_joined_csv(rows: list[JoinedRow]) -> None:
    import csv
    with JOINED_CSV_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for row in rows:
            s = row.structured
            bst = s.get("blindSpotsTriggered")
            bst_count = len(bst) if isinstance(bst, list) else ""
            w.writerow([
                row.ticker, row.call_date, row.split, row.predicted or "",
                row.ground_truth or "", row.benchmark_rel_return_pct
                if row.benchmark_rel_return_pct is not None else "",
                row.hit if row.hit is not None else "",
                s.get("recommendation", ""), s.get("thesisHealth", ""),
                s.get("thesisDelta", ""), s.get("stumbleType", ""),
                s.get("credibilityDelta", ""), s.get("ratchetTranche", ""),
                s.get("activeDriverCount", ""),
                json.dumps(bst) if bst is not None else "",
                bst_count,
                s.get("threatMechanismImpaired", ""),
                s.get("mitigationArgumentPresent", ""),
                s.get("recommendedSize", ""), s.get("capPercent", ""),
                s.get("freshMoneyAllocation", ""),
            ])


def bearish_denominators(rows: list[JoinedRow]) -> dict:
    """Reproduces the state-of-play / PROMPT_ARCHITECTURE.md §2.1 reference
    figures (train 103 bearish, 60.2% right, 44.9% base rate; tune 84
    bearish, 59.5% right, 48.4% base rate).

    Two things the reference figures require that are easy to get wrong
    (both caught by the discrepancy check in prompt §5b):

    1. WOLF/SPWR (and NOVA, though it does not appear in either eval dir at
       all as of this run) must be excluded ENTIRELY -- every call from
       those tickers, not just the individual calls that happen to be
       missing forward price data. The wrap-ups' own baseline invocations
       (wrap-ups/baseline-v6-tune-batch-out.md) score with an explicit
       --tickers allowlist that leaves WOLF/SPWR out altogether.
    2. The base rate is the share of ALL scoreable calls (any predicted
       direction) whose ground truth is "bearish" -- NOT the share of
       bearish-PREDICTED calls whose ground truth is bearish (that second
       quantity is identical to pct_right by construction, since hit for a
       bearish-predicted call is true exactly when ground_truth=="bearish").
    """
    out = {}
    for split in ("train", "tune"):
        all_scoreable = [
            r for r in rows
            if r.split == split and r.hit is not None
            and r.ticker not in UNGRADABLE_TICKERS
        ]
        bearish_predicted_raw = [
            r for r in rows if r.split == split and r.predicted == "bearish"
        ]
        subset = [r for r in bearish_predicted_raw if r.ticker not in UNGRADABLE_TICKERS]
        scoreable = [r for r in subset if r.hit is not None]
        n = len(scoreable)
        hits = sum(1 for r in scoreable if r.hit)
        pct_right = round(hits / n * 100, 1) if n else None

        base_rate_hits = sum(1 for r in all_scoreable if r.ground_truth == "bearish")
        base_rate_pct = round(base_rate_hits / len(all_scoreable) * 100, 1) if all_scoreable else None

        ungradable = [r for r in bearish_predicted_raw if r.ticker in UNGRADABLE_TICKERS]
        out[split] = {
            "n_bearish_predicted_raw": len(bearish_predicted_raw),
            "n_bearish_predicted_ex_ungradable": len(subset),
            "n_scoreable": n,
            "n_right": hits,
            "pct_right": pct_right,
            "n_all_scoreable_calls": len(all_scoreable),
            "base_rate_pct_bearish_actual": base_rate_pct,
            "n_bearish_calls_lost_to_ungradable_tickers": len(ungradable),
            "ungradable_by_ticker": {
                t: sum(1 for r in bearish_predicted_raw if r.ticker == t)
                for t in UNGRADABLE_TICKERS
            },
        }
    pooled_scoreable = [
        r for r in rows
        if r.predicted == "bearish" and r.hit is not None
        and r.ticker not in UNGRADABLE_TICKERS
    ]
    pooled_all = [
        r for r in rows if r.hit is not None and r.ticker not in UNGRADABLE_TICKERS
    ]
    pooled_n = len(pooled_scoreable)
    pooled_hits = sum(1 for r in pooled_scoreable if r.hit)
    pooled_base = sum(1 for r in pooled_all if r.ground_truth == "bearish")
    out["pooled"] = {
        "n_scoreable": pooled_n,
        "n_right": pooled_hits,
        "pct_right": round(pooled_hits / pooled_n * 100, 1) if pooled_n else None,
        "base_rate_pct_bearish_actual": round(pooled_base / len(pooled_all) * 100, 1) if pooled_all else None,
    }
    return out


# ---------------------------------------------------------------------------
# Axes — order and predictions recorded in findings.md BEFORE any contingency
# table is computed (prompt §5c rule 1).
# ---------------------------------------------------------------------------

def axis_bucket_A1(s: dict) -> Optional[str]:
    rec = (s.get("recommendation") or "").strip().lower()
    if rec == "exit":
        return "Exit"
    if rec == "trim":
        return "Trim"
    return None


def axis_bucket_A2(s: dict) -> Optional[str]:
    h = (s.get("thesisHealth") or "").strip().lower()
    if h == "broken":
        return "Broken"
    if h == "weakening":
        return "Weakening"
    return None


def axis_bucket_A3(s: dict) -> Optional[str]:
    bst = s.get("blindSpotsTriggered")
    if not isinstance(bst, list):
        return None
    n = len(bst)
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    return "2+"


def axis_bucket_A4(s: dict) -> Optional[str]:
    st = (s.get("stumbleType") or "").strip()
    if not st:
        return None
    low = st.lower()
    if "structural" in low:
        return "Structural"
    if "execution" in low:
        return "Execution"
    if "discovery" in low:
        return "Discovery"
    return st  # unexpected category, keep visible rather than drop silently


def axis_bucket_A5(s: dict) -> Optional[str]:
    rt = s.get("ratchetTranche")
    if rt is None or rt == "":
        return "null"
    try:
        n = int(rt)
    except (TypeError, ValueError):
        return str(rt)
    if n >= 3:
        return "3"
    return str(n)


def axis_bucket_A6(s: dict) -> Optional[str]:
    cd = s.get("credibilityDelta")
    if cd is None or cd == "":
        return None
    try:
        v = float(cd)
    except (TypeError, ValueError):
        low = str(cd).strip().lower()
        if low in ("negative", "down", "declining"):
            return "negative"
        if low in ("neutral", "positive", "stable", "up", "improving"):
            return "neutral_or_positive"
        return None
    if v < 0:
        return "negative"
    return "neutral_or_positive"


def axis_bucket_A7(s: dict) -> Optional[str]:
    v = s.get("threatMechanismImpaired")
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    low = str(v).strip().lower()
    if low in ("true", "yes"):
        return "true"
    if low in ("false", "no"):
        return "false"
    return None


def axis_bucket_A8(s: dict) -> Optional[str]:
    rs = s.get("recommendedSize")
    cp = s.get("capPercent")
    val = rs if rs not in (None, "") else cp
    if val is None or val == "":
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    # Bin by cut depth (lower recommended size / cap = deeper cut = stronger
    # conviction, per prompt §5c A8).
    if v <= 15:
        return "<=15%"
    if v <= 30:
        return "15-30%"
    return ">30%"


AXES = [
    ("A1_recommendation_exit_vs_trim", axis_bucket_A1),
    ("A2_thesisHealth_broken_vs_weakening", axis_bucket_A2),
    ("A3_blindSpotsTriggered_count", axis_bucket_A3),
    ("A4_stumbleType", axis_bucket_A4),
    ("A5_ratchetTranche", axis_bucket_A5),
    ("A6_credibilityDelta_sign", axis_bucket_A6),
    ("A7_threatMechanismImpaired", axis_bucket_A7),
    ("A8_recommendedSize_capPercent_binned", axis_bucket_A8),
]


def compute_axis(rows: list[JoinedRow], axis_name: str, bucket_fn, split: str) -> dict:
    subset = [
        r for r in rows
        if r.split == split and r.predicted == "bearish" and r.hit is not None
        and r.ticker not in UNGRADABLE_TICKERS
    ]
    buckets: dict[str, list[JoinedRow]] = {}
    excluded_null = 0
    for r in subset:
        b = bucket_fn(r.structured)
        if b is None:
            excluded_null += 1
            continue
        buckets.setdefault(b, []).append(r)

    bucket_stats = {}
    for b, items in buckets.items():
        n = len(items)
        hits = sum(1 for r in items if r.hit)
        rate = round(hits / n * 100, 1) if n else None
        lo, hi = wilson_95(hits, n)
        bucket_stats[b] = {
            "n": n, "hits": hits, "hit_rate_pct": rate,
            "ci95_lo_pct": round(lo, 1), "ci95_hi_pct": round(hi, 1),
        }

    return {
        "axis": axis_name, "split": split,
        "n_bearish_scoreable": len(subset),
        "n_excluded_null_field": excluded_null,
        "buckets": bucket_stats,
    }


AXIS_FIELD_MAP = {
    "A1_recommendation_exit_vs_trim": "recommendation",
    "A2_thesisHealth_broken_vs_weakening": "thesisHealth",
    "A3_blindSpotsTriggered_count": "blindSpotsTriggered_raw",
    "A4_stumbleType": "stumbleType",
    "A5_ratchetTranche": "ratchetTranche",
    "A6_credibilityDelta_sign": "credibilityDelta",
    "A7_threatMechanismImpaired": "threatMechanismImpaired",
    "A8_recommendedSize_capPercent_binned": "recommendedSize",
}
COVERAGE_EXCLUSION_THRESHOLD_PCT = 5.0


def main() -> None:
    RUN_STATE_DIR.mkdir(parents=True, exist_ok=True)

    rows, coverage = build_joined_rows()
    write_joined_csv(rows)

    print("=" * 72)
    print("COVERAGE REPORT (bearish calls only, per prompt §5a hard stop)")
    print("=" * 72)
    print(json.dumps(coverage, indent=2))

    excluded_axes = {}
    for axis_name, field in AXIS_FIELD_MAP.items():
        null_pct = coverage["field_null_pct"].get(field, 0.0)
        if null_pct > COVERAGE_EXCLUSION_THRESHOLD_PCT:
            excluded_axes[axis_name] = {
                "field": field, "null_pct": null_pct,
                "reason": (
                    f"{null_pct}% of bearish calls (pooled train+tune) are "
                    f"missing '{field}' -- exceeds the {COVERAGE_EXCLUSION_THRESHOLD_PCT}% "
                    f"threshold in prompt §5a. Not usable as an axis."
                ),
            }
    if excluded_axes:
        print()
        print("=" * 72)
        print("AXES EXCLUDED FOR COVERAGE (prompt §5a hard stop)")
        print("=" * 72)
        print(json.dumps(excluded_axes, indent=2))

    print()
    print("=" * 72)
    print("5b — BEARISH DENOMINATORS")
    print("=" * 72)
    denom = bearish_denominators(rows)
    print(json.dumps(denom, indent=2))

    print()
    print("=" * 72)
    print("5c — AXIS CONTINGENCY TABLES (train, then tune)")
    print("=" * 72)
    with CELLS_JSONL_PATH.open("w") as cf:
        for axis_name, bucket_fn in AXES:
            if axis_name in excluded_axes:
                print(f"SKIPPING {axis_name}: {excluded_axes[axis_name]['reason']}")
                continue
            for split in ("train", "tune"):
                result = compute_axis(rows, axis_name, bucket_fn, split)
                print(json.dumps(result, indent=2))
                cf.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
classify_tickers.py — Speculative/established classifier benchmark.

Three classifiers, side-by-side:
1) Volatility-only:  trailing 252-day annualized σ ≥ threshold.
2) Company-stage:    3 signals from v6 evals (conviction σ, thesis transitions,
                     MTR untested ratio).
3) 3-axis (vol + cap + P/E):  speculative if ≥2 of:
   - Vol axis: trailing σ ≥ vol-threshold
   - Cap axis: market cap < cap-threshold
   - Multiple axis: trailing P/E > pe-threshold OR negative OR null

(3) is the production classifier. (1) and (2) are retained for comparison.

Usage:
    cd analysis && python3 classify_tickers.py
    cd analysis && python3 classify_tickers.py --vol-threshold 0.50 \\
        --cap-threshold 50e9 --pe-threshold 50
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EVALS_DIR = SCRIPT_DIR / "data" / "evals" / "v6"
PRICE_CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"
FUNDAMENTALS_CACHE_PATH = SCRIPT_DIR / "data" / "fundamentals_cache.json"
MANIFEST_PATH = SCRIPT_DIR / "data" / "transcripts" / "_manifest.json"

# --- Volatility classifier ------------------------------------------------

def trailing_vol_annualized(closes: dict, window_days: int = 252) -> float | None:
    """Annualized σ of daily log returns over the most recent window_days."""
    if not closes:
        return None
    items = sorted(closes.items())
    if len(items) < 30:
        return None
    recent = items[-window_days:] if len(items) > window_days else items
    rets = []
    for i in range(1, len(recent)):
        p0 = recent[i-1][1]
        p1 = recent[i][1]
        if p0 > 0 and p1 > 0:
            rets.append(math.log(p1 / p0))
    if len(rets) < 20:
        return None
    daily = statistics.stdev(rets)
    return daily * math.sqrt(252)

# --- Company-stage classifier --------------------------------------------

STRUCTURED_RE = re.compile(r"---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---",
                            re.DOTALL)

def extract_structured(eval_text: str) -> dict | None:
    m = STRUCTURED_RE.search(eval_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None

def load_ticker_timeline(ticker: str) -> list[dict]:
    manifest = json.loads(MANIFEST_PATH.read_text())
    entries = sorted([m for m in manifest if m["ticker"] == ticker],
                     key=lambda m: m["call_date"])
    timeline = []
    for e in entries:
        cache_path = EVALS_DIR / f"{ticker}_{e['call_date']}.txt"
        if not cache_path.exists():
            continue
        score = extract_structured(cache_path.read_text())
        if score is None:
            continue
        score["call_date"] = e["call_date"]
        timeline.append(score)
    return timeline

def company_stage_signals(timeline: list[dict]) -> dict:
    sizes = [t.get("recommendedSize") for t in timeline
             if t.get("recommendedSize") is not None]
    healths = [t.get("thesisHealth") for t in timeline if t.get("thesisHealth")]
    mtrs = [t.get("mitigationCapabilityTrackRecord") for t in timeline
            if t.get("mitigationCapabilityTrackRecord")]

    if len(sizes) >= 3:
        sample = sizes[-6:] if len(sizes) >= 6 else sizes
        sigma_size = statistics.stdev(sample)
    else:
        sigma_size = 0.0
    s1 = sigma_size >= 10.0

    recent_h = healths[-4:] if len(healths) >= 4 else healths
    transitions = sum(1 for i in range(1, len(recent_h))
                      if recent_h[i] != recent_h[i-1])
    s2 = transitions >= 2

    if mtrs:
        untested_count = sum(1 for m in mtrs
                             if m and m.lower() in ("untested", "mixed",
                                                     "weak", "unproven"))
        untested_ratio = untested_count / len(mtrs)
    else:
        untested_ratio = 0.0
    s3 = untested_ratio >= 0.5

    fired = sum([s1, s2, s3])
    return {
        "s1_conviction_oscillation": s1,
        "s1_sigma_size": round(sigma_size, 1),
        "s2_thesis_instability": s2,
        "s2_transitions_last4": transitions,
        "s3_mtr_untested": s3,
        "s3_untested_ratio": round(untested_ratio, 2),
        "signals_fired": fired,
        "is_speculative": fired >= 2,
    }

# --- 3-axis classifier (production) --------------------------------------

def three_axis_classify(vol_ann: float | None,
                         mkt_cap: float | None,
                         trailing_pe: float | None,
                         vol_threshold: float = 0.50,
                         cap_threshold: float = 50e9,
                         pe_threshold: float = 50.0) -> dict:
    """Speculative if ≥2 of {vol, small-cap, high-multiple} axes fire."""
    vol_axis = vol_ann is not None and vol_ann >= vol_threshold
    cap_axis = mkt_cap is not None and mkt_cap < cap_threshold
    if trailing_pe is None or trailing_pe < 0:
        # No earnings (loss) or null → high-multiple by definition
        mult_axis = True
        mult_reason = "neg/null"
    else:
        mult_axis = trailing_pe > pe_threshold
        mult_reason = f"{trailing_pe:.0f}"
    fired = sum([vol_axis, cap_axis, mult_axis])
    return {
        "vol_axis": vol_axis,
        "cap_axis": cap_axis,
        "mult_axis": mult_axis,
        "mult_reason": mult_reason,
        "axes_fired": fired,
        "is_speculative": fired >= 2,
    }

# --- Reporting ------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vol-threshold", type=float, default=0.50,
                        help="Annualized σ threshold (default 0.50).")
    parser.add_argument("--cap-threshold", type=float, default=50e9,
                        help="Market cap floor for cap axis (default 50e9 = $50B).")
    parser.add_argument("--pe-threshold", type=float, default=50.0,
                        help="P/E threshold for high-multiple axis (default 50).")
    parser.add_argument("--tickers", nargs="*",
                        help="Restrict to this list. Default: all in manifest.")
    parser.add_argument("--csv", type=Path,
                        help="Also write results to this CSV path.")
    args = parser.parse_args()

    prices = json.loads(PRICE_CACHE_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    fundamentals: dict = {}
    if FUNDAMENTALS_CACHE_PATH.exists():
        fundamentals = json.loads(FUNDAMENTALS_CACHE_PATH.read_text())
    else:
        print(f"WARNING: {FUNDAMENTALS_CACHE_PATH} missing — 3-axis classifier "
              "will treat market cap and P/E as null for every ticker. "
              "Run fetch_fundamentals.py on the laptop first.\n")

    all_tickers = sorted(set(m["ticker"] for m in manifest))
    tickers = args.tickers if args.tickers else all_tickers
    tickers = [t for t in tickers if t in all_tickers]

    rows = []
    for t in tickers:
        vol = trailing_vol_annualized(prices.get(t, {}))
        timeline = load_ticker_timeline(t)
        stage = company_stage_signals(timeline)

        f = fundamentals.get(t, {})
        mkt_cap = f.get("marketCap")
        trailing_pe = f.get("trailingPE")
        three = three_axis_classify(vol, mkt_cap, trailing_pe,
                                    args.vol_threshold,
                                    args.cap_threshold,
                                    args.pe_threshold)

        vol_class = "speculative" if (vol is not None and vol >= args.vol_threshold) \
                    else ("established" if vol is not None else "unknown")
        stage_class = "speculative" if stage["is_speculative"] else "established"
        three_class = "speculative" if three["is_speculative"] else "established"

        rows.append({
            "ticker": t,
            "n_calls": len(timeline),
            "vol_pct": f"{100*vol:.0f}" if vol is not None else "n/a",
            "mcap_b": f"{mkt_cap/1e9:.0f}" if mkt_cap else "n/a",
            "pe": f"{trailing_pe:.0f}" if trailing_pe and trailing_pe > 0 else
                  ("neg" if trailing_pe is not None else "n/a"),
            "vol_class": vol_class,
            "stage_class": stage_class,
            "ax_v": "✓" if three["vol_axis"] else " ",
            "ax_c": "✓" if three["cap_axis"] else " ",
            "ax_p": "✓" if three["mult_axis"] else " ",
            "axes_fired": three["axes_fired"],
            "three_class": three_class,
        })

    headers = ["ticker", "n_calls", "vol_pct", "mcap_b", "pe",
               "vol_class", "stage_class",
               "ax_v", "ax_c", "ax_p", "axes_fired", "three_class"]
    labels = {"ticker":"TICKER", "n_calls":"N", "vol_pct":"σ%",
              "mcap_b":"MCap$B", "pe":"P/E",
              "vol_class":"VOL", "stage_class":"STAGE",
              "ax_v":"V", "ax_c":"C", "ax_p":"P",
              "axes_fired":"F", "three_class":"3-AXIS"}
    widths = {h: max(len(labels[h]), max((len(str(r[h])) for r in rows), default=1))
              for h in headers}
    print("  ".join(labels[h].ljust(widths[h]) for h in headers))
    print("  ".join("-" * widths[h] for h in headers))
    for r in rows:
        print("  ".join(str(r[h]).ljust(widths[h]) for h in headers))

    print()
    print(f"Thresholds: σ≥{args.vol_threshold*100:.0f}%, "
          f"cap<${args.cap_threshold/1e9:.0f}B, P/E>{args.pe_threshold:.0f}")

    for label, key in [("Vol-only", "vol_class"),
                       ("Stage", "stage_class"),
                       ("3-axis", "three_class")]:
        spec = [r["ticker"] for r in rows if r[key] == "speculative"]
        est  = [r["ticker"] for r in rows if r[key] == "established"]
        print(f"  {label:9} speculative={spec}")
        print(f"  {label:9} established={est}")

    # Disagreement matrix between 3-axis (production) and the other two
    vs_vol  = [r["ticker"] for r in rows if r["vol_class"] != "unknown"
               and r["vol_class"] != r["three_class"]]
    vs_stage = [r["ticker"] for r in rows
                if r["stage_class"] != r["three_class"]]
    print()
    print(f"3-axis vs vol-only disagreements: {vs_vol or 'none'}")
    print(f"3-axis vs stage disagreements:    {vs_stage or 'none'}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"\nWrote {args.csv}")

    return 0

if __name__ == "__main__":
    sys.exit(main())

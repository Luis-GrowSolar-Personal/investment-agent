#!/usr/bin/env python3
"""
corpus_construction_outcomes_v2.py -- Fix-pass Step D of corpus-construction.

Re-measures outcome balance on CORPUS_MANIFEST_V2.json (78 companies), same
method as analysis/corpus_construction_outcomes.py (Step 4b, first pass):
182-calendar-day forward return of each company's LAST available call date
vs SPY over the same window, +/-5 point dead band. Per-company proxy, not
per-call -- same simplification as the first pass, for the same reason
(full per-call date lists for the ORIGINAL 71 were not persisted; this run's
Step B DID persist full per-call dates in availability_fix_working.json for
all 78, but the per-company method is kept for direct comparability with
the first pass's own headline figure).

Extends analysis/data/corpus_v2/corpus_v2_price_cache.json (the SAME file
the first pass used) -- does not touch analysis/data/price_cache.json
(frozen, production, untouched). Adds S4-inclusive/exclusive split per
PREREGISTRATION_FIX.json's A4 disclosure requirement, on top of the first
pass's S5-exclusion headline.

Run only after CORPUS_MANIFEST_V2.json is frozen (Step C) -- it is.
"""
import json, sys, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance")

REPO = Path(__file__).parent.parent
MANIFEST = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json"
CACHE = REPO / "analysis/data/corpus_v2/corpus_v2_price_cache.json"
OUT = REPO / "analysis/data/corpus_v2/outcome_balance_v2.json"

DEAD_BAND_PCT = 5.0
FORWARD_DAYS = 182


def get_series(ticker, start, end, cache):
    if ticker in cache and cache[ticker]:
        return cache[ticker]
    if ticker in cache and not cache[ticker]:
        return cache[ticker]
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        cache[ticker] = {}
        return {}
    if hasattr(df.columns, "levels"):
        close = df[("Close", ticker)] if ("Close", ticker) in df.columns else df["Close"]
    else:
        close = df["Close"]
    out = {str(idx.date()): float(v) for idx, v in close.items() if v == v}
    cache[ticker] = out
    return out


def price_on_or_after(series, d0):
    for i in range(8):
        k = (d0 + datetime.timedelta(days=i)).isoformat()
        if k in series:
            return series[k]
    return None


def price_on_or_before(series, d0):
    for i in range(8):
        k = (d0 - datetime.timedelta(days=i)).isoformat()
        if k in series:
            return series[k]
    return None


def dist_pct(rows):
    n = len(rows)
    dist = {"beats": 0, "lags": 0, "moves_with": 0}
    for x in rows:
        dist[x["bucket"]] += 1
    pct = {k: round(100 * v / n, 1) if n else 0 for k, v in dist.items()}
    return n, dist, pct


def main():
    manifest = json.loads(MANIFEST.read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    rows = []
    for stratum, block in manifest["strata"].items():
        for rec in block["frozen"]:
            if rec.get("last_call") is None:
                continue
            rows.append({"ticker": rec["ticker"], "stratum": stratum, "last_call": rec["last_call"]})

    spy_series = get_series("SPY", "2020-01-01", None, cache)

    results = []
    for r in rows:
        t, s, last_call = r["ticker"], r["stratum"], r["last_call"]
        call_date = datetime.date.fromisoformat(last_call)
        fwd_date = call_date + datetime.timedelta(days=FORWARD_DAYS)
        if fwd_date > datetime.date.today() - datetime.timedelta(days=3):
            results.append({**r, "skipped": "forward window not yet elapsed"})
            continue
        series = get_series(t, "2020-01-01", None, cache)
        p0 = price_on_or_after(series, call_date)
        p1 = price_on_or_before(series, fwd_date)
        s0 = price_on_or_after(spy_series, call_date)
        s1 = price_on_or_before(spy_series, fwd_date)
        if None in (p0, p1, s0, s1) or p0 == 0 or s0 == 0:
            results.append({**r, "skipped": "missing price data"})
            continue
        stock_ret = (p1 / p0 - 1) * 100
        spy_ret = (s1 / s0 - 1) * 100
        diff = stock_ret - spy_ret
        bucket = "beats" if diff > DEAD_BAND_PCT else ("lags" if diff < -DEAD_BAND_PCT else "moves_with")
        results.append({**r, "stock_ret_pct": round(stock_ret, 2), "spy_ret_pct": round(spy_ret, 2),
                        "diff_pts": round(diff, 2), "bucket": bucket})

    CACHE.write_text(json.dumps(cache))
    counted = [x for x in results if "bucket" in x]
    skipped = [x for x in results if "skipped" in x]

    n_all, dist_all, pct_all = dist_pct(counted)
    counted_ex_s5 = [x for x in counted if x["stratum"] != "S5"]
    n_ex_s5, dist_ex_s5, pct_ex_s5 = dist_pct(counted_ex_s5)
    counted_ex_s5_s4 = [x for x in counted_ex_s5 if x["stratum"] != "S4"]
    n_ex_s5_s4, dist_ex_s5_s4, pct_ex_s5_s4 = dist_pct(counted_ex_s5_s4)
    counted_s4_only = [x for x in counted if x["stratum"] == "S4"]
    n_s4, dist_s4, pct_s4 = dist_pct(counted_s4_only)

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "Same as first pass (analysis/corpus_construction_outcomes.py): 182-day forward return of each company's LAST call vs SPY, +/-5pt dead band, per-company proxy.",
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json",
        "n_companies_measured": n_all, "n_skipped": len(skipped), "skipped_detail": skipped,
        "distribution_all_including_S4_and_S5": {"n": n_all, "counts": dist_all, "pct": pct_all},
        "distribution_excluding_S5_only": {"n": n_ex_s5, "counts": dist_ex_s5, "pct": pct_ex_s5,
            "note": "This is the figure directly comparable to the first pass's headline (44.4/35.2/20.4, n=54) and the existing corpus (46.2/42.1/11.7) -- both of those ALSO exclude S5 but do NOT separately exclude S4."},
        "distribution_excluding_S5_and_S4_per_A4": {"n": n_ex_s5_s4, "counts": dist_ex_s5_s4, "pct": pct_ex_s5_s4,
            "note": "Per PREREGISTRATION_FIX.json A4: S4 is outcome-defined (failures) and must be reported both ways. This is the ex-S4 version of the line above."},
        "s4_only": {"n": n_s4, "counts": dist_s4, "pct": pct_s4,
            "s4_share_of_ex_s5_companies": round(100 * n_s4 / n_ex_s5, 1) if n_ex_s5 else 0,
            "s4_share_of_ex_s5_calls": None},
        "prior_figures_for_comparison": {
            "first_pass_v1_ex_s5": {"beats": 44.4, "lags": 35.2, "moves_with": 20.4, "n": 54,
                "source": "analysis/data/corpus_v2/outcome_balance.json -> distribution_excluding_S5_ruler_headline.pct"},
            "existing_corpus": {"beats": 46.2, "lags": 42.1, "moves_with": 11.7,
                "source": "analysis/corpus_construction_outcomes.py -> existing_corpus_comparison (hardcoded prior baseline)"},
        },
        "per_company": results,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "per_company"}, indent=2))


if __name__ == "__main__":
    main()

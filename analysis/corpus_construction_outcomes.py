#!/usr/bin/env python3
"""
corpus_construction_outcomes.py -- Step 4b of corpus-construction.

Measures outcome balance (beats/lags/moves-with SPY, 182-day forward,
+/-5% dead band) on the FROZEN corpus from CORPUS_MANIFEST.json. Must be
run only after the manifest is committed (4a), never before -- this is
what keeps the freeze-then-measure order honest.

Simplification, stated here and in the wrap-up: uses each company's LAST
available call date (from the manifest's `last_call`) as the single
outcome-measurement point per company, rather than every call in the
window, because full per-call date lists were not persisted by the Step 3
availability check and re-deriving them would cost additional vendor calls
for no availability-relevant purpose. This is a per-company proxy for the
scorecard's per-call grading, not a reproduction of it.

Writes analysis/data/corpus_v2/corpus_v2_price_cache.json -- a NEW file,
never analysis/data/price_cache.json (frozen, untouched).
"""
import json, sys, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance")

REPO = Path(__file__).parent.parent
MANIFEST = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST.json"
NEW_CACHE = REPO / "analysis/data/corpus_v2/corpus_v2_price_cache.json"
OUT = REPO / "analysis/data/corpus_v2/outcome_balance.json"

DEAD_BAND_PCT = 5.0
FORWARD_DAYS = 182


def get_series(ticker, start, end, cache):
    if ticker in cache:
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


def main():
    manifest = json.loads(MANIFEST.read_text())
    cache = json.loads(NEW_CACHE.read_text()) if NEW_CACHE.exists() else {}

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
        if diff > DEAD_BAND_PCT:
            bucket = "beats"
        elif diff < -DEAD_BAND_PCT:
            bucket = "lags"
        else:
            bucket = "moves_with"
        results.append({**r, "stock_ret_pct": round(stock_ret, 2), "spy_ret_pct": round(spy_ret, 2),
                        "diff_pts": round(diff, 2), "bucket": bucket})

    NEW_CACHE.write_text(json.dumps(cache))
    counted = [x for x in results if "bucket" in x]
    skipped = [x for x in results if "skipped" in x]
    n = len(counted)
    dist = {"beats": 0, "lags": 0, "moves_with": 0}
    for x in counted:
        dist[x["bucket"]] += 1
    pct = {k: round(100 * v / n, 1) if n else 0 for k, v in dist.items()}

    # exclude S5 from the headline, per PREREGISTRATION.json
    counted_no_s5 = [x for x in counted if x["stratum"] != "S5"]
    n2 = len(counted_no_s5)
    dist2 = {"beats": 0, "lags": 0, "moves_with": 0}
    for x in counted_no_s5:
        dist2[x["bucket"]] += 1
    pct2 = {k: round(100 * v / n2, 1) if n2 else 0 for k, v in dist2.items()}

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "182-calendar-day forward return of each company's LAST available call date vs SPY over the same window, +/-5 point dead band. Per-company proxy, not per-call.",
        "n_companies_measured": n, "n_skipped": len(skipped), "skipped_detail": skipped,
        "distribution_all_including_S5": {"counts": dist, "pct": pct},
        "distribution_excluding_S5_ruler_headline": {"counts": dist2, "pct": pct2, "n": n2},
        "existing_corpus_comparison": {"beats": 46.2, "lags": 42.1, "moves_with": 11.7},
        "per_company": results,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "per_company"}, indent=2))


if __name__ == "__main__":
    main()

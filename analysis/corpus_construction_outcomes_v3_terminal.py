#!/usr/bin/env python3
"""
corpus_construction_outcomes_v3_terminal.py -- corpus-fix-4, Step B.

Re-grades outcome balance on CORPUS_MANIFEST_V2.json with RMO removed
(Step D of corpus-fix-4) and applies the A6 terminal-value grading rule
(analysis/data/corpus_v2/PREREGISTRATION_FIX.json -> A6_terminal_value_grading)
to NOVA, FRC, SUNW -- the three S4 companies whose equity was verified
against public record to have been wiped out (see A6 addendum and the
wrap-up for sources).

ZERO NEW PRICE FETCHES. corpus_v2_price_cache.json holds NO price data at
all (not partial data ending at failure -- fully empty {}) for NOVA, FRC,
SUNW, RMO: their price series were never successfully fetched by the prior
runs' yfinance calls (all four returned empty dataframes, cached as {}).
This is a finding that contradicts the prompt's framing ("their price
series end when they fail" implies partial pre-failure data exists) --
flagged explicitly in the wrap-up.

The fix does not require fetching an entry price. Terminal value for a
verified wipeout is exactly zero, and (0 / p0 - 1) * 100 = -100.0 for ANY
positive p0 -- so the -100% forward return is exact and does not depend on
sourcing the entry price at all. Only SPY's already-cached series (present
for the full 2020-2026 window) is needed to compute the benchmark leg.
"""
import json, datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
MANIFEST = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json"
CACHE = REPO / "analysis/data/corpus_v2/corpus_v2_price_cache.json"
OUT = REPO / "analysis/data/corpus_v2/outcome_balance_v3_terminal.json"

DEAD_BAND_PCT = 5.0
FORWARD_DAYS = 182

TERMINAL_OVERRIDES = {
    # ticker: (terminal_value, terminal_date, source_url)
    "NOVA": (0.0, "2025-06-08",
             "https://www.chemanalyst.com/NewsAndDeals/NewsDetails/sunnova-chapter-11-bankruptcy-plan-confirmed-paving-way-for-final-wind-down-40043 "
             "(Plan effective 2025-11-14, equity holders zero recovery); filing "
             "https://www.sec.gov/Archives/edgar/data/1772695/000177269525000110/nova-20250609.htm "
             "(Ch.11 filed 2025-06-08); NYSE delisting notice "
             "https://www.sec.gov/Archives/edgar/data/1772695/000087666125000435/ruleprovisionnotice.htm "
             "(trading suspended 2025-06-09, delisted effective 2025-06-23)"),
    "FRC": (0.0, "2023-05-01",
            "https://www.fdic.gov/resources/resolutions/bank-failures/failed-bank-list/first-republic.html "
            "(FDIC receivership 2023-05-01; assets sold to JPMorgan Chase; common equity holders "
            "received no recovery -- standard priority in an FDIC receivership)"),
    "SUNW": (0.0, "2024-02-05",
             "https://www.sec.gov/Archives/edgar/data/1172631/000149315224004968/form8-k.htm "
             "(Chapter 7 liquidation petition filed 2024-02-05, all subsidiaries ceased operations "
             "same day; NASDAQ delisting notice received 2024-02-06, trading suspended "
             "no later than 2024-02-15). Chapter 7 liquidation places common equity last in "
             "priority; company did not survive as an operating entity. NOTE: ticker continued "
             "to trade OTC post-delisting under SUNWQ at near-zero prices (public quotes show "
             "SUNWQ around $0.002 and below as of the most recent check) -- functionally, not "
             "literally, a total wipeout. Graded as terminal value zero because the residual "
             "quoted value is immaterial relative to the +/-5pp dead band; this is stated, not "
             "hidden."),
}

REMOVED_TICKERS = {"RMO"}  # Step D of corpus-fix-4: removed from the corpus entirely


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
    cache = json.loads(CACHE.read_text())  # read-only; NOT extended (zero new fetches)

    rows = []
    for stratum, block in manifest["strata"].items():
        for rec in block["frozen"]:
            if rec["ticker"] in REMOVED_TICKERS:
                continue
            if rec.get("last_call") is None:
                continue
            rows.append({"ticker": rec["ticker"], "stratum": stratum, "last_call": rec["last_call"]})

    spy_series = cache["SPY"]

    results = []
    terminal_grading_log = []
    for r in rows:
        t, s, last_call = r["ticker"], r["stratum"], r["last_call"]
        call_date = datetime.date.fromisoformat(last_call)
        fwd_date = call_date + datetime.timedelta(days=FORWARD_DAYS)

        if t in TERMINAL_OVERRIDES:
            terminal_value, terminal_date, source = TERMINAL_OVERRIDES[t]
            s0 = price_on_or_after(spy_series, call_date)
            s1 = price_on_or_before(spy_series, fwd_date)
            if s0 is None or s1 is None:
                results.append({**r, "skipped": "missing SPY benchmark price for terminal-value grading window"})
                continue
            stock_ret = -100.0  # (0 / p0 - 1) * 100 for any p0 > 0
            spy_ret = (s1 / s0 - 1) * 100
            diff = stock_ret - spy_ret
            bucket = "beats" if diff > DEAD_BAND_PCT else ("lags" if diff < -DEAD_BAND_PCT else "moves_with")
            results.append({**r, "stock_ret_pct": round(stock_ret, 2), "spy_ret_pct": round(spy_ret, 2),
                            "diff_pts": round(diff, 2), "bucket": bucket,
                            "graded_via": "A6_terminal_value_grading",
                            "terminal_value": terminal_value, "terminal_date": terminal_date,
                            "source": source})
            terminal_grading_log.append({"ticker": t, "call_date": last_call, "fwd_date_would_be": fwd_date.isoformat(),
                                          "terminal_date": terminal_date, "terminal_value": terminal_value,
                                          "affected": True})
            continue

        if fwd_date > datetime.date.today() - datetime.timedelta(days=3):
            results.append({**r, "skipped": "forward window not yet elapsed"})
            continue
        series = cache.get(t, {})
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

    counted = [x for x in results if "bucket" in x]
    skipped = [x for x in results if "skipped" in x]

    n_all, dist_all, pct_all = dist_pct(counted)
    counted_ex_s5 = [x for x in counted if x["stratum"] != "S5"]
    n_ex_s5, dist_ex_s5, pct_ex_s5 = dist_pct(counted_ex_s5)
    counted_ex_s5_s4 = [x for x in counted_ex_s5 if x["stratum"] != "S4"]
    n_ex_s5_s4, dist_ex_s5_s4, pct_ex_s5_s4 = dist_pct(counted_ex_s5_s4)
    counted_s4_only = [x for x in counted if x["stratum"] == "S4"]
    n_s4, dist_s4, pct_s4 = dist_pct(counted_s4_only)
    s4_total_after_rmo_removal = 4  # WOLF, NOVA, FRC, SUNW
    s4_gradable_now = n_s4

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "run_id": "corpus-construction",
        "pass": "corpus-fix-4, Step B",
        "method": "Same as v2 (182-day forward return of each company's LAST call vs SPY, "
                   "+/-5pt dead band, per-company proxy), on the corpus with RMO removed "
                   "(Step D), with A6_terminal_value_grading applied to NOVA/FRC/SUNW. "
                   "ZERO new price fetches -- terminal value 0 makes stock_ret exactly -100% "
                   "independent of the (unfetched) entry price; only cached SPY prices are used.",
        "manifest_source": "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json (RMO excluded per corpus-fix-4 Step D)",
        "n_companies_measured": n_all, "n_skipped": len(skipped), "skipped_detail": skipped,
        "terminal_value_grading_applied": terminal_grading_log,
        "s4_gradable_before_this_fix": 1,
        "s4_total_after_rmo_removal": s4_total_after_rmo_removal,
        "s4_gradable_after_this_fix": s4_gradable_now,
        "distribution_all_including_S4_and_S5": {"n": n_all, "counts": dist_all, "pct": pct_all},
        "distribution_excluding_S5_only": {"n": n_ex_s5, "counts": dist_ex_s5, "pct": pct_ex_s5},
        "distribution_excluding_S5_and_S4_per_A4": {"n": n_ex_s5_s4, "counts": dist_ex_s5_s4, "pct": pct_ex_s5_s4},
        "s4_only": {"n": n_s4, "counts": dist_s4, "pct": pct_s4},
        "prior_figures_for_comparison": {
            "v2_ex_s5": {"beats": 44.6, "lags": 37.5, "moves_with": 17.9, "n": 56,
                         "source": "analysis/data/corpus_v2/outcome_balance_v2.json -> distribution_excluding_S5_only.pct"},
            "v1_ex_s5": {"beats": 44.4, "lags": 35.2, "moves_with": 20.4, "n": 54,
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

#!/usr/bin/env python3
"""
add_qqq_to_scorer_cache.py -- prompts/per-trim-value-qqq.md Step 1 ($0 except
one yfinance fetch of QQQ).

Adds QQQ to analysis/data/corpus_v2/scorer_price_cache_v1.json by the exact
method scorer_price_cache_backfill_driver.py used for every other ticker
(the two lines below are copied from its cmd_build, per the prompt's
"reuse the driver's fetch function if it can be imported; otherwise copy the
two lines exactly and say so" -- the driver's fetch is inlined in cmd_build
and keyed to its own module-level ticker list/cache-file loop, so it is not
importable as a standalone function; copied instead):

    hist = yf.Ticker(symbol).history(start="2019-06-01", end=AS_OF_DATE, auto_adjust=False)
    series = {d.strftime("%Y-%m-%d"): round(float(c), 4) for d, c in hist["Close"].items()}

end is set to the day after SPY's last date in the canonical cache (so QQQ
and SPY cover the same span), not "today", since the canonical cache was
built on an earlier date than this run.

Does NOT touch analysis/data/price_cache.json (frozen; read only for the
cross-check). Changes no existing key in the canonical cache.
"""
import json, sys, hashlib
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

REPO = Path(__file__).resolve().parent.parent
CANON = REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json"
LEGACY = REPO / "analysis/data/price_cache.json"
STATE = REPO / "analysis/data/run_state/per-trim-value-qqq"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    canon_sha_before = sha256_file(CANON)
    legacy_sha_before = sha256_file(LEGACY)
    canon = json.loads(CANON.read_text())
    legacy = json.loads(LEGACY.read_text())

    assert "QQQ" not in canon, "QQQ already in canonical cache -- stop, do not overwrite"

    spy_dates = sorted(canon["SPY"].keys())
    spy_last = date.fromisoformat(spy_dates[-1])
    end = (spy_last + timedelta(days=1)).isoformat()

    # -- the two lines from scorer_price_cache_backfill_driver.py cmd_build, unchanged --
    hist = yf.Ticker("QQQ").history(start="2019-06-01", end=end, auto_adjust=False)
    series = {d.strftime("%Y-%m-%d"): round(float(c), 4) for d, c in hist["Close"].items()}
    # -- end copied lines --

    qqq_dates = sorted(series.keys())

    # Assert 1: QQQ's trading dates equal SPY's trading dates in the canonical cache.
    date_diff = {
        "in_spy_not_qqq": sorted(set(spy_dates) - set(qqq_dates)),
        "in_qqq_not_spy": sorted(set(qqq_dates) - set(spy_dates)),
    }
    dates_match = not date_diff["in_spy_not_qqq"] and not date_diff["in_qqq_not_spy"]

    # Assert 2: cross-check against legacy QQQ on every shared date.
    legacy_qqq = legacy.get("QQQ", {})
    shared = sorted(set(qqq_dates) & set(legacy_qqq.keys()))
    max_rel_diff, max_rel_diff_date = 0.0, None
    for d in shared:
        a, b = series[d], legacy_qqq[d]
        if b == 0:
            continue
        rel = abs(a - b) / abs(b)
        if rel > max_rel_diff:
            max_rel_diff, max_rel_diff_date = rel, d
    cross_check_ok = max_rel_diff <= 0.001  # 0.1%

    result = {
        "canon_sha256_before": canon_sha_before,
        "legacy_sha256_before": legacy_sha_before,
        "spy_span": [spy_dates[0], spy_dates[-1]],
        "fetch_start": "2019-06-01", "fetch_end_exclusive": end,
        "qqq_n_dates": len(qqq_dates), "qqq_span": [qqq_dates[0], qqq_dates[-1]] if qqq_dates else None,
        "dates_match_spy": dates_match, "date_diff": date_diff,
        "n_shared_with_legacy": len(shared),
        "max_rel_diff_vs_legacy": max_rel_diff, "max_rel_diff_date": max_rel_diff_date,
        "cross_check_ok_le_0.1pct": cross_check_ok,
    }
    (STATE / "add_qqq_preflight.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))

    if not dates_match:
        print("STOP: QQQ trading dates do not equal SPY's. Writing nothing.")
        sys.exit(1)
    if not cross_check_ok:
        print(f"STOP: cross-check exceeds 0.1% ({max_rel_diff*100:.4f}% on {max_rel_diff_date}). Writing nothing.")
        sys.exit(1)

    other_keys_before = {k: canon[k] for k in canon}  # full snapshot for the post-write identity check
    canon["QQQ"] = series
    CANON.write_text(json.dumps(canon, indent=2))
    canon_sha_after = sha256_file(CANON)

    # Assert 3: every non-QQQ key in the canonical cache is identical to before.
    reloaded = json.loads(CANON.read_text())
    non_qqq_identical = all(reloaded[k] == other_keys_before[k] for k in other_keys_before)

    # Assert 4: legacy cache sha256 unchanged.
    legacy_sha_after = sha256_file(LEGACY)
    legacy_unchanged = legacy_sha_after == legacy_sha_before

    post = {
        "canon_sha256_after": canon_sha_after,
        "non_qqq_keys_identical_to_before": non_qqq_identical,
        "legacy_sha256_after": legacy_sha_after,
        "legacy_unchanged": legacy_unchanged,
        "canon_ticker_count_after": len(reloaded),
    }
    (STATE / "add_qqq_postwrite.json").write_text(json.dumps(post, indent=1))
    print(json.dumps(post, indent=1))

    if not (non_qqq_identical and legacy_unchanged):
        print("STOP: post-write identity check failed.")
        sys.exit(1)

    print("OK: QQQ added to canonical cache.")


if __name__ == "__main__":
    main()

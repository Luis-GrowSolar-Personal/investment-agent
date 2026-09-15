#!/usr/bin/env python3
"""
scorer_price_cache_backfill_driver.py -- prompts/scorer-price-cache-backfill.md

Builds analysis/data/corpus_v2/scorer_price_cache_v1.json: a NEW price cache,
same {ticker: {date: close}} shape analyst_direct_scorer.py's PriceCache
class already parses, covering all 164 corpus companies + SPY. Does NOT
touch analysis/data/price_cache.json (frozen; legacy benchmarks replay off
it -- verified byte-identical before/after via sha256).

Usage:
  python3 scorer_price_cache_backfill_driver.py register   # Step A: A11 + audit extension
  python3 scorer_price_cache_backfill_driver.py build       # Step B: fetch prices via yfinance
  python3 scorer_price_cache_backfill_driver.py report      # per-ticker coverage summary
"""
import json, sys, datetime, hashlib
from pathlib import Path

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "analysis" / "data" / "corpus_v2"
SPLIT_PATH = CORPUS_DIR / "SPLIT_V7_RESERVE_REPLACEMENTS.json"
ALIASES_PATH = CORPUS_DIR / "TICKER_ALIASES.json"
LEGACY_CACHE_PATH = REPO_ROOT / "analysis" / "data" / "price_cache.json"
NEW_CACHE_PATH = CORPUS_DIR / "scorer_price_cache_v1.json"
PREREG_PATH = CORPUS_DIR / "PREREGISTRATION_FIX.json"
AUDIT_PATH = CORPUS_DIR / "PROPAGATION_AUDIT_A1_A9.json"
MANIFEST_PATH = REPO_ROOT / "docs" / "handoffs"  # not used; placeholder for clarity

AS_OF_DATE = datetime.date.today().isoformat()

# Aliases the prompt names explicitly, not all present in TICKER_ALIASES.json
# yet. Verified against the vendor (yfinance) before trusting, same as any
# other alias in this project.
EXTRA_ALIASES = {
    "SUNW": "SUNWQ",
    "FRC": "FRCB",
}

KNOWN_UNRECOVERABLE = {"NOVA", "WOLF"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_company_list():
    split = json.loads(SPLIT_PATH.read_text())
    companies = sorted(set(split["train"] + split["tune"] + split["holdout"]))
    return companies


def load_alias_map():
    raw = json.loads(ALIASES_PATH.read_text())
    amap = {e["original_symbol"]: e["working_symbol"]
            for e in raw["entries"] if e.get("working_symbol")}
    amap.update(EXTRA_ALIASES)
    return amap


def cmd_register():
    companies = load_company_list()
    amap = load_alias_map()
    prereg = json.loads(PREREG_PATH.read_text())
    prereg["A11_scorer_price_cache"] = {
        "registered_at": now_iso(),
        "prompt": "scorer-price-cache-backfill",
        "ordering_attestation": (
            "Registered before fetching any price. This addendum documents "
            "which cache analyst_direct_scorer.py actually opens, and builds "
            "a new one -- it does not re-derive or change any A1/A9 coverage "
            "verdict."
        ),
        "new_cache_path": str(NEW_CACHE_PATH.relative_to(REPO_ROOT)),
        "which_scorer_reads_which_cache": {
            "analyst_direct_scorer.py": "analysis/data/price_cache.json (default) "
                "-- now overridable via --price-cache, added this run",
            "this_run_points_it_at": str(NEW_CACHE_PATH.relative_to(REPO_ROOT)),
            "corpus_a9_gate_used": "analysis/data/corpus_v2/corpus_v2_price_cache.json "
                "(yfinance/Yahoo) -- a THIRD, separate file from either of the above",
        },
        "as_of_date": AS_OF_DATE,
        "ticker_count": len(companies) + 1,  # + SPY
        "ticker_list": companies + ["SPY"],
        "alias_map_used": amap,
        "known_unrecoverable": sorted(KNOWN_UNRECOVERABLE),
        "frozen_legacy_cache_path": str(LEGACY_CACHE_PATH.relative_to(REPO_ROOT)),
        "frozen_legacy_cache_sha256_before": sha256_file(LEGACY_CACHE_PATH),
    }
    PREREG_PATH.write_text(json.dumps(prereg, indent=2))
    print(f"Registered A11_scorer_price_cache. {len(companies)} companies + SPY.")
    print(f"Legacy cache sha256 (before, must be unchanged after): "
          f"{prereg['A11_scorer_price_cache']['frozen_legacy_cache_sha256_before']}")

    audit = json.loads(AUDIT_PATH.read_text())
    audit.setdefault("standing_checks", [])
    audit["standing_checks"].append({
        "added_at": now_iso(),
        "added_by": "scorer-price-cache-backfill",
        "check": (
            "A coverage rule must name the artifact its consumer actually "
            "reads, and be verified against that artifact. Fourth instance "
            "of this failure shape in this project (Alphabet alias absent "
            "from manifest; A8 verdicts left in a side file; versions.js "
            "disagreeing with the version registry; A9's price gate checking "
            "corpus_v2_price_cache.json while analyst_direct_scorer.py reads "
            "price_cache.json). This check should catch the fifth."
        ),
    })
    AUDIT_PATH.write_text(json.dumps(audit, indent=2))
    print(f"Extended {AUDIT_PATH.name} with the standing check.")


def cmd_build():
    prereg = json.loads(PREREG_PATH.read_text())
    a11 = prereg.get("A11_scorer_price_cache")
    if not a11:
        print("Run `register` first.")
        return
    companies = a11["ticker_list"]
    amap = a11["alias_map_used"]

    # Flat {ticker: {date: close}} -- exactly the shape PriceCache parses.
    # as_of_date lives in PREREGISTRATION_FIX.json's A11 entry, not in this
    # file, per the prompt's explicit "same shape ... PriceCache already
    # parses" instruction.
    cache = {}
    if NEW_CACHE_PATH.exists():
        cache = json.loads(NEW_CACHE_PATH.read_text())

    report_rows = []
    for orig in companies:
        if orig in cache:
            continue
        if orig in KNOWN_UNRECOVERABLE:
            report_rows.append({"ticker": orig, "symbol_used": None, "status": "known_unrecoverable"})
            continue
        symbol = amap.get(orig, orig)
        try:
            hist = yf.Ticker(symbol).history(start="2019-06-01", end=AS_OF_DATE, auto_adjust=False)
        except Exception as e:
            report_rows.append({"ticker": orig, "symbol_used": symbol, "status": f"error: {e}"})
            continue
        if hist is None or hist.empty:
            report_rows.append({"ticker": orig, "symbol_used": symbol, "status": "empty"})
            continue
        series = {d.strftime("%Y-%m-%d"): round(float(c), 4) for d, c in hist["Close"].items()}
        cache[orig] = series
        NEW_CACHE_PATH.write_text(json.dumps(cache, indent=2))
        dates = sorted(series.keys())
        report_rows.append({
            "ticker": orig, "symbol_used": symbol, "status": "ok",
            "first": dates[0], "last": dates[-1], "n_rows": len(dates),
        })
        print(f"  {orig} <- {symbol}: {len(dates)} rows, {dates[0]}..{dates[-1]}")

    report_path = NEW_CACHE_PATH.with_suffix(".report.json")
    existing_report = []
    if report_path.exists():
        existing_report = json.loads(report_path.read_text())
    existing_report.extend(report_rows)
    report_path.write_text(json.dumps(existing_report, indent=2))
    print(f"\nBuilt/updated {NEW_CACHE_PATH}. {len(cache)} tickers total.")
    after_hash = sha256_file(LEGACY_CACHE_PATH)
    print(f"Legacy price_cache.json sha256 AFTER: {after_hash}")
    print(f"Matches before? {after_hash == a11['frozen_legacy_cache_sha256_before']}")


def cmd_report():
    report_path = NEW_CACHE_PATH.with_suffix(".report.json")
    rows = json.loads(report_path.read_text())
    ok = [r for r in rows if r["status"] == "ok"]
    bad = [r for r in rows if r["status"] != "ok"]
    print(f"OK: {len(ok)}  NOT OK: {len(bad)}")
    for r in bad:
        print(" ", r)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "register":
        cmd_register()
    elif cmd == "build":
        cmd_build()
    elif cmd == "report":
        cmd_report()
    else:
        print(__doc__)

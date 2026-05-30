#!/usr/bin/env python3
"""
backtest_from_files.py — Same backtest logic as backtest_runner.py, but
reads transcripts from disk and prices from price_cache.json instead of
Postgres + yfinance.

Purpose: let the prompt-iteration loop run end-to-end inside environments
that don't have network access to Railway Postgres or Yahoo Finance
(e.g. the Cowork sandbox).

Requirements:
    dump_transcripts.py must have been run at least once so that
    analysis/data/transcripts/*.txt + _manifest.json exist.
    analysis/data/price_cache.json must contain keys for every ticker
    being backtested plus "SPY".

CSV output schema is identical to backtest_runner.py so downstream
tools (variance_check.py, backtest_diff.py, read_eval.py) work unchanged.

Usage:
    python3 backtest_from_files.py --ticker ENPH --save-evals
    python3 backtest_from_files.py  # all tickers in manifest
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Sandbox environment fixups (must run before importing anthropic/httpx).
# These only trigger inside environments where the HTTP proxy does MITM TLS
# interception (e.g. Cowork's Linux sandbox). On a normal Mac they are no-ops
# because ALL_PROXY isn't set and /etc/ssl/certs/ca-certificates.crt doesn't
# exist.
# ---------------------------------------------------------------------------
os.environ.pop("ALL_PROXY", None)   # anthropic picks this up and fails on SOCKS
os.environ.pop("GRPC_PROXY", None)
_SANDBOX_CA = "/etc/ssl/certs/ca-certificates.crt"
if "SSL_CERT_FILE" not in os.environ and Path(_SANDBOX_CA).exists():
    os.environ["SSL_CERT_FILE"] = _SANDBOX_CA

import pandas as pd
from dotenv import load_dotenv
import anthropic


# ---------------------------------------------------------------------------
# Env + constants (match backtest_runner.py)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(ENV_PATH)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    sys.exit(f"ERROR: ANTHROPIC_API_KEY not found (looked in {ENV_PATH}).")

MODEL = "claude-sonnet-4-6"
# MODEL_SLUG: short label used as part of the eval cache subdir name.
# Strip the "claude-" prefix so subdir names stay readable.
# e.g. "claude-sonnet-4-20250514" → "sonnet-4-20250514"
MODEL_SLUG = MODEL.removeprefix("claude-")
VERSION = "1.3.0-files"
FORWARD_DAYS = 90

DATA_DIR = SCRIPT_DIR / "data"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
MANIFEST_PATH = TRANSCRIPT_DIR / "_manifest.json"
PRICE_CACHE_PATH = DATA_DIR / "price_cache.json"
EVALS_DIR = DATA_DIR / "evals"

# CSV column order must match backtest_runner.py output exactly.
CSV_COLUMNS = [
    "ticker",
    "call_date",
    "transcript_title",
    "recommendation",
    "thesis_health",
    "thesis_delta",
    "type_classification",
    "stumble_type",
    "threat_mechanism_impaired",
    "credibility_delta",
    "ratchet_tranche",
    "fresh_money_allocation",
    "recommended_size",
    "cap_percent",
    "mitigation_argument_present",
    "mitigation_track_record",
    "blind_spots_triggered",
    "active_driver_count",
    "price_at_call",
    "spy_at_call",
    "price_forward_90d",
    "spy_forward_90d",
    "forward_date",
    "ticker_return_pct",
    "spy_return_pct",
    "relative_return_pct",
    "signal_correct",
    "prompt_version",
]


# ---------------------------------------------------------------------------
# Prompt loading (identical rule to backtest_runner.py)
# ---------------------------------------------------------------------------

def load_evaluation_prompt() -> tuple[str, str, Path]:
    candidates = [
        SCRIPT_DIR.parent / "docs" / "EVALUATION_PROMPT.md",
        SCRIPT_DIR.parent / "server" / "docs" / "EVALUATION_PROMPT.md",
    ]
    for path in candidates:
        if path.exists():
            text = path.read_text()
            m = re.search(r"^#\s*Version:\s*(\S+)", text, re.MULTILINE)
            version = m.group(1).strip() if m else "unknown"
            return text, version, path
    sys.exit("ERROR: docs/EVALUATION_PROMPT.md not found.")


# ---------------------------------------------------------------------------
# Price cache lookup
# ---------------------------------------------------------------------------

class PriceCache:
    """Thin wrapper over the JSON price cache. Returns closing price on
    the nearest trading day on or after the target date."""

    def __init__(self, path: Path):
        with path.open() as f:
            self._data: dict[str, dict[str, float]] = json.load(f)
        # Pre-sort each ticker's date list once.
        self._sorted_dates: dict[str, list[str]] = {
            sym: sorted(d.keys()) for sym, d in self._data.items()
        }

    def has(self, symbol: str) -> bool:
        return symbol in self._data

    def price_on_or_after(self, symbol: str, target: dt.date) -> tuple[float | None, dt.date | None]:
        """Return (price, actual_trading_day) for the first trading day on
        or after `target`. Returns (None, None) if no such day exists in
        the cache."""
        if symbol not in self._sorted_dates:
            return None, None
        target_str = target.isoformat()
        for ds in self._sorted_dates[symbol]:
            if ds >= target_str:
                return float(self._data[symbol][ds]), dt.date.fromisoformat(ds)
        return None, None


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_transcript(client: anthropic.Anthropic, transcript_text: str,
                        evaluation_prompt: str) -> str:
    full_prompt = (
        evaluation_prompt.strip()
        + "\n\n---\n\nTRANSCRIPT:\n\n"
        + transcript_text
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": full_prompt}],
    )
    return response.content[0].text.strip()


def parse_structured_score(raw_output: str) -> dict:
    m = re.search(
        r"---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---",
        raw_output,
        re.DOTALL,
    )
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"    WARN: JSON parse error in structured block: {e}")
        return {}


# ---------------------------------------------------------------------------
# Signal correctness — must match backtest_runner.py logic exactly
# ---------------------------------------------------------------------------

def compute_signal_correct(recommendation: str, relative_return: float | None):
    if relative_return is None or not recommendation:
        return None
    if recommendation == "Add":
        return relative_return > 0
    if recommendation == "Hold":
        return abs(relative_return) <= 5
    if recommendation in ("Trim", "Exit"):
        return relative_return < 0
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", default=[],
                        help="Only evaluate this ticker. Repeatable.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate first transcript only, print output, exit.")
    parser.add_argument("--save-evals", action="store_true",
                        help="Save full evaluator output under data/evals/.")
    parser.add_argument("--reuse-cache", action="store_true",
                        help="Reuse cached eval text from data/evals/<prompt_version>/ "
                             "when present; skips API call. Implies --save-evals.")
    parser.add_argument("--parallel", type=int, default=1,
                        help="Evaluate up to N transcripts concurrently (default: 1).")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        sys.exit(f"ERROR: {MANIFEST_PATH} not found. Run dump_transcripts.py first.")
    if not PRICE_CACHE_PATH.exists():
        sys.exit(f"ERROR: {PRICE_CACHE_PATH} not found.")

    manifest: list[dict] = json.loads(MANIFEST_PATH.read_text())
    if args.ticker:
        wanted = {t.upper() for t in args.ticker}
        manifest = [m for m in manifest if m["ticker"].upper() in wanted]
        if not manifest:
            sys.exit(f"ERROR: no manifest entries for tickers {sorted(wanted)}.")

    # Sort chronologically per ticker so runs are deterministic.
    manifest.sort(key=lambda m: (m["ticker"], m["call_date"]))

    prompt_text, prompt_version, prompt_path = load_evaluation_prompt()
    print(f"Backtest-from-files v{VERSION}")
    print(f"Prompt: {prompt_path.name}  version: {prompt_version}")
    print(f"Transcripts: {len(manifest)}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prices = PriceCache(PRICE_CACHE_PATH)
    if not prices.has("SPY"):
        sys.exit("ERROR: price_cache.json does not contain SPY.")

    def process_entry(entry: dict) -> dict | None:
        """Evaluate one transcript, compute returns, return a CSV row dict."""
        symbol = entry["ticker"]
        call_date = dt.date.fromisoformat(entry["call_date"])
        title = entry["title"]
        tx_path = TRANSCRIPT_DIR / entry["filename"]

        if not tx_path.exists():
            print(f"  [{symbol} {call_date}] ERROR: transcript file missing.")
            return None
        if not prices.has(symbol):
            print(f"  [{symbol} {call_date}] ERROR: no price data. Skipping.")
            return None

        transcript_text = tx_path.read_text()
        # Version-key the cache by (prompt_version, model_slug) so evals from
        # different model/prompt combos never mix. e.g. "v6_sonnet-4-20250514"
        cache_dir = EVALS_DIR / f"{prompt_version}_{MODEL_SLUG}"
        cache_path = cache_dir / f"{symbol}_{call_date}.txt"
        raw_output = None
        if args.reuse_cache and cache_path.exists():
            raw_output = cache_path.read_text()
            print(f"  [{symbol} {call_date}] cache-hit  (prompt {prompt_version})")
        if raw_output is None:
            try:
                raw_output = evaluate_transcript(client, transcript_text, prompt_text)
            except Exception as e:
                print(f"  [{symbol} {call_date}] eval failed: {e}")
                return None

        if args.save_evals or args.reuse_cache:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(raw_output)

        score = parse_structured_score(raw_output)

        price_at, _ = prices.price_on_or_after(symbol, call_date)
        spy_at, _ = prices.price_on_or_after("SPY", call_date)
        fwd_target = call_date + dt.timedelta(days=FORWARD_DAYS)
        price_fwd, fwd_actual = prices.price_on_or_after(symbol, fwd_target)
        spy_fwd, _ = prices.price_on_or_after("SPY", fwd_target)

        ticker_return = None
        spy_return = None
        relative_return = None
        if price_at and price_fwd:
            ticker_return = round((price_fwd - price_at) / price_at * 100, 2)
        if spy_at and spy_fwd:
            spy_return = round((spy_fwd - spy_at) / spy_at * 100, 2)
        if ticker_return is not None and spy_return is not None:
            relative_return = round(ticker_return - spy_return, 2)

        rec = score.get("recommendation", "")
        signal_correct = compute_signal_correct(rec, relative_return)
        correct_display = signal_correct if signal_correct is not None else "n/a"
        print(f"  [{symbol} {call_date}] {rec:5}  rel:{relative_return}%  "
              f"correct:{correct_display}")

        return {
            "ticker": symbol,
            "call_date": call_date,
            "transcript_title": title,
            "recommendation": rec,
            "thesis_health": score.get("thesisHealth"),
            "thesis_delta": score.get("thesisDelta"),
            "type_classification": score.get("typeClassification"),
            "stumble_type": score.get("stumbleType"),
            "threat_mechanism_impaired": score.get("threatMechanismImpaired"),
            "credibility_delta": score.get("credibilityDelta"),
            "ratchet_tranche": score.get("ratchetTranche"),
            "fresh_money_allocation": score.get("freshMoneyAllocation"),
            "recommended_size": score.get("recommendedSize"),
            "cap_percent": score.get("capPercent"),
            "mitigation_argument_present": score.get("mitigationArgumentPresent"),
            "mitigation_track_record": score.get("mitigationCapabilityTrackRecord"),
            "blind_spots_triggered": json.dumps(score.get("blindSpotsTriggered", [])),
            "active_driver_count": score.get("activeDriverCount"),
            "price_at_call": price_at,
            "spy_at_call": spy_at,
            "price_forward_90d": price_fwd,
            "spy_forward_90d": spy_fwd,
            "forward_date": fwd_actual,
            "ticker_return_pct": ticker_return,
            "spy_return_pct": spy_return,
            "relative_return_pct": relative_return,
            "signal_correct": signal_correct,
            "prompt_version": prompt_version,
        }

    rows: list[dict] = []

    if args.dry_run:
        # Dry run: process only the first entry and print its raw eval output.
        if not manifest:
            print("No entries to evaluate.")
            return 1
        entry = manifest[0]
        symbol = entry["ticker"]
        call_date = entry["call_date"]
        print(f"\n[dry-run] {symbol} {call_date}")
        tx_path = TRANSCRIPT_DIR / entry["filename"]
        raw = evaluate_transcript(client, tx_path.read_text(), prompt_text)
        print("\n--- EVAL OUTPUT (first 2000 chars) ---")
        print(raw[:2000])
        print("--- END ---")
        return 0

    if args.parallel and args.parallel > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        print(f"Running {len(manifest)} evals with parallelism={args.parallel}")
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {pool.submit(process_entry, e): e for e in manifest}
            for fut in as_completed(futures):
                row = fut.result()
                if row is not None:
                    rows.append(row)
        # Preserve chronological order in output.
        rows.sort(key=lambda r: (r["ticker"], r["call_date"]))
    else:
        for entry in manifest:
            row = process_entry(entry)
            if row is not None:
                rows.append(row)

    if not rows:
        print("\nNo rows produced.")
        return 1

    # Filename convention matches backtest_runner.py: backtest_<YYYY-MM-DD>[_TICKER].csv
    today = dt.date.today().isoformat()
    tickers_in_run = sorted({r["ticker"] for r in rows})
    suffix = f"_{tickers_in_run[0]}" if len(tickers_in_run) == 1 else ""
    out_path = DATA_DIR / f"backtest_{today}{suffix}.csv"

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    df.to_csv(out_path, index=False)

    # Summary
    scored = df[df["signal_correct"].notna()]
    print("\n" + "=" * 60)
    print(f"Wrote {out_path}")
    if not scored.empty:
        by_ticker = scored.groupby("ticker")["signal_correct"].agg(
            correct="sum", total="count"
        )
        print("\nSignal accuracy:")
        for sym, row in by_ticker.iterrows():
            c, t = int(row["correct"]), int(row["total"])
            pct = 100.0 * c / t if t else 0.0
            print(f"  {sym}: {c}/{t} = {pct:.0f}%")
        total_c = int(scored["signal_correct"].sum())
        total_t = len(scored)
        print(f"  OVERALL: {total_c}/{total_t} = {100.0*total_c/total_t:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

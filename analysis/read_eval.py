#!/usr/bin/env python3
"""
read_eval.py — Read and display evaluator output for a specific call.

Usage:
    # Show full eval
    python3 analysis/read_eval.py ENPH 2024-02-06

    # Show specific section only
    python3 analysis/read_eval.py ENPH 2024-02-06 --section "THESIS HEALTH"
    python3 analysis/read_eval.py ENPH 2024-02-06 --section "STUMBLE"
    python3 analysis/read_eval.py ENPH 2024-02-06 --section "MITIGATION"
    python3 analysis/read_eval.py ENPH 2024-02-06 --section "RECOMMENDATION"

    # Compare two evals side by side (old vs new, if both exist)
    python3 analysis/read_eval.py ENPH 2024-02-06 --compare

    # List all available evals
    python3 analysis/read_eval.py --list
    python3 analysis/read_eval.py --list ENPH

Output:
    Reads from analysis/data/evals/<TICKER>_<date>.txt
"""

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
EVALS_DIR = SCRIPT_DIR / "data" / "evals"

SECTION_ALIASES = {
    "thesis":       "THESIS HEALTH",
    "thesis health": "THESIS HEALTH",
    "credibility":  "MANAGEMENT CREDIBILITY",
    "management":   "MANAGEMENT CREDIBILITY",
    "stumble":      "STUMBLE CLASSIFICATION",
    "threat":       "THREAT MECHANISM TEST",
    "mitigation":   "MITIGATION ARGUMENT TEST",
    "position type": "POSITION TYPE",
    "sizing":       "POSITION SIZING RECOMMENDATION",
    "recommendation": "RECOMMENDATION",
    "fresh money":  "FRESH MONEY TEST",
    "fictional":    "FICTIONAL DETAIL CHECK",
    "structured":   "STRUCTURED",
}


def find_eval(ticker, date_str):
    """Find eval file for ticker + date. Returns Path or None."""
    pattern = f"{ticker.upper()}_{date_str}.txt"
    path = EVALS_DIR / pattern
    return path if path.exists() else None


def extract_section(text, section_name):
    """
    Extract a named section from eval output.
    Sections are delimited by ## SECTION NAME headers.
    """
    # Normalize
    name_upper = section_name.upper()

    # Special case: structured block
    if "STRUCTURED" in name_upper:
        match = re.search(
            r'---STRUCTURED---.*?---END STRUCTURED---',
            text, re.DOTALL
        )
        return match.group(0) if match else None

    # Find the section header
    pattern = rf'##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##\s|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return f"## {section_name}\n{match.group(1).strip()}"

    # Try partial match on section name
    pattern2 = rf'##\s+[^\n]*{re.escape(section_name.split()[0])}[^\n]*\n(.*?)(?=\n##\s|\Z)'
    match2 = re.search(pattern2, text, re.DOTALL | re.IGNORECASE)
    if match2:
        header = re.search(rf'##\s+[^\n]*{re.escape(section_name.split()[0])}[^\n]*', text, re.IGNORECASE)
        header_text = header.group(0) if header else f"## {section_name}"
        return f"{header_text}\n{match2.group(1).strip()}"

    return None


def resolve_section(raw):
    """Resolve section alias to canonical name."""
    lower = raw.lower().strip()
    return SECTION_ALIASES.get(lower, raw.upper())


def list_evals(ticker_filter=None):
    """List all available eval files."""
    if not EVALS_DIR.exists():
        print(f"❌  No evals directory found at {EVALS_DIR}")
        print("    Run: python3 analysis/backtest_runner.py --ticker ENPH --save-evals")
        return

    files = sorted(EVALS_DIR.glob("*.txt"))
    if ticker_filter:
        files = [f for f in files if f.stem.startswith(ticker_filter.upper() + "_")]

    if not files:
        print(f"  No eval files found{' for ' + ticker_filter.upper() if ticker_filter else ''}.")
        return

    print(f"\n  {'TICKER':<8} {'DATE':<12} {'FILE'}")
    print(f"  {'─'*8} {'─'*12} {'─'*40}")
    for f in files:
        parts = f.stem.split("_", 1)
        ticker = parts[0] if len(parts) > 1 else "?"
        date = parts[1] if len(parts) > 1 else f.stem
        print(f"  {ticker:<8} {date:<12} {f.name}")
    print(f"\n  Total: {len(files)} eval(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Read evaluator output for a specific earnings call."
    )
    parser.add_argument('ticker', nargs='?', help='Ticker symbol (e.g. ENPH)')
    parser.add_argument('date', nargs='?', help='Call date (e.g. 2024-02-06)')
    parser.add_argument(
        '--section', '-s',
        help='Show only this section (e.g. "thesis", "stumble", "mitigation", "recommendation")',
        default=None
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available eval files'
    )
    args = parser.parse_args()

    if args.list or (not args.ticker and not args.date):
        list_evals(args.ticker)
        return

    if not args.ticker or not args.date:
        print("Usage: python3 analysis/read_eval.py <TICKER> <DATE> [--section SECTION]")
        print("       python3 analysis/read_eval.py --list [TICKER]")
        sys.exit(1)

    path = find_eval(args.ticker, args.date)
    if not path:
        print(f"❌  No eval found for {args.ticker.upper()} {args.date}")
        print(f"    Expected: {EVALS_DIR / (args.ticker.upper() + '_' + args.date + '.txt')}")
        print(f"    Run: python3 analysis/read_eval.py --list")
        sys.exit(1)

    text = path.read_text()

    if args.section:
        canonical = resolve_section(args.section)
        section_text = extract_section(text, canonical)
        if section_text:
            print(f"\n{'═'*60}")
            print(f"  {args.ticker.upper()}  |  {args.date}  |  {canonical}")
            print(f"{'═'*60}\n")
            print(section_text)
            print()
        else:
            print(f"❌  Section '{args.section}' not found in eval.")
            print(f"    Available aliases: {', '.join(SECTION_ALIASES.keys())}")
    else:
        print(text)


if __name__ == '__main__':
    main()

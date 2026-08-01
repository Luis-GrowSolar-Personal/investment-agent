#!/usr/bin/env python3
"""
backtest_runner.py — Ticker-level signal quality backtest for the Portfolio Analyst framework.

For each portfolio ticker, runs transcripts chronologically through the evaluator:
  1. Calls the evaluator with the raw transcript (no anonymization — see NOTE below)
  2. Records the structured score
  3. Fetches actual price on call date and 90 days later (next trading day)
  4. Computes return vs SPY benchmark
  5. Writes a scored CSV with full audit trail

NOTE: Anonymization was attempted but abandoned. These tickers (AAPL, TSLA, etc.) are
too uniquely identifiable from their financial structure alone — anonymization scored
1.5/10 after three attempts. The backtest runs with company identity known, which
matches production conditions (you always know what you're evaluating in real use).
Known limitation: evaluator priors about each company may influence scoring.

Usage:
    python3 backtest_runner.py [--ticker AAPL] [--dry-run] [--save-transcripts]

Options:
    --ticker SYMBOL         Run only for this ticker (default: all portfolio tickers)
    --dry-run               Evaluate first transcript only, print result, exit
    --save-transcripts      Save raw transcripts being evaluated to data/transcripts/

Requirements:
    python3 -m pip install psycopg2-binary yfinance python-dotenv anthropic pandas

Output:
    analysis/data/backtest_YYYY-MM-DD.csv
    analysis/data/transcripts/<TICKER>_<date>.txt  (only with --save-transcripts)
"""

import os
import re
import sys
import json
import time
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

# Find .env — script lives in analysis/, .env is at project root
script_dir = Path(__file__).parent.resolve()
env_path = script_dir.parent / ".env"
if not env_path.exists():
    # Try one level up (if running from project root)
    env_path = script_dir / ".env"
load_dotenv(env_path)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not ANTHROPIC_API_KEY:
    print("❌  ANTHROPIC_API_KEY not found. Check your .env path.")
    sys.exit(1)
if not DATABASE_URL:
    print("❌  DATABASE_URL not found. Check your .env path.")
    sys.exit(1)

import anthropic
import psycopg2
import psycopg2.extras
import yfinance as yf
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Must be kept in sync with MODEL_VERSION in server/lib/versions.js -- that
# file is the single source of truth for the production model string, but
# it's JS and this is Python, so there's no automated way to share the
# constant across the two. This drifted once already: this file still had
# claude-sonnet-4-20250514 (retired by Anthropic) weeks after versions.js
# was updated to claude-sonnet-4-6 on 2026-06-27. Check versions.js before
# assuming this value is current.
MODEL = "claude-sonnet-4-6"
VERSION = "1.3.0"
FORWARD_DAYS = 90          # days ahead to measure return
OUTPUT_DIR = script_dir / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(DATABASE_URL)


def fetch_portfolio_tickers(conn, symbol_filter=None):
    """Return list of tickers to backtest.

    With no symbol_filter: only 'portfolio' status tickers (unchanged
    default behavior for a full regression run).

    With a symbol_filter (--ticker SYMBOL): status is NOT constrained.
    Naming a specific ticker is an explicit request for that ticker
    regardless of its current portfolio/watchlist status -- e.g. for
    one-off benchmark/variance runs (see MODEL_SELECTION_BENCHMARK_SPEC.md
    Step 0) against tickers that have since been demoted to watchlist.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if symbol_filter:
            cur.execute(
                'SELECT id, symbol, name FROM "Ticker" WHERE symbol = %s ORDER BY symbol',
                (symbol_filter.upper(),)
            )
        else:
            cur.execute(
                'SELECT id, symbol, name FROM "Ticker" WHERE status = %s ORDER BY symbol',
                ('portfolio',)
            )
        return cur.fetchall()


def fetch_transcripts_for_ticker(conn, ticker_id):
    """Return transcripts for a ticker in chronological order."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            '''SELECT id, "callDate", title, "rawText"
               FROM "Transcript"
               WHERE "tickerId" = %s
               ORDER BY "callDate" ASC''',
            (ticker_id,)
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# ANONYMIZATION PIPELINE — COMMENTED OUT
# Abandoned after 3 attempts: tickers are re-identifiable from financial
# structure alone regardless of name/product replacement. Backtest runs
# with company identity known, matching production conditions.
# Kept for reference in case a future approach becomes viable.
# ---------------------------------------------------------------------------
# # ---------------------------------------------------------------------------
# # Anonymization — 3-stage pipeline
# # ---------------------------------------------------------------------------
#
# # Known trademarks and brand terms that Claude tends to miss.
# # Keyed by ticker symbol; each entry is a list of (pattern, replacement) tuples.
# # Patterns are compiled with re.IGNORECASE and word-boundary anchors where safe.
# # Add new entries here when audits reveal leakage — no script changes needed elsewhere.
# TRADEMARK_SCRUB: dict[str, list[tuple[str, str]]] = {
#     "AAPL": [
#         (r"\bApple Intelligence\b",          "the AI feature suite"),
#         (r"\biPhone\b",                       "Device A"),
#         (r"\biPad\b",                         "Device C"),
#         (r"\bMacBook\b",                      "Device B laptop"),
#         (r"\bMac\b",                          "Device B"),
#         (r"\bApple Watch\b",                  "Device E"),
#         (r"\bAirPods?\b",                     "Device F"),
#         (r"\bApple Vision Pro\b",             "Device D"),
#         (r"\bvisionOS\b",                     "the headset OS"),
#         (r"\biOS\s*\d*",                     "the mobile OS"),
#         (r"\bmacOS\s*\w*",                   "the desktop OS"),
#         (r"\bipadOS\b",                       "the device OS"),
#         (r"\bwatchOS\b",                      "the wearable OS"),
#         (r"\bSequoia\b",                      "the latest desktop OS version"),
#         (r"\bWWDC\b",                         "the annual developer conference"),
#         (r"\bApp Store\b",                    "the application marketplace"),
#         (r"\bApple TV\+?\b",                 "the video subscription service"),
#         (r"\bApple Music\b",                  "the music subscription service"),
#         (r"\bApple Arcade\b",                 "the gaming subscription service"),
#         (r"\bApple Fitness\+?\b",            "the fitness subscription service"),
#         (r"\biCloud\b",                       "the cloud storage service"),
#         (r"\bApple Pay\b",                    "the payment platform"),
#         (r"\bApple Wallet\b",                 "the digital wallet"),
#         (r"\bApple Maps\b",                   "the mapping service"),
#         (r"\bSafari\b",                       "the browser"),
#         (r"\bSiri\b",                         "the virtual assistant"),
#         (r"\bPrivate Cloud Compute\b",        "the cloud AI processing infrastructure"),
#         (r"\bFinal Cut Pro\b",                "the professional video software"),
#         (r"\bLogic Pro\b",                    "the professional audio software"),
#         (r"\bBeats\b",                        "the audio brand"),
#         (r"\bM[1-4]\s*(Ultra|Max|Pro)?\b",  "the current-generation processor"),
#         (r"\bA1[5-9]\s*(Pro)?\b",           "the current-generation mobile processor"),
#         (r"\bC1\s*modem\b",                  "the new modem"),
#         (r"\bNeural Engine\b",                "the AI processing unit"),
#         (r"\bOpenAI\b",                       "the third-party AI provider"),
#         (r"\bChatGPT\b",                      "the third-party AI integration"),
#         (r"\bSeverance\b",                    "original content title A"),
#         (r"\bPresumed Innocent\b",            "original content title B"),
#         (r"\bThe Morning Show\b",             "original content title C"),
#         (r"\bSlow Horses\b",                  "original content title D"),
#         (r"\bThe Instigators\b",              "original content title E"),
#         (r"\bMatt Damon\b",                   "a prominent talent"),
#         (r"\bTim Cook\b",                     "the CEO"),
#         (r"\bLuca Maestri\b",                 "the outgoing CFO"),
#         (r"\bKevan Parekh\b",                 "the incoming CFO"),
#         (r"\bSuhasini Chandramouli\b",        "the IR Director"),
#     ],
#     "TSLA": [
#         (r"\bTesla\b",                        "Meridian Technologies"),
#         (r"\bElon Musk\b",                    "the CEO"),
#         (r"\bFull Self.Driving\b",            "the autonomous driving system"),
#         (r"\bAutopilot\b",                    "the driver assistance system"),
#         (r"\bCybertruck\b",                   "Device A"),
#         (r"\bModel [SXY3]\b",                "Device B"),
#         (r"\bRoadster\b",                     "Device C"),
#         (r"\bMegapack\b",                     "the grid storage product"),
#         (r"\bPowerwall\b",                    "the home storage product"),
#         (r"\bSupercharger\b",                 "the charging network"),
#         (r"\bDojo\b",                         "the AI training system"),
#         (r"\bOptimus\b",                      "the robotics platform"),
#         (r"\bGigafactory\b",                  "the manufacturing facility"),
#     ],
#     "AMPX": [
#         (r"\bAmprius\b",                      "Meridian Technologies"),
#         (r"\bSilicon Anode\b",                "the advanced anode technology"),
#     ],
#     "EOSE": [
#         (r"\bEos Energy\b",                   "Meridian Technologies"),
#         (r"\bZnyth\b",                        "the zinc-based storage system"),
#         (r"\bAquous\b",                       "the aqueous battery platform"),
#     ],
#     "SPWR": [
#         (r"\bSunPower\b",                     "Meridian Technologies"),
#         (r"\bMaxeon\b",                       "the high-efficiency panel technology"),
#         (r"\bSunVault\b",                     "the home storage system"),
#         (r"\bInfinityGuard\b",                "the warranty program"),
#     ],
#     "TTD": [
#         (r"\bThe Trade Desk\b",               "Meridian Technologies"),
#         (r"\bOpenPath\b",                     "the supply-side integration"),
#         (r"\bUID2\b",                         "the identity solution"),
#         (r"\bKoa\b",                          "the AI bidding system"),
#         (r"\bSolimar\b",                      "the campaign management platform"),
#         (r"\bConnected TV\b",                 "the streaming TV channel"),
#         (r"\bCTV\b",                          "the streaming TV channel"),
#     ],
# }
#
# # Analyst firm names — applied to all tickers
# ANALYST_FIRM_SCRUB: list[str] = [
#     "Morgan Stanley", "Goldman Sachs", "JPMorgan", "JP Morgan",
#     "Bank of America", "Citigroup", "Citi", "Wells Fargo", "Barclays",
#     "UBS", "Deutsche Bank", "Credit Suisse", "Evercore", "Melius",
#     "TD Cowen", "Cowen", "Needham", "Piper Sandler", "Canaccord",
#     "Arete Research", "Bernstein", "Raymond James", "Jefferies",
#     "Oppenheimer", "Mizuho", "RBC Capital", "Truist", "KeyBanc",
# ]
#
#
# def regex_prescrub(text: str, ticker: str) -> str:
#     """
#     Stage 0 — Deterministic regex replacement of known trademarks and brand names.
#     Runs before any Claude call. Zero hallucination risk.
#     Returns scrubbed text.
#     """
#     # Always replace the ticker symbol itself
#     text = re.sub(rf'\b{re.escape(ticker)}\b', 'MRID', text, flags=re.IGNORECASE)
#
#     # Ticker-specific trademark patterns
#     for pattern, replacement in TRADEMARK_SCRUB.get(ticker, []):
#         text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
#
#     # Analyst firm names — number them in order of first appearance
#     firm_map: dict[str, str] = {}
#     firm_counter = 1
#
#     def replace_firm(m: re.Match) -> str:
#         nonlocal firm_counter
#         firm = m.group(0)
#         key = firm.lower()
#         if key not in firm_map:
#             firm_map[key] = f"Firm {firm_counter}"
#             firm_counter += 1
#         return firm_map[key]
#
#     for firm in sorted(ANALYST_FIRM_SCRUB, key=len, reverse=True):  # longest first
#         text = re.sub(rf'\b{re.escape(firm)}\b', replace_firm, text, flags=re.IGNORECASE)
#
#     return text
#
#
# # Pass 2 — Financial scrub prompt (hardcoded — mechanical rules, no need to externalize)
# FINANCIAL_SCRUB_PROMPT = """You are a financial data scrubbing engine. Your sole output is the scrubbed transcript text. No preamble, no explanation, no markdown.
#
# You will receive an earnings call transcript that has already had names and products anonymized. Your job is to destroy all remaining financial fingerprints that could identify the company by cross-referencing against public filings.
#
# Apply these rules to EVERY number in the transcript:
#
# REVENUE AND DOLLAR FIGURES
# - Any dollar figure over $10B: round to nearest $2B
# - Any dollar figure $1B–$10B: round to nearest $500M
# - Any dollar figure under $1B: round to nearest $50M
# - Apply to ALL mentions: quarterly revenue, segment revenue, services revenue, guidance, cash balance, debt, buybacks, dividends, capex
#
# EPS
# - Round all EPS figures to nearest $0.10
#
# MARGINS AND PERCENTAGES  
# - Round all margin percentages (gross, operating, net) to nearest 2 percentage points
# - Round all growth rates (YoY, QoQ) to nearest 2 percentage points
# - Round all guidance ranges to nearest 1 percentage point
#
# UNIT COUNTS AND INSTALLED BASE
# - Any figure over 2 billion: replace with "multiple billions"
# - Any figure 1B–2B: replace with "over one billion"
# - Any figure 500M–1B: replace with "approaching one billion"
# - Any figure under 500M: replace with "hundreds of millions"
# - This applies to: active devices, subscribers, paid accounts, app counts, store counts
#
# SHARE COUNTS AND BUYBACKS
# - Share counts: round to nearest 10 million shares
# - Buyback dollar amounts: round to nearest $2B
#
# SPECIFIC DATES IN FINANCIAL CONTEXT
# - Keep quarter references (Q1, Q2, Q3, Q4) and fiscal years
# - Keep call date
# - Remove specific payment dates (e.g. "payable August 15") — replace with "payable next month"
#
# AWARD COUNTS AND NOMINATIONS
# - Replace all specific award nomination counts with "multiple award nominations"
#
# PRESERVE — do not change these:
# - Directional language: "up", "down", "grew", "declined", "accelerated", "decelerated"
# - Relative comparisons: "above", "below", "in line with"
# - Management tone and qualitative statements
# - Analyst questions and the substance of management answers
# - The structure and flow of the transcript
#
# Return ONLY the scrubbed transcript. No preamble. No explanation. No markdown.
#
# TRANSCRIPT TO SCRUB:
# """
#
#
# def load_anonymize_prompt(prompt_path=None):
#     """Load the Stage 1 anonymization prompt from an external .md file."""
#     candidates = []
#     if prompt_path:
#         candidates.append(Path(prompt_path))
#     candidates.append(script_dir / "ANON_PROMPT.md")
#
#     for path in candidates:
#         if path.exists():
#             print(f"  Using anonymization prompt: {path}")
#             text = path.read_text()
#             # Strip markdown code fences if present
#             text = re.sub(r'^```[^\n]*\n', '', text, flags=re.MULTILINE)
#             text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)
#             return text.strip()
#
#     raise FileNotFoundError(
#         "Cannot find anonymization prompt. "
#         "Expected at analysis/ANON_PROMPT.md or pass --anon-prompt <path>"
#     )
#
#
# def anonymize_transcript(client, raw_text, ticker, company_name, anon_prompt):
#     """
#     3-stage anonymization pipeline.
#       Stage 0: Regex pre-scrub (deterministic, no API call)
#       Stage 1: Structural rewrite via Claude (ANON_PROMPT.md)
#       Stage 2: Financial scrub via Claude (FINANCIAL_SCRUB_PROMPT)
#     Returns fully anonymized text.
#     """
#     # ── Stage 0: Regex pre-scrub ─────────────────────────────────────────────
#     print(f"    Stage 0 — regex pre-scrub ({len(raw_text):,} chars)...", end=" ", flush=True)
#     text = regex_prescrub(raw_text, ticker)
#     print("done")
#
#     # ── Stage 1: Structural rewrite ──────────────────────────────────────────
#     print(f"    Stage 1 — structural rewrite ({len(text):,} chars)...", end=" ", flush=True)
#     response = client.messages.create(
#         model=MODEL,
#         max_tokens=8192,
#         messages=[{"role": "user", "content": anon_prompt + "\n\n" + text}]
#     )
#     text = response.content[0].text.strip()
#     print(f"done ({len(text):,} chars)")
#
#     # ── Stage 2: Financial scrub ─────────────────────────────────────────────
#     print(f"    Stage 2 — financial scrub ({len(text):,} chars)...", end=" ", flush=True)
#     response = client.messages.create(
#         model=MODEL,
#         max_tokens=8192,
#         messages=[{"role": "user", "content": FINANCIAL_SCRUB_PROMPT + "\n\n" + text}]
#     )
#     text = response.content[0].text.strip()
#     print(f"done ({len(text):,} chars)")
#
#     return text
#
#
# ---------------------------------------------------------------------------
# END ANONYMIZATION PIPELINE
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def load_evaluation_prompt():
    """Load the evaluation prompt from docs/. Returns (text, version, path)."""
    import re
    candidates = [
        script_dir.parent / "docs" / "EVALUATION_PROMPT.md",
        script_dir.parent / "server" / "docs" / "EVALUATION_PROMPT.md",
        Path("/mnt/project/EVALUATION_PROMPT.md"),
    ]
    for path in candidates:
        if path.exists():
            text = path.read_text()
            match = re.search(r"^#\s*Version:\s*(.+)$", text, re.MULTILINE)
            version = match.group(1).strip() if match else "unknown"
            return text, version, path
    raise FileNotFoundError(
        "Cannot find EVALUATION_PROMPT.md. Expected at docs/EVALUATION_PROMPT.md"
    )


def evaluate_transcript(client, transcript_text, evaluation_prompt):
    """Run the transcript through the evaluator. Returns raw output."""
    print(f"    Evaluating...", end=" ", flush=True)

    full_prompt = (
        evaluation_prompt.strip()
        + "\n\n---\n\nTRANSCRIPT:\n\n"
        + transcript_text
    )

    response = client.messages.create(
        model=MODEL,
        # Raised from 4096 -> 8192 on 2026-07-05 (v10 gate): v9's longer
        # required narrative (5-step stumble test, 3 named sub-scores)
        # pushed some completions right up against 4096, causing
        # intermittent stop_reason=max_tokens truncation before the
        # ---STRUCTURED--- block -- same transcript, same prompt,
        # temperature=0, truncated in one run and not in another. See
        # EVALUATION_PROMPT.md v10 iteration log entry.
        max_tokens=8192,
        temperature=0,
        messages=[{
            "role": "user",
            "content": full_prompt
        }]
    )
    result = response.content[0].text.strip()
    if response.stop_reason == "max_tokens":
        # Response was cut off before the model finished -- if the
        # ---STRUCTURED--- block is missing downstream, this is why:
        # truncation, not a formatting/instruction-following miss. Longer
        # prompts (more required narrative sections, explicit sub-scoring)
        # push completions closer to the 4096 ceiling.
        print(f"done (⚠️  stop_reason=max_tokens, {response.usage.output_tokens} output tokens)")
    else:
        print(f"done (stop_reason={response.stop_reason})")
    return result


# ---------------------------------------------------------------------------
# Structured score extraction
# ---------------------------------------------------------------------------

def parse_structured_score(raw_output):
    """Extract the ---STRUCTURED--- JSON block from evaluator output."""
    match = re.search(
        r'---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---',
        raw_output,
        re.DOTALL
    )
    if not match:
        print("    ⚠️  No structured block found in evaluator output")
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"    ⚠️  JSON parse error in structured block: {e}")
        return {}


# ---------------------------------------------------------------------------
# Price data
# ---------------------------------------------------------------------------

def next_trading_day(date, prices_index):
    """
    Given a date and a DatetimeIndex of trading days,
    return the nearest trading day on or after the date.
    """
    # Normalize to date only
    if hasattr(date, 'date'):
        date = date.date()
    target = pd.Timestamp(date)
    # Find first index entry >= target
    candidates = prices_index[prices_index >= target]
    if len(candidates) == 0:
        return None
    return candidates[0]


def fetch_prices(ticker, start_date, end_date):
    """
    Fetch daily closing prices for ticker and SPY between start and end dates.
    Returns a DataFrame with columns [ticker, SPY].
    Adds a buffer of 10 days on each side to ensure trading day availability.
    """
    start = (pd.Timestamp(start_date) - pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    end = (pd.Timestamp(end_date) + pd.Timedelta(days=10)).strftime('%Y-%m-%d')

    data = yf.download(
        [ticker, 'SPY'],
        start=start,
        end=end,
        auto_adjust=True,
        progress=False
    )['Close']

    # Flatten MultiIndex if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1) if data.columns.nlevels > 1 else data.columns

    return data


def get_price_on_date(prices_df, ticker, target_date):
    """Get closing price for ticker on the next trading day >= target_date."""
    col = ticker if ticker in prices_df.columns else None
    if col is None:
        return None
    trading_day = next_trading_day(target_date, prices_df.index)
    if trading_day is None:
        return None
    try:
        return float(prices_df.loc[trading_day, col])
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main backtest logic
# ---------------------------------------------------------------------------

def run_backtest(symbol_filter=None, dry_run=False, save_transcripts=False, save_evals=False):
    conn = get_connection()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        evaluation_prompt, prompt_version, prompt_path = load_evaluation_prompt()
        print(f"Prompt: {prompt_path.name}  version: {prompt_version}")
    except FileNotFoundError as e:
        print(f"❌  {e}")
        conn.close()
        sys.exit(1)

    tickers = fetch_portfolio_tickers(conn, symbol_filter)
    if not tickers:
        print(f"❌  No portfolio tickers found{' for ' + symbol_filter if symbol_filter else ''}.")
        conn.close()
        sys.exit(1)

    print(f"\nBacktest runner — {len(tickers)} ticker(s)\n")

    all_rows = []

    for ticker_row in tickers:
        symbol = ticker_row['symbol']
        company = ticker_row['name'] or symbol
        print(f"\n{'='*60}")
        print(f"  {symbol} — {company}")
        print(f"{'='*60}")

        transcripts = fetch_transcripts_for_ticker(conn, ticker_row['id'])
        print(f"  {len(transcripts)} transcript(s) found")

        if len(transcripts) < 2:
            print(f"  ⚠️  Skipping — need at least 2 transcripts for one forward-return window")
            continue

        # Fetch price data for the full date range + 90-day forward window
        earliest = transcripts[0]['callDate']
        latest = transcripts[-1]['callDate']
        forward_end = pd.Timestamp(latest) + pd.Timedelta(days=FORWARD_DAYS + 15)

        print(f"  Fetching price data {earliest.date()} → {forward_end.date()}...", end=" ", flush=True)
        try:
            prices = fetch_prices(symbol, earliest, forward_end)
            print("done")
        except Exception as e:
            print(f"❌  Price fetch failed: {e}")
            continue

        for i, transcript in enumerate(transcripts):
            call_date = transcript['callDate']
            title = transcript['title']
            print(f"\n  [{i+1}/{len(transcripts)}] {title}")
            print(f"  Call date: {call_date.date()}")

            raw_text = transcript['rawText']

            if save_transcripts:
                tx_dir = OUTPUT_DIR / "transcripts"
                tx_dir.mkdir(exist_ok=True)
                tx_filename = tx_dir / f"{symbol}_{call_date.date()}.txt"
                tx_filename.write_text(raw_text)
                print(f"    Saved transcript → {tx_filename}")

            # --- Evaluate ---
            try:
                raw_output = evaluate_transcript(client, raw_text, evaluation_prompt)
            except Exception as e:
                print(f"    ❌  Evaluation failed: {e}")
                continue

            if dry_run:
                print("\n--- EVALUATION OUTPUT (first 2000 chars) ---")
                print(raw_output[:2000])
                print("--- END ---\n")
                print("Dry run complete. Exiting.")
                conn.close()
                return

            if save_evals:
                evals_dir = OUTPUT_DIR / "evals"
                evals_dir.mkdir(exist_ok=True)
                eval_filename = evals_dir / f"{symbol}_{call_date.date()}.txt"
                eval_filename.write_text(raw_output)
                print(f"    Saved eval → {eval_filename}")

            # --- Parse structured score ---
            score = parse_structured_score(raw_output)

            # --- Price at call date ---
            price_at_call = get_price_on_date(prices, symbol, call_date)
            spy_at_call = get_price_on_date(prices, 'SPY', call_date)

            # --- Price 90 days forward ---
            forward_date = pd.Timestamp(call_date) + pd.Timedelta(days=FORWARD_DAYS)
            price_forward = get_price_on_date(prices, symbol, forward_date)
            spy_forward = get_price_on_date(prices, 'SPY', forward_date)

            # --- Compute returns ---
            ticker_return = None
            spy_return = None
            relative_return = None
            signal_correct = None

            if price_at_call and price_forward:
                ticker_return = round((price_forward - price_at_call) / price_at_call * 100, 2)
            if spy_at_call and spy_forward:
                spy_return = round((spy_forward - spy_at_call) / spy_at_call * 100, 2)
            if ticker_return is not None and spy_return is not None:
                relative_return = round(ticker_return - spy_return, 2)

            # --- Signal correctness ---
            # Add: outperformed SPY → correct signal
            # Hold: within ±5% of SPY → correct signal
            # Trim/Exit: underperformed SPY → correct signal
            rec = score.get('recommendation', '')
            if relative_return is not None and rec:
                if rec == 'Add':
                    signal_correct = relative_return > 0
                elif rec == 'Hold':
                    signal_correct = abs(relative_return) <= 5
                elif rec in ('Trim', 'Exit'):
                    signal_correct = relative_return < 0
                else:
                    signal_correct = None

            row = {
                'ticker': symbol,
                'call_date': call_date.date(),
                'transcript_title': title,
                'recommendation': score.get('recommendation'),
                'thesis_health': score.get('thesisHealth'),
                'thesis_delta': score.get('thesisDelta'),
                'type_classification': score.get('typeClassification'),
                'stumble_type': score.get('stumbleType'),
                'threat_mechanism_impaired': score.get('threatMechanismImpaired'),
                'credibility_delta': score.get('credibilityDelta'),
                'ratchet_tranche': score.get('ratchetTranche'),
                'fresh_money_allocation': score.get('freshMoneyAllocation'),
                'recommended_size': score.get('recommendedSize'),
                'cap_percent': score.get('capPercent'),
                'mitigation_argument_present': score.get('mitigationArgumentPresent'),
                'mitigation_track_record': score.get('mitigationCapabilityTrackRecord'),
                'blind_spots_triggered': json.dumps(score.get('blindSpotsTriggered', [])),
                'active_driver_count': score.get('activeDriverCount'),
                'price_at_call': price_at_call,
                'spy_at_call': spy_at_call,
                'price_forward_90d': price_forward,
                'spy_forward_90d': spy_forward,
                'forward_date': forward_date.date(),
                'ticker_return_pct': ticker_return,
                'spy_return_pct': spy_return,
                'relative_return_pct': relative_return,
                'signal_correct': signal_correct,
                'prompt_version': prompt_version,
            }

            all_rows.append(row)

            # Rate limit: be kind to the API
            time.sleep(2)

        print(f"\n  ✅  {symbol} complete")

    conn.close()

    if not all_rows:
        print("\n❌  No rows produced.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(['ticker', 'call_date'])

    today = datetime.date.today().isoformat()
    # When running a single ticker, include the symbol in the filename
    # to prevent sequential single-ticker runs from overwriting each other.
    if symbol_filter:
        output_path = OUTPUT_DIR / f"backtest_{today}_{symbol_filter.upper()}.csv"
    else:
        output_path = OUTPUT_DIR / f"backtest_{today}.csv"
    df.to_csv(output_path, index=False)

    print(f"\n{'='*60}")
    print(f"✅  Wrote {len(df)} rows → {output_path}")
    print(f"\nSignal accuracy summary:")
    scored = df[df['signal_correct'].notna()].copy()
    scored['signal_correct'] = scored['signal_correct'].astype(float)
    if scored.empty:
        print("  No scored rows (all transcripts may be the last in their ticker window)")
    else:
        summary = scored.groupby('ticker')['signal_correct'].agg(correct='sum', total='count')
        summary['accuracy_pct'] = (summary['correct'] / summary['total'] * 100).round(1)
        print(summary.to_string())
        overall_correct = scored['signal_correct'].sum()
        overall_total = len(scored)
        print(f"\nOverall: {overall_correct:.0f}/{overall_total} "
              f"= {overall_correct/overall_total*100:.1f}% correct")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Backtest the Portfolio Analyst evaluator against historical transcripts."
    )
    parser.add_argument(
        '--ticker',
        help='Run only for this ticker symbol (e.g. AAPL)',
        default=None
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Evaluate first transcript only, print result, then exit'
    )
    parser.add_argument(
        '--save-transcripts',
        action='store_true',
        help='Save raw transcripts being evaluated to analysis/data/transcripts/'
    )
    parser.add_argument(
        '--save-evals',
        action='store_true',
        help='Save full evaluator narrative to analysis/data/evals/<TICKER>_<date>.txt'
    )
    args = parser.parse_args()

    print(f"Backtest runner v{VERSION}")
    print(f"Save evals: {args.save_evals}")
    run_backtest(
        symbol_filter=args.ticker,
        dry_run=args.dry_run,
        save_transcripts=args.save_transcripts,
        save_evals=args.save_evals,
    )


if __name__ == '__main__':
    main()

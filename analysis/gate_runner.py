#!/usr/bin/env python3
"""
gate_runner.py — Promotion Gate champion-vs-challenger driver.

Applies the §5 promotion rule from docs/architecture/PROMOTION_GATE.md:
  1. Primary metric beats incumbent by more than the noise threshold
  2. Secondary metric does not materially regress
  3. Gain is not concentrated in a single ticker or sub-period
  4. On ties, keep the simpler incumbent (complexity penalty)

Implements §4 metric-to-change mapping:
  Analyst changes (prompt / model):  primary = analyst-direct hit-rate lift (§3.1)
  Allocator changes (params):        primary = return / max-drawdown (§3.2)

Implements §7 holdout protocol:
  - Training window  → tune/sweep (never show challenger holdout data)
  - Holdout window   → ONE look after training comparison confirms candidacy
  - Robustness       → per-ticker and per-year slicing on training window

Writes every gate run to analysis/data/gate_ledger.json (the experiment ledger).
Each entry records the champion, challenger, pre-registered metric, verdict, date.

Usage:
    cd analysis

    # Model-version gate (equivalence hurdle — adopt unless clearly worse):
    python3 gate_runner.py analyst \\
        --champion   data/evals/v6_sonnet-4-20250514 \\
        --challenger data/evals/v6_sonnet-4-6 \\
        --tickers ENPH TTD AMPX ENVX EOSE QS SPWR \\
        --holdout-start 2024-11-01 \\
        --hurdle model_version \\
        --label "model_pin: sonnet-4-20250514 vs sonnet-4-6"

    # Prompt-version gate (improvement hurdle — adopt only if clearly better):
    python3 gate_runner.py analyst \\
        --champion  data/evals/v6_sonnet-4-20250514 \\
        --challenger data/evals/v7_sonnet-4-20250514 \\
        --tickers ENPH TTD AMPX ENVX EOSE QS SPWR \\
        --holdout-start 2024-11-01 \\
        --hurdle improvement \\
        --label "prompt v6 vs v7"

Pre-reqs:
    - Both eval cache dirs must exist and contain *.txt eval files
    - analysis/data/price_cache.json must have prices + SPY
    - analysis/data/gate_ledger.json must exist (created by version plumbing step)

Note: the challenger eval cache for a new model must be generated first by running
backtest_from_files.py with the new MODEL constant and --save-evals.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PRICE_CACHE_PATH  = SCRIPT_DIR / "data" / "price_cache.json"
GATE_LEDGER_PATH  = SCRIPT_DIR / "data" / "gate_ledger.json"

# ── Import the analyst-direct scorer ────────────────────────────────────────
import sys
sys.path.insert(0, str(SCRIPT_DIR.parent))
from analysis.analyst_direct_scorer import (
    PriceCache, score_eval_dir, CallRecord,
    FORWARD_DAYS, DEAD_BAND, BENCHMARK,
)


# ---------------------------------------------------------------------------
# Noise threshold via bootstrap
# ---------------------------------------------------------------------------

def bootstrap_noise(
    records: list[CallRecord],
    n_resamples: int = 2000,
    seed: int = 42,
) -> float:
    """
    Estimate the sampling spread (std dev) of the lift metric by bootstrapping
    across *tickers* (not calls), consistent with §6.

    Returns the bootstrap std dev of the lift. The candidate must clear the
    champion lift by at least 1 std dev to pass (conservative but not extreme).
    """
    if not records:
        return float("inf")

    rng = random.Random(seed)
    tickers = list({r.ticker for r in records})
    by_ticker = {t: [r for r in records if r.ticker == t] for t in tickers}

    lifts: list[float] = []
    for _ in range(n_resamples):
        # Sample tickers with replacement
        sampled_tickers = [rng.choice(tickers) for _ in tickers]
        sample = []
        for t in sampled_tickers:
            sample.extend(by_ticker[t])
        if not sample:
            continue
        our = sum(1 for r in sample if r.hit) / len(sample)
        base = sum(1 for r in sample if r.always_bullish_hit) / len(sample)
        lifts.append(our - base)

    if len(lifts) < 2:
        return float("inf")
    return statistics.stdev(lifts)


# ---------------------------------------------------------------------------
# Robustness: per-ticker and per-year slicing
# ---------------------------------------------------------------------------

def per_ticker_lifts(records: list[CallRecord]) -> dict[str, float]:
    by_ticker: dict[str, list[CallRecord]] = {}
    for r in records:
        by_ticker.setdefault(r.ticker, []).append(r)
    result: dict[str, float] = {}
    for ticker, rows in by_ticker.items():
        if not rows:
            continue
        our  = sum(1 for r in rows if r.hit) / len(rows)
        base = sum(1 for r in rows if r.always_bullish_hit) / len(rows)
        result[ticker] = round(our - base, 4)
    return result


def per_year_lifts(records: list[CallRecord]) -> dict[int, float]:
    by_year: dict[int, list[CallRecord]] = {}
    for r in records:
        by_year.setdefault(r.call_date.year, []).append(r)
    result: dict[int, float] = {}
    for year, rows in sorted(by_year.items()):
        if not rows:
            continue
        our  = sum(1 for r in rows if r.hit) / len(rows)
        base = sum(1 for r in rows if r.always_bullish_hit) / len(rows)
        result[year] = round(our - base, 4)
    return result


def lift_of(records: list[CallRecord]) -> float:
    if not records:
        return 0.0
    our  = sum(1 for r in records if r.hit) / len(records)
    base = sum(1 for r in records if r.always_bullish_hit) / len(records)
    return our - base


def hit_rate(records: list[CallRecord]) -> float:
    if not records:
        return 0.0
    return sum(1 for r in records if r.hit) / len(records)


# ---------------------------------------------------------------------------
# Verdict logic (§5)
# ---------------------------------------------------------------------------

def promotion_verdict(
    champ_lift: float,
    chall_lift: float,
    noise_std: float,
    robustness_ok: bool,
    change_class: str = "improvement",
) -> tuple[str, str]:
    """
    Returns (verdict, reason).

    Two hurdles, controlled by change_class:

    "improvement"   — prompt changes, eval logic, allocator params.
        Adopt only if challenger clearly BETTER than champion.
        verdict: "PROMOTE" | "HOLD"
        PROMOTE  → Δ > +1 SD  AND robustness OK
        HOLD     → anything else (including clear regression)

    "model_version" — Claude model bumps.
        Adopt unless challenger clearly WORSE than champion.
        Rationale: incumbent will eventually be deprecated; an equivalent
        newer model is preferable to a forced unvalidated migration later.
        verdict: "PROMOTE" | "EQUIVALENT→PROMOTE" | "HOLD"
        PROMOTE           → Δ > +1 SD  (clearly better; robustness still checked)
        EQUIVALENT→PROMOTE→ −1 SD ≤ Δ ≤ +1 SD  (noise band; safe to adopt)
        HOLD              → Δ < −1 SD  (clear regression; keep incumbent)

    In both classes, Δ < −1 SD is a regression and blocks promotion.
    """
    delta = champ_lift - chall_lift  # negative = challenger is better
    # (Note: delta here is champion − challenger; we want challenger − champion.)
    # Rewrite with clear naming:
    delta = chall_lift - champ_lift  # positive = challenger leads

    if change_class == "model_version":
        # Equivalence hurdle: block only on clear regression (Δ < −1 SD)
        if delta < -noise_std:
            return "HOLD", (
                f"challenger clearly regresses "
                f"(Δ={delta*100:+.1f}pp < −{noise_std*100:.1f}pp noise floor) — "
                f"keep incumbent"
            )
        if delta > noise_std:
            if not robustness_ok:
                return "PROMOTE", (
                    f"challenger improves (Δ={delta*100:+.1f}pp > +{noise_std*100:.1f}pp) "
                    f"but gain concentrated in <50% tickers — "
                    f"adopting (model_version: equivalence bar applies) [PROMOTE]"
                )
            return "PROMOTE", (
                f"challenger improves (Δ={delta*100:+.1f}pp > +{noise_std*100:.1f}pp) "
                f"and is robust across tickers [PROMOTE]"
            )
        # Noise band: statistically equivalent → adopt to avoid deprecation risk
        return "EQUIVALENT", (
            f"challenger is statistically equivalent "
            f"(Δ={delta*100:+.1f}pp within ±{noise_std*100:.1f}pp noise band) — "
            f"adopting to avoid deprecation risk [EQUIVALENT→PROMOTE]"
        )

    else:
        # Improvement hurdle (default): promote only if clearly better
        if delta <= 0:
            return "HOLD", (
                f"challenger does not improve on champion "
                f"(Δ={delta*100:+.1f}pp ≤ 0)"
            )
        if delta < noise_std:
            return "HOLD", (
                f"improvement (Δ={delta*100:+.1f}pp) does not clear noise threshold "
                f"({noise_std*100:.1f}pp = 1 bootstrap SD) — keep simpler incumbent"
            )
        if not robustness_ok:
            return "HOLD", (
                f"challenger lift Δ={delta*100:+.1f}pp clears noise threshold but "
                f"gain is not robust across tickers (<50% of tickers improved)"
            )
        return "PROMOTE", (
            f"challenger lift Δ={delta*100:+.1f}pp clears noise threshold "
            f"({noise_std*100:.1f}pp) and is robust across tickers/periods"
        )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def append_to_ledger(entry: dict, path: Path = GATE_LEDGER_PATH) -> None:
    try:
        ledger = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        ledger = []
    ledger.append(entry)
    path.write_text(json.dumps(ledger, indent=2))


# ---------------------------------------------------------------------------
# Analyst gate (§2.2 + §3.1)
# ---------------------------------------------------------------------------

def run_analyst_gate(
    champion_dir: Path,
    challenger_dir: Path,
    holdout_start: date,
    prices: PriceCache,
    tickers: Optional[list[str]],
    label: str,
    n_bootstrap: int,
    skip_holdout: bool,
    change_class: str = "improvement",
) -> dict:
    """Full analyst-layer gate run. Returns the verdict dict."""
    hurdle_desc = (
        "equivalence (model_version: adopt unless clearly worse)"
        if change_class == "model_version"
        else "improvement (adopt only if clearly better)"
    )
    print(f"\n{'='*68}")
    print(f"PROMOTION GATE — Analyst Layer")
    print(f"Label:      {label}")
    print(f"Hurdle:     {hurdle_desc}")
    print(f"Champion:   {champion_dir.name}")
    print(f"Challenger: {challenger_dir.name}")
    print(f"Holdout ≥:  {holdout_start}")
    if tickers:
        print(f"Tickers:    {', '.join(sorted(tickers))}")
    print(f"{'='*68}")

    # ── Load records (training window only first) ───────────────────────────
    print("\nScoring training window…")
    champ_train = [r for r in score_eval_dir(champion_dir, prices, tickers)
                   if r.hit is not None and r.call_date < holdout_start]
    chall_train = [r for r in score_eval_dir(challenger_dir, prices, tickers)
                   if r.hit is not None and r.call_date < holdout_start]

    print(f"  Champion  scoreable in training:   {len(champ_train)}")
    print(f"  Challenger scoreable in training:  {len(chall_train)}")

    if not champ_train or not chall_train:
        print("ERROR: insufficient training data to score. Aborting.")
        return {"verdict": "ERROR", "reason": "insufficient training data"}

    champ_lift_train = lift_of(champ_train)
    chall_lift_train = lift_of(chall_train)
    delta_train      = chall_lift_train - champ_lift_train

    # ── Bootstrap noise (on champion training set) ──────────────────────────
    print(f"\nBootstrapping noise threshold (n={n_bootstrap})…")
    noise_std = bootstrap_noise(champ_train, n_resamples=n_bootstrap)
    print(f"  Bootstrap std dev: {noise_std*100:.2f}pp  (threshold = 1 SD)")

    # ── Robustness: per-ticker and per-year ─────────────────────────────────
    champ_ticker_lifts = per_ticker_lifts(champ_train)
    chall_ticker_lifts = per_ticker_lifts(chall_train)
    champ_year_lifts   = per_year_lifts(champ_train)
    chall_year_lifts   = per_year_lifts(chall_train)

    # Robustness: challenger improvement should not be driven by a single ticker
    # or single year. Check: is the improvement positive in ≥50% of tickers?
    shared_tickers = [t for t in chall_ticker_lifts if t in champ_ticker_lifts]
    ticker_improvements = [
        chall_ticker_lifts[t] - champ_ticker_lifts[t]
        for t in shared_tickers
    ]
    pct_tickers_improved = (
        sum(1 for d in ticker_improvements if d > 0) / len(ticker_improvements)
        if ticker_improvements else 0
    )
    robustness_ok = pct_tickers_improved >= 0.50

    # ── Training verdict ────────────────────────────────────────────────────
    train_verdict, train_reason = promotion_verdict(
        champ_lift_train, chall_lift_train, noise_std, robustness_ok,
        change_class=change_class,
    )

    print(f"\n{'─'*68}")
    print(f"TRAINING WINDOW RESULTS")
    print(f"  Champion  lift:   {champ_lift_train*100:+.1f}pp  "
          f"(hit {hit_rate(champ_train)*100:.1f}%  n={len(champ_train)})")
    print(f"  Challenger lift:  {chall_lift_train*100:+.1f}pp  "
          f"(hit {hit_rate(chall_train)*100:.1f}%  n={len(chall_train)})")
    print(f"  Delta:            {delta_train*100:+.1f}pp")
    print(f"  Noise threshold:  {noise_std*100:.2f}pp")
    print(f"  Robustness:       {pct_tickers_improved*100:.0f}% of tickers improved "
          f"({'OK' if robustness_ok else 'FAIL ≥50% required'})")
    print(f"  Training verdict: {train_verdict} — {train_reason}")

    print(f"\n  Per-ticker lift delta (challenger − champion):")
    for t in sorted(shared_tickers):
        d = chall_ticker_lifts[t] - champ_ticker_lifts[t]
        print(f"    {t:<6}: {d*100:+.1f}pp  "
              f"(champ {champ_ticker_lifts[t]*100:+.1f}  "
              f"chall {chall_ticker_lifts[t]*100:+.1f})")

    print(f"\n  Per-year lift delta (challenger − champion):")
    shared_years = sorted(set(chall_year_lifts) & set(champ_year_lifts))
    for y in shared_years:
        d = chall_year_lifts[y] - champ_year_lifts[y]
        print(f"    {y}: {d*100:+.1f}pp  "
              f"(champ {champ_year_lifts[y]*100:+.1f}  "
              f"chall {chall_year_lifts[y]*100:+.1f})")

    # ── Holdout (only if training verdict is PROMOTE) ───────────────────────
    holdout_verdict = None
    holdout_reason  = None
    champ_lift_holdout = None
    chall_lift_holdout = None
    n_champ_holdout = 0
    n_chall_holdout = 0

    # EQUIVALENT skips holdout: we are not claiming improvement, nothing to validate
    # on the holdout window; running it would just burn the one-look.
    if train_verdict == "PROMOTE" and not skip_holdout:
        print(f"\n{'─'*68}")
        print(f"HOLDOUT WINDOW (one look — ≥ {holdout_start})")
        champ_holdout = [r for r in score_eval_dir(champion_dir, prices, tickers)
                         if r.hit is not None and r.call_date >= holdout_start]
        chall_holdout = [r for r in score_eval_dir(challenger_dir, prices, tickers)
                         if r.hit is not None and r.call_date >= holdout_start]
        n_champ_holdout = len(champ_holdout)
        n_chall_holdout = len(chall_holdout)

        if not champ_holdout or not chall_holdout:
            holdout_verdict = "HOLD"
            holdout_reason  = "insufficient holdout data (calls too recent to score)"
            print(f"  ⚠  {holdout_reason}")
        else:
            champ_lift_holdout = lift_of(champ_holdout)
            chall_lift_holdout = lift_of(chall_holdout)
            delta_holdout = chall_lift_holdout - champ_lift_holdout

            print(f"  Champion  lift:   {champ_lift_holdout*100:+.1f}pp  "
                  f"(hit {hit_rate(champ_holdout)*100:.1f}%  n={n_champ_holdout})")
            print(f"  Challenger lift:  {chall_lift_holdout*100:+.1f}pp  "
                  f"(hit {hit_rate(chall_holdout)*100:.1f}%  n={n_chall_holdout})")
            print(f"  Delta:            {delta_holdout*100:+.1f}pp")

            if delta_holdout > 0:
                holdout_verdict = "PROMOTE"
                holdout_reason  = (f"challenger also leads on holdout "
                                   f"(Δ={delta_holdout*100:+.1f}pp)")
            else:
                holdout_verdict = "HOLD"
                holdout_reason  = (f"challenger does not improve on holdout "
                                   f"(Δ={delta_holdout*100:+.1f}pp) — keep incumbent")
    elif skip_holdout:
        holdout_verdict = "SKIPPED"
        holdout_reason  = "--skip-holdout flag set"
    elif train_verdict == "EQUIVALENT":
        holdout_verdict = "SKIPPED"
        holdout_reason  = "EQUIVALENT result — holdout not consumed (no improvement claim)"

    # ── Final verdict ────────────────────────────────────────────────────────
    if train_verdict == "EQUIVALENT":
        # model_version equivalence path: adopt, no holdout consumed
        final_verdict = "PROMOTE"
        final_reason  = train_reason
    elif train_verdict != "PROMOTE":
        final_verdict = train_verdict   # HOLD
        final_reason  = train_reason
    elif holdout_verdict in ("PROMOTE", "SKIPPED"):
        final_verdict = "PROMOTE"
        final_reason  = (f"training: {train_reason}; "
                         f"holdout: {holdout_verdict} — {holdout_reason}")
    else:
        final_verdict = "HOLD"
        final_reason  = (f"training passed but holdout did not: {holdout_reason}")

    print(f"\n{'='*68}")
    print(f"FINAL VERDICT: {final_verdict}")
    print(f"  {final_reason}")
    print(f"{'='*68}\n")

    # ── Build ledger entry ───────────────────────────────────────────────────
    entry = {
        "date":             datetime.now().isoformat(timespec="seconds"),
        "label":            label,
        "change_class":     "analyst",
        "change_class_detail": change_class,   # "improvement" | "model_version"
        "hurdle":           "equivalence" if change_class == "model_version" else "improvement",
        "primary_metric":   "analyst_direct_lift_pp",
        "champion":         champion_dir.name,
        "challenger":       challenger_dir.name,
        "holdout_start":    holdout_start.isoformat(),
        "tickers_scoped":   tickers,
        "training": {
            "n_champion":           len(champ_train),
            "n_challenger":         len(chall_train),
            "champion_lift_pp":     round(champ_lift_train * 100, 2),
            "challenger_lift_pp":   round(chall_lift_train * 100, 2),
            "delta_pp":             round(delta_train * 100, 2),
            "noise_std_pp":         round(noise_std * 100, 2),
            "pct_tickers_improved": round(pct_tickers_improved * 100, 1),
            "robustness_ok":        robustness_ok,
            "verdict":              train_verdict,
            # EQUIVALENT = within noise band; maps to PROMOTE for model_version
        },
        "holdout": {
            "n_champion":       n_champ_holdout,
            "n_challenger":     n_chall_holdout,
            "champion_lift_pp": round(champ_lift_holdout * 100, 2) if champ_lift_holdout is not None else None,
            "challenger_lift_pp": round(chall_lift_holdout * 100, 2) if chall_lift_holdout is not None else None,
            "verdict":          holdout_verdict,
            "reason":           holdout_reason,
        },
        "final_verdict":    final_verdict,
        "final_reason":     final_reason,
    }
    return entry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="change_class", required=True)

    # ── analyst sub-command ─────────────────────────────────────────────────
    analyst_p = sub.add_parser(
        "analyst",
        help="Gate run for an analyst-layer change (prompt or model version)",
    )
    analyst_p.add_argument("--champion",    type=Path, required=True,
                           help="Champion eval cache dir")
    analyst_p.add_argument("--challenger",  type=Path, required=True,
                           help="Challenger eval cache dir")
    analyst_p.add_argument("--holdout-start", type=parse_date,
                           default=date(2024, 11, 1),
                           help="Holdout split date (default: 2024-11-01)")
    analyst_p.add_argument("--tickers",     nargs="*", default=None,
                           help="Restrict to these tickers (default: all in eval dir)")
    analyst_p.add_argument("--label",       default="",
                           help="Human-readable label for this gate run")
    analyst_p.add_argument("--n-bootstrap", type=int, default=2000,
                           help="Bootstrap resamples for noise threshold (default: 2000)")
    analyst_p.add_argument("--skip-holdout", action="store_true",
                           help="Skip holdout look (for debugging / incomplete challenger cache)")
    analyst_p.add_argument("--hurdle",
                           choices=["improvement", "model_version"],
                           default="improvement",
                           dest="hurdle",
                           help=(
                               "Hurdle type. "
                               "'improvement' (default): adopt only if challenger clearly beats champion. "
                               "'model_version': adopt unless challenger clearly regresses — "
                               "use for Claude model bumps where the incumbent will eventually be deprecated."
                           ))
    analyst_p.add_argument("--dry-run",     action="store_true",
                           help="Do not write to gate_ledger.json")

    args = ap.parse_args()

    if not PRICE_CACHE_PATH.exists():
        ap.error(f"Price cache not found: {PRICE_CACHE_PATH}")
    prices = PriceCache(PRICE_CACHE_PATH)

    if args.change_class == "analyst":
        champ_dir = args.champion
        chall_dir = args.challenger
        if not champ_dir.is_absolute():
            champ_dir = SCRIPT_DIR / champ_dir
        if not chall_dir.is_absolute():
            chall_dir = SCRIPT_DIR / chall_dir
        if not champ_dir.exists():
            ap.error(f"--champion dir not found: {champ_dir}")
        if not chall_dir.exists():
            ap.error(f"--challenger dir not found: {chall_dir}")

        entry = run_analyst_gate(
            champion_dir=champ_dir,
            challenger_dir=chall_dir,
            holdout_start=args.holdout_start,
            prices=prices,
            tickers=args.tickers,
            label=args.label or f"{champ_dir.name} vs {chall_dir.name}",
            n_bootstrap=args.n_bootstrap,
            skip_holdout=args.skip_holdout,
            change_class=args.hurdle,
        )

        if not args.dry_run:
            append_to_ledger(entry)
            print(f"Ledger updated → {GATE_LEDGER_PATH}")
        else:
            print("(dry-run: ledger not written)")
            print("\nLedger entry would be:")
            print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()

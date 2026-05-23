"""
allocator_v4.py — v3 + Wall Street consensus as a sizing modifier.

Framing: consensus data does NOT generate alpha (it's already in the price).
But it CAN inform risk-aware sizing by surfacing uncertainty:
  - Few analysts following → unproven name, sparse opinion → smaller cap
  - High target dispersion → fundamental disagreement → smaller cap
  - EPS revisions trending DOWN → leading indicator of multiple compression → smaller cap
  - Our analyst's recommendation strongly disagrees with Street consensus →
    higher uncertainty, regardless of who's right → smaller cap

These multiply onto v3's existing caps (Type A speculative 15%, established 35%,
Type B 50%). Each fired modifier reduces the cap by 30%; multiple fire
multiplicatively.

Designed as a paper test against v3 to see if consensus-aware sizing reduces
drawdowns without much impact on absolute returns. Expected outcome: modest DD
improvement, neutral/slightly-negative return impact.
"""
from __future__ import annotations

import json
from datetime import date as D
from pathlib import Path
from typing import Optional

from .accounts import Portfolio, Trade
from .allocator_v2 import (
    _build_sell_trades, _weighted_cost_basis,
    PROFIT_TAKE_THRESHOLD_PCT, PROFIT_TAKE_REDUCTION_PCT,
    TYPE_A_SPECULATIVE_CAP_PCT, TYPE_A_ESTABLISHED_CAP_PCT, TYPE_B_CAP_PCT,
)
from .allocator_v3 import (
    decide as decide_v3,
    STARTER_PCT_SPECULATIVE, STARTER_PCT_ESTABLISHED,
)


# Sizing modifiers (multiplicative reductions on the cap)
LOW_COVERAGE_THRESHOLD = 5         # < 5 analysts → low coverage
HIGH_DISPERSION_THRESHOLD = 0.25   # CV > 0.25 → high disagreement
CAP_MULT_PER_FIRE = 0.7            # each fired risk signal multiplies cap by 0.7
DISAGREEMENT_THRESHOLD = 2         # rec gap of 2+ levels (Add vs Sell-eq) = strong disagreement


def _consensus_data_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "analyst_consensus_cache.json"


_consensus_cache: Optional[dict] = None


def _load_consensus():
    global _consensus_cache
    if _consensus_cache is None:
        path = _consensus_data_path()
        if path.exists():
            _consensus_cache = json.loads(path.read_text())
        else:
            _consensus_cache = {}
    return _consensus_cache


def _our_rec_to_score(rec: Optional[str]) -> Optional[float]:
    """Map our analyst's per-call rec to the same 1-5 scale yfinance uses
    for recommendationMean (1=Strong Buy, 5=Strong Sell)."""
    if rec == "Add": return 1.5
    if rec == "Hold": return 3.0
    if rec == "Trim": return 4.0
    if rec == "Exit": return 5.0
    return None


def _consensus_modifiers(ticker: str, our_per_call_rec: Optional[str]) -> tuple[float, list[str]]:
    """Compute the multiplicative cap modifier and a list of which signals fired.
    Returns (mult, [reasons])."""
    consensus = _load_consensus().get(ticker, {})
    if not consensus:
        return 1.0, []
    fires = []

    # 1. Low coverage
    n = consensus.get("n_analysts")
    if n is not None and n < LOW_COVERAGE_THRESHOLD:
        fires.append(f"low_coverage_{n}")

    # 2. High target dispersion
    cv = consensus.get("target_dispersion_cv")
    if cv is not None and cv > HIGH_DISPERSION_THRESHOLD:
        fires.append(f"high_dispersion_cv{cv:.2f}")

    # 3. EPS revisions trending down
    rev = consensus.get("recent_eps_revision_dir")
    if rev == -1:
        fires.append("eps_revisions_down")

    # 4. Disagreement with our analyst
    street = consensus.get("recommendation_mean")
    ours = _our_rec_to_score(our_per_call_rec)
    if street is not None and ours is not None:
        if abs(street - ours) >= DISAGREEMENT_THRESHOLD:
            fires.append(f"street_disagreement(us={ours:.1f}_st={street:.1f})")

    mult = CAP_MULT_PER_FIRE ** len(fires)
    return mult, fires


def decide(
    *,
    ticker: str,
    final_action: str,
    recommended_size_pct: Optional[float],
    type_classification: Optional[str],
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
    prices_today: dict[str, float],
    tier: Optional[str] = None,
    is_first_call: bool = False,
    driver_count: Optional[int] = None,
) -> list[Trade]:
    """v4 = v3 with consensus-driven cap modifiers on Add decisions."""
    if day_price is None or day_price <= 0:
        return []

    # Profit-taking and exit/trim/hold logic unchanged from v3 — only Add
    # gets the consensus modifier (since that's what controls position size).
    if final_action != "Add":
        # Defer to v3 for Hold/Trim/Exit/profit-take/etc.
        return decide_v3(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call,
            driver_count=driver_count,
        )

    # For Add: compute the modified cap, then call v3 with a reduced
    # recommended_size_pct so v3's cap logic enforces the smaller target.
    mult, fires = _consensus_modifiers(ticker, our_per_call_rec=final_action)

    # Apply modifier to the recommended size (acts as a virtual cap)
    if recommended_size_pct is not None and mult < 1.0:
        modified_size = recommended_size_pct * mult
    else:
        modified_size = recommended_size_pct

    # Pass through to v3 with modified size
    return decide_v3(
        ticker=ticker, final_action=final_action,
        recommended_size_pct=modified_size,
        type_classification=type_classification,
        portfolio=portfolio, day_price=day_price,
        trade_date=trade_date, prices_today=prices_today,
        tier=tier, is_first_call=is_first_call,
        driver_count=driver_count,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest():
    # Synthetic consensus: AMPX has high dispersion + low coverage.
    # AAPL has high coverage, low dispersion.
    global _consensus_cache
    _consensus_cache = {
        "AMPX": {
            "n_analysts": 3, "mean_target": 15, "current_price": 12,
            "high_target": 25, "low_target": 5,
            "target_dispersion_cv": 0.33, "recommendation_mean": 1.5,
            "recent_eps_revision_dir": 0,
        },
        "AAPL": {
            "n_analysts": 35, "mean_target": 240, "current_price": 220,
            "high_target": 270, "low_target": 200,
            "target_dispersion_cv": 0.07, "recommendation_mean": 2.0,
            "recent_eps_revision_dir": 1,
        },
    }

    # AMPX should fire low_coverage + high_dispersion = 2 fires → 0.7^2 = 0.49
    mult, fires = _consensus_modifiers("AMPX", "Add")
    assert len(fires) >= 2, f"expected 2+ fires, got {fires}"
    assert abs(mult - (0.7**len(fires))) < 1e-9

    # AAPL with our Add (1.5) vs street rec_mean=2.0 → diff=0.5, no disagreement fire
    mult2, fires2 = _consensus_modifiers("AAPL", "Add")
    assert "street_disagreement" not in " ".join(fires2)

    # Now have our analyst say Trim (4.0) on AAPL where Street says Buy (2.0) — diff=2.0 → fires
    mult3, fires3 = _consensus_modifiers("AAPL", "Trim")
    assert any("street_disagreement" in f for f in fires3)

    print("All allocator_v4.py self-tests passed.")
    print(f"  AMPX modifier = {mult:.3f} (fires: {fires})")
    print(f"  AAPL/Add modifier = {mult2:.3f} (fires: {fires2})")
    print(f"  AAPL/Trim disagreement = {mult3:.3f} (fires: {fires3})")


if __name__ == "__main__":
    _selftest()

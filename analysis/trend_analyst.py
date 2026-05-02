#!/usr/bin/env python3
"""
trend_analyst.py — Trend layer over the per-call structured scores.

Implements docs/architecture/TREND_LAYER.md as pure functions plus a CLI.
Reads a backtest CSV produced by backtest_from_files.py, emits an
augmented CSV with per-row trend verdicts and final actions applied
from the §6 matrix.

Usage:
    python3 trend_analyst.py --input data/backtest_2026-04-22_ENPH.csv
    python3 trend_analyst.py --input data/backtest_2026-04-22_ENPH.csv \
                             --input data/backtest_2026-04-22_TTD.csv \
                             --output data/backtest_with_trend.csv

Firewall: reads only structured scores (never transcripts, never
portfolio state). Output is a trend verdict; final-action override is
a mechanical matrix defined in TREND_LAYER.md §6.

Self-tests are embedded — run `python3 trend_analyst.py --self-test`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Encoders for categorical fields
# ---------------------------------------------------------------------------

_THESIS_SCORE = {
    "Strengthening": 2,
    "Intact": 0,
    "Weakening": -2,
    "Broken": -4,
}

_MITIGATION_SCORE = {
    "strong": 3,
    "mixed": 2,
    "weak": 1,
    "unproven": 0,
    None: 0,
    "": 0,
    "null": 0,
}

_CREDIBILITY_SCORE = {
    "positive": 1,
    "neutral": 0,
    "negative": -1,
    None: 0,
    "": 0,
}


def encode_thesis(value) -> int:
    return _THESIS_SCORE.get(value, 0)


def encode_mitigation(value) -> int:
    if value is None:
        return 0
    return _MITIGATION_SCORE.get(value, 0)


def encode_credibility(value) -> int:
    if value is None:
        return 0
    return _CREDIBILITY_SCORE.get(value, 0)


def _to_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Quarter-to-quarter signal detection (TREND_LAYER.md §4)
# ---------------------------------------------------------------------------

def detect_soft_signals(prev: dict, curr: dict) -> list[str]:
    """Return the list of soft-signal codes (S1-S4) that fire when moving
    from `prev` to `curr`. Empty list means "not soft"."""

    fired = []

    # S1 — Conviction erosion: recommendedSize drops by >= 3pp
    prev_size = _to_float(prev.get("recommended_size"))
    curr_size = _to_float(curr.get("recommended_size"))
    if prev_size is not None and curr_size is not None:
        if prev_size - curr_size >= 3:
            fired.append("S1_conviction_erosion")

    # S2 — Gap widening: (size - fresh) widens by >= 2pp
    prev_fresh = _to_float(prev.get("fresh_money_allocation"))
    curr_fresh = _to_float(curr.get("fresh_money_allocation"))
    if (prev_size is not None and prev_fresh is not None
            and curr_size is not None and curr_fresh is not None):
        prev_gap = prev_size - prev_fresh
        curr_gap = curr_size - curr_fresh
        if curr_gap - prev_gap >= 2:
            fired.append("S2_gap_widening")

    # S3 — Credibility inflection: pos/neutral -> negative
    prev_cred = prev.get("credibility_delta")
    curr_cred = curr.get("credibility_delta")
    if curr_cred == "negative" and prev_cred in ("positive", "neutral", None, ""):
        fired.append("S3_credibility_negative")

    # S4 — Mitigation erosion
    prev_mtr = encode_mitigation(prev.get("mitigation_track_record"))
    curr_mtr = encode_mitigation(curr.get("mitigation_track_record"))
    # Only count when both sides have a real value and there is a drop
    if (prev.get("mitigation_track_record") not in (None, "", "null")
            and curr.get("mitigation_track_record") not in (None, "", "null")
            and curr_mtr < prev_mtr):
        fired.append("S4_mitigation_erosion")

    return fired


_SIGNAL_PROSE = {
    "S1_conviction_erosion":   "the analyst lowered recommended size by 3+ percentage points",
    "S2_gap_widening":         "the gap between recommended size and fresh-money allocation widened by 2+ points (analyst getting more cautious about new buying)",
    "S3_credibility_negative": "credibility flipped to negative this quarter",
    "S4_mitigation_erosion":   "the mitigation track record (whether management has historically delivered on this kind of headwind) got weaker",
}


def _humanize_signals(signals) -> str:
    """Turn ['S1_conviction_erosion', 'S2_gap_widening'] into a readable
    English clause for use in rationale strings."""
    if not signals:
        return "no signals"
    parts = [_SIGNAL_PROSE.get(s, s) for s in sorted(set(signals))]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}; and {parts[1]}"
    return "; ".join(parts[:-1]) + f"; and {parts[-1]}"


def classify_quarter(prev: dict | None, curr: dict) -> dict:
    """Classify a single quarter's signals relative to the prior quarter.

    Returns: { "signals": [...], "soft": bool, "sharp": bool }
    A quarter with no prior comparable data is "unknown" — never soft.
    """
    if prev is None:
        return {"signals": [], "soft": False, "sharp": False}
    signals = detect_soft_signals(prev, curr)
    soft = len(signals) >= 1
    sharp = len(signals) >= 2
    return {"signals": signals, "soft": soft, "sharp": sharp}


# ---------------------------------------------------------------------------
# Trajectory classification (TREND_LAYER.md §5)
# ---------------------------------------------------------------------------

def compute_trend_verdict(history: list[dict],
                            tier: str = "established") -> dict | None:
    """Given a list of per-call analyses for ONE ticker, chronological
    (oldest first), produce a trend verdict for the LATEST entry.

    `tier`: "speculative" or "established" (default).
        - speculative: Rule 7 fires `upgrade_one` on a single improving
          quarter (faster recognition of inflections on volatile names).
        - established: Rule 7 requires two consecutive improving quarters
          before issuing `upgrade_one` (the original behavior).
        Hard-signal blocks (S3/S4) still apply uniformly across tiers —
        an improving quarter with a credibility-negative or mitigation
        erosion signal does NOT trigger upgrade_one regardless of tier.
        Downside rules (1-6) are tier-invariant: the v2.1 Strengthening
        gates and S3/S4 overrides apply to both.

    Returns None if history has fewer than 3 entries (not enough data).
    """
    if len(history) < 3:
        return None

    curr = history[-1]
    prev = history[-2]
    prev2 = history[-3]

    # Per-quarter classifications (each looks one step back)
    curr_cls = classify_quarter(prev, curr)
    prev_cls = classify_quarter(prev2, prev)
    prev2_cls = classify_quarter(history[-4] if len(history) >= 4 else None, prev2)

    # Precompute common deltas for the verdict struct
    oldest = history[-4] if len(history) >= 4 else history[-3]
    conviction_delta = (_to_float(curr.get("recommended_size"), 0.0)
                        - _to_float(oldest.get("recommended_size"), 0.0))
    curr_gap = (_to_float(curr.get("recommended_size"), 0.0)
                - _to_float(curr.get("fresh_money_allocation"), 0.0))
    oldest_gap = (_to_float(oldest.get("recommended_size"), 0.0)
                  - _to_float(oldest.get("fresh_money_allocation"), 0.0))
    gap_delta = curr_gap - oldest_gap
    thesis_score_delta = (encode_thesis(curr.get("thesis_health"))
                          - encode_thesis(oldest.get("thesis_health")))

    # Rule 1 — defer to graduated exit ratchet on explicit Weakening/Broken
    if curr.get("thesis_health") in ("Weakening", "Broken"):
        health = curr.get("thesis_health")
        return _verdict(
            trajectory="deteriorating",
            consecutive_soft_q=_consecutive_soft(history),
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override=None,
            rationale=(
                f"The analyst has already flagged the thesis as {health} on "
                f"this call, which is a more decisive signal than anything "
                f"the trend layer would add. The downstream allocator's "
                f"graduated exit ratchet (trim → trim more → exit over "
                f"successive quarters of non-improvement) takes over from "
                f"here, so the trend layer doesn't issue a separate "
                f"override — it just confirms the deteriorating direction."
            ),
        )

    # Rule 2 — three consecutive soft quarters
    if curr_cls["soft"] and prev_cls["soft"] and prev2_cls["soft"]:
        signals = curr_cls["signals"] + prev_cls["signals"] + prev2_cls["signals"]
        all_signals = set(signals)
        hard_signals_present = bool(all_signals & {"S3_credibility_negative",
                                                    "S4_mitigation_erosion"})
        # Gate: on a Strengthening thesis with no hard signals (S3/S4), three
        # soft quarters are conviction oscillation on a volatile-but-improving
        # name, not deterioration. Treat as advisory, no action.
        # Reason: ENVX 2025-04-30 misfired (Add→Hold on a +98% rel rally) with
        # Strengthening + only S1/S2 signals. AMPX 2026-03-05 has the same
        # pattern. Symmetric to the Rule 4 Strengthening gate added in v2.
        if (curr.get("thesis_health") == "Strengthening"
                and not hard_signals_present):
            return _verdict(
                trajectory="softening",
                consecutive_soft_q=3,
                conviction_delta=conviction_delta,
                gap_delta=gap_delta,
                thesis_score_delta=thesis_score_delta,
                suggested_override=None,
                rationale=(
                    f"For three quarters running, the analyst has tightened "
                    f"conviction or pulled back on fresh-money allocation "
                    f"(soft signals: {_humanize_signals(all_signals)}). "
                    f"Normally a streak this long would call for a trim, "
                    f"but the underlying thesis is still rated Strengthening "
                    f"and none of the harder warning signs (credibility "
                    f"break, mitigation track record erosion) have fired. "
                    f"On a Strengthening thesis, a soft-only streak usually "
                    f"reflects the analyst getting more disciplined on a "
                    f"winning name — sizing it more carefully — rather than "
                    f"the thesis itself deteriorating. The trend layer flags "
                    f"this as a watch item but doesn't override the "
                    f"per-call recommendation."
                ),
            )
        return _verdict(
            trajectory="deteriorating",
            consecutive_soft_q=3,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override="trim_regardless",
            rationale=(
                f"Three consecutive quarters of soft signals "
                f"({_humanize_signals(all_signals)}). The analyst keeps "
                f"tightening conviction or revealing mitigation/credibility "
                f"weakness without ever flagging the thesis as Strengthening "
                f"again — that's the pattern of a thesis quietly breaking "
                f"down. The trend layer overrides any Hold to Trim and "
                f"freezes any Add."
            ),
        )

    # Rule 3 — two consecutive soft, latest sharp
    if curr_cls["sharp"] and prev_cls["soft"]:
        return _verdict(
            trajectory="deteriorating",
            consecutive_soft_q=2,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override="trim_regardless",
            rationale=(
                f"The previous quarter showed soft signals (analyst getting "
                f"more cautious), and this quarter the picture got worse — "
                f"two or more concerns fired at once "
                f"({_humanize_signals(curr_cls['signals'])}). At least one "
                f"of those is a hard signal (credibility breaking down or "
                f"mitigation track record eroding), which means the "
                f"deterioration isn't just noise. The trend layer overrides "
                f"to a trim regardless of what the per-call rec says."
            ),
        )

    # Rule 4 — two consecutive soft, latest mild
    if curr_cls["soft"] and prev_cls["soft"]:
        # Gate: if the analyst still calls thesis Strengthening, S1/S2 signals
        # alone aren't enough to override. Treat as advisory, no action.
        # Reason: on rising positions the evaluator legitimately tunes size
        # downward and drifts fresh-money-gap without the underlying thesis
        # deteriorating. Validated on AMPX/EOSE 2025 where Rule 4 misfired
        # on +61% / +143% / +10% rallies (see memory: trend_layer_v1_result).
        if curr.get("thesis_health") == "Strengthening":
            return _verdict(
                trajectory="softening",
                consecutive_soft_q=2,
                conviction_delta=conviction_delta,
                gap_delta=gap_delta,
                thesis_score_delta=thesis_score_delta,
                suggested_override=None,
                rationale=(
                    f"The analyst has shown two quarters of soft signals "
                    f"({_humanize_signals(curr_cls['signals'])}) — typically "
                    f"this would prompt the trend layer to step the "
                    f"recommendation down one notch. But the underlying "
                    f"thesis is still rated Strengthening, which means the "
                    f"position is fundamentally working. On rising-conviction "
                    f"calls, mild soft signals usually reflect the analyst "
                    f"sizing the position more disciplinedly rather than the "
                    f"thesis breaking. The trend layer flags this as a "
                    f"watch item but keeps the per-call rec in place."
                ),
            )
        return _verdict(
            trajectory="softening",
            consecutive_soft_q=2,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override="downgrade_one",
            rationale=(
                f"Two consecutive quarters of soft signals "
                f"({_humanize_signals(curr_cls['signals'])}) on a thesis "
                f"that's no longer rated Strengthening. The analyst keeps "
                f"becoming more cautious — tightening conviction or pulling "
                f"back on fresh money — and the underlying thesis hasn't "
                f"re-strengthened to compensate. The trend layer steps the "
                f"recommendation down one notch (Add → Hold, or Hold → Trim) "
                f"to reflect the directional drift."
            ),
        )

    # Rule 5 — latest soft, priors not
    if curr_cls["soft"] and not prev_cls["soft"]:
        return _verdict(
            trajectory="softening",
            consecutive_soft_q=1,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override=None,
            rationale=(
                f"This quarter showed a single soft signal "
                f"({_humanize_signals(curr_cls['signals'])}) but the prior "
                f"quarter was clean. One isolated quarter of softness isn't "
                f"enough to act on — could just be the analyst tuning "
                f"position size on a strong call. The trend layer flags it "
                f"to monitor; if next quarter also comes in soft, the "
                f"two-soft rule will kick in and we'll consider stepping "
                f"the recommendation down."
            ),
        )

    # Rule 6 — flattening: Strengthening -> Intact with no S1-S4 firing
    curr_thesis = curr.get("thesis_health")
    prev_thesis = prev.get("thesis_health")
    prev2_thesis = prev2.get("thesis_health")
    recent_strengthening = (prev_thesis == "Strengthening"
                            or prev2_thesis == "Strengthening")
    if (curr_thesis == "Intact"
            and recent_strengthening
            and not curr_cls["soft"]):
        return _verdict(
            trajectory="flattening",
            consecutive_soft_q=0,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override=None,
            rationale=(
                "The thesis just stepped down from Strengthening to Intact, "
                "with none of the soft warning signs firing — typical of a "
                "growth name maturing into a steady-state cash generator. "
                "It's not deteriorating, but the upside is no longer "
                "compounding the way it was. The trend layer doesn't "
                "automatically act on this: the right call depends on "
                "whether there's a higher-conviction candidate to rotate "
                "into, which is a Layer 3 (opportunity scanner) decision "
                "we haven't built yet. Until then, treat this as a 'on "
                "deck for review' signal."
            ),
        )

    # Rule 7 — improving
    size_up = False
    if prev_size := _to_float(prev.get("recommended_size")):
        if curr_size := _to_float(curr.get("recommended_size")):
            size_up = (curr_size - prev_size) >= 3
    gap_narrowed = False
    curr_gap_single = (_to_float(curr.get("recommended_size"), 0.0)
                       - _to_float(curr.get("fresh_money_allocation"), 0.0))
    prev_gap_single = (_to_float(prev.get("recommended_size"), 0.0)
                       - _to_float(prev.get("fresh_money_allocation"), 0.0))
    if curr_gap_single <= prev_gap_single:
        gap_narrowed = True
    no_cred_or_mtr_drop = not (set(curr_cls["signals"]) & {"S3_credibility_negative",
                                                            "S4_mitigation_erosion"})
    curr_improving = size_up and gap_narrowed and no_cred_or_mtr_drop
    # Two consecutive improving quarters → upgrade
    prev_size_up = False
    if prev2_size := _to_float(prev2.get("recommended_size")):
        if prev_size := _to_float(prev.get("recommended_size")):
            prev_size_up = (prev_size - prev2_size) >= 3
    prev_gap_narrowed = (
        (_to_float(prev.get("recommended_size"), 0.0)
         - _to_float(prev.get("fresh_money_allocation"), 0.0))
        <=
        (_to_float(prev2.get("recommended_size"), 0.0)
         - _to_float(prev2.get("fresh_money_allocation"), 0.0))
    )
    prev_improving = prev_size_up and prev_gap_narrowed
    if curr_improving and prev_improving:
        return _verdict(
            trajectory="improving",
            consecutive_soft_q=0,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override="upgrade_one",
            rationale=(
                "Two quarters in a row of strengthening conviction — the "
                "analyst keeps raising recommended size while keeping the "
                "fresh-money gap tight, with no credibility or mitigation "
                "concerns appearing. That's a clean inflection signal "
                "across multiple periods, not a one-off. The trend layer "
                "steps the recommendation up one notch (Hold → Add)."
            ),
        )
    if curr_improving:
        # Speculative tier: a single improving quarter is enough for upgrade_one.
        # Rationale: on volatile small-caps, waiting for two-quarter confirmation
        # cedes the inflection (QS 2025-04-23 was Hold into +229%; SPWR 2025-01-15
        # was Hold into +22%). Hard-signal blocks (S3/S4) above already handled by
        # the no_cred_or_mtr_drop check inside curr_improving.
        if tier == "speculative":
            return _verdict(
                trajectory="improving",
                consecutive_soft_q=0,
                conviction_delta=conviction_delta,
                gap_delta=gap_delta,
                thesis_score_delta=thesis_score_delta,
                suggested_override="upgrade_one",
                rationale=(
                    "The analyst stepped conviction up this quarter (higher "
                    "recommended size, fresh-money gap not widening, no "
                    "credibility or mitigation concerns). On a speculative "
                    "ticker (small-cap, volatile, or pre-revenue), waiting "
                    "for a second confirming quarter often means missing "
                    "the inflection — these names move fast. The trend "
                    "layer steps the recommendation up one notch now "
                    "(Hold → Add) rather than waiting."
                ),
            )
        return _verdict(
            trajectory="improving",
            consecutive_soft_q=0,
            conviction_delta=conviction_delta,
            gap_delta=gap_delta,
            thesis_score_delta=thesis_score_delta,
            suggested_override=None,
            rationale=(
                "The analyst stepped conviction up this quarter (higher "
                "recommended size, fresh-money gap not widening, no "
                "credibility or mitigation concerns). On an established "
                "ticker we wait for a second confirming quarter before "
                "stepping the recommendation up — one strong quarter on a "
                "mature name can be noise. Watch this; if next quarter "
                "also comes in improving, the trend layer will upgrade."
            ),
        )

    # Rule 8 — stable
    return _verdict(
        trajectory="stable",
        consecutive_soft_q=0,
        conviction_delta=conviction_delta,
        gap_delta=gap_delta,
        thesis_score_delta=thesis_score_delta,
        suggested_override=None,
        rationale=(
            "Recent quarters look broadly consistent — conviction holding, "
            "no soft signals firing, no improving inflection either. "
            "Nothing for the trend layer to act on; the per-call "
            "recommendation passes through unchanged."
        ),
    )


def _consecutive_soft(history: list[dict]) -> int:
    """Count how many latest-backward quarters were soft."""
    n = 0
    for i in range(len(history) - 1, 0, -1):
        cls = classify_quarter(history[i - 1], history[i])
        if cls["soft"]:
            n += 1
        else:
            break
    return n


def _verdict(trajectory, consecutive_soft_q, conviction_delta, gap_delta,
             thesis_score_delta, suggested_override, rationale) -> dict:
    return {
        "trajectory": trajectory,
        "consecutive_soft_q": consecutive_soft_q,
        "conviction_delta": round(conviction_delta, 2),
        "gap_delta": round(gap_delta, 2),
        "thesis_score_delta": thesis_score_delta,
        "suggested_override": suggested_override,
        "rationale": rationale,
    }


# ---------------------------------------------------------------------------
# Allocator matrix (TREND_LAYER.md §6)
# ---------------------------------------------------------------------------

def apply_matrix(per_call_rec: str, verdict: dict | None,
                 layer3_rotation_target: bool = False) -> tuple[str, str]:
    """Apply the §6 matrix, return (final_action, rationale).

    Key rule: the matrix acts on `verdict["suggested_override"]`, not on
    `verdict["trajectory"]` alone. A trajectory classification without an
    override is advisory only — the per-call recommendation passes through.

    `layer3_rotation_target` reserved for future Layer 3 integration —
    default False means "no rotation target" which leaves flatteners alone.

    Rationale strategy: the verbose explanation lives in
    `verdict["rationale"]`. The matrix delegates to that rationale rather
    than generating its own terse summary, so every advisory row in the
    feed reads as a coherent multi-sentence explanation. For Exit/Trim
    floors and unknown-rec edge cases the matrix prepends a brief
    contextual note then includes the verdict rationale.
    """
    if verdict is None:
        return per_call_rec, ("No trend verdict yet — this ticker has fewer "
                              "than three prior calls in its history, which "
                              "is the minimum the trend layer needs to "
                              "evaluate a trajectory. Comes online once a "
                              "third call lands.")

    trajectory = verdict["trajectory"]
    override = verdict["suggested_override"]
    rationale = verdict.get("rationale") or ""

    # Exit and Trim are floors — trend never flips them up. The verbose
    # verdict rationale still applies (it explains the trajectory direction);
    # we just prepend a note that the floor is binding.
    if per_call_rec == "Exit":
        return "Exit", (
            "The per-call recommendation is Exit — the trend layer never "
            "upgrades a per-call Exit (the analyst's conviction has already "
            f"capitulated). Trend layer's view of the trajectory: {rationale}"
        )
    if per_call_rec == "Trim":
        return "Trim", (
            "The per-call recommendation is Trim — the trend layer never "
            "upgrades a per-call Trim (we don't second-guess the analyst's "
            f"deterioration call upward). Trend layer's view: {rationale}"
        )

    # Flattening + Layer 3 rotation is the one trajectory-driven override
    # that stands alone (rotation opportunity cost, not trend deterioration).
    if trajectory == "flattening" and layer3_rotation_target:
        if per_call_rec == "Hold":
            return "Trim", (
                "The thesis is flattening AND Layer 3 surfaced a "
                "higher-conviction candidate — rotating from a maturing "
                f"name to a rising one. {rationale}"
            )
        if per_call_rec == "Add":
            return "Hold", (
                "The thesis is flattening AND Layer 3 surfaced a "
                "higher-conviction candidate — don't add fresh money to "
                f"the flattening name; let it ride. {rationale}"
            )

    # For Hold and Add, the verbose verdict rationale already explains both
    # the trajectory and whether/why the override fires. We delegate to it
    # entirely rather than re-summarizing.
    if per_call_rec in ("Hold", "Add"):
        if override == "trim_regardless":
            return "Trim" if per_call_rec == "Hold" else "Hold", rationale
        if override == "downgrade_one":
            return "Trim" if per_call_rec == "Hold" else "Hold", rationale
        if override == "upgrade_one":
            # On Hold this becomes Add. On Add it's a no-op (we don't have a
            # rec above Add) — just keep Add and surface the rationale.
            return "Add", rationale
        # No override — pass through. The verbose rationale explains why the
        # trajectory wasn't enough to act on.
        return per_call_rec, rationale

    # Unknown per-call rec — surface what we have plus a note.
    return per_call_rec, (
        f"Per-call recommendation '{per_call_rec}' wasn't one of the "
        f"expected values (Add/Hold/Trim/Exit), so the trend layer "
        f"passes it through unchanged. Trend layer's view: {rationale}"
    )


# ---------------------------------------------------------------------------
# Classifier integration (option 1 — runner-side classification)
# ---------------------------------------------------------------------------

def _trailing_vol_annualized(closes: dict, window_days: int = 252):
    """Mirror of classify_tickers.trailing_vol_annualized to keep the trend
    layer free of cross-module imports. Returns annualized σ or None."""
    import math, statistics
    if not closes:
        return None
    items = sorted(closes.items())
    if len(items) < 30:
        return None
    recent = items[-window_days:] if len(items) > window_days else items
    rets = []
    for i in range(1, len(recent)):
        p0, p1 = recent[i-1][1], recent[i][1]
        if p0 > 0 and p1 > 0:
            rets.append(math.log(p1 / p0))
    if len(rets) < 20:
        return None
    return statistics.stdev(rets) * math.sqrt(252)


def build_tier_function(price_cache_path: Path,
                          fundamentals_cache_path: Path,
                          vol_threshold: float = 0.50,
                          cap_threshold: float = 50e9,
                          pe_threshold: float = 50.0,
                          freshness_days: int = 30):
    """Build a `tier_for_ticker(symbol) -> "speculative"|"established"`
    function backed by the local price + fundamentals caches.

    Logs a freshness warning if the fundamentals cache is stale (>
    freshness_days old). Manual refresh today via fetch_fundamentals.py;
    will move to a Railway cron job when the Portfolio module ships.
    """
    import datetime as _dt
    prices = json.loads(price_cache_path.read_text()) if price_cache_path.exists() else {}
    fundamentals = (json.loads(fundamentals_cache_path.read_text())
                    if fundamentals_cache_path.exists() else {})

    if fundamentals_cache_path.exists():
        mtime = _dt.datetime.fromtimestamp(fundamentals_cache_path.stat().st_mtime)
        age_days = (_dt.datetime.now() - mtime).days
        if age_days > freshness_days:
            print(f"WARNING: {fundamentals_cache_path.name} is {age_days} days "
                  f"old (>{freshness_days}). Re-run fetch_fundamentals.py on the "
                  f"laptop to refresh market cap and P/E snapshots.")
    else:
        print(f"WARNING: {fundamentals_cache_path} missing — every ticker "
              f"will fall back to the multiple-axis-fires-on-null rule. "
              f"Run fetch_fundamentals.py on the laptop.")

    def tier_for_ticker(ticker: str) -> str:
        vol = _trailing_vol_annualized(prices.get(ticker, {}))
        f = fundamentals.get(ticker, {})
        mkt_cap = f.get("marketCap")
        trailing_pe = f.get("trailingPE")
        vol_axis = vol is not None and vol >= vol_threshold
        cap_axis = mkt_cap is not None and mkt_cap < cap_threshold
        if trailing_pe is None or trailing_pe < 0:
            mult_axis = True
        else:
            mult_axis = trailing_pe > pe_threshold
        fired = sum([vol_axis, cap_axis, mult_axis])
        return "speculative" if fired >= 2 else "established"

    return tier_for_ticker


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

BACKTEST_FIELDS_IN = [
    "ticker", "call_date", "recommendation", "thesis_health", "thesis_delta",
    "stumble_type", "credibility_delta", "recommended_size",
    "fresh_money_allocation", "mitigation_track_record",
    "relative_return_pct", "signal_correct",
]

BACKTEST_FIELDS_OUT = [
    "ticker", "tier", "call_date", "per_call_rec", "thesis_health",
    "recommended_size", "fresh_money_allocation",
    "trajectory", "consecutive_soft_q", "conviction_delta",
    "gap_delta", "thesis_score_delta", "suggested_override",
    "final_action", "final_confidence", "final_rationale",
    "relative_return_pct", "per_call_correct", "final_correct",
]


def compute_signal_correct(recommendation: str, relative_return: float | None) -> bool | None:
    if relative_return is None:
        return None
    if recommendation == "Add":
        return relative_return > 0
    if recommendation == "Hold":
        return abs(relative_return) <= 5
    if recommendation in ("Trim", "Exit"):
        return relative_return < 0
    return None


def compute_final_confidence(verdict: dict | None,
                              per_call_rec: str,
                              final_action: str) -> str:
    """Three-state confidence on the final action:
    - "unknown": insufficient history (no verdict)
    - "advisory": trend layer saw a non-stable trajectory but did not
                  override; final action equals per-call rec by default,
                  but the trajectory signal is real and worth surfacing.
                  Captures the QS 2025-04-23 / SPWR 2025-01-15 pattern
                  where the trend layer flagged something but couldn't
                  act on it within current rules.
    - "confident": either an override fired, OR trajectory is stable.
                   Trend layer has no concerns about the action.
    """
    if verdict is None:
        return "unknown"
    trajectory = verdict.get("trajectory", "stable")
    override = verdict.get("suggested_override")
    if trajectory in ("stable", "unknown"):
        return "confident"
    if override is not None and final_action != per_call_rec:
        # Override fired and actually changed the action
        return "confident"
    # Trajectory shows movement but action passes through unchanged
    return "advisory"


def process_csv(paths: list[Path],
                  tier_for_ticker=None) -> list[dict]:
    """Read one or more backtest CSVs, group by ticker, produce trend
    verdicts per row chronologically (no look-ahead), apply the matrix.

    `tier_for_ticker`: optional callable `(ticker) -> "speculative"|"established"`.
    If None, every ticker is treated as "established" (back-compat).
    """
    rows: list[dict] = []
    for p in paths:
        with p.open() as f:
            rows.extend(csv.DictReader(f))

    # Group by ticker, sort chronologically within each group
    by_ticker: dict[str, list[dict]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(r)
    for t in by_ticker:
        by_ticker[t].sort(key=lambda r: r["call_date"])

    out: list[dict] = []
    for ticker, history in by_ticker.items():
        tier = "established"
        if tier_for_ticker is not None:
            tier = tier_for_ticker(ticker) or "established"
        for i in range(len(history)):
            curr = history[i]
            prior = history[: i + 1]  # history up to and including curr
            verdict = compute_trend_verdict(prior, tier=tier)

            per_call_rec = curr.get("recommendation", "")
            final_action, final_rationale = apply_matrix(per_call_rec, verdict)

            rel = _to_float(curr.get("relative_return_pct"))
            per_call_correct = compute_signal_correct(per_call_rec, rel)
            final_correct = compute_signal_correct(final_action, rel)
            final_confidence = compute_final_confidence(verdict, per_call_rec,
                                                          final_action)

            v = verdict or {}
            out.append({
                "ticker": ticker,
                "tier": tier,
                "call_date": curr.get("call_date"),
                "per_call_rec": per_call_rec,
                "thesis_health": curr.get("thesis_health"),
                "recommended_size": curr.get("recommended_size"),
                "fresh_money_allocation": curr.get("fresh_money_allocation"),
                "trajectory": v.get("trajectory", "unknown"),
                "consecutive_soft_q": v.get("consecutive_soft_q", 0),
                "conviction_delta": v.get("conviction_delta", 0),
                "gap_delta": v.get("gap_delta", 0),
                "thesis_score_delta": v.get("thesis_score_delta", 0),
                "suggested_override": v.get("suggested_override"),
                "final_action": final_action,
                "final_confidence": final_confidence,
                "final_rationale": final_rationale,
                "relative_return_pct": curr.get("relative_return_pct"),
                "per_call_correct": per_call_correct,
                "final_correct": final_correct,
            })
    return out


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _scoreboard(rows: list[dict], key: str) -> tuple[int, int]:
    correct = 0
    scored = 0
    for r in rows:
        v = r[key]
        if v is True:
            correct += 1
            scored += 1
        elif v is False:
            scored += 1
    return correct, scored


def _mk(d):
    """Helper: build a minimal analysis dict for tests."""
    defaults = {
        "thesis_health": "Intact",
        "recommendation": "Hold",
        "recommended_size": 30,
        "fresh_money_allocation": 30,
        "credibility_delta": "neutral",
        "mitigation_track_record": "mixed",
        "stumble_type": "None",
    }
    defaults.update(d)
    return defaults


def run_self_tests() -> int:
    """Hand-crafted histories covering the §5 branches."""
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    # 1. Insufficient history
    check("insufficient history",
          compute_trend_verdict([_mk({}), _mk({})]), None)

    # 2. Explicit Weakening → deteriorating, no override
    hist = [_mk({"thesis_health": "Strengthening"}),
            _mk({"thesis_health": "Intact"}),
            _mk({"thesis_health": "Weakening"})]
    v = compute_trend_verdict(hist)
    check("weakening defers",
          (v["trajectory"], v["suggested_override"]),
          ("deteriorating", None))

    # 3. Three consecutive soft → trim_regardless
    #    Use size drops across 4 quarters: 50, 46, 42, 38 (each -4pp = S1)
    hist = [_mk({"recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"recommended_size": 46, "fresh_money_allocation": 46}),
            _mk({"recommended_size": 42, "fresh_money_allocation": 42}),
            _mk({"recommended_size": 38, "fresh_money_allocation": 38})]
    v = compute_trend_verdict(hist)
    check("three soft",
          (v["trajectory"], v["suggested_override"]),
          ("deteriorating", "trim_regardless"))

    # 3b. Three consecutive soft BUT thesis Strengthening with no S3/S4 → no override
    # (Validated on ENVX 2025-04-30: Rule 2 misfired on +98% rel rally. Symmetric
    # to Rule 4's Strengthening gate from v2.)
    hist = [_mk({"thesis_health": "Strengthening",
                 "recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 46, "fresh_money_allocation": 46}),  # S1
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 42, "fresh_money_allocation": 42}),  # S1
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 38, "fresh_money_allocation": 38})]  # S1
    v = compute_trend_verdict(hist)
    check("three soft gated by Strengthening",
          (v["trajectory"], v["suggested_override"]),
          ("softening", None))

    # 3c. Three consecutive soft on Strengthening BUT with S3 present → still overrides
    # (Credibility-negative is a hard signal and beats the Strengthening gate.)
    hist = [_mk({"thesis_health": "Strengthening",
                 "recommended_size": 50, "fresh_money_allocation": 50,
                 "credibility_delta": "positive"}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 46, "fresh_money_allocation": 46,
                 "credibility_delta": "neutral"}),  # S1
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 42, "fresh_money_allocation": 42,
                 "credibility_delta": "neutral"}),  # S1
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 38, "fresh_money_allocation": 38,
                 "credibility_delta": "negative"})]  # S1 + S3
    v = compute_trend_verdict(hist)
    check("three soft + S3 on Strengthening → still overrides",
          (v["trajectory"], v["suggested_override"]),
          ("deteriorating", "trim_regardless"))

    # 4. Two consecutive soft, latest sharp (S1 + S2) → trim_regardless
    hist = [_mk({"recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"recommended_size": 46, "fresh_money_allocation": 46}),  # S1
            _mk({"recommended_size": 40, "fresh_money_allocation": 30})]  # S1 + S2
    v = compute_trend_verdict(hist)
    check("two soft + sharp",
          (v["trajectory"], v["suggested_override"]),
          ("deteriorating", "trim_regardless"))

    # 5. Two consecutive soft, latest mild (S1 only), thesis=Intact → downgrade_one
    hist = [_mk({"recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"recommended_size": 46, "fresh_money_allocation": 46}),  # S1
            _mk({"recommended_size": 42, "fresh_money_allocation": 42})]  # S1
    v = compute_trend_verdict(hist)
    check("two soft mild (Intact)",
          (v["trajectory"], v["suggested_override"]),
          ("softening", "downgrade_one"))

    # 5b. Two consecutive soft BUT thesis still Strengthening → no override
    # (Validated on AMPX/EOSE 2025: Rule 4 was misfiring on +61%, +143% rallies)
    hist = [_mk({"thesis_health": "Strengthening",
                 "recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 46, "fresh_money_allocation": 46}),  # S1
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 42, "fresh_money_allocation": 42})]  # S1
    v = compute_trend_verdict(hist)
    check("two soft mild gated by Strengthening",
          (v["trajectory"], v["suggested_override"]),
          ("softening", None))

    # 6. Latest soft, prior not → softening, no override
    hist = [_mk({"recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"recommended_size": 46, "fresh_money_allocation": 46})]  # S1
    v = compute_trend_verdict(hist)
    check("latest soft only",
          (v["trajectory"], v["suggested_override"]),
          ("softening", None))

    # 7. Flattening — Strengthening → Intact with no S1-S4
    hist = [_mk({"thesis_health": "Strengthening", "recommended_size": 45}),
            _mk({"thesis_health": "Strengthening", "recommended_size": 45}),
            _mk({"thesis_health": "Intact", "recommended_size": 45})]
    v = compute_trend_verdict(hist)
    check("flattening",
          (v["trajectory"], v["suggested_override"]),
          ("flattening", None))

    # 8. Two consecutive improving → upgrade_one
    #    Size rising, fresh matching (no gap)
    hist = [_mk({"recommended_size": 30, "fresh_money_allocation": 30}),
            _mk({"recommended_size": 35, "fresh_money_allocation": 35}),  # +5
            _mk({"recommended_size": 40, "fresh_money_allocation": 40})]  # +5
    v = compute_trend_verdict(hist)
    check("two improving",
          (v["trajectory"], v["suggested_override"]),
          ("improving", "upgrade_one"))

    # 9. Single improving → improving, no override (established tier default)
    hist = [_mk({"recommended_size": 30, "fresh_money_allocation": 30}),
            _mk({"recommended_size": 30, "fresh_money_allocation": 30}),
            _mk({"recommended_size": 35, "fresh_money_allocation": 35})]
    v = compute_trend_verdict(hist)
    check("one improving (established)",
          (v["trajectory"], v["suggested_override"]),
          ("improving", None))

    # 9b. Single improving on SPECULATIVE tier → upgrade_one (Phase B)
    # Captures the QS 2025-04-23 / SPWR 2025-01-15 inflection-lag pattern
    # where waiting for two-quarter confirmation cedes the rally.
    v = compute_trend_verdict(hist, tier="speculative")
    check("one improving (speculative) → upgrade_one",
          (v["trajectory"], v["suggested_override"]),
          ("improving", "upgrade_one"))

    # 9c. Single improving on speculative WITH S3 (credibility-negative) →
    # NOT improving (S3 blocks curr_improving inside Rule 7), so falls through
    # to Rule 8 stable. Hard signals beat the speculative tier upgrade.
    hist = [_mk({"recommended_size": 30, "fresh_money_allocation": 30,
                 "credibility_delta": "neutral"}),
            _mk({"recommended_size": 30, "fresh_money_allocation": 30,
                 "credibility_delta": "neutral"}),
            _mk({"recommended_size": 35, "fresh_money_allocation": 35,
                 "credibility_delta": "negative"})]  # S3 fires
    v = compute_trend_verdict(hist, tier="speculative")
    # Latest is soft (S3 fired) but priors are not → Rule 5 (single soft)
    check("one improving + S3 on speculative → softening passthrough",
          (v["trajectory"], v["suggested_override"]),
          ("softening", None))

    # 10. Stable
    hist = [_mk({"recommended_size": 30}),
            _mk({"recommended_size": 30}),
            _mk({"recommended_size": 30})]
    v = compute_trend_verdict(hist)
    check("stable",
          (v["trajectory"], v["suggested_override"]),
          ("stable", None))

    # 10b. Tier invariance on the downside: the three-soft Strengthening gate
    # must NOT trigger an override on the speculative tier either. Phase B's
    # asymmetric design — speculative changes only the upside (Rule 7).
    hist = [_mk({"thesis_health": "Strengthening",
                 "recommended_size": 50, "fresh_money_allocation": 50}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 46, "fresh_money_allocation": 46}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 42, "fresh_money_allocation": 42}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 38, "fresh_money_allocation": 38})]
    v = compute_trend_verdict(hist, tier="speculative")
    check("three soft Strengthening (speculative) — gate still holds",
          (v["trajectory"], v["suggested_override"]),
          ("softening", None))

    # 10c. Tier invariance: hard signal (S3) on Strengthening still overrides
    # under speculative tier. Capability/credibility breaks matter on every name.
    hist = [_mk({"thesis_health": "Strengthening",
                 "recommended_size": 50, "fresh_money_allocation": 50,
                 "credibility_delta": "positive"}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 46, "fresh_money_allocation": 46,
                 "credibility_delta": "neutral"}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 42, "fresh_money_allocation": 42,
                 "credibility_delta": "neutral"}),
            _mk({"thesis_health": "Strengthening",
                 "recommended_size": 38, "fresh_money_allocation": 38,
                 "credibility_delta": "negative"})]
    v = compute_trend_verdict(hist, tier="speculative")
    check("three soft + S3 (speculative) → hard signal overrides",
          (v["trajectory"], v["suggested_override"]),
          ("deteriorating", "trim_regardless"))

    # 11. Matrix: Hold + deteriorating → Trim
    v = {"trajectory": "deteriorating", "suggested_override": "trim_regardless",
         "rationale": "test"}
    action, _ = apply_matrix("Hold", v)
    check("matrix Hold+det", action, "Trim")

    # 12. Matrix: Add + improving → Add
    v = {"trajectory": "improving", "suggested_override": "upgrade_one",
         "rationale": "test"}
    action, _ = apply_matrix("Add", v)
    check("matrix Add+imp", action, "Add")

    # 13. Matrix: Hold + improving (upgrade_one) → Add
    action, _ = apply_matrix("Hold", v)
    check("matrix Hold+imp upgrade", action, "Add")

    # 14. Matrix: Trim is a floor
    v = {"trajectory": "improving", "suggested_override": "upgrade_one",
         "rationale": "test"}
    action, _ = apply_matrix("Trim", v)
    check("matrix Trim floor", action, "Trim")

    # 15. Matrix: flattening without Layer 3 → passthrough (no action)
    # Reason: Luis's design call — flattening alone isn't a sell signal.
    # Only act if Layer 3 surfaces a rotation candidate.
    v = {"trajectory": "flattening", "suggested_override": None,
         "rationale": "test"}
    action, _ = apply_matrix("Add", v, layer3_rotation_target=False)
    check("matrix Add+flat no-L3 passthrough", action, "Add")
    action, _ = apply_matrix("Hold", v, layer3_rotation_target=False)
    check("matrix Hold+flat no-L3 passthrough", action, "Hold")

    # 15b. Matrix: flattening WITH Layer 3 rotation → act
    action, _ = apply_matrix("Add", v, layer3_rotation_target=True)
    check("matrix Add+flat with-L3", action, "Hold")
    action, _ = apply_matrix("Hold", v, layer3_rotation_target=True)
    check("matrix Hold+flat with-L3", action, "Trim")

    # 16. Matrix: softening with no override → passthrough (Add stays Add)
    # Reason: single-soft-quarter Rule 5 is advisory, not action.
    v = {"trajectory": "softening", "suggested_override": None,
         "rationale": "test"}
    action, _ = apply_matrix("Add", v)
    check("matrix Add+softening no-override passthrough", action, "Add")
    action, _ = apply_matrix("Hold", v)
    check("matrix Hold+softening no-override passthrough", action, "Hold")

    # 17. Matrix: softening WITH downgrade_one override → act
    v = {"trajectory": "softening", "suggested_override": "downgrade_one",
         "rationale": "test"}
    action, _ = apply_matrix("Add", v)
    check("matrix Add+softening downgrade", action, "Hold")
    action, _ = apply_matrix("Hold", v)
    check("matrix Hold+softening downgrade", action, "Trim")

    if failures:
        print("SELF-TEST FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All self-tests passed.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", default=[],
                        help="Path to a backtest CSV produced by "
                             "backtest_from_files.py (repeatable).")
    parser.add_argument("--output", type=Path,
                        help="Augmented CSV output path. Default is "
                             "next to first input with _trend suffix.")
    parser.add_argument("--self-test", action="store_true",
                        help="Run the embedded self-tests and exit.")
    parser.add_argument("--classify", action="store_true",
                        help="Use the 3-axis classifier from price + "
                             "fundamentals caches to assign per-ticker tier "
                             "(speculative vs. established). Without this "
                             "flag, every ticker is treated as established.")
    args = parser.parse_args()

    if args.self_test:
        return run_self_tests()

    if not args.input:
        parser.error("--input is required (or use --self-test).")

    paths = [Path(p).resolve() for p in args.input]
    for p in paths:
        if not p.exists():
            sys.exit(f"ERROR: input not found: {p}")

    tier_fn = None
    if args.classify:
        script_dir = Path(__file__).resolve().parent
        tier_fn = build_tier_function(
            script_dir / "data" / "price_cache.json",
            script_dir / "data" / "fundamentals_cache.json",
        )

    rows = process_csv(paths, tier_for_ticker=tier_fn)
    if not rows:
        sys.exit("No rows produced.")

    out_path = args.output
    if out_path is None:
        base = paths[0].parent
        out_path = base / f"backtest_trend_{dt.date.today().isoformat()}.csv"

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BACKTEST_FIELDS_OUT)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {out_path}  ({len(rows)} rows)")

    # Scoreboard
    pc_correct, pc_scored = _scoreboard(rows, "per_call_correct")
    fn_correct, fn_scored = _scoreboard(rows, "final_correct")
    print("\nScoreboard:")
    print(f"  Per-call baseline:  {pc_correct}/{pc_scored} = "
          f"{100*pc_correct/pc_scored:.0f}%" if pc_scored else "  baseline: n/a")
    print(f"  With trend layer:   {fn_correct}/{fn_scored} = "
          f"{100*fn_correct/fn_scored:.0f}%" if fn_scored else "  with trend: n/a")
    print(f"  Delta: {fn_correct - pc_correct:+d} calls")

    # Per-ticker breakdown
    print("\nPer-ticker:")
    by_ticker: dict[str, list[dict]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(r)
    for t, trs in sorted(by_ticker.items()):
        pc_c, pc_s = _scoreboard(trs, "per_call_correct")
        fn_c, fn_s = _scoreboard(trs, "final_correct")
        tier_str = trs[0].get("tier", "established")
        print(f"  {t} [{tier_str:11}]: per-call {pc_c}/{pc_s}  "
              f"trend {fn_c}/{fn_s}  delta {fn_c - pc_c:+d}")

    # By-tier summary (only meaningful when --classify is used)
    if args.classify:
        for tier_label in ("speculative", "established"):
            tier_rows = [r for r in rows if r.get("tier") == tier_label]
            if not tier_rows:
                continue
            pc_c, pc_s = _scoreboard(tier_rows, "per_call_correct")
            fn_c, fn_s = _scoreboard(tier_rows, "final_correct")
            tickers_in_tier = sorted({r["ticker"] for r in tier_rows})
            print(f"\nTier '{tier_label}' ({', '.join(tickers_in_tier)}):")
            print(f"  per-call: {pc_c}/{pc_s}  trend: {fn_c}/{fn_s}  "
                  f"delta {fn_c - pc_c:+d}")

    # Flips
    flips = [r for r in rows if r["per_call_rec"] != r["final_action"]]
    if flips:
        print(f"\n{len(flips)} row(s) where trend layer flipped the action:")
        for r in flips:
            print(f"  [{r['ticker']} {r['call_date']}] "
                  f"{r['per_call_rec']} -> {r['final_action']} "
                  f"(trajectory: {r['trajectory']}, "
                  f"per-call-correct: {r['per_call_correct']}, "
                  f"final-correct: {r['final_correct']})")

    # Advisory rows — trend layer saw a non-stable trajectory but didn't override.
    # These are the "I noticed something but didn't act" cases that surface
    # patterns over time. Scan for: was per-call rec actually right? are we
    # systematically missing inflections in one direction?
    advisories = [r for r in rows if r["final_confidence"] == "advisory"]
    if advisories:
        print(f"\n{len(advisories)} advisory row(s) — trajectory signal "
              f"present, no override (review for missed inflections):")
        for r in advisories:
            pcc = r["per_call_correct"]
            pcc_str = "✓" if pcc is True else ("✗" if pcc is False else "?")
            rel = r.get("relative_return_pct") or "n/a"
            print(f"  [{r['ticker']} {r['call_date']}] "
                  f"{r['per_call_rec']} (kept) — "
                  f"trajectory={r['trajectory']:<13} "
                  f"per-call={pcc_str} rel90d={rel}")

        # Quick stats: of advisory rows, how often was per-call wrong?
        scored = [r for r in advisories if r["per_call_correct"] in (True, False)]
        wrong = [r for r in scored if r["per_call_correct"] is False]
        if scored:
            print(f"\n  Advisory accuracy: per-call rec was correct on "
                  f"{len(scored) - len(wrong)}/{len(scored)} advisory rows. "
                  f"Watch the wrong cases for emerging patterns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

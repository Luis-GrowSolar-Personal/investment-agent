#!/usr/bin/env python3
"""
test_trend_fixtures.py — Parity test runner (Python side).

Runs analysis/data/trend_verdict_fixtures.json through
analysis/trend_analyst.py's compute_trend_verdict / apply_matrix /
compute_final_confidence.

The Node counterpart (server/lib/trendAnalyst.fixtures.test.js) runs the same
fixtures through server/lib/trendAnalyst.js. Both must pass — this is the
regression bar for any change to the trend-verdict/matrix/confidence rules in
either language (see server/lib/trendAnalyst.js's file header).

Usage:
    python3 analysis/test_trend_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trend_analyst import (  # noqa: E402
    compute_trend_verdict,
    apply_matrix,
    compute_final_confidence,
)


def main() -> int:
    fixtures_path = Path(__file__).resolve().parent / "data" / "trend_verdict_fixtures.json"
    fixtures = json.loads(fixtures_path.read_text())

    defaults = fixtures["verdict_defaults"]
    failures: list[str] = []

    # --- verdict cases ----------------------------------------------------
    for case in fixtures["verdict_cases"]:
        name = case["name"]
        history = []
        for entry in case["history"]:
            row = dict(defaults)
            row.update(entry)
            history.append(row)

        verdict = compute_trend_verdict(history, tier=case.get("tier", "established"))
        expected = case["expected"]

        if expected is None:
            if verdict is not None:
                failures.append(f"[verdict] {name}: got {verdict!r}, want None")
            continue

        if verdict is None:
            failures.append(f"[verdict] {name}: got None, want {expected!r}")
            continue

        got = (verdict["trajectory"], verdict["suggested_override"])
        want = (expected["trajectory"], expected["suggested_override"])
        if got != want:
            failures.append(f"[verdict] {name}: got {got!r}, want {want!r}")

    # --- matrix cases -------------------------------------------------------
    for case in fixtures["matrix_cases"]:
        name = case["name"]
        action, _rationale = apply_matrix(
            case["per_call_rec"],
            case["verdict"],
            layer3_rotation_target=case.get("layer3_rotation_target", False),
        )
        if action != case["expected_action"]:
            failures.append(f"[matrix] {name}: got {action!r}, want {case['expected_action']!r}")

    # --- confidence cases ----------------------------------------------------
    for case in fixtures["confidence_cases"]:
        name = case["name"]
        got = compute_final_confidence(case["verdict"], case["per_call_rec"], case["final_action"])
        if got != case["expected"]:
            failures.append(f"[confidence] {name}: got {got!r}, want {case['expected']!r}")

    if failures:
        print("FIXTURE FAILURES (Python):")
        for f in failures:
            print(f"  - {f}")
        return 1

    total = (
        len(fixtures["verdict_cases"])
        + len(fixtures["matrix_cases"])
        + len(fixtures["confidence_cases"])
    )
    print(f"All {total} fixture cases passed (Python).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

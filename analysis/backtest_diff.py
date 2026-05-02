#!/usr/bin/env python3
"""
backtest_diff.py — Compare two backtest CSVs and surface meaningful changes.

Focuses on the four fields most likely to change with the v2 prompt:
  - stumble_type
  - mitigation_track_record
  - recommendation
  - thesis_health

For every row where any of these fields changed, prints a side-by-side
comparison with the call date and ticker for manual review.

Usage:
    python3 analysis/backtest_diff.py --baseline analysis/data/backtest_2026-04-12.csv \
                                      --new analysis/data/backtest_2026-04-13.csv
"""

import argparse
import pandas as pd
import sys

DIFF_FIELDS = [
    'stumble_type',
    'mitigation_track_record',
    'recommendation',
    'thesis_health',
]

ACCURACY_FIELDS = ['signal_correct']


def load(path):
    df = pd.read_csv(path)
    df['call_date'] = pd.to_datetime(df['call_date']).dt.date
    return df


def merge(baseline, new):
    """Merge on ticker + call_date. Keep only rows present in both."""
    merged = baseline.merge(
        new,
        on=['ticker', 'call_date'],
        suffixes=('_old', '_new'),
        how='inner'
    )
    print(f"  Matched rows: {len(merged)} of {len(baseline)} baseline / {len(new)} new")
    return merged


def find_changes(merged):
    """Return rows where any tracked field changed."""
    changed_mask = pd.Series(False, index=merged.index)
    for field in DIFF_FIELDS:
        old_col = f"{field}_old"
        new_col = f"{field}_new"
        if old_col in merged.columns and new_col in merged.columns:
            changed_mask |= (merged[old_col].fillna('') != merged[new_col].fillna(''))
    return merged[changed_mask]


def print_changes(changed):
    if changed.empty:
        print("\n  No changes in tracked fields across matched rows.")
        return

    print(f"\n  {len(changed)} row(s) with changes:\n")
    for _, row in changed.iterrows():
        print(f"  {'─'*56}")
        print(f"  {row['ticker']}  |  {row['call_date']}")
        title_col = 'transcript_title_old' if 'transcript_title_old' in row.index else 'transcript_title'
        if title_col in row.index:
            print(f"  {row[title_col]}")
        print()
        for field in DIFF_FIELDS:
            old_col = f"{field}_old"
            new_col = f"{field}_new"
            if old_col in row.index and new_col in row.index:
                old_val = row[old_col]
                new_val = row[new_col]
                if str(old_val) != str(new_val):
                    marker = "⚡"
                else:
                    marker = "  "
                print(f"  {marker} {field:<30} {str(old_val):<20} → {str(new_val)}")
        print()


def accuracy_summary(baseline, new):
    """Compare overall signal accuracy between old and new."""
    print(f"\n{'═'*60}")
    print("  SIGNAL ACCURACY COMPARISON")
    print(f"{'═'*60}\n")

    for label, df in [("BASELINE (v1 prompt)", baseline), ("NEW (v2 prompt)", new)]:
        scored = df.dropna(subset=['signal_correct']).copy()
        scored['signal_correct'] = scored['signal_correct'].astype(float)
        if scored.empty:
            print(f"  {label}: no scored rows")
            continue
        total = len(scored)
        correct = int(scored['signal_correct'].sum())
        pct = 100 * correct / total
        print(f"  {label}")
        print(f"    Overall: {correct}/{total} = {pct:.1f}%")

        by_ticker = scored.groupby('ticker')['signal_correct'].agg(
            correct='sum', total='count'
        )
        by_ticker['pct'] = (by_ticker['correct'] / by_ticker['total'] * 100).round(1)
        for ticker, t_row in by_ticker.iterrows():
            print(f"    {ticker:<8} {int(t_row['correct'])}/{int(t_row['total'])}  ({t_row['pct']}%)")
        print()


def main():
    parser = argparse.ArgumentParser(description="Diff two backtest CSVs.")
    parser.add_argument('--baseline', required=True, help='Path to baseline CSV (v1 prompt)')
    parser.add_argument('--new', required=True, help='Path to new CSV (v2 prompt)')
    args = parser.parse_args()

    print(f"\n{'═'*60}")
    print("  BACKTEST DIFF — v1 vs v2 prompt")
    print(f"{'═'*60}")
    print(f"  Baseline: {args.baseline}")
    print(f"  New:      {args.new}\n")

    baseline = load(args.baseline)
    new = load(args.new)

    merged = merge(baseline, new)

    print(f"\n{'═'*60}")
    print("  FIELD-LEVEL CHANGES (stumble / mitigation / rec / thesis)")
    print(f"{'═'*60}")
    changed = find_changes(merged)
    print_changes(changed)

    accuracy_summary(baseline, new)

    if not changed.empty:
        print(f"{'═'*60}")
        print("  ACTION: Review each changed row above.")
        print("  For each change ask:")
        print("    1. Did stumble_type reclassify correctly? (Execution→Discovery)")
        print("    2. Did mitigation_track_record downgrade correctly? (strong→unproven)")
        print("    3. Did recommendation change as a result? Was it warranted?")
        print(f"{'═'*60}\n")


if __name__ == '__main__':
    main()

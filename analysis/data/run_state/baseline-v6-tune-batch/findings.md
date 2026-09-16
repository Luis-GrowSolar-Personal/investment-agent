
- 2026-09-16T01:05:37Z: Coverage miss (transcript): GIS 2026Q1 call_date=2025-09-17 status=404

- 2026-09-16T01:46:02Z: Coverage miss (transcript): SRE 2020Q1 call_date=2020-05-04 status=404

- 2026-09-16T02:11:00Z: **Bug caught by the pilot, before batch submission**: `all_calls()` in baseline_v6_tune_batch_driver.py originally scanned the ENTIRE shared `transcripts/` directory (train+tune tickers coexist there), not scoped to tune's working-symbol set. The 5-call pilot picked 5 ABBV (train) transcripts instead of tune ones. Cost of this: $0.4321 for 5 calls that duplicate work already scored and committed on train -- pure waste, not corpus contamination (results discarded, not written to any eval cache; renamed to scores_DISCARDED_wrong_ticker_pilot.jsonl, not deleted, for the record). Fixed `all_calls()` to filter by tune's working-symbol set before re-running the pilot. Had this not been caught, `cmd_submit()` would have used the same unfiltered `all_calls()` and the ~$47 batch would have re-scored up to 1,240 already-scored train calls alongside tune ones -- violating hard constraint #1 ("Train split ONLY... Do not score train again") and roughly doubling the real spend.

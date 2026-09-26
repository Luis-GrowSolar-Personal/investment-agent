# P7 bookkeeping — wrap-up

**Run ID:** `p7-bookkeeping`. Branch `sweep/db-corpus-baseline`. Cost $0; no API calls, DB writes or scoring. **Scope boundary: report, do not decide.**

**Bookkeeping commit: `f56745a`** (the three record files). This wrap-up is committed separately after it, since it cites the hash.

## Files changed
- `docs/architecture/VERSION_REGISTRY.json`: P7-three-voices `status` → `falsified`, `falsified: "2026-09-26"`, one-sentence `detail` naming gate 1 and the wrap-up; sha `0a34f5a9…` kept.
- `analysis/data/gate_ledger.json`: entry 3 (P7 vs P6B-minimal two draws) via `append_to_ledger()`; ledger now 3 entries. Three gates with value, range, target and per-draw result; `final_verdict: FALSIFIED`; `diagnostics_of_record` (gap/pressure shares, carrier cell 55 calls at 25.5% vs 33.2% base); `cost_usd` 34.07; holdout locked; tune not run. Every figure cites `p7-three-voices-train/results.json` and its key.
- `docs/architecture/PROMPT_ARCHITECTURE.md`: §2.2 P7 row → falsified, P9 row → "next (draft under review)"; dated **Result** paragraph under the P7 block (5 lines, includes the "reworded prompt is not queued" sentence); §2.5 sentence added, marked `(added 2026-09-26)`.

## Verification
`python3 analysis/whats_live.py` exits 0. It prints `MATCH evaluation_prompt promoted=357b6b0b…` (v6, unchanged); it prints nothing about candidates. Registry JSON parses. Ledger reloads with 3 entries.

## Propagation hits (not fixed; outside the named files)
- `docs/handoffs/2026-09-24-state-of-play.md:354`: "P7 … next candidate (§5.3)". A dated state-of-play; its .docx and artifact are also stale by design.
- `docs/handoffs/2026-09-26-next-steps-review.md:96`: "P7 is the next candidate prompt after they land" (historical review).

## Deviations / notes
- Rules 2–3 kept: B's champion status, promoted version and §2.3a rules 1–6 untouched; no P9 pre-registration.
- The prompt says "one commit at the end"; I made two (records, then this wrap-up) to cite the hash.
- Untracked files present at start and left alone: `prompts/P7-bookkeeping.md`, `prompts/P9-expected-return.md`, `docs/prompts/candidates/EVALUATION_PROMPT_P9_expected_return.md`. The tree was therefore not literally clean, but no tracked file was modified.
- `gate_ledger.json` is now tracked (commit in the log before this run), which resolves the earlier flag that it was untracked.

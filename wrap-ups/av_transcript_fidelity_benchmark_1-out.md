# Wrap-up: AV Transcript Fidelity Benchmark

Prompt: `prompts/av_transcript_fidelity_benchmark_1.md`
Full report: `analysis/av_fidelity_test/REPORT.md`
Manifest: `analysis/av_fidelity_test/av_fidelity_1-manifest.json`

## Status: Complete (all 7 planned samples processed; no resume needed)

Not a "partial run" — all 7 selected samples ran through Steps 1-6. 3 of 7 cleared the determinism gate and produced a full DB-vs-AV field diff; 4 of 7 failed the determinism gate and were correctly skipped at Step 5 per the prompt's hard-stop rule (this is a designed stop, not an incomplete run).

## Headline

- **AV budget: 7/15 calls used**, all successful, no rate-limit errors.
- **Determinism: 3/7 clean, 4/7 failed** — including one flip of `recommendation` itself (Hold vs Add, EOSE Q1) between two identical-input, temperature=0 runs of the same DB transcript. This confirms the instability EVALUATION_PROMPT.md's own v9/v10 changelog already documents; it is not a new finding, but it means only 3 of the 7 planned samples could produce a citable DB-vs-AV comparison this run.
- **Of the 3 comparisons that ran: 9/45 fields differed**, 3 of those 9 in the four flagged credibility/mitigation fields. The largest divergence (SPWR Q1: thesisHealth, recommendation, credibilityDelta, mitigationCapabilityTrackRecord all differ) also has the lowest DB/AV text-similarity ratio among that subset (0.1768).
- No conclusion is drawn on AV suitability — per the prompt, that's for the design session.

## Deviations flagged (see REPORT.md "Flagged premises" for full detail)

1. `docs/EVALUATION_PROMPT.md` on disk is the **v10+auto1 candidate** (gate "not yet run" per its own header), not the v6 text `server/lib/versions.js` claims is production. This benchmark used the file as found (per "do not modify" + the prompt naming this exact file), but the result describes v10+auto1's behavior, and separately surfaces that production's `evaluate.js` may currently be serving v10+auto1 while stamping rows `promptVersion: "v6"`.
2. Sample pool narrowed to AMPX/EOSE/SPWR only (AV coverage pre-confirmed only for those 3 of the 6 portfolio tickers; ENVX isn't a portfolio ticker in this DB).
3. Prompt's AV rate-limit spacing was corrected mid-session (15s → 70-75s, no auto-retry) per your explicit instruction before Step 2 ran — see `prompts/av_transcript_fidelity_benchmark_1.md` git history, commit `f9e2b02`.
4. A rate-limit-detection bug in my first fetch attempt (false-matched the word "note" inside legit transcript text) caused one unnecessary stop; fixed immediately, no AV call wasted.

## Not done / left for design session

- No qualitative diff of *why* AV word counts are so much lower than DB for EOSE/SPWR specifically (ratios ≤0.18) vs. AMPX (ratios ≥0.70) — flagged as anomalous, not investigated further.
- No comparison of this run's 4/7 instability rate against EVALUATION_PROMPT.md's previously logged 21.4%/69.0% instability figures — different corpus, different prompt version, would need its own controlled comparison.
- The v10+auto1 vs versions.js v6 mismatch above — needs a design-session decision, not a CLI fix.

## Follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 analysis/av_fidelity_test/driver.py   # re-run scoring (no new AV calls; uses saved raw/)
cat analysis/av_fidelity_test/REPORT.md       # full per-sample tables
```

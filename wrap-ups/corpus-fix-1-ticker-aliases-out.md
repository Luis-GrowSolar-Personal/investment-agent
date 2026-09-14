# corpus-fix-1-ticker-aliases — wrap-up

**Run ID:** `corpus-construction` (continuation). **Cost:** $0 Anthropic API, zero
transcripts scored. **Vendor calls this run:** 5. **Running period total:** 167 →
**172** — `analysis/data/run_state/corpus-construction/progress.json` →
`calls_used_total`.

## Plain-language summary

This run asked one question: when the vendor (EarningsCall.biz) said it had zero
earnings calls for a company, was that because the company really isn't covered,
or because the vendor files that company under a different stock symbol? Getting
this wrong either way is a real cost — treating a real gap as fixable wastes
effort, and treating a fixable identity mix-up as a real gap throws away usable
data.

Two companies were named up front: **Alphabet (GOOGL)** and **SVB Financial /
Silicon Valley Bank (SIVB)**. Checking the corpus file turned up two more
companies with the same zero-data symptom that weren't in the original framing:
**Honeywell (HON)** and **UPS**.

Result: **one real recovery, one confirmed genuine gap, and two false alarms.**
- **GOOGL was a symbol mix-up.** The vendor has Alphabet's earnings calls filed
  under `GOOG` (its other share class), not `GOOGL`. Querying `GOOG` returns 24
  calls across the full 2020–2025 window, correctly labeled "Alphabet Inc."
- **SIVB was not a symbol mix-up.** The vendor does have an `SIVB` entry, but it
  has zero events on it, and the two post-bankruptcy symbol variants tried
  (`SIVBQ`, `SIVB.Q`) don't exist in the vendor's list at all. This is a real,
  confirmed coverage gap.
- **HON and UPS were never actually gaps.** They were marked "not in vendor's
  symbol list" in the corpus file, but that flag dates from an earlier pass and
  was never re-checked in the fix pass that came after it. Querying them
  directly today returns full, valid data for both. No alias was needed — this
  was a stale data field, not a coverage or identity problem.

Because no company's actual pass/fail membership in the 78-company corpus
changed as a result of this — see below for why — **no new manifest file was
needed.** `CORPUS_MANIFEST_V2.json` is untouched. A new file,
`TICKER_ALIASES.json`, records the alias map and evidence for the scoring run
that will eventually need it.

## Ordering — confirmed

The addendum to `PREREGISTRATION_FIX.json` (new key `A5_ticker_alias_resolution`)
was written and committed (`f6cc2b5`) **before** any vendor query in this run.
The vendor probe ran afterward, in a separate commit (`7522890`).

## Candidates tried, per company

Vendor mechanism reused unchanged from Step B of the prior fix pass
(`analysis/corpus_construction_fix_driver.py`): `symbols-v2.txt` for the symbol
table, then `/events` per candidate symbol+exchange, filtered to 2020-01-01
through 2025-12-31.

| Company | Candidate tried | In vendor's symbol list? | Events (2020–25) | Company name returned |
|---|---|---|---|---|
| GOOGL | `GOOGL` (original) | No | 0 | — |
| GOOGL | `GOOG` (share-class alias) | **Yes** | **24** (2020-02-03 → 2025-10-29, max gap 100d) | "Alphabet Inc." |
| SIVB | `SIVB` (original) | Yes | 0 | "SVB Financial Group" |
| SIVB | `SIVBQ` (post-bankruptcy suffix) | No | 0 | — |
| SIVB | `SIVB.Q` (post-bankruptcy suffix, alt form) | No | 0 | — |
| HON | `HON` (original, re-queried) | **Yes** | **24** (2020-01-31 → 2025-10-23, max gap 105d) | "Honeywell International Inc." |
| UPS | `UPS` (original, re-queried) | **Yes** | **24** (2020-01-30 → 2025-10-28, max gap 105d) | "United Parcel Service, Inc." |

Full raw results: `analysis/data/corpus_v2/alias_probe_working.json`.
Candidate-selection reasoning: `analysis/data/corpus_v2/PREREGISTRATION_FIX.json`
→ `A5_ticker_alias_resolution`.

Candidate source (a) (dual-class check): GOOGL is the only dual-class company in
the 78-company corpus — checked the full member list in
`CORPUS_MANIFEST_V2.json` → `step_e_split` (train+tune+holdout, 78 names); no
other pair applies. Source (b) (post-bankruptcy suffix) applied only to SIVB —
no other company in the corpus has a documented bankruptcy/receivership
terminal event outside S4, and S4's other three restored names (FRC, RMO,
SUNW) already have real event data under their original symbols (per
`availability_fix_working.json`, all `in_symbol_list: true` with 6–10 calls
each). Source (c) (name search) wasn't needed — the share-class and
re-query checks above resolved every candidate without it.

## Which companies were recovered, which remain absent

- **Recovered (real, usable data found): GOOGL**, under alias `GOOG`.
- **Remains absent (confirmed genuine gap): SIVB.** Both bankruptcy-suffix
  aliases checked came back empty; the vendor's own `SIVB` row has zero events.
  This is the diagnostic the prompt named as the most likely contradiction to
  watch for — **it is the finding here.** The zero-event reading for SIVB was
  real, not an identity artifact.
- **Not a gap at all, no alias needed: HON, UPS.** Both were flagged as
  "not in vendor's symbol list" in `CORPUS_MANIFEST_V2.json`, but that field
  was never re-tested during the prior fix pass (absent from
  `availability_fix_working.json` entirely — confirmed by direct inspection).
  Re-querying their own original symbols today returns complete valid data for
  both. This is a **stale manifest field, not a resolved identity problem** —
  flagged as a finding for a future pass to correct, not corrected here (out of
  this run's scope, which is alias resolution, not manifest data hygiene).

## Rules applied unchanged — no relaxation

- GOOGL under `GOOG`: n=24 (≥12 required) and max_gap=100 days (≤240 required)
  — passes A1 exactly as registered. This does not change GOOGL's corpus
  membership: GOOGL is in **S5**, which the prompt's own framing treats as
  exempt from eviction on availability grounds regardless — GOOGL was already
  a member before this run. The identity fix changes *why* it's defensible to
  keep (real data exists, not just an exemption), not *whether* it's a member.
- SIVB: no alias recovered anything, so A2's registered S4 rule is applied to
  the same zero-event reading as before. SIVB remains excluded. **No threshold
  was loosened to admit it.**
- HON/UPS under their own original symbols: n=24 and max_gap=105 days each —
  both pass A1 cleanly. Neither was evicted or needed rescue: `CORPUS_MANIFEST_V2.json`'s
  own S1 note already records both as retained under the fix pass's explicit
  no-eviction rule, independent of this run.

## Resulting stratum counts — unchanged from V2

| Stratum | V2 target | V2 frozen | After this run |
|---|---|---|---|
| S1 | 20 | 22 | 22 (unchanged) |
| S2 | 16 | 15 | 15 (unchanged) |
| S3 | 20 | 20 | 20 (unchanged) |
| S4 | 8 | 5 | **5 — still 5 of 8, NOT 6 of 8** |
| S5 | 16 | 16 | 16 (unchanged) |
| **Total** | 80 | **78** | **78 (unchanged)** |

**S4 did not reach 6 of 8.** It stays at 5 of 8, per V2's manifest (`totals`
→ `frozen_total_v2`: 78; `strata.S4` → `frozen`: 5 entries). SIVB's alias
candidates found nothing, so the stratum's shortfall (3 companies) is
confirmed unresolved by identity fixes, exactly as the prompt anticipated as
the likely outcome to watch for.

**Alphabet (GOOGL) is now retrievable** — under `GOOG`, not `GOOGL` — with
real, complete data. It was already a corpus member before this fix (S5's
exemption), so retrievability doesn't change membership, but it does mean a
future scoring run should query `GOOG`, not `GOOGL`, to actually get Alphabet's
transcripts. `TICKER_ALIASES.json` records this for that purpose.

## Manifest — no V3 written

No company's pass/fail membership status changed as a result of alias
resolution:
- GOOGL: already a member (S5 exemption), still a member.
- SIVB: already excluded, still excluded.
- HON, UPS: already members (S1 no-eviction retention), still members.

Per the prompt's Step 3d ("re-freeze only if membership changed"),
**`CORPUS_MANIFEST_V2.json` is left completely intact and no
`CORPUS_MANIFEST_V3.json` was written.** V2's sha256 is unchanged:
`9b256b71eaa3038f5897a1a82d54c314abec8e843c5523a00c9a274a14f486ce` (as recorded
at freeze time — see the flagged discrepancy below).

## Alias map

Written to `analysis/data/corpus_v2/TICKER_ALIASES.json` regardless of outcome,
as instructed — includes GOOGL→GOOG (confirmed), SIVB (no working alias found),
and HON/UPS (no alias needed; original symbols valid) with full evidence for
each.

## Deviations from the prompt, flagged plainly

1. **Manifest sha256 mismatch — flagged before treating the file as
   authoritative, per the prompt's own instruction.** The prompt and
   `progress.json` both cite `CORPUS_MANIFEST_V2.json`'s sha256 as
   `9b256b71eaa3038f5897a1a82d54c314abec8e843c5523a00c9a274a14f486ce` (the
   value **at the time it was frozen**, commit `71fb50f`). The file's **current
   on-disk hash is `4ff870d073827f6dda221fae75bd12a9c4b231230864ea1e4eb17c1dc039b5bb`**
   — different. Cause, confirmed by diff: commit `7f7c222` (Step F/Step E lock,
   a *later* commit in the same corpus-construction-fix run) appended a new
   `step_e_split` key (the train/tune/holdout split) directly into this file
   after it was frozen, changing its bytes without changing its filename. The
   company list, strata, and per-company fields I relied on for this run are
   unchanged between the two versions (verified by diff — only the appended
   `step_e_split` block differs), so this run's conclusions are unaffected. But
   the file is no longer bit-identical to what it was at "freeze," and citing
   its sha256 going forward should use the current value, not the one recorded
   at freeze time, unless the specific historical file is what's meant. This is
   a finding for whoever runs corpus-fix-2 (the split), since corpus-fix-2 is
   the step that presumably wrote `step_e_split` and should reconcile which
   hash is authoritative going forward.
2. **Candidate list widened beyond the two named companies, per the prompt's
   own instruction to check the manifest for others.** HON and UPS were added
   after confirming they show zero/null events and `in_vendor_symbol_list:
   false` in `CORPUS_MANIFEST_V2.json`. This was recorded in the
   `PREREGISTRATION_FIX.json` addendum *before* querying, as required.
3. **HON/UPS's "stale manifest field" finding is reported, not fixed.**
   Correcting `CORPUS_MANIFEST_V2.json`'s stored `in_vendor_symbol_list`/
   `n_calls_2020_2025` fields for HON and UPS would touch the frozen manifest
   for a data-hygiene reason unrelated to alias resolution — out of this run's
   scope (identity resolution only). Left for a future pass or for
   corpus-fix-2/3 to decide whether it's worth correcting.

## What was deliberately not done

- No outcome balance work, no train/tune/holdout split work, no detection-
  threshold or cost projection — those are corpus-fix-2 and corpus-fix-3,
  explicitly out of scope here.
- No correction to HON/UPS's stale manifest fields (see deviation 3 above).
- No relaxation of A1 or A2 thresholds anywhere.
- No modification to `analysis/data/price_cache.json`.

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on the driver — passed.
- `json.load(...)` on `PREREGISTRATION_FIX.json`, `TICKER_ALIASES.json`, and
  `progress.json` after each edit — passed.
- Confirmed `git_dirty_at_start == false` for this run (stashed unrelated WIP
  first; corpus-fix prompt files for this and the next two prompts were left
  untouched as this task's own inputs).
- Confirmed the driver commit (`f6cc2b5`) precedes the results commit
  (`7522890`), and that `f6cc2b5` actually contains the driver file.

## Follow-up commands

```bash
# Re-run this probe (idempotent, 5 more vendor calls each time it's re-run)
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 analysis/corpus_fix1_ticker_aliases_driver.py run

# Inspect the alias map and raw probe results
cat analysis/data/corpus_v2/TICKER_ALIASES.json
cat analysis/data/corpus_v2/alias_probe_working.json

# Confirm the manifest hash discrepancy independently
shasum -a 256 analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json
git show 71fb50f:analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json | shasum -a 256
```

## End-of-run state

```
git stash pop   # restored unrelated WIP stashed before this run
git status      # clean except this run's own committed changes
```

Final branch: `sweep/db-corpus-baseline`, no merge, no push. Tree left clean
after popping the stash.

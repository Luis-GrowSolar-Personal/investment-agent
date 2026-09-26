# State of play 2026-09-26 bookkeeping. Wrap-up

**Run ID:** `sop-2026-09-26-bookkeeping`. Branch `sweep/db-corpus-baseline`. **Complete run. Cost $0** (no API calls, DB writes or scoring).
**Scope boundary: report, do not decide.** B's champion status, the promoted prompt (v6) and the promoted model (`claude-sonnet-4-6`) are unchanged. Opus is recorded as a finding, not registered as a candidate.

## Commits, in order
1. `f2e899f` `prompt: state of play 2026-09-26 bookkeeping` (this prompt file)
2. `b2f089b` `docs: state of play 2026-09-26 (analyst = downside detector; model policy; Opus finding); CLAUDE.md pointer` (`docs/handoffs/2026-09-26-state-of-play.md`, its `.docx`, and `CLAUDE.md`)
3. `9b8e5e2` `docs: §2.3a rule 8 (model policy); Opus screen recorded as ledger entry 5 finding` (`PROMPT_ARCHITECTURE.md`, `VERSION_REGISTRY.json`, `gate_ledger.json`, `analysis/opus_posthoc_repro.py`, this run's state)
4. This wrap-up commit, then `git push` (hash reported in chat).

Before committing I checked the tree: the only pending files were the three the prompt named, plus the prompt itself. Nothing else was modified or untracked apart from this run's own state directory.

## `CLAUDE.md` diff summary (verified before the commit)
Only the "Start here" block changed: (a) the path `docs/handoffs/2026-09-24-state-of-play.md` → `docs/handoffs/2026-09-26-state-of-play.md`; (b) the artifact URL `CW96Nyoxsx4kM4B2JF1Q8r` → `UgtKzgxJzdXRKGA8o8u5NW`; (c) the one-paragraph description of the sections (now §0 defined terms, §1 what ran, §2 what is known, §3 the decisions of 2026-09-26 including the model policy, §4 next steps, §5 what is open). Nine lines changed in one hunk; nothing else. The state of play's `.md` carries the same URL on its reading-version line (line 3).

## Step 1 — `PROMPT_ARCHITECTURE.md`
- §2.3a **rule 8, model policy**, added verbatim as given (placed after rule 7).
- §2.2 model-gate row: appended "screen run 2026-09-26 (`wrap-ups/opus-screen-out.md`); full test deferred under §2.3a rule 8".

## Step 2 — Opus recorded as a finding
- **`analysis/data/gate_ledger.json` entry 5** (`change_class_detail: model_screen`; champion "P6B-minimal on claude-sonnet-4-6 (two draws)", challenger "P6B-minimal on claude-opus-5-5 (one draw, 300 train calls)"; `final_verdict: "FINDING — not a candidate"`; `cost_usd: 14.06`). Metrics cited to `wrap-ups/opus-screen-out.md` and `opus-screen/results.json` keys: disagreement 33.3% / 35.0% vs 15.0%; screen figure +19.2 (+12.4 to +25.9); rank 0.270 vs B 0.138 / 0.123; bottom-47 hit 70.2%; top-58 hit 48.3%; 8 of 300 calls at +3 or higher (B: 70); cost $0.0469 per call.
- **`post_hoc_diagnostics`**, labelled "computed in Cowork after the run, not pre-registered", cited to state of play §2.4.
- **`VERSION_REGISTRY.json`** → `artifacts.model.findings`: one entry (`claude-opus-5-5`, screened 2026-09-26, "sharper on the downside, no better on winners, one draw of 300 calls", ledger entry 5, "not a candidate; see PROMPT_ARCHITECTURE.md 2.3a rule 8"). `promoted_version` untouched. `python3 analysis/whats_live.py` **exits 0**; it prints `MATCH model promoted=70303e61…` and `MATCH evaluation_prompt promoted=357b6b0b…` (v6); it prints nothing about the findings list.

## Which post-hoc Opus figures reproduced
All of them, from the committed score files, by `analysis/opus_posthoc_repro.py` (`posthoc_repro.json`; same 300 calls; paired gain = Opus rank correlation minus the mean of B's two draws; ticker-block bootstrap, 2,000 draws, seed 11):

| figure | state of play §2.4 | reproduced |
|---|---|---|
| paired ranking gain | +0.14 (+0.07 to +0.22) | **+0.139 (+0.072 to +0.212)** |
| megacaps | +0.13 (+0.02 to +0.28) | +0.123 (+0.013 to +0.282), using stratum S1 |
| the rest | +0.15 (+0.06 to +0.23) | +0.145 (+0.060 to +0.233) |
| excluding ±20 moves | +0.09 (−0.02 to +0.19) | +0.090 (−0.017 to +0.197) |
| mean score below B's, big losers | −1.25 | **−1.25** (59 calls) |
| mean score below B's, big winners | −0.55 | **−0.55** (43 calls) |

All are within 0.01 of the quoted numbers. The two largest differences: the megacap point (0.123 vs 0.13) and the paired range's upper end (0.212 vs 0.22). **One assumption:** the state of play does not define "megacaps"; I used stratum S1, which the earlier wraps describe as the megacap group. The ledger says so. Big losers and winners are ≤ −20 and ≥ +20, and the score difference is Opus minus the mean of B's two draws (versus draw 1 alone: −1.27 and −0.58).

## Propagation check (`git grep` over `docs/` and `CLAUDE.md`)
Files that still name the 2026-09-24 state of play as current, or call the model gate "next": none in the files this run may edit. Hits, not fixed:
- `docs/architecture/VERSION_REGISTRY.json` line 21 (`research_champion.note`) cites `docs/handoffs/2026-09-24-state-of-play.md` section 5 as the source of the 2026-09-25 champion decision: a historical source citation, still true.
- `docs/architecture/PROMOTION_GATE.md:728` says "before the next model gate run" about corpus balance; unrelated to the queue.
- Superseded handoffs (`2026-09-24-state-of-play.md`, the 09-25/09-26 next-steps documents) naturally mention the 09-24 document; excluded from the grep as provenance.

## Deviations
None from the prompt. Notes: rule 8 sits after rule 7 in §2.3a; the prompt asked for "verbatim", and the text is verbatim apart from the markdown numbering and line wrapping. The published artifact was not touched.

```bash
python3 analysis/opus_posthoc_repro.py
python3 analysis/whats_live.py
```

# Prompt- and Model-Version Drift — Investigation Findings

**Run:** `prompt-version-drift-investigation` | **Date:** 2026-09-03 | **Branch:** `sweep/db-corpus-baseline`
**Status:** Complete, full run (all 8 steps). Wall-clock: ~90 minutes.
**Scope:** Investigate and report only, per `PROMOTION_GATE.md` §1/§8. No code, config, DB, or ledger writes were made. All queries `SELECT`-only. No LLM calls, no deploys, no restarts.

---

## 0. Corrections and follow-up — 2026-09-03, after the run

Two checks were run after this report was written. Both change it. The original
text is corrected in place below; this section records what changed and why.

| # | What the report said | What is now established |
|---|---|---|
| 1 | Contamination began at the DEV deploy of **2026-08-25**, blast radius **one row** (id 895) | The 2026-08-25 deploy is only the *most recent* one. Railway retains just 20 deployment records (earliest `2026-08-22T18:02:05Z`), so the deploy that first carried v10+auto1 is no longer in Railway's history. `87bcfaa` is itself a commit **on `dev`** (2026-08-01 16:00) and `dev` took **44 commits between 2026-08-01 and 2026-08-23**, so with deploy-on-push the drifted build went live within days of 2026-08-01. **Contamination begins ≈2026-08-01, and the blast radius is the 18 Analysis rows created in August, not one.** |
| 2 | Corpus homogeneity "circumstantial, not provable" — the possibility that differently-scored rows sit inside the backtest window was left open | **Closed.** Every version-stamped row is outside the simulation window; see the query below. |

**Query 2, run 2026-09-03 (read-only):**

```
 promptVersion |       modelVersion       | rows | earliest_call | latest_call | inside_backtest
---------------+--------------------------+------+---------------+-------------+-----------------
 v6            | claude-sonnet-4-20250514 |    6 | 2026-05-06    | 2026-06-11  |               0
 v6            | claude-sonnet-4-6        |   36 | 2025-08-05    | 2026-08-26  |               0
```

`inside_backtest` counts rows whose transcript call date falls in
2022-01-01 – 2024-06-12 **and** whose ticker is in ALL16 — i.e. rows the
simulator actually loads. It is **zero for every stamped row**: the earliest
call date on any of the 42 stamped rows is 2025-08-05, more than a year after
the window closes. Combined with the migration-ordering explanation for the 764
unstamped rows (§2) and the fact that the one attempt to regenerate the v6 eval
cache spent nothing (`wrap-ups/regen-v6-eval-cache-and-run-sweep-out.md`:
*"No sweep run. No cache regenerated. $0 spent."*), **the backtest corpus is
established as unaffected and the settled configuration stands.**

**Decision taken (Luis, 2026-09-03): remediation option A, roll back.**
`docs/EVALUATION_PROMPT.md` was restored on `dev` at commit `c514ae1` to its
content at `7063465`, sha256
`357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`, verified
byte-identical to the restored file. `versions.js` needed no change:
`PROMPT_VERSION = 'v6'` is true again. v10+auto1 remains in history at `87bcfaa`
as an ungated candidate. **Option C (quarantine) is in force until the redeploy
lands** — no new evaluations. Relabelling the 18 affected rows, the startup
hash-check (§7), and the model-version question are all still open.

---

## 1. Headline

**Yes, there is live contamination.** DEV (Railway project `investment-agent-DEV`, service `investment-agent-DEV`) is running commit `37f535acb85e8edf9d48b663e41b24ec6b852777`, deployed **2026-08-25T14:36:46-04:00**. At that commit, `docs/EVALUATION_PROMPT.md` is byte-identical (sha256 `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14`) to the current working-tree file, which declares itself `v10+auto1 (auto-iterate candidate — pending gate)`. `server/lib/versions.js` at that same commit still hardcodes `PROMPT_VERSION = 'v6'`. **The deployed build sends v10+auto1 to the analyst and labels every resulting DB row `v6`.**

**Corrected 2026-09-03 (see §0):** this deploy is the most recent carrying v10+auto1, not the first. The drift went live on or about 2026-08-01; blast radius is 18 rows, not one.

**Separately, and worth stating up front: `investment-agent-PROD` is not running the application at all.** Its latest deployment (commit `2830d274`, 2026-04-04) has Railway status `FAILED`, zero running instances, and predates the entire Node/Express app — no `server/` directory exists at that commit. `CLAUDE.md`'s "Hosting: Railway (dev and prod services)" line does not currently describe reality for PROD. This wasn't the question this run was sent to answer, but it fell out of Step 1 and is reported plainly.

## 2. Corpus verdict

**Homogeneous only circumstantially — not provably so.** *(Materially strengthened 2026-09-03 — see §0: no version-stamped row falls inside the simulation window.)* This is the same conclusion the prior recon (`wrap-ups/recon-analysis-table-v6-corpus-out.md`, 2026-08-30 snapshot) reached; this run re-confirms it live and adds the mechanism.

- The backtest simulator and the live app **share one database and one `Analysis` table** — `analysis/simulator/data.py` reads `DATABASE_URL` from the same root `.env` that resolves to `investment-agent-db-dev`, the exact database DEV's `evaluate.js`/`save.js` write into. Production drift contaminates the corpus directly; the two pipelines are not independent.
- Of 806 total `Analysis` rows today: 764 have both `promptVersion` and `modelVersion` NULL, 6 are tagged `v6`/`claude-sonnet-4-20250514`, 18 are tagged `v6`/`claude-sonnet-4-6` (pre-cutoff), and 18 more `v6`/`claude-sonnet-4-6` post-cutoff (see table in §4).
- The 764 NULL rows are explained, not mysterious: `analysis/rebackfill_v6_analyses.py` — the script that bulk-populated most of the corpus — was committed 2026-05-02, **three weeks before** the `add_version_columns` migration (2026-05-23) existed. Its `INSERT` statement simply never had those columns to populate. It performs a wholesale, single-source regeneration from a `data/evals/v6/` cache directory, so its output is v6 *by construction of its input source* — but the DB rows themselves carry no proof of that, which is exactly why it remains circumstantial.
- **Nothing here disturbs the settled `ALLOCATOR_OPERATING_MODEL.md` §0 configuration.** One correction to this prompt's own framing: the settled figures ($184,819 final value, 17.32% drawdown, K=30) do not actually live in §0 of that document — §0 lists a 39.12% drawdown ceiling and 2.5pp `X`. The $184,819/17.32%/K=30 figures are real and settled, but they're in `docs/handoffs/2026-09-01-allocator-state-of-play.md` (lines 37, 45, 55). Wherever they live, they were computed from `analysis_corpus_20260830.sql`, which the prior recon already vetted as internally cutoff-consistent — untouched by anything found in this run.
- **New since the recon's snapshot:** the `Analysis` table now has 806 rows, not 805. One new row was written on 2026-08-31 — see §5.

## 3. Model-version finding (separate from the prompt finding)

`server/lib/versions.js` currently pins `MODEL_VERSION = 'claude-sonnet-4-6'` — **the exact model `data/gate_ledger.json` entry 1 rejected** with verdict `HOLD` (`delta_pp: -7.44` against a `noise_std_pp: 4.2` noise floor, `robustness_ok: false`).

The full sequence, reconstructed from git history (nothing here required a DB write):

1. **2026-05-23T13:31:42-04:00** (`a31f3c0`) — the model was accidentally bumped to `claude-sonnet-4-6` directly in `evaluate.js`, before `versions.js` existed.
2. **Same day, 2026-05-23T20:58:12-04:00** (`1d79015`) — caught same-day; `versions.js` created, model reverted to `claude-sonnet-4-20250514`.
3. **Same evening, 2026-05-23T19:55:18** — gate run (`gate_ledger.json` entry 1) formally tests this exact substitution. Verdict: **HOLD**. Champion retained. Explicit note in `PROMOTION_GATE.md` §10: "Re-run when sonnet-4-7 or later snapshot is available."
4. **Five weeks later, 2026-06-27T16:44:31-04:00** (`9028d0e`) — the identical substitution is reintroduced, via a code comment claiming Anthropic retired the dated snapshot. **No new gate run. No ledger entry. No wrap-up or doc note recording this as a deliberate exception.** This investigation did not independently verify the retirement claim (would require querying Anthropic's model catalog — out of scope for a read-only DB/git run).
5. It has been live ever since, including in the current DEV deployment.

**This is itself a `PROMOTION_GATE.md` §8 finding: an unrecorded migration to a model the gate explicitly rejected.** It is arguably the larger of the two problems this investigation was asked to weigh — the prompt affects what the analyst says; this affects that too, and the regression is already measured (7.44pp against a 4.2pp noise floor).

## 4. Timelines

### `docs/EVALUATION_PROMPT.md` — content hash at every commit that ever touched it

| Commit | Date | Header (quoted) | sha256 |
|---|---|---|---|
| `3bf13fa` | 2026-03-31 17:15:52-04:00 | *(no version header yet)* | `06a5f1ae55a7c6030d8e32c2d31c3ba9d55d87297391a006b69eca12597cc056` |
| `3a658b2` | 2026-04-04 16:54:42-04:00 | *(rename to `docs/`, content unchanged)* | `06a5f1ae55a7c6030d8e32c2d31c3ba9d55d87297391a006b69eca12597cc056` |
| `75596f2` | 2026-04-07 21:01:32-04:00 | *(structured score fields added, still no header)* | `714ba3cc7517afa8a4956bab9f242566699192e9800882975ef5f193468940a6` |
| `22d2c71` | 2026-05-02 12:33:23-04:00 | `# Version: v6 (stable best after v5→v8 iteration)` | `74ec94ae166b649bb3d8639288f49b6b7076dcb26f1cde727da1a6f98e19ba15` |
| `3d9a9d6` | 2026-05-30 10:17:08-04:00 | *(unchanged: "v6...")* | `1734ea8c9795f53ab5b3ba3a68c520bdb52dbb3f0a3607d20ca02c6f3255dfc1` — **content changed, header didn't** |
| `7063465` | 2026-06-27 16:26:16-04:00 | *(unchanged: "v6...")* | `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b` — **content changed, header didn't; last commit to declare v6** |
| `87bcfaa` | 2026-08-01 16:00:12-04:00 | `# Version: v10+auto1 (auto-iterate candidate — pending gate)` | `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14` — **== deployed, == working tree** |

The header changed exactly twice in the file's whole history; content changed at *every* commit that touched it. The two mid-timeline "content changed, header didn't" commits (`3d9a9d6`, `7063465`) turned out to be benign on inspection — they trace to already-documented decisions (`DESIGN_PRINCIPLES.md`'s retired variable Type B cap, and the `summary` field addition), not disguised drift. But they prove the header was never a reliable content signal even before this episode.

**Commit at which the file last declared v6:** `70634653bc0378c515203ec900aa98937f9807b2`, content sha256 `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`. (Needed for remediation option A below.)

### `server/lib/versions.js` — content hash at every commit that ever touched it

| Commit | Date | `PROMPT_VERSION` | `MODEL_VERSION` | Commit message |
|---|---|---|---|---|
| `1d79015` | 2026-05-23 20:58:12-04:00 | `'v6'` | `'claude-sonnet-4-20250514'` | "Portfolio Analyst Phase 1: Position/Lot/CashBalance schema + entry UI; two-hurdle gate logic; model-pin gate result (HOLD)" |
| `9028d0e` | 2026-06-27 16:44:31-04:00 | `'v6'` (unchanged) | `'claude-sonnet-4-6'` | "fix: update model to sonnet-4-6 (dated snapshot retired); feat: analysis summary field" |

`versions.js` has not been touched since `9028d0e` — 68 days before `87bcfaa` deployed v10+auto1 with no corresponding edit.

### `docs/EVALUATION_PROMPT.md`'s own iteration log, quoted exactly

> `v6: added explicit Execution-stumble handling + clarified no-stumble cases. Backtest: ENPH 6/9 + TTD 3/6 = 9/15 (60%). Current best (live in production as of 2026-07-05).`

**This self-description is now known false** — v6 is not what's live; v10+auto1 is.

> `v9 (2026-07-05, candidate): ... Gate status: must clear BOTH (a) Step 0 rerun showing reduced instability, AND (b) full backtest regression matching or beating v6's 60% (9/15) baseline before promotion to production. ... RESULT (Gate A, 2026-07-05): FAILED. Stability got WORSE, not better — 26/84 unstable (69.0%) vs v6's 18/84 (21.4%).`

**v9 failed its own stated gate.**

> `v10 (2026-07-05, candidate): ... Gate status: not yet run.`

**v10's gate was never run.**

> `v10+auto1 (2026-07-06, auto_iterate_prompt.py): [describes a specific decision-matrix defect — a run mislabeled 'Add' as 'Hold (with watch condition for Add)']`

**v10+auto1 carries no gate-status statement at all.** It is the most recent entry, the least gate-documented, and it is what's deployed today.

`data/gate_ledger.json` has exactly **one** entry, and it is a §2.2b model-version test, not a §2.2a prompt test — no prompt version (v7 through v10+auto1) has ever been gate-tested via the formal ledger mechanism.

## 5. Contamination scope

Anchored to the DEV deploy timestamp (`2026-08-25T14:36:46-04:00`), not the commit date:

```sql
SELECT id, "transcriptId", "createdAt", "promptVersion", "modelVersion"
FROM "Analysis" WHERE "createdAt" >= '2026-08-25 14:36:46-04' ORDER BY "createdAt";
```

| id | transcriptId | createdAt | promptVersion | modelVersion |
|---|---|---|---|---|
| 895 | 786 | 2026-08-31 14:41:11.369 | v6 | claude-sonnet-4-6 |

**Superseded — see §0. The correct count is 18 rows (all of August), anchored to ≈2026-08-01.** The query below was anchored to the most recent deploy rather than the first, and returns only the newest of those rows: NVDA, call date 2026-08-26, "NVIDIA (NVDA) Q2 2027 Earnings Call Transcript," recommendation "Add," thesisHealth "Strengthening." This count is **not** the contamination scope; it is the count since the latest deploy. Railway retains only 20 deployment records, so the first drifted deploy cannot be dated from Railway — it is bounded instead by `87bcfaa`'s own date on `dev` (2026-08-01) and the 44 dev commits that followed before 2026-08-23.

- `promptVersion: "v6"` on this row is **known false** — the build serving it holds v10+auto1 content.
- `modelVersion: "claude-sonnet-4-6"` is **accurate as a description of what ran**, but that model is the one the gate rejected (§3) — accurate label, unvalidated choice.

## 6. Remediation options — presented, not chosen

### Prompt-version question

- **A. Roll back.** Restore `docs/EVALUATION_PROMPT.md` to the v6 blob at commit `7063465` (sha256 `357b6b0b...`) and redeploy DEV. Leaves v10+auto1 as an ungated candidate awaiting a proper §2.2a run — restores the gate's intended order (gate, then promote).
- **B. Ratify.** Leave v10+auto1 running, correct `versions.js` to say so, relabel the one affected row (id 895), and run the §2.2a gate retroactively. **This inverts gate-then-promote and is a process exception, not a precedent** — and per §4, v10+auto1 sits downstream of a version (v9) that already failed a gate once.
- **C. Quarantine.** Stop generating new analyses on DEV until a decision is made. Compatible with either A or B — an immediate step either way, not a third alternative. No time pressure was found that argues against it.
- **D. What Steps 1–6 actually revealed, beyond A/B/C:** there **is** live contamination (not "none" — flagging per the prompt's own instruction to state this plainly either way). The one bounded, concrete fact worth weighing alongside A/B/C: the blast radius today is exactly one row.

### Model-version question — its own option set

- Re-pinning to a dated snapshot may be moot if `claude-sonnet-4-20250514` really is retired (unverified by this run). If Luis wants to check, current dated Claude snapshots would need to be looked up directly — this investigation did not query Anthropic's model catalog (out of scope for a read-only DB/git run).
- Whatever model is chosen, adopting it is a **§2.2b equivalence-hurdle gate run** — the same kind of run entry 1 already did — not a config edit. The prior HOLD verdict does not silently expire; a fresh run against a current corpus is what would supersede it.
- Quarantine (option C above) applies equally to this question, and for the same reason: every live evaluation between now and a decision runs on a model the last gate rejected.

## 7. Prevention

Separate from remediation. At minimum: have the server hash the prompt file it loads at startup and refuse to boot if that hash doesn't match the version `versions.js` declares. Roughly five lines — read `docs/EVALUATION_PROMPT.md`, hash it, compare against a recorded hash for the declared `PROMPT_VERSION`, and fail loudly rather than silently serving mismatched content. This is the live-system counterpart to `CONFORMANCE_FIXTURES.md`'s principle: the validated artifact and the running artifact must be provably the same object. Proposed here, not implemented — this run made no code changes.

## 8. My read of the evidence

Two separable problems, two separable reads:

**Prompt version.** The evidence points toward **A (roll back)** over B. Not because v10+auto1 is necessarily worse — nobody knows, because it's never been measured — but because its own file says exactly that: v9 failed a gate, v10's gate was never run, and v10+auto1 is a further, undocumented patch on top of an unproven candidate. Ratifying it now would be promoting on the strength of "it's already running," which is the exact failure mode `PROMOTION_GATE.md` §1 exists to prevent. The blast radius for rolling back is small (one known-mislabeled row) and the cost of running an ungated candidate in production compounds with every real evaluation.

**Model version.** This one reads more clearly as an emergency exception that was never logged as such, not a considered decision either way. A same-day catch-and-gate-and-revert on 2026-05-23, followed five weeks later by a silent reintroduction of the identical, already-rejected substitution — with a plausible but unverified justification ("dated snapshot retired") — is the shape of "someone hit a wall and shipped the only thing that worked," not "someone re-evaluated and chose differently." If the retirement claim is true, the honest fix is a fresh §2.2b gate run against the current model landscape, not treating the 2026-05-23 HOLD as having quietly expired.

**Combined:** Quarantine (C) reads as the low-regret first move regardless of which way A/B and the model-question land — it costs nothing (no active development is blocked, per the ground rule that there's no time pressure here) and stops the one contaminated-row count from growing while the two decisions above get made deliberately.

---

## Not investigated (out of scope for this run)

- Whether `claude-sonnet-4-20250514` was actually retired by Anthropic — would need to query Anthropic's own model catalog/docs.
- Whether row 895's actual `recommendation`/`thesisHealth` output would differ under a true v6 prompt — would require an LLM call, out of scope for this investigation's no-LLM-calls rule.
- Railway managed Postgres backup/restore paths (dashboard-only, not reachable via CLI within this run).
- The two benign mid-timeline content changes (`3d9a9d6`, `7063465`) were traced to already-documented decisions but not further audited for other undocumented deltas beyond the diffs shown in §4.

## Follow-up commands

Re-run the contamination-scope query directly (read-only):

```zsh
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  psql "$DATABASE_URL" -c "
SELECT id, \"transcriptId\", \"createdAt\", \"promptVersion\", \"modelVersion\"
FROM \"Analysis\" WHERE \"createdAt\" >= '2026-08-25 14:36:46-04' ORDER BY \"createdAt\";
"
```

Confirm current DEV/PROD deploy state (needs `railway` CLI auth):

```zsh
railway link -p investment-agent-DEV --service investment-agent-DEV
railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['environments']['edges'][0]['node']['serviceInstances']['edges'])"
```

Full run state, including every query and diff run in this investigation: `analysis/data/run_state/prompt-version-drift-investigation/findings.md`.

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015Kb2SZQL6A1rgyH82EzBB2

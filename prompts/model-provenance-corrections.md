# Model provenance — registry corrections and retirement tracking

Small corrective run. **$0 API spend. No LLM calls. No DB writes.** Branch
`sweep/db-corpus-baseline`; no merge to `dev`. `run_id`
**`model-provenance-corrections`**.

Read first: `docs/architecture/PROMOTION_GATE.md` **§8 (corrected 2026-09-12)
and the new §8.1**, which this run implements in the registry and tooling.

## Why

A web check of Anthropic's own documentation on 2026-09-12 established two
facts that invalidate assumptions recorded throughout this repo:

1. **`claude-sonnet-4-6` is NOT a bare alias — it is a pinned snapshot.** From
   Claude 4.6 onward the dateless ID *is* the canonical immutable snapshot;
   Anthropic ships new versions under new IDs and never repoints an existing
   one. The pre-4.6 convention (where `claude-sonnet-4-5` floated) is what §8
   was written against. **Recording the model ID string is therefore
   sufficient provenance — no behavioural fingerprint is needed**, because
   silent drift of a pinned ID cannot happen.
2. **`claude-sonnet-4-20250514` genuinely retired 2026-06-15.** The registry
   records that claim as "never independently verified against Anthropic's
   model catalog." It is now verified. And **`claude-sonnet-4-6` is Active
   with retirement not sooner than 2027-02-17**, with ≥60 days' notice policy.

## Step 0 — hygiene, and a hard precondition

**PRECONDITION — check this first and STOP if it fails.** This run rewrites
`docs/architecture/VERSION_REGISTRY.json`. Every scoring driver reads that
file as a hard gate before each call, and `version_guard._load_registry()`
does **not** cache — it re-reads from disk. A scoring run that catches the
file mid-write, or during Step 5's deliberate mutation, will hard-fail and
abort a paid run for entirely the wrong reason.

**So: confirm no scoring run is in flight before touching the registry.**
Check `analysis/data/run_state/*/progress.json` for any run whose steps show
an incomplete scoring phase (in particular `test4-analyst-noise-floor-v6`).
If one is live, **stop and report** — do not proceed, do not "work around it."

Then: clean tree (a concurrent session's `ec-fidelity-benchmark-1` files may
be dirty — record, do not touch). Driver/edits committed before any manifest.
**Do not modify `analysis/test4_noise_floor/`, `analysis/test6_look_ahead/`,
or any `test4-analyst-noise-floor-v6` state.**

## Step 1 — correct the registry's `model` artifact

In `docs/architecture/VERSION_REGISTRY.json`:

- **Withdraw the bare-alias flag.** The `note` currently says
  `"'claude-sonnet-4-6' is a bare, undated alias -- violates PROMOTION_GATE.md
  Sec8's own rule. Known forced exception..."`. That is **wrong**. Replace it
  with the corrected understanding, citing §8's 2026-09-12 correction, and
  **keep the old text visible as superseded** per this project's standing rule
  that a corrected claim supersedes explicitly and is never quietly replaced.
- **Record the retirement verification**: `claude-sonnet-4-20250514` retired
  2026-06-15 — previously unverified, now confirmed.
- **Add `retirement_date: "2027-02-17"`** (tentative, "not sooner than") and a
  `retirement_policy_notice_days: 60` field.
- Update `status` from `"promoted, flagged"` to reflect that the flag is
  withdrawn.

## Step 2 — add `model` to every benchmark record

All seven `benchmarks` records currently carry **no model field** — verified
this session. So staleness is computed on the prompt axis only, and the
registry is blind to model change. Add the model ID in effect for each:

- `settled_control`, `test1_zero_info_floor`, `ew_baseline`,
  `sizing_channel_null`, `small_cap_materiality` — derived from the **corpus**,
  scored by **`claude-sonnet-4-20250514`** (retired). Verify per record rather
  than assuming; a record computed purely in-simulator from corpus rows
  inherits the corpus model.
- `test4_per_tier_noise_floors`, `test6_look_ahead_null` — **`claude-sonnet-4-6`**.

Add the model to each record's `valid_while` so a future model change marks
them stale automatically, exactly as a prompt change does today.

## Step 3 — retirement countdown in `whats_live.py`

Add a section reporting **days until retirement** for any registered model
carrying a `retirement_date`, with a warning threshold at **90 days** (ahead
of the 60-day notice, so the deadline arrives as a countdown rather than an
email). Today that is `claude-sonnet-4-6` → 2027-02-17.

Per §8.1 step 2, the message must name the consequence, not just the date:
before retirement, a paired bridge sample must be captured under both the
outgoing and incoming model, because after retirement pairing is impossible
forever — as already happened with the corpus.

Keep exit-code behaviour unchanged: a retirement countdown is informational,
**not** a non-zero exit.

## Step 4 — withdraw the stale caveats in prior wrap-ups

`wrap-ups/test4-analyst-noise-floor-out.md` and
`wrap-ups/test6-look-ahead-prohibition-out.md` both carry
"reproducibility risk: **bare alias, flagged**". **Do not rewrite the
wrap-ups** — they are historical records. Instead append a short, dated
correction note at the end of each, stating the caveat is withdrawn and
pointing at §8's correction. Same treatment for any equivalent claim in
`docs/handoffs/2026-09-07-state-of-play.md`.

## Step 5 — verify

Show output for each:

1. `whats_live.py` → exit 0; retirement countdown present and correct for
   `claude-sonnet-4-6`; benchmark records now display their model.
2. A benchmark record's staleness flips when its model is changed — proving
   the new `valid_while` entry actually works, not merely that the field
   exists. **Do this on a COPY of the registry at a temporary path, pointing
   the checker at that copy. Never mutate the live
   `docs/architecture/VERSION_REGISTRY.json` for a demonstration**, even
   briefly and even with a revert — it is a live runtime dependency of every
   scoring driver. Delete the copy afterward.
3. `git status --short` clean of demo residue.

## Report

> **Registry: bare-alias flag withdrawn (old text preserved as superseded),
> retirement of 4-20250514 verified, retirement_date 2027-02-17 recorded.
> Benchmarks: model added to [N]/7 records, [N] corpus-model / [N]
> sonnet-4-6; valid_while extended. whats_live.py: countdown [N] days,
> warning threshold 90d, exit 0. Wrap-up caveats withdrawn in [N] files by
> appended note, originals unaltered. Demo 2 (staleness flips on model
> change) [passes]. $0 API spend.**

Flag plainly: any benchmark record whose model could not be determined from
its provenance rather than assumed, and any place the withdrawn bare-alias
claim appears that this run did not reach.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers.
- No LLM calls, no DB writes, no merge to `dev`, no allocator or
  trend-analyst logic changes.
- Historical wrap-ups are appended to, never rewritten.
- Do not write new handoff docs. This prompt in, one wrap-up out.

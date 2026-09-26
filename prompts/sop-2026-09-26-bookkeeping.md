# State of play 2026-09-26: commit it, and record the model policy — $0

**Run ID:** `sop-2026-09-26-bookkeeping`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/sop-2026-09-26-bookkeeping-out.md`
**Cost: $0.** File edits and commits only. No API calls, no DB writes, no
scoring.

## Framing

A new state of play was written in Cowork: `docs/handoffs/2026-09-26-state-of-play.md`,
with `.docx` and a published reading version
(<https://claude.ai/artifact/UgtKzgxJzdXRKGA8o8u5NW>). `CLAUDE.md`'s "Start
here" pointer was updated to it. None of this is committed yet. This run
commits those files and records two decisions from the state of play's §3
where future sessions read them. It decides nothing new.

**Read first:** `docs/handoffs/2026-09-26-state-of-play.md` (all);
`wrap-ups/opus-screen-out.md`; `gate_ledger.json` entries 2–4 (copy their
shape).

## Ground rules

1. $0. No API calls, no DB writes, no cache refresh.
2. Record, don't interpret. Every figure cites its wrap-up and key.
3. **Do not change** B's champion status, the promoted prompt (v6) or the
   promoted model (`claude-sonnet-4-6`).
4. **Opus is recorded as a finding, not a champion or candidate.** Do not
   register it as a model candidate.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/sop-2026-09-26-bookkeeping/`.
`progress.json` first. Then, before the clean-tree check, verify these
pending changes and commit them, **in this order, each as its own
commit**:

1. **This prompt file** → `prompt: state of play 2026-09-26 bookkeeping`.
2. **The state of play**, `docs/handoffs/2026-09-26-state-of-play.md`
   and `.docx` **together with `CLAUDE.md`**, in one commit, because the
   pointer must land in the same commit (`CLAUDE.md` rule). Commit message:
   `docs: state of play 2026-09-26 (analyst = downside detector; model policy; Opus finding); CLAUDE.md pointer`.
   - Verify that the `CLAUDE.md` diff touches only the "Start here" block:
     the path, the artifact URL, and the one-paragraph description of the
     sections.
   - Verify that the `.md`'s reading-version line carries the URL above.
3. **Any other modified or untracked file → stop and report.** Do not
   commit it.

Then clean tree; hard stop if `git_dirty` cannot be recorded `false`.

## Step 1 — `PROMPT_ARCHITECTURE.md` §2.3a, rule 8 (decided 2026-09-26)

Add it verbatim, in plain language:

> **8. Model policy.** Research iterates on Sonnet (`claude-sonnet-4-6`).
> Larger models (Opus, Fable) are used sparingly: **once**, to confirm a
> finished Sonnet candidate. It is kept if it's better and dropped if not.
> A larger model is never made the research incumbent, so future
> candidates are not forced onto the costlier model. A model step is
> judged **by ranking strength and same-size groups (bottom N / top N),
> never by the fixed cut-offs** (≤ −2 / ≥ +3), because those were fitted
> to Sonnet's scale. Opus scored only 8 of 300 calls +3 or higher, against
> Sonnet's 70. The research incumbent and the production model are
> separate decisions. Source: `docs/handoffs/2026-09-26-state-of-play.md` §3.

Also in `PROMPT_ARCHITECTURE.md`, in the §2.2 row for the model gate on
B: add "screen run 2026-09-26 (`wrap-ups/opus-screen-out.md`); full test
deferred under §2.3a rule 8."

## Step 2 — record the Opus screen as a finding, $0

**2a. `analysis/data/gate_ledger.json` — entry 5.** Shape like entries 2–4.
- `change_class: "analyst"`, `change_class_detail: "model_screen"`,
  `champion: "P6B-minimal on claude-sonnet-4-6 (two draws)"`,
  `challenger: "P6B-minimal on claude-opus-5-5 (one draw, 300 train calls)"`.
- `final_verdict: "FINDING — not a candidate"`.
- `final_reason`: one sentence. Opus reads calls differently and is
  sharper on the downside; kept as a finding under §2.3a rule 8.
- `metrics`, cited to `wrap-ups/opus-screen-out.md`:
  - disagreement 33.3% / 35.0% against Sonnet's 15.0%;
  - screen figure +19.2 (+12.4 to +25.9);
  - ranking 0.270 against B's 0.138 / 0.123 on the same 300;
  - bottom-47 hit 70.2%;
  - top-58 hit 48.3%;
  - 8 of 300 calls scored +3 or higher;
  - cost $0.0469 per call.
- `post_hoc_diagnostics`, **labelled "computed in Cowork after the run,
  not pre-registered"**, cited to the state of play §2.4:
  - paired ranking gain +0.14 (+0.07 to +0.22);
  - megacaps +0.13 (+0.02 to +0.28) against the rest +0.15 (+0.06 to
    +0.23);
  - excluding ±20 moves +0.09 (−0.02 to +0.19);
  - mean score below B's: big losers −1.25, big winners −0.55.

  If you can reproduce any of these from the committed score files
  cheaply, do so and say which reproduced. Otherwise mark them "quoted,
  not reproduced".
- `cost_usd: 14.06`.

**2b. `docs/architecture/VERSION_REGISTRY.json`.** Under
`artifacts.model`, add a `findings` list with one entry:
- `claude-opus-5-5`;
- screened 2026-09-26;
- "sharper on the downside, no better on winners, one draw of 300 calls";
- ledger entry 5;
- "not a candidate; see PROMPT_ARCHITECTURE §2.3a rule 8".

`promoted_version` stays `claude-sonnet-4-6`. Run
`python3 analysis/whats_live.py`; it must exit 0.

Commit: `docs: §2.3a rule 8 (model policy); Opus screen recorded as ledger entry 5 finding`.

## Step 3 — propagation check

`git grep` `docs/` and `CLAUDE.md` for any file that still names the
2026-09-24 state of play as current, or calls the model gate "next". List
the hits. Fix only files named above.

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/sop-2026-09-26-bookkeeping-out.md`, `.md` only. It lists:
- the commit hashes, in order;
- the `CLAUDE.md` diff summary;
- what `whats_live.py` printed;
- which post-hoc Opus figures reproduced;
- the propagation hits.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure. **Finish with `git push`** of `sweep/db-corpus-baseline`
after the wrap-up commit, and report the pushed hash; on failure, say so
and never force.

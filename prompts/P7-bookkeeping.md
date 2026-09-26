# P7 bookkeeping — record the falsified result, $0

**Run ID:** `p7-bookkeeping`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P7-bookkeeping-out.md`
**Cost: $0.** File edits only. **No API calls, no DB writes, no scoring.**

## Framing

P7 (three voices) ran on train and was falsified on its purpose gate:
its top 235 calls were right 31.5% of the time against a 47.0% target
and B's 39.6% / 36.2% (`wrap-ups/P7-three-voices-train-out.md`). The
standing rule is that every candidate is logged whether it survives or
not, so nobody re-runs it. This run records the result in the three
places future sessions read. It decides nothing new.

**Read first:** `wrap-ups/P7-three-voices-train-out.md` (all);
`analysis/data/run_state/p7-three-voices-train/results.json`;
`gate_ledger.json` entry 2 (copy its shape).

## Ground rules

1. Record, do not interpret beyond the wrap-up. Every figure cites
   `results.json` and its key.
2. Do not touch B's research-champion status, the promoted version, or
   §2.3a rules 1–6.
3. Do not write P9's pre-registration (it is a separate draft under review).
4. Clean tree at start; one commit at the end.

## Steps

**1. `docs/architecture/VERSION_REGISTRY.json`.** P7-three-voices
candidate: `status` → `falsified`, `falsified: "2026-09-26"`, and a
one-sentence `detail` naming gate 1 and the wrap-up. Keep the sha
(`0a34f5a9…`). Run `python3 analysis/whats_live.py` afterwards; it must
exit 0.

**2. `analysis/data/gate_ledger.json` — entry 3, P7 vs B.** Append with
`append_to_ledger()`, shaped like entry 2:
- `change_class: "analyst"`, `change_class_detail: "prompt"`,
  `champion: "P6B-minimal (two draws)"`, `challenger: "P7-three-voices"`.
- `split: "train"`, `holdout: "locked — not yet looked at"`,
  `tune: "not run — falsified on train"`.
- `gates`: the three, each with value, range, target, held/failed per B
  draw. Gate 1 31.5% vs 47.0%, failed. Gate 2 vs draw 1 −0.017 (−0.050
  to +0.016), failed; vs draw 2 +0.014, held; not held against both.
  Gate 3 58.6% vs 57.0%, held.
- `final_verdict: "FALSIFIED"`, `final_reason`: one sentence from the
  wrap-up's "What this means".
- `diagnostics_of_record`: the `gap` and `pressure` shares (claims_ahead
  78.8%, avoided 79.7%), and the predicted carrier cell (numbers_ahead +
  answered, 55 calls, 25.5% right against a 33.2% base rate). These are
  why a reworded P7 is not queued.
- `cost_usd: 34.07`.

**3. `docs/architecture/PROMPT_ARCHITECTURE.md`.**
- §2.2 table: P7 row → **falsified 2026-09-26 (train; gate 1 31.5% vs
  47%)**. P9 row → **next (draft under review)**.
- Under the P7 block, add a dated **Result** paragraph of at most five
  lines. It covers the gate outcome; the finding that the model labelled
  ~80% of calls "claims ahead" and "avoided", so the labels could not
  separate companies; that the predicted carrier cell was below the base
  rate; and **"A reworded three-voices prompt is not queued: the groups
  the labels did form showed no bullish edge."**
- §2.5: add one sentence. "P7 passed its pre-flight at 20.7% disagreement
  against a 20% threshold and then failed; disagreement is not
  improvement. Pre-flights for candidates with new output fields also
  stop when those fields behave far outside their predictions (see the
  P9 draft)." Mark it `(added 2026-09-26)`.

**4. Propagation check.** `git grep` `docs/` and `CLAUDE.md` for P7
described as "next" or "running". List the hits; fix only the files
named above.

Commit: `docs: P7 falsified on train — registry, ledger entry 3, PROMPT_ARCHITECTURE result`.

## Report

`wrap-ups/P7-bookkeeping-out.md`, `.md` only. It lists the files changed,
the commit hash, what `whats_live.py` printed, and the propagation hits.
**Scope boundary: report, do not decide.**

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure.

# Wrap-up: Prompt- and Model-Version Drift Investigation

Prompt: `prompts/prompt-version-drift-investigation.md`
Full findings document (the actual deliverable): `docs/handoffs/2026-09-03-prompt-version-drift.md` + `.docx`
Run state (every query/diff run): `analysis/data/run_state/prompt-version-drift-investigation/findings.md`

## Status: Complete, all 8 steps. Wall-clock ~90 minutes. Not a partial run.

Run-state resume protocol used (no `cells.jsonl` — this run is a sequence of independent facts, not a cell grid, as the prompt itself specified). No resume was needed; this was a fresh run, `git_dirty=false` confirmed before starting.

## Headline

Live contamination **confirmed**: DEV (`investment-agent-DEV` on Railway) is running commit `37f535a` (deployed 2026-08-25), whose `docs/EVALUATION_PROMPT.md` is byte-identical to the current v10+auto1 working-tree file, while `versions.js` still stamps `PROMPT_VERSION = 'v6'`. Exactly **one** stored `Analysis` row (id 895, NVDA) was written under this contaminated build so far.

Separately: `investment-agent-PROD` on Railway is **not running the application at all** — its last deploy (commit from 2026-04-04, before `server/` existed) is status `FAILED`, zero instances.

Model-version finding, independent of the prompt one: production is pinned to `claude-sonnet-4-6`, the exact model `data/gate_ledger.json`'s only entry rejected with verdict `HOLD` (-7.44pp vs 4.2pp noise floor). The reintroduction (commit `9028d0e`, 2026-06-27) has no recorded justification beyond a code comment claiming the previous dated snapshot was retired — unverified by this run, and never logged as a process exception anywhere searched (wrap-ups, handoffs, ledger, commit history).

Full detail, timelines, corpus-homogeneity analysis, remediation options (presented, not chosen, per the ground rule), and prevention proposal are all in the handoff document — this wrap-up intentionally doesn't restate them.

## Deviations from the prompt

- One premise correction: the prompt's evidence table attributes `$184,819` / `17.32%` / `K=30` to `ALLOCATOR_OPERATING_MODEL.md` §0. That section doesn't contain those figures (it has 39.12% drawdown ceiling, 2.5pp `X`). The real figures live in `docs/handoffs/2026-09-01-allocator-state-of-play.md`. Doesn't change Step 3's substance — same corpus either way — but flagged rather than silently corrected.
- Two mid-timeline commits (`3d9a9d6`, `7063465`) matched the "content changed, header didn't" pattern the prompt specifically warned about — investigated and found benign (already-documented decisions), not additional undisclosed drift. Reported anyway since the prompt asked for this exact scan.
- Found one thing the prompt didn't ask about but Step 1 surfaced directly: PROD's non-deployment status. Reported since it contradicts `CLAUDE.md`'s hosting description.

## Not done / left for the design session

- No verification of whether `claude-sonnet-4-20250514` was actually retired by Anthropic (would need to query Anthropic's model catalog, out of scope for a read-only DB/git run).
- No re-run of row 895's evaluation under a true v6 prompt to see if the output actually differs (would be an LLM call, against this run's standing no-LLM-calls rule).
- No decision made on any of the remediation options (A/B/C/D for the prompt question, or the separate model-version option set) — per the ground rule, that's explicitly Luis's call.
- No code changes, including the proposed prevention mechanism (startup hash-check) — proposed only.

## Follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
cat docs/handoffs/2026-09-03-prompt-version-drift.md   # full findings
cat analysis/data/run_state/prompt-version-drift-investigation/findings.md   # every query/diff, in order
```

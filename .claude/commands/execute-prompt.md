Execute a prompt from `./prompts/` and write a report to `./wrap-ups/`.

This is the standing workflow for the **Investment Agent** project (personal
account — Luis; entirely separate from Windmar Energy).

The thread works one way: `prompts/*.md` in → CLI session with DB access →
`wrap-ups/*-out.md` out → a design session interprets. **The CLI reports. It
never selects a configuration, amends a spec, or resolves an open item.**

## Step 1 — Find the prompt

If the user named a prompt, use that. Otherwise take the newest file in
`./prompts/`:

```
ls -t ./prompts/ | head -5
```

**When resuming an interrupted run, the user should name the prompt explicitly**
— mtime ordering is not reliable days later.

## Step 2 — Read the prompt and the specs it names

Read the prompt in full, then read every architecture document it names before
writing code. `docs/architecture/` holds `ALLOCATOR_OPERATING_MODEL.md`,
`DESIGN_PRINCIPLES.md`, `DOMAIN.md`, `BACKTEST_SIMULATOR.md`,
`PORTFOLIO_ANALYST_SPEC.md`, `PROMOTION_GATE.md`, `BUILD_STATE.md` and others.
**Their decisions are closed — do not re-derive them.**

Also read `CLAUDE.md` for standing project rules.

## Step 3 — Honour the resume protocol, if the prompt has one

Long prompts carry a `run_id` and a **Step −1 resume protocol** with state in
`analysis/data/run_state/<run_id>/` (`progress.json`, `cells.jsonl`,
`findings.md`). If present, execute it **first**:

- matching `prompt_sha256` → resume; skip completed steps and any cell whose
  `config_hash` already appears; report what was reused
- changed prompt → archive the old state, start fresh, say so
- changed `driver_commit` → invalidate `cells.jsonl`, keep `findings.md`

Flush `cells.jsonl` after **every** cell, update `progress.json` after **every**
step, and append to `findings.md` the moment a finding is established. Never
hold findings in memory for a final composition pass.

**Running low on budget is a reason to stop cleanly, not to rush.** Write the
wrap-up with what is done, mark the rest `pending` with a precise `next_action`,
and say plainly that it is a partial run.

## Step 4 — Verify the premise before implementing

These prompts have repeatedly contained mistaken premises, and catching them has
been worth more than the measurements. Confirm that claimed line numbers,
function names, files, reference figures and defects actually exist. **If a
premise is wrong, flag it and adapt** — surface it in the report rather than
implementing around it.

Equally: **a gate is a hard stop.** When a prompt says stop and report, stop —
do not work around it, do not press on with a "close enough" number, and do not
adjust code to make a gate pass for the wrong reason. A correct fix that moves a
number *away* from its target is still the correct fix; say so.

A diagnostic that contradicts an expectation stated in the prompt is a
**finding to report**, never a reason to stop.

## Step 5 — Standing constraints

Unless the prompt explicitly says otherwise:

- **No LLM calls, no API spend, no DB writes.** Measurement runs read the
  corpus; they never modify it.
- **No cache refreshes.** `analysis/data/price_cache.json` and
  `fundamentals_cache.json` stay frozen at 2026-05-11 — the staleness warning is
  expected and must not be "fixed".
- **Work on the branch the prompt names** (currently
  `sweep/db-corpus-baseline`). Never commit to `dev` or `main`, and never push
  unless asked.
- `python3` / `pip3`, zsh-compatible, **no `--break-system-packages`**, no Linux
  package managers or path assumptions — this is macOS.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf. Stash and pop. `testing/` is gitignored and holds real brokerage
  position exports — it must never enter version history.
- The analyst/allocator firewall holds: portfolio data never reaches the
  analyst, transcript data never reaches the allocator.

## Step 6 — Reproducibility (`ALLOCATOR_OPERATING_MODEL.md` §10b)

**A result without a manifest is not citable.**

- Clean tree before running — hard stop if `git_dirty` cannot be recorded
  `false`.
- Commit the driver **before** any manifest is written, as its own commit;
  manifests follow in a separate commit.
- Every manifest records the git commit and dirty flag, the driver file, the
  corpus window and event counts, checksums for `type_classifications.json` and
  both tier caches, every parameter and seed, and the results.
- Assert that the recorded commit actually contains the driver file.

## Step 7 — Verify before committing

`python3 -c "import ast; ast.parse(open('f.py').read())"` for Python,
`node --check` for JS, `JSON.parse` for JSON, and re-grep to confirm the change
landed. Stage **specific files** — never `git add .`.

Commit-message trailer: `Co-Authored-By: <the model you are> <noreply@anthropic.com>`.

## Step 8 — Write the report

Always write a report, even if the prompt says terminal-only. Name it after the
prompt's basename with an `-out` suffix:
`prompts/foo.md` → `wrap-ups/foo-out.md`.

Follow the structure the prompt asks for, and always include:

- the lead-with summary block the prompt specifies, filled in
- resume status when applicable — steps already done, cells reused, whether this
  is a partial run
- what was found, with specific files, line numbers, before/after
- verification performed and its results
- **any deviation from the prompt and why** — flagged premises, scope calls
- what was deliberately **not** done, and what is left for the design session
- exact follow-up commands, in fenced blocks

**Flag plainly:** any gate that failed, any rule that gave an uncomfortable
answer, and **any previously published number that turns out to be wrong**. A
corrected figure must supersede the old one explicitly, never replace it
quietly.

## Step 9 — Summarize in chat

Lead with what matters: the headline result or the gate that stopped the run,
what it means, and the report path. Don't dump file contents.

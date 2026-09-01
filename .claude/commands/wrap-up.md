Close out a Claude Code session for the **Investment Agent** project cleanly, so
the next session — or the design session reading the results — can pick up
without loss.

This is a **checklist, not a document generator.** `CLAUDE.md` says handoff
documents are written only when Luis asks for one, never proactively at the end
of a session. The per-prompt report in `wrap-ups/<prompt>-out.md` is the
session's output; this command verifies that report and everything around it is
actually safe to walk away from.

**Do not** write session notes, **do not** update `CLAUDE.md`, and **do not**
push, unless Luis explicitly asks in this session.

Work through these in order and report the result of each.

## 1 — The report exists and is committed

Confirm `wrap-ups/<prompt-basename>-out.md` was written for the prompt this
session ran, and that it is committed rather than sitting untracked. An
uncommitted wrap-up is the single most common loose end in this repo, and it
will trip the next run's clean-tree gate.

## 2 — Run state reflects reality

If the prompt carried a `run_id`, open
`analysis/data/run_state/<run_id>/progress.json` and check that:

- every step's status matches what actually happened — no step left
  `in_progress`
- `next_action` is a precise, single sentence someone cold could act on
- `findings.md` contains every finding established this session, in the wording
  the wrap-up uses
- `cells.jsonl` was flushed — its last entry corresponds to the last cell run

If the run was partial, say so explicitly in the wrap-up and make sure
`next_action` names the exact resumption point.

## 3 — Manifests are citable

For every manifest written this session, verify:

- `git_dirty: false`
- the recorded `git_commit` actually contains the recorded `driver_file`
  (`git cat-file -e <commit>:<path>`)
- the driver was committed **before** the manifests, as separate commits

Report any manifest that fails. Per §10b, a result whose manifest records
`git_dirty: true` — or whose commit predates its own driver — **is not
citable**, and the wrap-up must say so rather than quoting the number.

## 4 — The standing assertion still holds

If any code on the measurement path changed this session, confirm the
`no_reserve` control still reproduces **$141,836.57**. If it moved, that is the
headline of the session and belongs at the top of the report.

## 5 — The tree is clean and nothing sensitive is staged

```
git status --porcelain          # expect empty
git log --oneline -5
git status -sb | head -1        # note unpushed commits
```

Confirm `testing/` is still gitignored — it holds real brokerage position
exports and must never enter version history. Confirm `.env` is untracked.

Report how many commits are ahead of origin, and leave pushing to Luis.

## 6 — Irreplaceable artifacts

Note, without acting on it, whether
`~/investment-agent-backups/analysis_corpus_20260830.sql` has an off-machine
copy yet. The model that produced that corpus is retired, so it cannot be
regenerated at any price; it is the one artifact in this project whose loss is
unbounded.

Also confirm `price_cache.json` / `fundamentals_cache.json` are still frozen at
2026-05-11 and were not refreshed.

## 7 — Report

Give Luis a short close-out in chat:

- the report path, and whether the run was complete or partial
- if partial: the exact resumption point from `next_action`
- anything from checks 1–6 that failed, and what it means
- unpushed commit count
- what is genuinely left to do — no invented next steps

Nothing else. If a check passes, one line is enough.

# Regenerate v6 eval cache + allocator operating model sweep — wrap-up

**Status: STOPPED at Step 0c calibration. No sweep run. No cache regenerated.
$0 spent.**

## Step 0a — carried forward, not redone

Confirmed already: task #75 fix is on `dev` at commit `37f535a`. Not re-verified.

## Step 0b — v6 prompt restore: done, then reverted

Found the last commit where `docs/EVALUATION_PROMPT.md` read `# Version: v6`:
it's `7063465` ("feat: add summary field to Analysis..."), the parent of
`87bcfaa` which bumped it to `v10+auto1`. Confirmed via:

```zsh
git log --oneline -- docs/EVALUATION_PROMPT.md
git show 7063465:docs/EVALUATION_PROMPT.md | head -3   # "# Version: v6 ..."
git show 87bcfaa:docs/EVALUATION_PROMPT.md | head -3   # "# Version: v10+auto1 ..."
```

Created `sweep/v6-eval-cache` off `dev` and restored the v6 text there:

```zsh
git checkout -b sweep/v6-eval-cache
git show 7063465:docs/EVALUATION_PROMPT.md > docs/EVALUATION_PROMPT.md
head -5 docs/EVALUATION_PROMPT.md   # confirmed "# Version: v6 (stable best after v5→v8 iteration)"
```

This part worked exactly as the prompt predicted. **Reverted afterward** (see
Step 0c) — `docs/EVALUATION_PROMPT.md` is back to `v10+auto1` on `dev`; the
scratch branch exists but has no commits, only the (now-discarded) working-tree
change. Reproducible from the commands above whenever this resumes.

## Step 0c — calibration: STOP. The reference model no longer exists on this API key.

Before running the authorized $1-ticker calibration pass, I called the same
endpoint the warmer uses directly (to capture token usage, which
`eval_cache_warmer.py` doesn't print) against one AAPL transcript:

```python
client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096,
                        temperature=0, messages=[...])
```

Result:

```
anthropic.NotFoundError: Error code: 404 - {'type': 'error', 'error':
{'type': 'not_found_error', 'message': 'model: claude-sonnet-4-20250514'}}
```

`client.models.list()` on this key returns no `claude-sonnet-4-20250514` at
all. Current catalog:

```
claude-opus-5, claude-sonnet-5, claude-fable-5,
claude-opus-4-8, claude-opus-4-7, claude-sonnet-4-6, claude-opus-4-6,
claude-opus-4-5-20251101, claude-haiku-4-5-20251001, claude-sonnet-4-5-20250929
```

**`claude-sonnet-4-20250514` — the exact model the $287k reference result, the
whole `v6_sonnet-4-20250514` cache-directory naming convention, and
`eval_cache_warmer.py`'s hardcoded `MODEL` constant all assume — has been
retired from the API.** It cannot be called, at any price, with this key.

This is not a cost problem, it's a reproducibility wall: the prompt explicitly
said *"The warmer hardcodes `MODEL = "claude-sonnet-4-20250514"` ... Do not
change either [model or temperature]."* I can't honor that instruction and
also produce any output — the two are now in direct conflict. Substituting a
newer model (e.g. `claude-sonnet-4-5-20250929`) would silently change every
downstream verdict versus the reference corpus; that's a real, substantive
decision (does the $287k figure even mean anything once the evaluator model
changes?) that belongs to Luis, not something to pick unilaterally under a
"measurement, don't redesign" prompt.

**No calibration call was billed against the real prompt/transcript pair** —
the one call made was a preflight probe that itself 404'd before generating
any tokens, so there is no partial-cache pollution and no spend.

## What's needed from Luis before this can proceed

One decision: which model to evaluate under, given `claude-sonnet-4-20250514`
is gone.

- **Option A — accept a model swap.** Pick a currently-available model (the
  newer Sonnet line is the closest lineage: `claude-sonnet-4-5-20250929` or
  `claude-sonnet-4-6`) and accept that the $287k figure is no longer the
  baseline gate — Step 1 would instead *establish* a new baseline under the
  new model, not reproduce the old one. This is a bigger scope change than
  "regenerate the cache" — it invalidates the premise that the sweep is
  "priced against the validated result."
- **Option B — check for a cached/archived v6 eval corpus elsewhere** (another
  machine, a Railway DB snapshot, cloud storage) that predates the model's
  retirement, avoiding re-evaluation entirely. Worth a quick check before
  committing to Option A, since it would make this whole regeneration step
  moot.
- **Option C — stop this measurement track.** If neither A nor B is
  acceptable, task #77's baseline-relative sweep can't be run against the
  original reference at all; a redesigned measurement plan would be a
  separate design-session output, out of scope for this prompt.

Everything from Step 0d onward (universe pinning, baseline reproduction, the
harness parameterization, the full grid) is blocked on this decision and was
not started.

## Repo state left behind

- `dev`: unchanged (only the pre-existing uncommitted `CLAUDE.md` /
  `PORTFOLIO_ANALYST_SPEC.md` edits from before this session, untouched by me).
- `sweep/v6-eval-cache`: exists locally, no commits, no working-tree diff
  (the v6 restore was reverted). Safe to reuse or delete.
- No files under `analysis/data/evals/` were created.

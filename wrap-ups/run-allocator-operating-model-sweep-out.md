# Allocator operating model sweep — wrap-up (task #77 measurement)

**Status: STOPPED at Step 0, per the prompt's own instruction.** No sweep was
run. This report covers Step 0 only and the reason the run did not proceed
further.

## Step 0a — `splitBucketTarget` zero-cap divisor (task #75)

**Resolved: fixed, not pending.** `git log` shows commit `37f535a` "Exclude
zero-cap tickers from splitBucketTarget's divisor", present on `dev`. The
wrap-up (`fix-splitbuckettarget-zerocap-divisor-out.md`) is correct; the
tracker showing it pending is stale. Confirmed at `server/routes/moves.js:1248`
— `evenShare = claimants.length > 0 ? bucketTargetPct / claimants.length : 0`.

## Step 0b — eval cache regeneration: STOP, do not proceed on my own authority

The prompt's instruction was:

```
python3 analysis/dump_transcripts.py
ls analysis/data/evals/v6_sonnet-4-20250514/*.txt | wc -l   # expect ~659
```

**This does not do what the prompt says it does, and I did not run it.**

- `analysis/dump_transcripts.py` dumps raw transcript *text* from Postgres to
  `analysis/data/transcripts/` — that step is already done (660 files present,
  matches the ~659 the spec expects).
- The actually-missing thing, `analysis/data/evals/v6_sonnet-4-20250514/`, is
  the **LLM-evaluated output** of those transcripts (structured score per
  call) — produced by `eval_cache_warmer.py` or `backtest_from_files.py
  --save-evals`, not by `dump_transcripts.py`. Running the prompt's literal
  command would report "0 files, expect ~659" and change nothing.

Two further problems with regenerating it at all right now, found while
verifying the premise:

1. **The current prompt is not v6.** `docs/EVALUATION_PROMPT.md` is versioned
   `v10+auto1 (auto-iterate candidate — pending gate)` on this branch. The v6
   text (`v6: added explicit Execution-stumble handling...`) only exists in
   git history, not in the working tree. `eval_cache_warmer.py` reads
   whatever's live in `EVALUATION_PROMPT.md` and tags the cache dir by
   `(prompt_version, model_slug)` — running it as-is today would write to a
   `v10+auto1_sonnet-...` directory, which `data_from_cache.py` does not look
   for (it hardcodes `v6_sonnet-4-20250514`, falling back to legacy `v6`).
   Regenerating without first checking out the historical v6 prompt text
   would silently produce a cache the simulator can't see, or worse, one it
   *could* be pointed at but that doesn't correspond to the validated $287k
   result (different prompt version = different verdicts = non-reproducible
   baseline).
2. **Real cost, not a free re-run.** 659 transcripts average ~54KB each
   (~8.9M input tokens at 4 chars/token) — call it $25–35+ in API spend for
   input tokens alone at Sonnet pricing, before output tokens or the
   evaluator's own system-prompt overhead, plus the wall-clock time of ~659
   sequential-ish LLM calls (parallelized in the warmer, but still
   substantial).

The prompt itself says: *"If regeneration is expensive or partially fails,
stop and report rather than running a sweep on a partial corpus."* This
qualifies as expensive and, as written, would not even reproduce the correct
artifact. So per that clause: **stopped, reporting, not running it.**

## What would actually regenerate the cache correctly

For the design session's information, the correct sequence (not run):

```zsh
cd analysis
git show <commit-with-v6-prompt>:docs/EVALUATION_PROMPT.md > /tmp/EVALUATION_PROMPT_v6.md
# swap it in temporarily (or point eval_cache_warmer.py at the v6 text directly),
# confirm the version banner reads "v6" before dispatching any calls
python3 eval_cache_warmer.py --ticker <ALL 32 TICKERS> --parallel 15
# rerun until "all cached"; verify:
ls data/evals/v6_sonnet-4-20250514/*.txt | wc -l   # expect ~659
```

The v6 prompt text is recoverable from git history — `git log --all -p --
docs/EVALUATION_PROMPT.md` shows it verbatim (search for `# Version: v6`).
It has not been deleted, just superseded on the working branch.

## Not done — everything downstream of Step 0

Steps 1–5 (baseline reproduction, instrumentation, harness parameterization,
the full grid, and the report) all depend on the eval cache existing and
being verifiably v6-consistent. None of it was started:

- No baseline run.
- No harness changes.
- No sweep.
- `ALLOCATOR_OPERATING_MODEL.md` and other specs: untouched, as instructed.
- `server/routes/moves.js`: untouched, as instructed.

## What's needed from Luis before this can proceed

One decision: authorize the ~$25–35 API spend (order of magnitude; could run
higher with output tokens/overhead) to regenerate the v6 eval cache using the
historical prompt text, so the sweep runs against inputs that reproduce the
$287k reference. Once that's confirmed, re-run this prompt (or a follow-up
one) to execute Steps 1–5 for real.

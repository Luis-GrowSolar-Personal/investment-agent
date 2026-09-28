# Per-trim value — complete the QQQ leg — $0

**Run ID:** `per-trim-value-qqq`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/per-trim-value-qqq-out.md`
**Cost: $0.** No model API calls, no DB writes, no scoring. **One free
`yfinance` fetch of one ticker (QQQ)**, which is the only change to any
data file.

---

## Framing

`prompts/per-trim-value.md` ran on the SPY leg only. QQQ is absent from
`analysis/data/corpus_v2/scorer_price_cache_v1.json`, the file the
tradeable-entry ruler is built from, and the run correctly stopped
rather than substitute (`wrap-ups/per-trim-value-out.md`).

This run adds QQQ to that file **by the exact method SPY was added**,
then reruns the same analysis so the pre-registered reading can be
applied to both destinations, as written.

**The reading is not re-opened.** Everything in `prompts/per-trim-value.md`
under "Definitions" and "Pre-registered reading" applies unchanged.
This run only supplies the missing numbers.

**Checked by the design session before writing this prompt (do not
redo, but the asserts below re-verify):**
- The canonical cache was built by `analysis/scorer_price_cache_backfill_driver.py`:
  `yf.Ticker(symbol).history(start="2019-06-01", end=AS_OF_DATE, auto_adjust=False)`,
  `Close`, rounded to 4 decimals. SPY in it runs 2019-06-03 → 2026-09-14.
- The frozen legacy `analysis/data/price_cache.json` holds QQQ to
  2026-05-01 only, too short for the last train calls (latest 2025-12-17,
  needs prices to about 2026-06-17). Its SPY matches the canonical SPY on
  all 1,596 shared dates to within 0.00001%. **It stays frozen. Read it
  for the cross-check only.**

---

## Ground rules

1. $0. The only network call is the one `yfinance` fetch in Step 1.
2. **Do not change any existing key in the canonical cache.** QQQ is
   added; nothing else moves.
3. **Do not touch** `analysis/data/price_cache.json`.
4. Do not change the definitions, the reading, or the P9 band sizes.
5. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/per-trim-value-qqq/`. `progress.json`
first. Commit this prompt as its own commit
(`prompt: per-trim value, QQQ leg`). Clean tree; hard stop if
`git_dirty` cannot be recorded `false`.

## Step 1 — add QQQ to the canonical cache (one commit)

1. Record sha256 of the canonical cache and of the legacy cache.
2. Fetch QQQ with the same call and conversion as the backfill driver,
   `start="2019-06-01"`, `end` = the day after SPY's last date in the
   canonical cache (so QQQ and SPY cover the same span). Reuse the
   driver's fetch function if it can be imported; otherwise copy the two
   lines exactly and say so.
3. **Asserts (any failure → stop and report, write nothing):**
   - QQQ's trading dates equal SPY's trading dates in the canonical
     cache. Report any difference.
   - Cross-check against legacy QQQ on every shared date: largest
     relative difference. **Stop if it exceeds 0.1%.**
   - After writing: every non-QQQ key in the canonical cache is identical
     to before (load both, compare series for every ticker).
   - Legacy cache sha256 unchanged.
4. Write the updated canonical cache in the same JSON format. Record the
   new sha256. Commit:
   `data: add QQQ to scorer_price_cache_v1 (yfinance, auto_adjust=False, same method as SPY)`.

## Step 2 — rerun the per-trim analysis

- Use `analysis/per_trim_value.py` as committed. Its QQQ leg was coded
  and returned nothing only because the prices were missing. If any code
  change is needed (for example an output-directory argument so this run
  writes to `run_state/per-trim-value-qqq/` and does not overwrite the
  first run's `results.json`), make only that change and commit it on its
  own before any output.
- Same seeds, same bootstrap, same definitions.
- **Assert the SPY leg reproduces the first run exactly** (every
  figure in `run_state/per-trim-value/results.json` → SPY). A mismatch
  means something other than QQQ changed: stop and report.
- Preflight numbers as before, for QQQ: calls priced, calls dropped.

## Step 3 — apply the pre-registered reading, both destinations

Apply the reading from `prompts/per-trim-value.md` exactly as written,
to the pooled rows of Step 1 (fixed 2.5-point trims):

- **The analyst pays** — A − B range above zero for QQQ **and** SPY
  (or "against [index] only").
- **The index does the work** — A's range above zero, A − B's range
  includes zero.
- **Protection does not pay** — A's range includes or is below zero.

The SPY leg already read "protection does not pay." State the combined
verdict for both legs, and say plainly if the two legs read differently.

P9 layer: report the QQQ leg's per-band values and sized A − B per
point beside the SPY leg's, and whether both parts of the P9 condition
hold on QQQ. It still cannot change the Step 1 verdict.

**One diagnostic, labelled diagnostic-only.** The design session
expects the destination to change A a lot and A − B very little, because
the control is taken in the same quarters. Report A(QQQ) − A(SPY) and
[A − B](QQQ) − [A − B](SPY), pooled, fixed 2.5 and P9-sized. This is a
check on that expectation, not a condition.

Veto layer: not re-reported (one flagged call carries the tag; closed).

---

## Report step

`wrap-ups/per-trim-value-qqq-out.md`, `.md` only. Open with:

> QQQ added to the canonical price cache by the same method as SPY
> (commit ___); legacy QQQ agrees to within ___% on ___ shared dates.
> Into QQQ, moving 2.5 points of the book out of each of B's ___ flagged
> calls made ___ points per trim ($___ on $100,000), against ___ for a
> random name in the same quarter. The analyst's contribution is ___
> (range ___ to ___). Into SPY (unchanged): ___ against ___, contribution
> ___ (range ___ to ___). **Combined verdict under the fixed reading:
> [___].** Sized by P9 severity, the contribution per point moved into
> QQQ is ___ (range ___ to ___), against ___ into SPY.

Then the Step 1 table for QQQ in the same layout as the first wrap-up,
SPY beside it; the P9 per-band table for both; the diagnostic; the
cache-change record (shas before/after, date count, cross-check).

**Close with what it means**, per the three outcomes in
`prompts/per-trim-value.md`, and note that the book test
(`docs/handoffs/2026-09-28-allocator-book-test-design.md`, as amended)
now has the QQQ prices it needs.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure (file and key). One prompt in, one wrap-up out. **Finish
with `git push`** after the wrap-up commit and report the pushed hash.
If the push fails, say so and never force.

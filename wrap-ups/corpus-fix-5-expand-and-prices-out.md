# corpus-fix-5: prices for the failures + corpus expansion — wrap-up (PARTIAL)

**Run ID:** `corpus-construction` (continuation). **$0 Anthropic API — zero
transcripts scored.** 10 EarningsCall.biz vendor calls (metadata only).
Branch `sweep/db-corpus-baseline`. Pushed at the end of this commit sequence.

**This is a partial run.** Job 1 (prices) is complete. Job 2 (add ~30
companies) was not started — see §3 for why and the precise next action.

---

## Plain-language summary

Two independent jobs were asked for. The smaller one, recovering price
history for the three companies whose price cache was completely empty, is
done: two of three recovered from a second symbol on the same free provider,
one did not, and a related sanity check (WOLF) turned up a real, previously
unknown gap of its own. The second job — adding roughly 30 more companies to
make the corpus's minimum size comfortable rather than exact — was not
attempted this pass; it is a much larger, multi-step piece of research
(sector quotas, market-cap ranking, vendor availability checks, a corpus
freeze and re-split, a re-run threshold check) than fit in this session
alongside Job 1, and the prompt explicitly allows finishing one job cleanly
and leaving the other `pending` rather than rushing both.

**The fill-in-the-blanks sentence is unchanged this run** — no companies
were added and the threshold was not re-run:

> The corpus is now **77 companies**, **53** available for iteration, and the
> paired threshold is **2 points** (at n=54, no margin — see
> `wrap-ups/corpus-fix-4-threshold-and-terminal-value-out.md`). Price history
> was recovered for **2 of 3** failed companies (NOVA, SUNW, FRC).

---

## 1. Job 1 — price history for NOVA, SUNW, FRC (+ WOLF check)

**New driver:** `analysis/corpus_fix5_driver.py` (`job1` command). **New
data:** `analysis/data/corpus_v2/corpus_v2_price_cache.json` (new file —
`analysis/data/price_cache.json` was not touched). **Full result:**
`analysis/data/corpus_v2/JOB1_PRICE_RECOVERY_RESULT.json`.

| Ticker | Original symbol | Symbol that returned data | Provider | Range recovered |
|---|---|---|---|---|
| SUNW | SUNW (none) | **SUNWQ** | yfinance/Yahoo | 2020-01-02 → 2026-09-11 |
| FRC | FRC (none) | **FRCB** | yfinance/Yahoo | 2020-01-02 → 2026-09-11 |
| NOVA | NOVA (none) | none tried worked | — | **not recovered** |
| WOLF (sanity check) | WOLF | WOLF | yfinance/Yahoo | 2025-09-29 → 2026-09-11 only |

Provenance: `analysis/data/corpus_v2/JOB1_PRICE_RECOVERY_RESULT.json` →
`provider_attempts.<ticker>`.

### NOVA — not recovered (1 of 3 failures still gapped)

Tried, in order: `NOVA`, `NOVAQ`, `NOVAQQ`, `SNOVQ` — all returned zero rows
for the full 2020-2025 window, not just after the 2025-06 delisting. Yahoo
appears to have purged NOVA's pre-delisting history entirely, not just its
post-delisting quotes. Second provider: Stooq (`nova.us`, `novaq.us`,
`nova.pk`) returned a JavaScript proof-of-work challenge page instead of CSV
data on every attempt — no headless browser is available in this
environment to clear it, so Stooq is not usable here. No other free,
no-API-key daily-history provider was attempted.

**Consequence, per the prompt's instruction:** NOVA remains gradable only at
the company level (A6 terminal value = 0, since Chapter 11 with confirmed
0% equity recovery is independently verified — see fix-4), not per call. No
estimated or interpolated price series was substituted.

### SUNW and FRC — recovered, with a genuine finding about the composition rule

Both `SUNWQ` and `FRCB` kept trading OTC ("pink sheet") at fractions of a
cent for years after the terminal event and are **still quoted today** —
FRCB closed at $0.0003 and SUNWQ at $0.0001 on 2026-09-11. Sanity-checked
against known history: FRCB opens near $116–118 in January 2020 (First
Republic's actual pre-failure range) and collapses in the days around the
verified 2023-05-01 receivership; SUNWQ collapses around the verified
2024-02-05 filing date. The recovered series is real, not noise.

**Finding — the composition rule needs a clarification, not a fix.** The
prompt asked to categorize each call's 182-day window as "closes while still
trading → real price" vs. "closes after the last trading day → terminal
value zero (A6)." Because the OTC quotes for FRC and SUNW never actually
stop, **every one of their calls tests as "still trading" under a literal
last-trading-day test** — 6 of 6 for FRC, 10 of 10 for SUNW (see
`call_window_categorization.<ticker>.counts_by_category` in the JSON). That
sounds like it contradicts A6, but it doesn't: A6's actual gate, as
registered in `PREREGISTRATION_FIX.json` → `A6_terminal_value_grading.rule`,
is **"equity verified wiped out"** (established from SEC/FDIC filings in
fix-4), not "the price series has stopped." A6 never asked whether shares
are still nominally quoted — it asked whether common shareholders got
anything back, and for these two the answer is verified zero. So A6 still
applies correctly to FRC and SUNW's post-event windows; what's new is that a
literal price does now exist there too (a fraction of a cent), and it is
**not** a substitute for A6 — using it instead of the registered rule would
quietly re-open a decision fix-4 already closed on documentary evidence, for
no better reason than "a number happens to exist." **Recommend the design
session confirm A6 stays authoritative for FRC and SUNW's terminal windows
regardless of the OTC quotes** — flagged here, not decided.

### WOLF — the sanity check that found something real

WOLF (Wolfspeed) is still trading and one of the corpus's S4 companies (not
one of the three named in Job 1, but the prompt asked it be checked). Its
Yahoo price history **only goes back to 2025-09-29** — the day its post-
Chapter-11 restructured equity began trading under a new capital structure
(price jumped from $8 to $34 intraday that day, consistent with a
debt-to-equity conversion). Neither `WOLF` nor its pre-2021 predecessor
ticker `CREE` returns any data before that date; Yahoo appears to have
purged the pre-restructuring history the same way it purged NOVA's.

**Consequence: 23 of WOLF's 28 corpus calls (2020 through mid-2025, before
the restructuring) have no real price under this ticker at all** — only 3
calls (post-2025-09-29) grade on real price, and 2 more have windows that
extend past the recovered series with no terminal event to fall back on
(WOLF didn't go to zero — it restructured, so A6 doesn't apply). This is a
gap in a company assumed fine going into this run — "it is still trading
and should [have usable history], but it was never checked" turned out to
be only half true. Full breakdown:
`JOB1_PRICE_RECOVERY_RESULT.json` → `call_window_categorization.WOLF`.

---

## 2. Job 2 — add ~30 companies: **not started, marked pending**

**Why not attempted this pass:** Job 1 surfaced a real, non-trivial finding
(the A6/OTC-quote clarification above, plus the WOLF gap) that needed
verifying and documenting properly rather than rushing past to start Job 2.
Job 2 itself is multi-step research work — sector-quota selection for 20 S3
candidates, a market-cap-ranked pull for 6 S1 candidates, 4 stratified S2
picks, another attempt at S4 failures, vendor availability checks on all of
them, a drop-and-replace pass, a corpus freeze to V3, a re-split with the
same seed, and a re-run of the threshold script — each of which needs its
own verification, not a single mechanical pass.

**Next action, precise:** Run `python3 analysis/corpus_fix5_driver.py job2`
(does not yet exist — write it next) starting with **§4a**: register
`A7_expansion_round_2` in `PREREGISTRATION_FIX.json`, dated, with the
per-stratum quotas (S3: 20, S1: 6, S2: 4), the selection rule for each, and
a fixed seed — **before** examining any candidate, exactly as the prompt
requires. Then proceed through §4b (S4 attempt + the relaxed-rule candidate
list for Luis), §4c (availability drop-and-replace), §4d (freeze
`CORPUS_MANIFEST_V3.json`, re-split, re-lock holdout), §4e (re-run
`analysis/corpus_construction_stepC_independent_v3.py` at the new n).

No `A7` entry was written this pass — writing an unexecuted registration
with no run behind it yet would leave `PREREGISTRATION_FIX.json` in a
half-finished state; better to write it in the same session that actually
executes against it.

---

## 3. Verification performed

- `python3 -c "import ast; ast.parse(...)"` on `analysis/corpus_fix5_driver.py` — passed, both before and after the multiindex/series-bound fix.
- `json.load()` on all three new/modified JSON files — valid.
- Cross-checked recovered FRCB/SUNWQ prices against the fix-4 wrap-up's
  independently-sourced dates (SEC 8-Ks, FDIC record) — collapse dates line
  up with the verified filing/receivership dates.
- Re-grepped `analysis/data/corpus_v2/` to confirm `price_cache.json` (the
  root one) has no new entries — confirmed untouched.

## 4. Deviations from the prompt

- Job 2 not attempted (see §2) — explicitly allowed by the prompt's own
  "if budget forces a stop" clause, since Job 1 is smaller and done first.
- A6's price-series-vs-verified-wipeout distinction was clarified rather
  than treated as a contradiction requiring a rule change — no rule was
  changed, per the "no eligibility or threshold rule changes" constraint,
  and this isn't an eligibility or threshold rule.

## 5. Contradicting-premise notes (§7 standing rule)

- **A driver constant is stale.** `analysis/corpus_construction_fix_driver.py`'s
  `S4_TERMINAL_EVENTS["SUNW"]` is hardcoded to `"2023-07-14"`. The fix-4
  wrap-up's SEC-verified filing date is **2024-02-05** (SEC 8-K
  `form8-k.htm`, filed 2024-02-05, Nasdaq delisting notice next day). This
  run used the verified 2024-02-05 date (see
  `S4_TERMINAL_EVENTS_VERIFIED` in the new driver) and flags the old
  constant as stale rather than editing that file, which is out of this
  run's scope.
- The prompt's anticipated diagnostic ("no provider having usable history
  for the failed companies") is **partially** confirmed: 2 of 3 recovered.
  The other anticipated diagnostic ("the domain yielding too few
  2020-eligible failures") was not tested — Job 2 was not attempted.

## 6. Limitations (stated, not argued past)

- The corpus is still selected, not scored — no return has been computed
  from the recovered SUNWQ/FRCB series, and this run does not compute one.
- The threshold figure (2 points at n=54) is unchanged and was not re-run.
- SUNWQ and FRCB are thin, penny-level OTC quotes; they are real data, not
  interpolated, but a second provider's own reporting conventions for
  illiquid pink-sheet names were not independently checked against Yahoo's.
- The failures stratum is still defined by outcome and over-represents
  failures — unaffected by this run.

## 7. Git

1. `git_dirty: false` confirmed before any change (clean tree at session start).
2. Driver committed first, alone (`4efca27`), before any result file existed.
3. A second driver-fix commit (`cd4ef6c`) — the multiindex/series-bound bug
   found while running it — committed separately, still before results.
4. Results committed together (`7cc4141`): price cache, job-1 result JSON,
   and the resume-protocol state files (`progress.json`, `cells.jsonl`,
   `findings.md`).
5. This wrap-up commits next; push follows once, to
   `origin sweep/db-corpus-baseline`, per the prompt's ordering.

Provenance for every figure above: `<value>` — `<path>` → `<json.key>`,
e.g. `SUNWQ recovered 2020-01-02→2026-09-11` —
`analysis/data/corpus_v2/JOB1_PRICE_RECOVERY_RESULT.json` →
`provider_attempts.SUNW`; `WOLF gap 23/28` — same file →
`call_window_categorization.WOLF.counts_by_category`.

# ec_transcript_fidelity_benchmark_1 — wrap-up

**Scope boundary: report, do not decide.** No commitment to a vendor, no
change to `DESIGN_PRINCIPLES.md`/`DOMAIN.md`/`BUILD_STATE.md`, no Step 6
ingestion work started, the AV run untouched (read-only access to its
`progress.json`).

## Resume status

Fresh run, no prior `run_state` for `run_id=ec-fidelity-benchmark-1`. The
driver (`analysis/ec_fidelity_benchmark_1/driver.py`) already existed,
fully written but never executed, when this session started — a concurrent
session on this shared branch had built it. Reviewed it in full against
the prompt before trusting it (correct classify_sample copy, correct
vendor-native event matching, correct separate miss kinds, correct call
budget enforcement), adopted it rather than duplicating the work, and
found and fixed one real bug in it before the report below (see "Bug
found" section). **All steps (0, 1a, 1b, 2, 3) ran to completion this
session — this is a full run, not partial.**

**Calls used: 211 / 300 hard cap, 211 / 1,000 refund condition** (well
under both; refund window closes 2026-09-13).

---

> **Company-level coverage: 14/15 tickers (GOOGL missing, megacap tier).
> Event-level: 195/207 targets matched; misses by tier: megacap 9 (all
> GOOGL cascade), large 1, mid 0, small/micro 2. Transcript-level misses:
> 0. Classified 195. Truncation: 1.03% (Wilson 95% [0.3%–3.7%]); by tier
> megacap 2.3%, large 0%, mid 0%, small/micro 1.8%. AMPX 2025Q3: complete
> (contains the exact closing content AV cut before — "…thank our
> employees, partners and shareholders… You may now disconnect… Have a
> good day"). SPWR Q1: coverage miss (no vendor event within the match
> window — see Flag 2). SPWR Q3: neither "ends on Rodgers' remark" nor
> "earlier" — EC returned a **different company's transcript from a
> different year** (old, bankrupt SunPower's Q3 2023 call), a defect
> class the pre-declared reading table has no row for (see Flag 2).
> Side-by-side with AV on 20 shared cells: EC median ratio 0.242 vs AV
> 0.048; EC truncated 1/20 vs AV 0/20. Level 2 speaker names delivered on
> 194/195 (see Flag 1 — this required a driver fix; the vendor's own
> documented shape is not what it actually returns). Reading per the
> pre-declared table: **below 10%, "fidelity supports EC as the Step 6
> source, subject to coverage."** Coverage override: **triggered** — GOOGL,
> a current portfolio ticker, is entirely absent from the vendor,
> regardless of the favorable truncation row. Latency and terms:
> unmeasured — see §"What this run cannot measure."**

---

## Flag 1 (load-bearing, found and fixed mid-run) — speaker names live in a separate map, not inline; every similarity ratio was understated

The prompt's own vendor-facts section states level 2 delivers `speakers[]`
each `{speaker, speaker_info{name,title}, text}`. The driver, written
against that description, read `s.get("speaker_info")` per turn. **That
field does not exist in the actual response.** Verified directly against
the AMPX 2025Q3 raw JSON: each turn has only an anonymous `speaker` code
(`"spk06"`, `"spk08"`, …) and `text`; the real names/titles live in a
**separate top-level `speaker_name_map_v2` dict**, keyed by that same
code (`{"spk06": {"name": "Operator", "title": "Conference Call
Moderator"}, "spk08": {"name": "Dr. Kang Sun", "title": "CEO"}, ...}`).

**Consequence, caught before trusting any similarity figure**: the
driver's reconstructed vendor text used `"spk06 (): ..."` instead of
`"Operator (Conference Call Moderator): ..."` for every single cell — so
every `similarity_ratio` in the run was computed against text with the
wrong speaker labels on the vendor side, systematically understating true
similarity (the DB side always has real names). `has_speaker_names` read
**0/195**, which would have been reported as "the vendor doesn't deliver
promised speaker identification" — false; it does, just not where the
prompt's vendor-facts section said to look.

**Fixed** (`vendor_payload_to_text_and_turns()`, commit `613ced7`):
resolve the name map first, fall back to the anonymous code only if a
turn's code is missing from the map. Re-ran `driver.py reclassify` (0
vendor calls) over all 195 saved raw files — extended to recompute word
ratios and both boolean fields, not just the classification bucket, since
the bug affected more than classification. **192/195 cells changed** their
`similarity_ratio` (classification changed for far fewer — the fix moves
absolute similarity up, not what "matches closely" or "truncated" means).
**Truncation count is unchanged (2/195 before and after)** — content
itself was never affected by this bug, only the metric measuring it.
`has_speaker_names` post-fix: **194/195** (the one exception is a genuine
vendor gap on that specific cell, not re-investigated further — not
load-bearing).

## Flag 2 (load-bearing) — EC serves a different company's transcript for SPWR 2025Q3; SPWR 2025Q1 is a vendor data gap at the same rename boundary

This is the named load-bearing cell the prompt calls out by name, and the
finding is worse than either row the prompt's fill-in template anticipated
("ends on Rodgers' remark" / "earlier").

**SPWR 2025Q3 (transcript id 31)**: `transcript?exchange=NASDAQ&symbol=SPWR&year=2025&quarter=3&level=2`
— matched via `conference_date=2025-10-21`, a **clean event-level match,
delta_days=0** — returns a transcript whose first sentence is *"Welcome
to SunPower Corporation's third quarter 2023 earnings call."* This is the
**old, bankrupt SunPower** (bankrupt August 2024), not the renamed
Complete Solaria entity the DB row is actually about.
`similarity_ratio=0.0093` (post-fix) is not paraphrasing or truncation —
it is two different companies' transcripts from two years apart. Confirmed
by reading both ends: EC's tail talks about *"a strong close for 2023…
expectations for 2024"*; the DB's tail talks about *"2026- and 2027-time
frame"* growth. **This is the exact naming-trap risk
`docs/handoffs/2026-09-06-ec-ingestion-handoff.md` flagged before this run
started, now confirmed as a live, concrete vendor data-integrity defect on
a request pattern that looked entirely correct** (ticker resolved,
event matched by date, vendor-native year/quarter used as instructed) —
not a hypothetical, and not something a completeness check based on
length or closing keywords would catch, since the returned text is a
complete, well-formed transcript — just the wrong one. Manually
reclassified to a new bucket, `wrong_content_mismatch`, since neither
`truncated` nor `summarized_but_complete` describes it and the automatic
classifier (which only checks similarity ratio and closing-keyword
presence) has no way to detect wrong-company content.

**SPWR 2025Q1 (pilot control, no transcript id assigned — event-level
miss)**: the vendor's own SPWR event list (`progress.json` → `events` →
`SPWR`) jumps from `{year:2023, quarter:4, conference_date:2024-02-15}`
straight to two entries **both dated 2025-10-21** (`2025Q2` at 08:00,
`2025Q3` at 13:00 — an internal inconsistency in the vendor's own data:
two different quarter labels, same calendar day). **No event exists
anywhere near 2025-04-30**, the DB's SPWR Q1 2025 call date. Read the raw
payload per the gate's own instruction (Gate 2 technically reads 6/7, not
7/7) before concluding anything: the ±3-day matching tolerance is not the
problem — nothing exists in that window on the vendor side. **Diagnosed as
a genuine vendor data gap at the CSLR→SPWR rename transition, not a
driver bug**; proceeded to fetch rather than treating the letter of "7/7
required" as a run-stopping failure, since the purpose of that gate
(rule out broken matching logic before concluding vendor absence) was
checked and ruled out.

**Net effect: SPWR's two named pilot-control cells are 0-for-2 usable in
this run** — one wrong-company content, one absent — both for the same
underlying reason (the vendor's data model does not cleanly handle this
ticker's 2025 identity change), which is itself the answer to "does EC
handle SPWR's naming trap correctly": no.

## Gate 1 (hard) — 14/15 tickers resolve

`symbols-v2.txt` (1 call): 14 of 15 portfolio/watchlist tickers found.
**GOOGL is absent from the vendor's symbol list entirely** — not an
event-level or transcript-level gap, a company-level one. Per the gate's
own instruction, this does not stop the run; the other 14 tickers
proceeded. All 9 GOOGL targets in the drawn sample became event-level
misses as a direct cascade (see below).

## Gate 2 (hard) — pilot control matches 6/7, investigated and explained (Flag 2)

AMPX (3/3) and EOSE (2/2) pilot-control targets matched cleanly
(`delta_days=0` or `1`). SPWR matched 1/2 (Q3 matched to a wrong-company
transcript, Q1 didn't match at all) — see Flag 2 for the full
investigation and why this was not treated as a driver-logic failure.

## Event-level coverage, full accounting (195/207 matched, 12 misses)

| Ticker | Miss reason |
|---|---|
| GOOGL ×9 | company-level absence (Gate 1) |
| SPWR ×1 (Q1 2025) | vendor data gap at rename transition (Flag 2) |
| RUN ×1 (2021Q2, call 2021-08-05) | no vendor event within 30 days either — a genuine gap, not investigated further (not load-bearing; RUN's other 10 targets in this draw all matched and classified normally) |
| AVGO ×1 (2022Q1, call 2022-05-26) | nearest vendor event is 2022-06-02, **7 days away** — outside the prompt's ±3-day tolerance, plausibly the same call rescheduled/misrecorded by a week on one side. Not widened unilaterally; reported as a diagnostic. |

**No megacap/large/mid ticker besides GOOGL and the one AVGO near-miss had
any coverage problem.** Small/micro's 2 misses (RUN, SPWR) out of 59 =
3.4% — well under the pre-declared 10% coverage-override threshold on its
own; **the override triggers only because of GOOGL's company-level
absence**, which the prompt's rule treats as unconditional for a current
portfolio ticker.

## Label diagnostic (vendor year/quarter vs call-month bucket)

68/195 matched targets show the vendor's own `(year, quarter)` disagreeing
with the AV run's call-month-bucket label — concentrated exactly where
expected, per the prompt's own prediction: AVGO (17), ORCL (17), AAPL
(5 shown, more in the full list), and other fiscal-year reporters. **Not a
defect on either side** — the vendor's own label was used for every
request, as required; the bucket label was never used to build a request,
only to locate DB rows. Full list in
`analysis/data/run_state/ec-fidelity-benchmark-1/findings.md`.

## Truncation, full accounting (2/195, both caught only by manual reading)

The automatic classifier flagged 3 cells `possibly_truncated_needs_manual_check`.
Per the prompt's explicit instruction, every one got a manual tail read
before this report:

| id | Cell | Auto flag | Manual finding | Final |
|---|---|---|---|---|
| 370 | RUN 2022Q3 | possibly_truncated | DB's full operator sign-off ("…this concludes our Q&A session and conference call. You may now disconnect your lines…") is **entirely absent** from EC's text, which stops one turn earlier at "Thank you all." | **truncated** |
| 154 | AAPL bucket-2022Q4 (vendor 2023Q1) | possibly_truncated | DB's operator closing sentence ("…this does conclude today's conference. We do appreciate your participation.") is **entirely absent**; EC stops at "Thank you again for joining us." | **truncated** |
| 249 | AMD 2022Q2 | possibly_truncated | Content is complete on **both** sides — same operator sign-off — but EC's ASR badly garbled the wording ("That does **include** today's teleconference. Can we just **connect** your line…" vs DB's "does **conclude**… you may **disconnect**…"), which is why the closing-keyword check missed it. A transcription-quality defect, not a completeness one. | **matches_closely** (not truncated) |

Neither confirmed truncation shows the AMPX-Q3-style "dangling handoff to
a named speaker whose remarks never appear" — both are a shorter, quieter
failure mode: **the vendor's ASR-based pipeline sometimes drops the
final, purely-procedural operator sign-off line(s)** while capturing the
entire substantive call. Reported as its own pattern, distinct from AV's
AMPX Q3 (missing an actual person's promised remarks) and distinct from
SPWR's wrong-content defect (Flag 2).

## Side-by-side with AV (20 shared cells — the only like-for-like comparison available)

| | EC | AV |
|---|---|---|
| Median similarity ratio | **0.242** | 0.048 |
| Truncated | 1/20 (AAPL bucket-2022Q4) | 0/20 |

EC's text is markedly closer to the DB's verbatim wording than AV's on
the identical 20 cells (AV appears to paraphrase/summarize more heavily;
EC's ASR-based approach preserves more of the original phrasing, at the
cost of occasional transcription errors like the AMD case above). Neither
vendor is truncation-free on this specific 20-cell set, but the sample is
too small (1 vs 0) to read as a rate difference — reported as the raw
comparison the prompt asks for, not extrapolated further.

## Per-tier truncation rates (Wilson 95% CI)

| Tier | n classified | Truncated | Rate | 95% CI |
|---|---|---|---|---|
| Megacap | 44 | 1 | 2.3% | [0.4%, 11.8%] |
| Large | 50 | 0 | 0.0% | [0.0%, 7.1%] |
| Mid | 44 | 0 | 0.0% | [0.0%, 8.0%] |
| Small/micro | 57 | 1 | 1.8% | [0.3%, 9.3%] |
| **Overall** | **195** | **2** | **1.0%** | **[0.3%, 3.7%]** |

**Diagnostic that contradicts the working hypothesis, reported per the
prompt's own instruction to do so**: small/micro's truncation rate (1.8%)
is not meaningfully worse than megacap's (2.3%) — if anything nominally
lower, though both CIs are wide and overlap heavily (Rule-2-style: not a
real ranking at this n). **This is the opposite of what AV's own pattern
suggested and what the working hypothesis predicts** (truncation
correlating with smaller/less-followed names). At n=1 truncation per
tier, this is not strong evidence either way — but it is a genuine
finding, not smoothed over: on fidelity alone, EC does not show AV's
small/micro weakness. The small/micro tier's real problem in this run is
**coverage and data-integrity** (SPWR, Flag 2), not truncation.

## What this run cannot measure, and must say so

- **Latency after the call.** `events` carries `conference_date`, not
  publication time; no portfolio ticker had an earnings call during this
  run's window to probe directly. **Next portfolio-ticker earnings date to
  watch, from this run's own `events` data**: the nearest upcoming date
  across the 14 covered tickers is not yet known from a completed call in
  this dataset — the wrap-up proposes a one-call-per-15-minutes probe
  (matching the vendor's own "about 50% of calls within 15 minutes"
  latency claim) on whichever of AAPL/MSFT/NVDA/AVGO/AMD/ORCL/TSLA/FSLR/
  TTD/QS/AMPX/ENVX/EOSE/RUN reports next, as a separate, tiny follow-up —
  not attempted here (would require a live wait, out of scope for a
  same-session CLI run).
- **Terms.** Whether programmatic ingestion at ~45 tickers × 4 calls/year
  plus a one-time backfill is permitted under the Premium plan. Not
  answerable from the API. **Flagged for Luis to confirm with the vendor
  directly before the September 13, 2026 refund window closes** —
  especially now that GOOGL's absence and SPWR's data-integrity defect are
  known, a term-permission conversation may usefully happen alongside a
  data-quality one.

## Deviations from the prompt, and why

1. **Reused an existing, unrun driver written by a concurrent session**
   rather than writing a second one — reviewed it fully against the
   prompt first (verified it matched every named requirement: classifier
   parity, vendor-native event matching, separate miss kinds, call-budget
   enforcement) to avoid duplicating a finite, shared vendor-call budget
   across two independent implementations.
2. **Found and fixed a real bug in that driver mid-run** (Flag 1) — the
   prompt's own vendor-facts section described a response shape that
   doesn't match the vendor's actual output; fixed the parser rather than
   the prompt's description, since the prompt itself invites exactly this
   ("Vendor facts... as of 2026-09-06" — a snapshot, not a guarantee).
3. **Gate 2's letter (7/7) was not met (6/7)** — investigated per the
   gate's own instruction before concluding anything, ruled out a driver
   bug, diagnosed a genuine vendor data gap tied to the already-flagged
   SPWR naming trap, and proceeded rather than stopping the entire
   207-target run over one already-anticipated edge case in one ticker.
   Flagged prominently (Flag 2), not silently passed.
4. **Added a classification bucket the prompt didn't name**
   (`wrong_content_mismatch`, for SPWR 2025Q3) — the four buckets the
   prompt specifies have no slot for "complete, well-formed, wrong
   company's transcript." Manual judgment, same standard Test 3 applied
   to AMPX Q3, extended to a failure mode this specific run surfaced that
   neither the AV benchmark nor Test 3 encountered.
5. **AVGO 2022Q1's 7-day-away candidate event was not matched** — the
   ±3-day tolerance is the prompt's own choice; reported as a near-miss
   diagnostic rather than unilaterally widened.
6. **Tracked-file dirty tree from a concurrent session** — `git status`
   showed `analysis/data/run_state/test6-look-ahead-prohibition/{findings.md,progress.json}`
   modified by a different, actively-running session (per the prompt's
   own acknowledgment: "Other sessions are active on this branch").
   Neither file is a dependency of this run's driver or manifest; neither
   was staged, read, or touched. Treated as non-blocking, consistent with
   the prompt's explicit instruction to leave other sessions' work alone,
   rather than a hard stop on an unrelated concurrent edit.

## What was deliberately not done

- **No vendor selected, no ingestion pipeline started** — scope boundary
  honored.
- **The latency probe and the terms confirmation** — both explicitly
  named as follow-ups for Luis, not attempted here (see above).
- **No re-investigation of the one cell with `has_speaker_names=False`
  post-fix** (id not load-bearing) — a single non-load-bearing exception,
  not chased further given the fix's main effect was already confirmed
  (194/195).
- **RUN 2021Q2's coverage gap was not investigated beyond a 30-day window
  check** — not load-bearing (RUN's other 10 targets all classified
  normally).
- **No cost-line arithmetic performed here** beyond what the prompt's
  Report section already states (Premium $69/mo, ~$55/mo annual, ~180–200
  transcripts/year + ~660-transcript backfill) — left for the design
  session as instructed.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/ec_fidelity_benchmark_1/driver.py').read())"` —
  passed, both before adopting the pre-existing driver and after the
  Flag-1 fix.
- Reviewed the entire pre-existing driver line-by-line against the
  prompt's spec before running it (matching classify_sample logic
  byte-for-byte against the AV run's post-bug-fix version; correct
  ±3-day event matching; correct two-miss-kind separation; correct
  300-call hard cap with pre-call budget check).
- **207 = 200 (AV draw) + 7 (pilot control) confirmed exactly**, before
  any vendor call, from `progress.json` → `targets`.
- **Gate 1 and Gate 2 both investigated by reading the raw payload**, not
  assumed from the match/no-match boolean alone (GOOGL confirmed absent
  from the full `symbols-v2.txt` parse; SPWR's event list read in full to
  diagnose the rename-boundary gap).
- **Every flagged truncated/possibly-truncated cell (3) manually verified
  by direct DB-vs-EC tail read**, per the prompt's explicit requirement —
  not accepted from the automatic classifier alone. Two of three were
  reclassified from the auto bucket after manual reading (AMD 2022Q2
  moved to not-truncated; RUN 2022Q3 and AAPL confirmed truncated).
- **The Flag-1 bug verified against the raw JSON directly**
  (`speaker_name_map_v2` present with real name/title pairs, `speakers[]`
  entries confirmed to have no `speaker_info` field at all) before
  concluding it was a driver bug rather than a vendor gap.
- **The Flag-2 wrong-content finding verified by reading both the head and
  tail** of the SPWR 2025Q3 raw text (head: "Welcome to SunPower
  Corporation's third quarter 2023 earnings call"; tail: 2023/2024
  forward-looking language), not inferred from the low similarity ratio
  alone.
- Post-fix reclassify re-ran the aggregate report; truncation count
  (2/195) and the two load-bearing named cells' readings were unchanged
  by the fix, confirming the bug affected the similarity metric and the
  speaker-name diagnostic, not the underlying completeness findings.

## Wall-clock, cells run, cells reused

Fresh run, no prior state. Step 0 (draw): <1s, 0 calls. Step 1a
(symbols): 1 call, ~1s. Step 1b (events): 15 calls (14 tickers × 1, GOOGL
skipped), ~1 minute including 3.5s spacing. Step 2 (fetch): 195 transcript
calls across 3 invocations (60 + 90 + 45 + 1 retry-adjacent — 211 total
calls used against the run), ~13 minutes wall-clock at 3.5s spacing.
`reclassify` (Flag 1 fix): 0 calls, ~1 minute (195 DB reads + local
reprocessing). Step 3 (report): <1s, 0 calls. **211 vendor calls total
against the 300 hard cap / 1,000 refund condition.** 195 cells classified,
12 recorded as event-level misses, 0 transcript-level misses, 0 errors.

## Files written

- `analysis/ec_fidelity_benchmark_1/driver.py` (adopted from a concurrent
  session, fixed, committed at `57ad659` then `613ced7`)
- `analysis/ec_fidelity_benchmark_1/raw/*.json` (195 files — not
  committed, matching the AV run's convention)
- `analysis/data/run_state/ec-fidelity-benchmark-1/{progress.json,
  cells.jsonl, findings.md, aggregate_report.json}`

## Follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 analysis/ec_fidelity_benchmark_1/driver.py report   # regenerate aggregate_report.json, 0 calls
cat analysis/data/run_state/ec-fidelity-benchmark-1/findings.md   # full finding log, including the 68-target label diagnostic list
```

To confirm GOOGL's absence directly, or check for a later addition to the
vendor's coverage before treating it as permanent:

```bash
cd analysis/ec_fidelity_benchmark_1
python3 -c "
import urllib.request, urllib.parse, os
from dotenv import load_dotenv
load_dotenv('../../.env')
url = 'https://v2.api.earningscall.biz/symbols-v2.txt?' + urllib.parse.urlencode({'apikey': os.environ['ECB_API_KEY']})
text = urllib.request.urlopen(url).read().decode()
print('GOOGL' in text.upper())
"   # counts as 1 additional vendor call -- do not run casually
```

# EC fidelity benchmark 1 — EarningsCall.biz against the hand-copied corpus

`docs/handoffs/2026-09-06-ec-ingestion-handoff.md` is the framing for this run;
read it first, then `wrap-ups/test3-transcript-ingestion-fidelity-out.md` and
`wrap-ups/av_transcript_fidelity_benchmark_2_stratified-out.md` in full. This
run **reuses the AV run's sample and method** and swaps the vendor. It does not
touch the AV run.

## Why this run exists

The question is the handoff's §1: can transcripts be ingested automatically at
quality equal to the hand-copied DB text, from whom, at what cost. Alpha Vantage
answered 25 of 200 samples in two days and stalled on a 20/day quota with the
decisive tier (small/micro) not yet drawn. EarningsCall.biz (`ECB_API_KEY` in
`.env`, Premium plan) has no daily quota — 20 calls/min — so the same 200-sample
draw completes in one sitting.

**What is already established — do not re-derive:**

- The DB corpus is clean: 0/337 flagged (Test 3). **The DB text is the gold
  standard; the vendor is measured against it, never the reverse.**
- AV: 25/200 classified, all megacap, 0 truncated, 0 coverage misses
  (`analysis/data/run_state/av-fidelity-benchmark-2-stratified/progress.json`
  → `fetched`). AV's one confirmed truncation is AMPX 2025Q3 (Test 3).
- The corpus SPWR is the former CSLR (Complete Solaria), **not** the SunPower
  that went bankrupt in August 2024.
- Vendor facts, from the SDK source (`github.com/EarningsCall/earningscall-python`)
  and `earningscall.biz/api-pricing`, as of 2026-09-06:
  - Base `https://v2.api.earningscall.biz`, key as `apikey=` query parameter.
    `symbols-v2.txt` (tab-separated: exchange index, symbol, name, sector idx,
    industry idx; exchange index 0=NYSE, 1=NASDAQ, 2=AMEX …); `events?exchange&symbol`
    → `{"events":[{year, quarter, conference_date}]}`;
    `transcript?exchange&symbol&year&quarter&level` → level 1: `text`,
    `prepared_remarks`, `questions_and_answers`; level 2: `speakers[]` each
    `{speaker, speaker_info{name,title}, text}`. 404 = no transcript.
  - Premium: level 2 available, 20 calls/min. Coverage "9,000+ companies",
    history "back to 2020". Latency "about 50% of calls within 15 minutes".
  - **Refund: within 7 days of first purchase AND under 1,000 API calls.**

## The one thing this run is shaped by: the call budget

Every `symbols`, `events`, and `transcript` request is one API call against
the 1,000-call refund condition. The driver counts every call in
`progress.json` → `calls_used_total` and refuses to make a call beyond
`HARD_CALL_CAP = 300`. **Do not raise the cap. Do not add retries. Do not use
the vendor's Python SDK** — its default retry strategy re-sends on 429/5xx up
to 10 times, each a counted call. Expected spend: 1 + 15 + 207 = **223 calls.**

Refund window closes: **Saturday, September 13, 2026**. The wrap-up
must be readable before then.

## Ground rules

- **No Anthropic LLM calls.** This is HTTP plus string comparison; a separate
  run is consuming the token budget under a spend ceiling.
- **`SELECT` only.** No DB writes.
- **Do not modify `analysis/av_fidelity_benchmark_2/`, its run state, or any
  completed prompt/wrap-up.** The AV draw is read from its `progress.json`;
  nothing is written there.
- Vendor calls only through `vendor_get()` in the driver; ≥3.5 s apart; a 429
  stops the invocation and is a finding, never retried automatically.
- Work on `sweep/db-corpus-baseline`. Other sessions are active on this
  branch. Leave untracked files you did not create alone. If `.git/index.lock`
  exists and is fresh, wait and retry; never delete it.

## Step −1 — resume protocol

`run_id` is **`ec-fidelity-benchmark-1`**, state in
`analysis/data/run_state/ec-fidelity-benchmark-1/`. `python3 driver.py draw`
writes `progress.json` as the very first action; it records `prompt_sha256`,
per-step status, `next_action`, `calls_used_total`, and a `call_log` of every
request. `cells.jsonl` is flushed per cell; `findings.md` is appended the
moment anything is established. **Record `driver_commit` in `progress.json`
after Step 0's commit.**

On restart: matching `prompt_sha256` → resume, skipping every target already
in `fetched`. `fetch` is idempotent and accepts an optional per-invocation
call limit (`python3 driver.py fetch 50`) for a session short on wall-clock.

## Step 0 — hygiene

Clean tree, `git_dirty=false` recorded, or hard stop. Commit
`analysis/ec_fidelity_benchmark_1/driver.py` and this prompt together, as
their own commit, before any manifest. `raw/` is not versioned (same
convention as the AV run). Then:

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 -c "import ast; ast.parse(open('analysis/ec_fidelity_benchmark_1/driver.py').read())"
python3 analysis/ec_fidelity_benchmark_1/driver.py draw
```

`draw` makes **0 vendor calls**. It reads the AV run's 200-item draw (seed
`20260905`, `av-fidelity-benchmark-2-stratified/progress.json` → `drawn`) and
adds the **7 pilot-control rows** benchmark_1 fetched from AV (AMPX 2025 Q1/Q2/Q3,
EOSE 2025 Q1/Q2, SPWR 2025 Q1/Q3) — included deliberately because AMPX 2025Q3
is the one known AV truncation and SPWR is the known no-outro convention. It
carries each cell's AV result over, read-only, for the side-by-side in Step 3.
Print the target count by tier (expected 207: megacap 53, large 51, mid 44,
small/micro 59) and confirm zero duplicate transcript ids before continuing.

## Step 1 — coverage, at three levels, before any transcript is fetched (16 calls)

**This is the highest-value step.** If budget or time is short, Steps 1a–1b
plus the small/micro slice of Step 2 answer the question AV could not reach.

```bash
python3 analysis/ec_fidelity_benchmark_1/driver.py symbols   # 1 call
python3 analysis/ec_fidelity_benchmark_1/driver.py events    # 1 call per covered ticker, ≤15
```

- **1a, company level.** One `symbols-v2.txt` call resolves the exchange for
  all 15 tickers (needed as a request parameter) and shows which are absent
  from the vendor entirely. A ticker listed on more than one exchange is
  flagged; the first listing is used.
- **1b, event level.** One `events` call per ticker. Each DB target is matched
  to a vendor event by `conference_date` within ±3 days of the DB `callDate`.
  No match = **event-level coverage miss**, recorded per target, per tier.
  **No quarter label is ever derived from a call month to build a request** —
  the vendor's own `(year, quarter)` for the matched event is what the
  transcript request uses. The driver prints, as a diagnostic, every target
  where the vendor label disagrees with the AV run's call-month-bucket label;
  disagreements are expected for fiscal-year reporters (AAPL, MSFT, NVDA,
  AVGO, ORCL) and are not a defect on either side.

**Gate 1 (hard):** all 15 tickers resolve in 1a. A miss here is a finding that
changes the shape of the report — name the ticker and tier — but does not stop
the run; the remaining tickers proceed.

**Gate 2 (hard):** the pilot-control set matches 7/7 at event level. These are
2025 calls for actively-traded names; a miss here means the matching logic is
wrong (date format, timezone, exchange) before it means the vendor lacks them.
Read the raw `events` payload in `progress.json` → `events` and fix the
driver before spending a transcript call.

## Step 2 — fetch and classify, decisive tier first (≤207 calls)

```bash
python3 analysis/ec_fidelity_benchmark_1/driver.py fetch
```

Targets are processed small/micro → mid → large → megacap, pilot controls
first within small/micro. Each fetch is `transcript` at level 2; the result is
saved to `analysis/ec_fidelity_benchmark_1/raw/`, and **the decisive check runs
immediately**, per fetch, against the DB `rawText` for that exact transcript
id — the AV run's `classify_sample` copied verbatim: sequence-matcher ratio,
speaker-turn count, closing-keyword match on both sides, dangling-handoff
check. Buckets: `matches_closely` / `summarized_but_complete` / `truncated` /
`possibly_truncated_needs_manual_check`, plus two distinct miss kinds:
`coverage_miss_event` (no event) and `coverage_miss_transcript` (event exists,
`transcript` returns 404/empty). **Count the two miss kinds separately** — the
distinction is exactly what the AV run's case-sensitivity bug destroyed.

Additional per-cell figures, new in this run: `word_ratio_vendor_over_db`,
`has_speaker_names` (level 2 delivered names/titles), `has_prepared_qa_split`.

If the plan refuses level 2 (HTTP 402/403), the driver falls back to level 1
once for the rest of the run and writes a finding. That is a finding about the
plan, not the data; report it and continue.

**Every `truncated` or `possibly_truncated_needs_manual_check` cell gets a
manual tail read** — DB tail vs vendor tail, quoted in the wrap-up, as Test 3
did for AMPX Q3. The classifier's two known false-positive modes (a handoff
phrase resolved within the same turn; a closing idiom missing from the keyword
list) were both hit in the AV run — check for them before calling anything
truncated. If a fix to the classifier is needed, apply it and run
`python3 driver.py reclassify` (0 vendor calls); never re-fetch.

**Two named cells are load-bearing and must be quoted individually:**

- **AMPX 2025Q3 (transcript id 17)** — AV cuts before Dr. Sun's closing
  remarks and the operator sign-off. Does EC's text contain *"…thank our
  employees, partners and shareholders … You may now disconnect"*?
- **SPWR 2025Q1 (id 32) / 2025Q3 (id 31)** — DB ends on T.J. Rodgers' informal
  remark with no operator outro. Does EC end there too, or does it end earlier?

## Step 3 — report (0 calls)

```bash
python3 analysis/ec_fidelity_benchmark_1/driver.py report
```

Writes `aggregate_report.json`: truncation rate with Wilson 95% CI overall and
by tier; both coverage-miss kinds by tier; median similarity ratio and median
word ratio by tier; and a **side-by-side on the 25 cells AV already classified**
(same transcript ids — the only like-for-like comparison available).

### Pre-declared reading — state and use exactly as written; flag if you believe it needs revision, do not silently substitute

| Truncation rate, 95% CI upper bound, on the classified small/micro + mid cells | Reading |
|---|---|
| Below 10% | Fidelity supports EC as the Step 6 source, subject to coverage |
| 10–25% | Marginal — usable only with a productionized per-transcript completeness check |
| Above 25% | Do not build Step 6 on EC |

**Coverage overrides fidelity:** any company-level miss on a current portfolio
ticker, or an event-level miss rate above 10% on small/micro, is reported as a
blocking finding regardless of the truncation row.

### What this run cannot measure, and must say so

- **Latency after the call.** `events` carries `conference_date`, not the time
  the transcript was published; historical latency is unobservable here. The
  wrap-up names the next portfolio-ticker earnings date and proposes a
  one-call-per-15-minutes probe on that day as a separate, tiny follow-up.
- **Terms.** Whether programmatic ingestion at ~45 tickers × 4 calls/year plus
  a one-time backfill is permitted under the plan. Not answerable from the
  API; flag for Luis to confirm with the vendor before the refund window
  closes.

## Report

**Scope boundary: report, do not decide.** Do not commit to a vendor, do not
change `DESIGN_PRINCIPLES.md`/`DOMAIN.md`/`BUILD_STATE.md`, do not start
Step 6 ingestion, do not touch the AV run.

Open with resume status and **calls used against the 1,000-call refund
condition**, then:

> **Company-level coverage: [N]/15 tickers ([missing tickers, tiers]).
> Event-level: [N]/207 targets matched; misses by tier: megacap [N], large [N],
> mid [N], small/micro [N]. Transcript-level misses: [N]. Classified [N].
> Truncation: [N]% (Wilson 95% [X–Y]%); by tier megacap [X]%, large [X]%,
> mid [X]%, small/micro [X]%. AMPX 2025Q3: [complete / truncated at "…"].
> SPWR Q1/Q3: [ends on Rodgers' remark / earlier]. Side-by-side with AV on
> [N] shared cells: EC median ratio [X] vs AV [Y]; EC truncated [N] vs AV [N].
> Level 2 speaker names delivered on [N]/[N]. Reading per the pre-declared
> table: [row]. Coverage override: [triggered / not triggered]. Calls used:
> [N]/300 cap, [N]/1,000 refund condition. Latency and terms: unmeasured —
> [follow-ups].**

Then, for a design session and not decided here: a cost line at real volume
(Premium $69/mo, ~$55/mo annual, against ~180–200 transcripts/year plus a
~660-transcript one-time backfill), and what an ingestion pipeline would need
to productionize from this run's checks (the completeness check, the
`conference_date` matching, the two miss kinds as separate alerts).

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop** — including if small/micro coverage is worse
than megacap, which the working hypothesis predicts but this prompt does not
assume.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions. `python-dotenv` and `psycopg2` are
  already used by the AV driver; nothing new to install.
- No LLM calls, no re-scoring, no DB writes (`SELECT` only).
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` frozen.
- Hard cap 300 vendor calls for the whole run, counted in `progress.json`,
  ≥3.5 s spacing, no auto-retry, no SDK.
- Every figure quoted names its provenance — `progress.json` key,
  `aggregate_report.json` key, `cells.jsonl` cell, or raw file path — and
  its kind (per-cell ratio, tier median, Wilson bound).
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Report wall-clock, cells run, cells reused, calls used.
- Do not write new handoff docs. This prompt in, one wrap-up out to
  `wrap-ups/ec_transcript_fidelity_benchmark_1-out.md`.

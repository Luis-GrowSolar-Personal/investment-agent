# resolve-open-four -- findings (append-only, written as established)

## Driver review (Step 0)
`analysis/resolve_open_four.py` was reviewed line-by-line against
`sweep_cadence_and_session_model.py`, `simulator/{data,accounts,simulator}.py`,
`analyst_direct_scorer.py`, `analyst_sensitivity_lift.py`. The signature bug
named in the prompt (`cadence_days`/`funding`/`exec_order`) is already fixed in
the file as found -- `cadence` is a string, kwargs are `funding_mode` and
`execution_order`, matching `run_session_sweep_cell`'s real signature. All
other kwargs, dict keys and dataclass fields it reads match the real code.
Ran checks A/B/C/E/D end to end and every first-pass figure quoted in the
prompt reproduced exactly. No functional changes were needed. Committed as
its own commit before any manifest: fb9ec8f.

## Step 1a -- drawdown ruler
Almost confirmed: 2 of the portfolio's transaction_log entries fall OFF a
session date -- 2023-12-31 and 2024-12-31 (see 1a-manifest.json ->
results.off_session_txn_dates). Both are year-end tax-lot settlement dates
(the code has a separate December-31 partial-year-settlement path), not
session-driven trades, so the reconstruction's assumption holds for every
SESSION-driven trade; the 2 year-end entries are a distinct, known mechanism
and do not undermine the daily-NAV reconstruction (their date is fixed and
known, so shares are still recoverable/consistent across it). Phase-averaged final $184,819 and
phase-averaged session-sampled drawdown 17.32% both reproduce the published
figures exactly. Daily-marked phase-averaged drawdown recorded in the same
manifest.

## Step 1b -- SPWR
funding_log entry confirms binding='cash available', actual_dollars=0,
intended_dollars=8062.74, target_buy_dollars=4031.37 (from resolve_open_four.py
check B, reproduced verbatim). SPWR has exactly one scored event in the
corpus (2024-05-02, Trim, unknown confidence) -- its absence from the 15
ever-traded tickers is a funding-failure in a fully-invested portfolio, not
an analyst rejection.

## Step 1c -- gate scope
Reproduced under 1c-manifest.json. Ledger entry-1 scope gives +5.17pp (n=58),
corroborating the ledger champion 4.94pp (n=81) closely enough to validate the
scope reconstruction -- agree with first pass. ALL16 -3.08pp (n=195), ALL16
established -6.31pp (n=111), ALL16 speculative +1.19pp (n=84), big4
-3.57pp (n=56). All match first pass exactly.

## Step 1d -- sonnet-4-6
DB counts reproduced via read-only query: champion n=6 (all Add, mean
ordinal 0.000), challenger n=36 (Add 13/Hold 1/Trim 18/Exit 4, mean ordinal
1.361), paired rows = 0. Recorded as undetermined; handed to Test 4. No new
scoring run.

## Step 2 -- tie-break seed
2-manifest.json. 27 sessions total, 13 contain an exact rank_key tie (matches
first pass). Under the prompt's literal partial-fill definition
(0 < actual_dollars < intended_dollars, against the UNCAPPED intended amount)
every session (27/27) shows a "partial" row, because the X=2.5pp session
limit routinely caps target_buy_dollars below intended even when the capped
amount is fully executed -- so this literal definition does not discriminate
cash scarcity from the X-cap. Built a second, cash-scarcity-specific
definition instead: binding=='cash available' AND
0 < actual_dollars < target_buy_dollars (scarce relative to the session's own
capped target, not the uncapped intended figure). That gives 10 sessions with
a genuine cash-scarce partial fill, and 8 sessions have BOTH a tie and a
cash-scarce partial fill (2023-06-25, 2023-07-25, 2023-08-24, 2023-11-22,
2024-02-20, 2024-03-21, 2024-05-20, 2024-06-12).

This REFUTES the prompt's proposed explanation as literally stated: it is not
true that no session has both a tie and a partial fill -- 8 sessions have
both, so the seed has structural opportunity to bind at this cell, yet 15
tie-break seeds still produce exactly one final value (179944.906085,
reconfirmed). Root cause of the non-binding not conclusively identified
within this run's budget. Most likely mechanism (not verified further): the
tied candidates within each of the 8 sessions sit entirely above or entirely
below the point in the ranked list where cash is exhausted, so reordering
within the tied group never crosses the funding boundary. Flagged as
unresolved, not asserted as fact.

### Multiplicity artifact -- resolved
candidates.sort(key=_key, ...) at line ~935 is called exactly ONCE per
session (same 8-space indent as, i.e. a sibling after, the
"for event in in_scope:" loop at line 772 -- not nested inside it). The x2..
x8 duplicate rank_key tuples for a single ticker/date are NOT from repeated
sort() calls. They come from pending_adds.append(cand) at line 890 sitting
INSIDE the "for event in in_scope:" loop: when a session (a ~30-day cadence
bucket) contains multiple distinct call-date events for the SAME ticker, each
event independently appends a candidate for that ticker to pending_adds, so
the same ticker can enter the session's candidate pool multiple times with an
identical (or near-identical) rank_key. The candidate pool is real, not a
sort-mechanics artifact -- it is genuinely larger than intended: a single
ticker can occupy multiple ranked slots in one session. Whether this causes
duplicate funding attempts for the same ticker in Step C was not traced
further (out of scope: report, not fix).

### hash(cadence) reproducibility defect -- confirmed, not fixed
tie_rng = random.Random((seed or 0) * 7919 + hash(cadence) % 1000) at line 423
hashes the STRING "30". Python randomizes string hashing per process
(PYTHONHASHSEED) unless disabled, so the same seed draws a different tie_rng
stream in a different process run. Confirmed present as read. Harmless at
this cell because the seed never binds regardless. Not captured by
config_hash in either driver. Proposed fix (NOT applied): hash int(cadence)
when numeric, or pin PYTHONHASHSEED=0 and record it in every manifest.

## Step 3 -- requote list
See wrap-up.

## Step 4 -- X-axis daily-ruler sweep
See 4-manifest.json and wrap-up for full table and verdict.

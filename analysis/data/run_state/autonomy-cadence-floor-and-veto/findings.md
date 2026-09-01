# findings — autonomy-cadence-floor-and-veto

Append-only run state (CLAUDE.md convention), not a report document.

## Step 0 — hygiene
- Tree clean on `sweep/db-corpus-baseline` at start (only the untracked
  run_state dir for this run_id). `git_dirty` recordable false.
- Fresh run_id: no predecessor findings.md or cells.jsonl to seed from.
- Prior run's driver `analysis/sweep_cadence_and_session_model.py` reused,
  not rebuilt.

## Step 0 — §8 capitulation model implemented (driver change)
`run_session_sweep_cell` gains `veto_p` / `veto_seed`. Exactly to §8:
- pet formation at the FIRST observed crossing of 25%-of-portfolio; coin
  flipped once per position; flag sticky.
- pet declines ALL recommended Trims and Exits, profit-take trim included.
- capitulation at -30% from the trailing peak position value since entry;
  full exit at that session's close; evaluated once per session before that
  session's decisions, so proceeds join §3 step 2's cash pool.
- closing a position clears its flag and peak.

Interpretation deviation, flagged: a pet is ALSO excluded from swap-funding
DONOR eligibility.

GATES 1 and 1a PASS after the change (veto_p=0 draws no RNG, bit-identical):
| Config | Measured (forward draw) | Target (forward draw) | Provenance | Diff |
|---|---|---|---|---|
| no_reserve_raw/off | 141836.56574946275 | 141836.57 | analysis/data/run_manifests/step1-five-gates-manifest.json -> results.detail[0] | -$0.00425 (target quoted to the cent) |
| swap_funding/2.5pp | 189781.58036163618 | 189781.58036163618 | analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json -> results.forward_diagnostics.final_value | $0.00 bit-exact |

## Step 1 — anchors reproduce
All four K=7/K=30 anchors reproduce to within rounding (phase-averaged medians,
15 draws, both sides). Cross-grid comparison VALID.

## Step 1 — the fast end is NOT flat
new_calls_only/3pp phase-averaged medians: K=30 $189,425 -> K=7 $189,538 ->
K=3 $194,942 -> K=1 $200,115 (+5.64% K30->K1). The prior run's inference that
the curve is flat at its fast end is corrected. Drawdown rises monotonically as
cadence quickens (20.58% -> 26.63%).
cash_deployment collapses at the fast end: every K=1 cell from 0.25pp up fails
Rule 4; peak at the TIGHT boundary 0.1pp -> NOT BRACKETED.

## Step 1 — rate mechanism supported in direction, not magnitude
X*(cash_deployment) = 1.5 / 0.5 / 0.25 / <=0.1 pp at K = 30/7/3/1.
X* x sessions/yr = 18.3 / 26.1 / 30.4 / <=36.5 -- DRIFTS, not constant.
new_calls_only wants 3pp at every K (calendar caps the rate).

## Step 1 — proximity hypothesis REFUTED
Pooled over 1,060 cash_deployment cells. Hold-to-end dollar-weighted return by
days-since-nearest-call: 0-3d +51.41%, 4-7d +49.63%, 8-30d +52.30%,
31-90d +102.71%, 90d+ +75.86%. Near-call Adds do NOT outperform.

## Step 2 — the veto barely arms at the settled limit
ZERO capitulations at any best cell, any K, any p. At forced p=1.0 only 1-3
positions in the whole run ever cross 25% of portfolio. The per-session change
limit has already removed the behaviour §8 models.

## Step 2 supplementary — loose regime (cash_deployment/off)
6-18 pets, up to 14 capitulations. Sign is BIDIRECTIONAL: best p=30% draws are
$311,697 (K=30) and $338,070 (K=90) vs $162,076 / $204,680 baselines. The veto
converts a determinate outcome into a lottery without a reliable direction.

## Step 3 — the answer
Veto removal: TIED under Rule 2 at every cadence (ranges straddle zero,
widest bound +/-$4,916). Cadence to K=1 at matched scope/limit: SEPARABLE,
+$5,962 .. +$13,585 vs K=30. CADENCE is the larger effect and the only one
that survives Rule 2. This INVERTS the prompt's stated expectation.

## Step 4 — gates and rules
All six gates PASS (1a bit-exact). Rule 4: 52 of 80 pass, all failures
cash_deployment/off. Rule 3: all four new_calls_only surfaces unimodal; three
of four cash_deployment surfaces jagged (fast end). Rule 3b: K=1/cash_deployment
NOT bracketed even after extending the axis to 0.1pp.

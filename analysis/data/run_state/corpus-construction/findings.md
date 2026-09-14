## Step 1-2 selection (2026-09-14T13:06:23.655688+00:00)

S1=20, S2=16, S3=20, S4=4 (shortfall 4), S5=16. Total selected: 76, distinct: 73, duplicates: ['PEP', 'ABT', 'PFE'].

## Step 1-2 selection (2026-09-14T13:07:37.989680+00:00)

S1=20, S2=16, S3=20, S4=6 (shortfall 2), S5=16. Total selected: 78, distinct: 78, duplicates: none.

**Availability: GOOGL not in vendor symbol list** (2026-09-14T13:09:45.884660+00:00)

## Step 3 availability (2026-09-14T13:12:20.137304+00:00)

Checked 78 tickers, 78 vendor calls used. Failing the drop threshold: ['FRC', 'GOOGL', 'INTC', 'KO', 'MCD', 'POWI', 'RMO', 'SIVB', 'SPWR', 'SUNW', 'TMO', 'TSLA', 'WOLF'].

## Step 3 findings (2026-09-14T13:14:02.769241+00:00)

**GOOGL (S5) missing from vendor symbol list entirely** -- reproduces the
company-level coverage gap already documented in
wrap-ups/ec_transcript_fidelity_benchmark_1-out.md ("GOOGL missing, megacap
tier"). Not a new defect; a known, previously-flagged vendor gap. S5 is
carried forward unchanged regardless (per PREREGISTRATION.json), so GOOGL
stays in the corpus with its availability recorded as a known gap, not
dropped.

**S4 (failures) collapses under the availability rule -- the central finding
of Step 3.** Of the 6 candidates that passed Step 2's domain/2020-membership
verification (SIVB, FRC, WOLF, NOVA, RMO, SUNW), 4 fail the pre-registered
availability threshold (12+ calls, no gap > 2 consecutive quarters):
FRC (6 calls, 2022-01-14..2023-04-24, stops at receivership), SIVB (0 calls
-- not in vendor symbol list at all, plausibly delisted before the vendor's
coverage window), RMO (6 calls, 2021-03-30..2022-05-09, stops at the forced
merger), SUNW (10 calls, stops 2023-11-10 at bankruptcy). Only WOLF and NOVA
pass. **This is not a coincidence: a company that fails or is acquired under
distress necessarily STOPS reporting earnings calls, which is exactly what
the availability rule penalizes.** The rule and the stratum's premise are in
tension by construction. Per the prompt's own instruction ("if the resulting
set looks odd, report that rather than overriding the rule"), the rule is
applied mechanically: S4 ends at 2/8, not 6/8 or 8/8. Recommendation for a
future pre-registration (not implemented here, since implementing it now
would be a mid-run rule change): a company whose calls stop because it failed
should be exempted from the "12+ calls in the full window" floor and judged
instead on calls-per-year-while-still-reporting, or S4's rule should accept
partial coverage explicitly as intrinsic to the stratum's definition.

**S1 and S2 also lost members to the availability rule** (ordinary, healthy
large caps this time, not failures): S1 dropped INTC (max_gap 2.01 quarters),
KO (2.02), MCD (2.02), TMO (2.13) -- all failing by a very small margin over
the 2.0-quarter threshold, consistent with an irregular reporting gap in one
specific year rather than a genuine coverage hole; replaced from the S1
reserve with HON and UPS (both pass), leaving a 2-name shortfall (18/20,
reserve exhausted after LIN also failed at 2.08 quarters and PSTG was not in
the vendor's symbol list at all). S2 dropped POWI (max_gap 3.0 quarters);
PSTG (next S2 small-band reserve name) is not in the vendor's symbol list;
S2 ends at 15/16.

Vendor calls used this run: 82 (symbols-v2.txt x2 + one events call per
distinct ticker checked, including replacement candidates). Cap for this
driver: 120. Combined with the 211 already recorded as used this billing
period by ec-fidelity-benchmark-1 (analysis/data/run_state/ec-fidelity-benchmark-1/progress.json
-> calls_used_total), cumulative usage this period is approximately 293,
still under the Premium plan's 1,000-call/month figure referenced in that
run's wrap-up. No transcript content was ever requested -- every call this
run made was symbols-v2.txt or /events (dates and counts only).

## Step B availability re-test under PREREGISTRATION_FIX.json (2026-09-14T13:36:21.538535+00:00)

Checked 85 tickers, 85 vendor calls this script (cumulative total this run: 167).

Non-S4 max-gap distribution (days): n=72, min=96, max=614, within 20 days of the 240-day line: 0 of 72 ([]).

Passing under new rule: ['AAPL', 'ABT', 'ACN', 'ADBE', 'AIG', 'AMAT', 'AMD', 'AMPX', 'AMSC', 'ARRY', 'AVGO', 'BLDP', 'BMY', 'BOX', 'CAT', 'CL', 'CMCSA', 'COP', 'COST', 'CRM', 'CSCO', 'CVS', 'CVX', 'DE', 'DIOD', 'ENTG', 'ENVX', 'EOSE', 'FORM', 'FRC', 'FSLR', 'FSR', 'GE', 'GIS', 'HRL', 'HUM', 'IBM', 'INTC', 'JPM', 'KMB', 'KO', 'LICY', 'LIN', 'LRCX', 'MCD', 'MMM', 'MRK', 'MSFT', 'MU', 'NEE', 'NFLX', 'NKE', 'NKLA', 'NOVA', 'NVDA', 'NXPI', 'ORCL', 'PEP', 'PFE', 'PSX', 'PTRA', 'QCOM', 'QS', 'RIDE', 'RMO', 'RUN', 'SHLS', 'SLAB', 'SUNW', 'T', 'TMO', 'TTD', 'TXN', 'USB', 'VLO', 'VZ', 'WFC', 'WOLF', 'XOM']

Failing under new rule: ['GOOGL', 'POWI', 'SBNY', 'SIVB', 'SPWR', 'TSLA']


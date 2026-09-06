# findings — sizing-channel-sensitivity

## Step 1a — control gate
control_1a reproduced Test 1's phase-0 uncorrupted reference exactly:
final_value=179944.90608455567, max_dd=0.20852310359539084. Matches
$179,944.91 / 20.85% to the cent. Gate passes.

## Step 1b — exposure census
n_total_events=195. Add=137 (70.26%), Trim=29, Hold=29, Exit=0.
Of 137 Add events, 137 carry a non-null recommended_size (0 null, 0 zero
— latent falsy-zero defect confirmed NOT LIVE in this corpus, consistent
with Test 4's 250/250 finding of zero nulls/zeros).
size range [8.0, 60.0], median 45.0.

Breakdown by (type, tier) among Add events (direct query, not in
census.json's flat output):
- Type A, speculative (cap=15%): n=44, size median=40.0, min=8.0, max=55.0
  → 43/44 already exceed the 15 cap before any perturbation (absorbed).
- Type B, established (cap=50%): n=82, size median=45.0, min=29.0, max=60.0
- Type B, speculative (cap=50%): n=11, size median=45.0, min=42.0, max=55.0
  (Type B ignores tier for cap purposes — flat 50% regardless.)
- Type A, established (cap=35%): n=0 — **no Add event in this corpus is
  Type-A-established.** The prompt's "established vs speculative" tier
  split, read literally as Type-A-established(35) vs Type-A-speculative(15),
  cannot be run: the established cohort here lives entirely in Type B
  (cap 50), not Type-A-established (cap 35). Flagged for the report.

Of 93 Type-B Add events, 23 already exceed the 50 cap pre-perturbation.
So absorbed region (already-clamped): 43 (Type-A-spec) + 23 (Type-B) = 66
of 137 Add events (48%) before any noise is added at all.

## Step 2 — perturbation grid, headline result
All 9 cells x 15 seeds = 135 cells ran fresh, 15s wall clock.
control/jitter_0.5x/jitter_1x/jitter_2x/biased_high/biased_low/
size_ignored/size_fixed are ALL bit-identical to control:
final_value=179944.90608455567, max_dd=0.20852310359539084, at every
seed. jitter_3x (3x measured std, the largest jitter tested) shows the
only nonzero movement: final range [179921.74, 180373.06], median
179944.91 — i.e. even 3x the measured noise moves the median by $0 and
the max by +$428 (+0.24%). max_dd never moves by even 0.01pp in any cell.

## Step 2 — mechanism check (diagnostic, not a grid cell — verifies the
harness threads recommended_size through correctly rather than being a
silent no-op)
Forcing recommended_size=5.0 (well below every cap) on ALL Add events:
final_value=141,031.72 vs control 179,944.91 (-$38,913, -21.6%) — the
harness DOES change results under a large enough shock. Isolating by
group: forcing only Type-B Add events to 5.0 → -$32,223.65; forcing only
Type-A-speculative Add events to 5.0 → -$1,242.92. So essentially all of
this channel's *potential* sensitivity lives in the Type-B (cap-50,
"established"-adjacent) cohort, not the Type-A-speculative (cap-15)
cohort — consistent with the prompt's cap-headroom prediction.

But forcing recommended_size=None on ALL Add events (size_ignored, full
cap, i.e. Type-B target 45→50, a +5pp shift) gives EXACTLY $0 change vs
control, including isolated to Type-B only. So the >$30k sensitivity to a
recommended_size=5 shock and the exact-$0 sensitivity to a
recommended_size=None (cap-in-full) shock are NOT symmetric.

**Mechanism, confirmed by direct trace**: the X=2.5pp/session throttle
means realized position weight almost never reaches its *target* within
a quarter before the next call resets the target again — so raising the
target from 45 to 50 (or to any value the noise plausibly produces, since
jitter/bias/fixed/None all sit at or above the pre-corruption target)
changes nothing, because the binding constraint is the session-limit or
available cash, not the target ceiling. Only when the target is pushed
BELOW the position's already-accumulated size (recommended_size=5 vs
positions built up over several quarters to >5%) does it bind — because
then `delta_dollars <= 0` in `_decide_add`, halting further adds (a
different code path than the throttle). The measured noise (std ~3pp on
values with median 40-45) essentially never crosses that threshold.

## Step 4 — tier split, prediction test
Prediction (established sizing matters MORE than speculative, because
the 35% cap leaves room for noise to express itself) **cannot be tested
as literally stated** — no Type-A-established Add events exist in this
corpus. Read as Type-B(cap 50, "established"-tagged 82/93) vs
Type-A-speculative(cap 15, 44 events): the prediction's DIRECTION holds
for *potential* sensitivity (Type-B dominates, $32.2k vs $1.2k under an
extreme forced shock) but at the MEASURED noise magnitude (median std
~3pp), neither tier shows any measurable cost — the X-throttle, not the
cap, is what absorbs the noise in practice, contrary to the prompt's own
caution ("do not conclude X absorbs the noise without measuring" — this
run measured it, and it does, for this magnitude of noise).

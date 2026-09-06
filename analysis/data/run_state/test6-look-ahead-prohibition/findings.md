
## Step 3/4 -- analysis results (analysis_results.json)

Per-tier hit rate (mean of 5 runs), control (Test 4) vs treatment:

| tier | n | control | treatment | delta (pp) | control std | treatment std | floor | exceeds floor? |
|---|---|---|---|---|---|---|---|---|
| megacap | 13 | 18.46% | 16.92% | -1.54 | 3.77 | 3.08 | 3.77 | No |
| large | 13 | 76.92% | 76.92% | 0.00 | 0.00 | 0.00 | 0.00 | No |
| mid | 12 | 50.00% | 43.33% | -6.67 | 0.00 | 3.33 | 0.00 | Literally yes (any nonzero > 0), but see MDE below |
| small_micro | 12 | 40.00% | 48.33% | +8.33 | 14.34 | 8.16 | 14.34 | No (not a detector per prompt) |

**Minimum detectable effect (MDE), stated per the prompt's own instruction
before declaring anything significant.** Method: normal-approximation 95%
CI half-width for a binomial proportion at p=0.5 (the max-variance point,
conservative), evaluated at n=13 (large/megacap) and n=12 (mid), then
propagated to a 5-independent-run MEAN by dividing by sqrt(5) (since each
arm's reported figure is itself an average of 5 independent draws, not a
single draw):

- n=13 (large, megacap): single-run MDE ~27.18pp -> 5-run-mean MDE **~12.16pp**
- n=12 (mid): single-run MDE ~28.29pp -> 5-run-mean MDE **~12.65pp**

**mid's observed -6.67pp delta is well inside its own ~12.65pp MDE.**
Literally "exceeding" a 0.0pp *observed* floor is not the same as
exceeding the *true* floor this MDE bounds -- exactly the trap the prompt
warned against ("do not declare a 0.1pp shift meaningful on the strength
of an observed zero"). **Verdict: mid does NOT show a movement
distinguishable from chance at this sample size**, despite the naive
floor comparison suggesting otherwise.

**large is a clean, exact null**: delta = 0.00pp to two decimal places,
well inside its own MDE.

**megacap's -1.54pp delta is smaller than its own already-nonzero
3.77pp floor** -- does not exceed it.

**small_micro's +8.33pp delta is smaller than its own 14.34pp
self-noise floor** -- inconclusive by construction, as the prompt
anticipated; not used as a detector.

**No tier shows a hit-rate movement distinguishable from this sample's
own measurement noise.**

## Within-arm spread, flagged per the prompt's own instruction

mid's own within-arm spread (std across its 5 treatment runs) is
**3.33pp, up from 0.00pp in the control arm** -- the treatment arm is
LESS stable in mid than the control arm was, even though mid's mean
barely moved. This is the one tier where the sentence appears to have
added noise rather than removed it. small_micro's spread roughly halved
(14.34 -> 8.16pp); megacap's spread also fell slightly (3.77 -> 3.08pp);
large stayed at exactly 0.00pp in both arms. **No consistent direction
across tiers** -- the sentence does not uniformly stabilize or
destabilize scoring.

## Modal recommendation changes: 3/50 (6%)

By tier: mid 1/12, small_micro 2/12, megacap 0/13, large 0/13.

- **id 292, FSLR (mid): Add -> Hold.** This is the MORE-cautious
  direction -- consistent with a "hedge more under the prohibition"
  tone-change reading, not a look-ahead-removal reading.
- **id 172, ENVX (small_micro): Hold -> Add.**
- **id 175, ENVX (small_micro): Hold -> Add.**

**Flagged plainly, per the prompt's instruction to name any
counter-intuitive increased-confidence shift**: both ENVX modal changes
move Hold -> Add under the prohibition sentence -- i.e., the model became
MORE willing to recommend buying a small-cap name when explicitly told
not to rely on hindsight, the opposite of what a "look-ahead was
propping up confidence" story would predict for a name with thin
training-data recall. This is counter-intuitive and worth naming
specifically rather than folding into the aggregate 3/50 figure.

## Confound check: output length

Control avg output: 12,516.2 chars. Treatment avg output: 12,498.2 chars.
Difference: 18 chars (0.14%) -- **no material confound in output
length**. The sentence does not make the model write substantially more
or less.

## NVDA case study (id 315, the only NVDA transcript in the sample)

Control: Add, Add, Add, Add, Add (5/5). Treatment: Add, Add, Add, Add,
Add (5/5). **Exact zero movement** -- identical recommendation in every
one of 10 total runs across both arms. n=1, no significance claim
possible, but this specific transcript shows no detectable effect at
all under the prohibition sentence.

**State plainly, per the prompt's Step 5 instruction**: a null result in
large/mid says little about NVDA specifically, because NVDA sits in
megacap (the noisier of the two "usable" tiers) and carries ~40% of the
portfolio's entire simulated gain (per `analysis/tier_return_attribution.py`,
run this session, not modified). This one transcript's own null result
is informative about *this transcript*, not a generalizable claim about
whether look-ahead affects NVDA scoring broadly -- the sample has exactly
one NVDA call, and megacap's own floor (3.77pp) means small effects
there are not reliably detectable in general.

## Differential test (Step 4)

Look-ahead predicts high-recall tiers (megacap, large) move MORE than
low-recall tiers (small_micro). Observed: megacap -1.54pp, large 0.00pp
(both essentially null), vs small_micro +8.33pp (largest raw magnitude,
but within its own 14.34pp floor, i.e., not reliably different from
noise). **This is neither the look-ahead-predicted differential pattern
(high-recall tiers moving more) nor a clean uniform pattern (mid moved
-6.67pp, unlike anything else) -- the movements are scattered across
tiers with no tier exceeding its own noise floor except possibly mid,
which fails its own MDE check.** The differential test is **inconclusive**
by the prompt's own stated fallback rule ("if the small/micro delta is
within its own floor, say the differential test is inconclusive").

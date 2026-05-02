# Trend Layer — Design Sketch

Status: PROPOSAL (not yet implemented). Drafted April 2026 after the
v5→v8 prompt iteration showed that the credibility-signal-to-action
gap cannot be closed at the single-transcript level. See
EVALUATION_PROMPT.md header comment for iteration history.

## 1. Purpose

Detect quarter-over-quarter deterioration (or improvement) in a
portfolio ticker that individual transcript evaluations miss because
each call is scored in isolation. Encodes the "water the flowers,
trim the weeds" principle as a mechanical rule operating on the
structured-score history, not on fresh transcript reading.

Worked example motivating this layer — TTD 2025-11-06, which v6
correctly scored as Strengthening + No stumble → Add and the stock
then fell 43%. Looking at TTD's four prior structured scores in
sequence, the recommendedSize fell from 52 → 52 → 52 → 45 and the
freshMoneyAllocation gap widened. The model, without prior-quarter
context, cannot see that its own conviction is eroding across
quarters. The trend layer is what sees that.

## 2. Placement in the Architecture

Per DESIGN_PRINCIPLES.md the flow is Layer 3 → Layer 2 → Layer 1
(find → classify → enforce). The trend layer sits between Layer 2
and Layer 1 as a subcomponent of the allocator's input stage — it
is NOT a new layer. It takes the per-call analyst score (Layer 2
output), looks up the same ticker's prior N scores from the
Analysis table, produces a trend verdict, and hands both the
latest score AND the trend verdict to the allocator.

The firewall is preserved:
- Trend layer inputs: structured scores only (no transcripts, no
  portfolio composition, no prices).
- Trend layer outputs: a trend verdict struct. Not a trade
  recommendation. The allocator still owns the final action.

## 3. Data Contract

**Input** — last N analyses for a single ticker, pulled from the
Analysis table (`prisma/schema.prisma` already persists every field
needed). Chronological order, oldest to newest. N = 4 by default,
minimum of 3 required to produce a verdict. If fewer than 3
analyses exist, the trend layer returns `null` and the allocator
falls through to per-call logic alone.

Fields read per analysis (all already persisted):
- callDate
- thesisHealth (Strengthening | Intact | Weakening | Broken)
- recommendation (Add | Hold | Trim | Exit)
- recommendedSize (number %)
- freshMoneyAllocation (number %)
- credibilityDelta (positive | neutral | negative)
- mitigationCapabilityTrackRecord (strong | mixed | weak | unproven)
- stumbleType (None | Discovery | Execution | Structural)

**Output** — a single verdict struct:
```
{
  trajectory:          "improving" | "stable" | "flattening" | "softening" | "deteriorating",
  consecutiveSoftQ:    int   // consecutive quarters with any soft signal, latest-backward
  convictionDelta:     number // recommendedSize latest minus 3 quarters ago
  gapDelta:            number // (size - fresh) latest minus (size - fresh) 3 quarters ago
  thesisScoreDelta:    int    // encoded thesis: Strengthening=+2 Intact=0 Weakening=-2 Broken=-4, latest - oldest
  suggestedOverride:   null | "upgrade_one" | "downgrade_one" | "trim_regardless"
  rationale:           string // 1-2 sentences explaining which signals fired
}
```

The five trajectories are distinct states, not a linear spectrum:

- **improving**: conviction rising, gap narrowing — flowers
- **stable**: no meaningful change across 3+ quarters — hold
- **flattening**: Strengthening steps down to Intact and holds there;
  no other soft signals fire. Growth curve is maturing, not
  deteriorating. Action is conditional on Layer 3 opportunity cost.
- **softening**: one or two soft signals fire in the latest quarter
  after a stable history — early warning, not yet actionable on its own
- **deteriorating**: sustained pattern of soft signals (§5 rules) —
  weeds

## 4. Signal Definitions

A quarter is "soft" if any of the following is true when comparing
it to the immediately prior quarter's analysis:

**S1 — Conviction erosion:** recommendedSize drops by ≥ 3
percentage points.

**S2 — Gap widening:** freshMoneyAllocation gap (recommendedSize −
freshMoneyAllocation) widens by ≥ 2 percentage points.

**S3 — Credibility inflection:** credibilityDelta goes from
positive or neutral to negative.

**S4 — Mitigation erosion:** mitigationCapabilityTrackRecord
weakens (strong → mixed, mixed → weak, etc.).

A single signal firing is "soft." Two or more firing in the same
quarter is "sharp."

**Note on thesis step-downs:** Intact → Weakening and any step
into Weakening or Broken are deliberately NOT a soft signal here.
The graduated exit ratchet in CLAUDE.md already fires on explicit
Weakening classifications — adding a parallel trigger would
double-count. The trend layer's job is to catch softening *inside*
the Strengthening/Intact band, before the analyst itself scores
Weakening.

**Strengthening → Intact is not deterioration.** A business
maturing from hypergrowth to steady growth is a compounder, not a
weed. This transition alone (with no S1–S4 signals firing)
produces a `flattening` trajectory, handled per §5/§6 as
conditional on Layer 3 opportunity cost — not as an automatic
downgrade.

## 5. Trajectory Classification

Rules applied in order, first match wins:

1. thesisHealth is Weakening or Broken in the latest analysis →
   `trajectory = deteriorating`, `suggestedOverride = null`.
   The existing graduated exit ratchet in CLAUDE.md already fires
   on explicit Weakening; the trend layer defers entirely to
   avoid double-counting.

2. Three consecutive soft quarters, each firing at least one
   S1–S4 signal → `trajectory = deteriorating`,
   `suggestedOverride = trim_regardless`.

3. Two consecutive soft quarters, with the latest quarter being
   sharp (2+ signals) → `trajectory = deteriorating`,
   `suggestedOverride = trim_regardless`.

4. Two consecutive soft quarters, latest not sharp →
   `trajectory = softening`, `suggestedOverride = downgrade_one`.

5. Latest quarter soft, prior quarters not → `trajectory =
   softening`, `suggestedOverride = null`. Too early to act;
   record the yellow flag and wait for next quarter.

6. Latest thesisHealth is Intact AND the most recent prior
   Strengthening quarter is within the last 2 quarters AND no
   S1–S4 signals fire in the latest quarter → `trajectory =
   flattening`, `suggestedOverride = null`. The allocator will
   decide whether to hold or rotate based on Layer 3 opportunity
   cost (§6).

7. recommendedSize up ≥ 3pp AND freshMoneyAllocation gap
   narrowed (or stayed at zero) AND no S3/S4 signals fire →
   `trajectory = improving`. If this holds for two consecutive
   quarters, `suggestedOverride = upgrade_one`; if only one
   quarter, `suggestedOverride = null`.

8. Otherwise → `trajectory = stable`.

Rationale for the "2 soft + sharp → act" rule: on a single
quarter being sharp, the analyst probably already captured the
severity in its own recommendation. Waiting for the second
consecutive soft quarter is what makes this a trend signal rather
than a one-call reaction.

Rationale for requiring two consecutive improving quarters
before upgrading: same asymmetry the other way would be noise
on a single good quarter. Flowers need consistent growth before
we reach for more water.

## 6. Allocator Integration

The allocator reads (per-call recommendation, trend verdict) and
combines them per this matrix:

| Per-call Rec | Trend          | Final Action                              |
|--------------|----------------|-------------------------------------------|
| Exit         | any            | Exit                                      |
| Trim         | any            | Trim                                      |
| Hold         | deteriorating  | Trim (override)                           |
| Hold         | softening      | Hold; flag for next Q                     |
| Hold         | flattening     | See Layer 3 rotation check below          |
| Hold         | stable         | Hold                                      |
| Hold         | improving      | Add up to per-call cap (override up)      |
| Add          | deteriorating  | Hold (override, freeze adds)              |
| Add          | softening      | Hold (override)                           |
| Add          | flattening     | Hold; see Layer 3 rotation check          |
| Add          | stable         | Add                                       |
| Add          | improving      | Add, target tightens toward per-call cap  |

The matrix is symmetric: trends can raise conviction as well as
lower it, but never past the per-call `recommendedSize`. That cap
is the Layer-2 analyst's ceiling and Layer 1 respects it — the
trend layer only changes how aggressively we approach the cap,
not where the cap sits.

A single hard asymmetry remains: overrides never flip a Trim or
Exit into a Hold. If the per-call analyst says get out, the trend
layer cannot talk them back in — their window of information is
fresher.

**Layer 3 rotation check (for `flattening` trajectory):**
When the trend is flattening and Layer 3's Radar Inbox contains
a candidate with higher conviction signals than this ticker's
current Intact score, the allocator recommends rotating capital
from the flattener to the new candidate. If no rotation target
exists, Hold. Concretely:
- No Layer 3 yet → Hold by default (current state, April 2026).
- Layer 3 exists and has a higher-conviction candidate → Trim
  flattener by 10pp, redeploy into candidate.
- Layer 3 exists but no better candidate → Hold.

This is the one place in the design where Layer 3 is a real
input to Layer 1 for a portfolio ticker — because flattening is
the only state where the opportunity cost is the relevant
question, not the ticker's own fundamentals.

When `suggestedOverride = trim_regardless`, the allocator
executes the Trim branch and passes the trend rationale to the
tax-cost calculation so the user sees why.

## 7. Backtest Validation Plan

Before wiring the trend layer into live use, validate it on the
same 15-call ENPH+TTD corpus that has been iterated against:

Step 1. For each ticker, run the v6 evaluator on every historical
transcript in order. Persist the structured scores.

Step 2. Feed the score history into the trend layer per-quarter
(at each call, the trend layer sees only the scores available up
to and including that call — no look-ahead).

Step 3. Apply the matrix in §6 to produce a "final action" for
each call. Compute signal accuracy vs the same 90-day relative
return rubric used today.

Step 4. Compare against v6 baseline 9/15. If improvement is
marginal or negative, tune thresholds (3pp → 2pp, etc.) and
re-run. If a specific threshold choice overfits to 2 calls,
abandon it — 15 calls is not statistically powerful enough to
justify narrow rules.

Step 5. If the layer survives this validation, expand to all 48
dumped transcripts (AAPL, AMPX, ENPH, EOSE, SPWR, TSLA, TTD) for
a broader sanity check before any database or API integration.

## 8. Implementation Shape

Deferred until §7 validates. When built, expected location:
`analysis/trend_analyst.py` for the backtest version (reads from
`data/evals/` or a merged CSV, produces trend verdicts, feeds a
dry-run allocator). The production version would live in
`server/lib/trend.ts` and read from the Analysis table directly,
producing a verdict that the allocator surfaces alongside each
portfolio-ticker row on the Dashboard.

No new database schema. Every field needed is already on Analysis.

## 9. What This Is Not

Not an analyst replacement. Not a retraining loop. Not a
sentiment tracker. Not a factor model.

It is a purely mechanical check that reads the analyst's own
confidence trajectory and applies the graduated-exit logic in
§5/§6 of DESIGN_PRINCIPLES.md to signals finer than categorical
thesis-health steps. It is the "water the flowers, trim the
weeds" heuristic made executable from structured data.

## 10. Open Questions

- Does the trend layer apply to Type A and Type B equally, or
  should the thresholds differ given Type B has wider cap ranges
  (40-60%) and therefore more room for noise? Proposal: same
  thresholds; revisit if Type B specifically over-fires in the
  backtest.

- Strengthening → Intact is not a soft signal per §4 (treated as
  `flattening`, not `softening`). This means the trend layer
  will likely NOT catch TTD 2025-11-06 on its own (that call was
  Strengthening + size dropping from 52→45; S1 might fire on
  the 7pp size drop alone). If it doesn't, that miss is accepted
  as the cost of Luis's principle: we don't trim a mature
  compounder just because growth stops accelerating. Rotation
  out of flatteners is the Layer 3 concern.

- When the existing graduated exit ratchet fires (explicit
  Weakening ratchet tranche 1, 2, 3), does the trend layer add
  anything or defer entirely? Current §5 rule 1 defers. Revisit
  if the backtest shows cases the ratchet misses but the trend
  layer catches.

- Upgrade asymmetry: the matrix allows Hold → Add on two
  consecutive improving quarters but NOT Trim → Hold on any
  positive trend. The per-call Trim is treated as a harder floor
  than the per-call Add. Is that the right asymmetry, or should
  improving trends also soften a Trim call? Current answer: keep
  the asymmetry. A Trim recommendation means the analyst saw
  fresh transcript-level evidence of a problem the trend layer
  can't see. Revisit if the backtest shows Trims that were
  clearly overreactions a trend could have dampened.

/**
 * trendAnalyst.js — JS port of analysis/trend_analyst.py's pure verdict /
 * matrix / confidence functions.
 *
 * Why this exists: server/routes/save.js needs to compute a trend verdict
 * for the newly-saved Analysis row at save time (Stage 3 of the trend-layer
 * operationalization — see docs/CoWork_handoff_2026-06-14e.md). Railway's
 * nixpacks build is Node-only (no Python at runtime), so a Python subprocess
 * isn't viable. This file is a faithful line-by-line port of the
 * trajectory-classification (§5) and allocator-matrix (§6) logic in
 * analysis/trend_analyst.py.
 *
 * SINGLE SOURCE OF TRUTH RISK: this duplicates logic that also lives in
 * analysis/trend_analyst.py (used by analysis/sync_trend_to_db.py for the
 * tier-classifier cron and full-history backfills). The two implementations
 * MUST stay in sync. Enforcement: analysis/data/trend_verdict_fixtures.json
 * is a shared fixture set (derived from trend_analyst.py's self-tests) run
 * against BOTH implementations —
 *   - Python:  python3 analysis/test_trend_fixtures.py
 *   - Node:    node server/lib/trendAnalyst.fixtures.test.js
 * Any change to the verdict/matrix/confidence rules must be made in BOTH
 * files and must keep both fixture runners green.
 *
 * NOT ported: build_tier_function (3-axis speculative/established
 * classifier). That requires price_cache.json / fundamentals_cache.json,
 * which are laptop-only artifacts. save.js reads the tier from
 * Ticker.tierOverride ?? Ticker.tierMechanical ?? 'established' instead of
 * recomputing it — tier reclassification stays a separate (deferred) cron.
 *
 * Field naming: input history rows use the same snake_case keys as
 * trend_analyst.py's expected schema (thesis_health, recommended_size,
 * fresh_money_allocation, credibility_delta, mitigation_track_record) so the
 * shared JSON fixtures can be consumed unchanged by both implementations.
 * Callers (save.js) are responsible for mapping Prisma's camelCase Analysis
 * fields to this shape.
 */

'use strict';

// ---------------------------------------------------------------------------
// Encoders for categorical fields
// ---------------------------------------------------------------------------

const THESIS_SCORE = {
  Strengthening: 2,
  Intact: 0,
  Weakening: -2,
  Broken: -4,
};

const MITIGATION_SCORE = {
  strong: 3,
  mixed: 2,
  weak: 1,
  unproven: 0,
  null: 0,
  '': 0,
};

const CREDIBILITY_SCORE = {
  positive: 1,
  neutral: 0,
  negative: -1,
  null: 0,
  '': 0,
};

function encodeThesis(value) {
  return THESIS_SCORE[value] ?? 0;
}

function encodeMitigation(value) {
  if (value === null || value === undefined) return 0;
  return MITIGATION_SCORE[value] ?? 0;
}

function encodeCredibility(value) {
  if (value === null || value === undefined) return 0;
  return CREDIBILITY_SCORE[value] ?? 0;
}

function toFloat(value, defaultValue = null) {
  if (value === null || value === undefined || value === '') return defaultValue;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isNaN(n) ? defaultValue : n;
}

// ---------------------------------------------------------------------------
// Quarter-to-quarter signal detection (TREND_LAYER.md §4)
// ---------------------------------------------------------------------------

/** Returns the list of soft-signal codes (S1-S4) that fire moving prev -> curr. */
function detectSoftSignals(prev, curr) {
  const fired = [];

  // S1 — Conviction erosion: recommendedSize drops by >= 3pp
  const prevSize = toFloat(prev.recommended_size);
  const currSize = toFloat(curr.recommended_size);
  if (prevSize !== null && currSize !== null) {
    if (prevSize - currSize >= 3) fired.push('S1_conviction_erosion');
  }

  // S2 — Gap widening: (size - fresh) widens by >= 2pp
  const prevFresh = toFloat(prev.fresh_money_allocation);
  const currFresh = toFloat(curr.fresh_money_allocation);
  if (prevSize !== null && prevFresh !== null && currSize !== null && currFresh !== null) {
    const prevGap = prevSize - prevFresh;
    const currGap = currSize - currFresh;
    if (currGap - prevGap >= 2) fired.push('S2_gap_widening');
  }

  // S3 — Credibility inflection: pos/neutral -> negative
  const prevCred = prev.credibility_delta;
  const currCred = curr.credibility_delta;
  if (currCred === 'negative'
      && (prevCred === 'positive' || prevCred === 'neutral' || prevCred === null || prevCred === undefined || prevCred === '')) {
    fired.push('S3_credibility_negative');
  }

  // S4 — Mitigation erosion. Only count when both sides have a real value and
  // there is a drop.
  const NULLISH = [null, undefined, '', 'null'];
  const prevMtrRaw = prev.mitigation_track_record;
  const currMtrRaw = curr.mitigation_track_record;
  if (!NULLISH.includes(prevMtrRaw) && !NULLISH.includes(currMtrRaw)) {
    const prevMtr = encodeMitigation(prevMtrRaw);
    const currMtr = encodeMitigation(currMtrRaw);
    if (currMtr < prevMtr) fired.push('S4_mitigation_erosion');
  }

  return fired;
}

const SIGNAL_PROSE = {
  S1_conviction_erosion: 'the analyst lowered recommended size by 3+ percentage points',
  S2_gap_widening: 'the gap between recommended size and fresh-money allocation widened by 2+ points (analyst getting more cautious about new buying)',
  S3_credibility_negative: 'credibility flipped to negative this quarter',
  S4_mitigation_erosion: 'the mitigation track record (whether management has historically delivered on this kind of headwind) got weaker',
};

/** Turn ['S1_conviction_erosion', 'S2_gap_widening'] into a readable English clause. */
function humanizeSignals(signals) {
  if (!signals || signals.length === 0) return 'no signals';
  const parts = [...new Set(signals)].sort().map(s => SIGNAL_PROSE[s] ?? s);
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]}; and ${parts[1]}`;
  return `${parts.slice(0, -1).join('; ')}; and ${parts[parts.length - 1]}`;
}

/**
 * Classify a single quarter's signals relative to the prior quarter.
 * Returns { signals, soft, sharp }. A quarter with no prior comparable data
 * is "unknown" — never soft.
 */
function classifyQuarter(prev, curr) {
  if (prev === null || prev === undefined) {
    return { signals: [], soft: false, sharp: false };
  }
  const signals = detectSoftSignals(prev, curr);
  return { signals, soft: signals.length >= 1, sharp: signals.length >= 2 };
}

/** Count how many latest-backward quarters were soft. */
function consecutiveSoft(history) {
  let n = 0;
  for (let i = history.length - 1; i > 0; i--) {
    const cls = classifyQuarter(history[i - 1], history[i]);
    if (cls.soft) n += 1;
    else break;
  }
  return n;
}

function round2(x) {
  return Math.round((x + Number.EPSILON) * 100) / 100;
}

function makeVerdict(trajectory, consecutiveSoftQ, convictionDelta, gapDelta, thesisScoreDelta, suggestedOverride, rationale) {
  return {
    trajectory,
    consecutive_soft_q: consecutiveSoftQ,
    conviction_delta: round2(convictionDelta),
    gap_delta: round2(gapDelta),
    thesis_score_delta: thesisScoreDelta,
    suggested_override: suggestedOverride,
    rationale,
  };
}

// ---------------------------------------------------------------------------
// Trajectory classification (TREND_LAYER.md §5)
// ---------------------------------------------------------------------------

/**
 * Given a list of per-call analyses for ONE ticker, chronological (oldest
 * first), produce a trend verdict for the LATEST entry.
 *
 * `tier`: "speculative" or "established" (default).
 *   - speculative: Rule 7 fires upgrade_one on a single improving quarter.
 *   - established: Rule 7 requires two consecutive improving quarters.
 *   Hard-signal blocks (S3/S4) apply uniformly across tiers. Downside rules
 *   (1-6) are tier-invariant.
 *
 * Returns null if history has fewer than 3 entries (not enough data).
 */
function computeTrendVerdict(history, tier = 'established') {
  if (history.length < 3) return null;

  const curr = history[history.length - 1];
  const prev = history[history.length - 2];
  const prev2 = history[history.length - 3];

  const currCls = classifyQuarter(prev, curr);
  const prevCls = classifyQuarter(prev2, prev);
  const prev2Cls = classifyQuarter(history.length >= 4 ? history[history.length - 4] : null, prev2);

  const oldest = history.length >= 4 ? history[history.length - 4] : history[history.length - 3];
  const convictionDelta = toFloat(curr.recommended_size, 0.0) - toFloat(oldest.recommended_size, 0.0);
  const currGap = toFloat(curr.recommended_size, 0.0) - toFloat(curr.fresh_money_allocation, 0.0);
  const oldestGap = toFloat(oldest.recommended_size, 0.0) - toFloat(oldest.fresh_money_allocation, 0.0);
  const gapDelta = currGap - oldestGap;
  const thesisScoreDelta = encodeThesis(curr.thesis_health) - encodeThesis(oldest.thesis_health);

  // Rule 1 — defer to graduated exit ratchet on explicit Weakening/Broken
  if (curr.thesis_health === 'Weakening' || curr.thesis_health === 'Broken') {
    const health = curr.thesis_health;
    return makeVerdict(
      'deteriorating', consecutiveSoft(history), convictionDelta, gapDelta, thesisScoreDelta, null,
      `The analyst has already flagged the thesis as ${health} on this call, which is a more decisive signal than anything the trend layer would add. The downstream allocator's graduated exit ratchet (trim → trim more → exit over successive quarters of non-improvement) takes over from here, so the trend layer doesn't issue a separate override — it just confirms the deteriorating direction.`,
    );
  }

  // Rule 2 — three consecutive soft quarters
  if (currCls.soft && prevCls.soft && prev2Cls.soft) {
    const allSignals = new Set([...currCls.signals, ...prevCls.signals, ...prev2Cls.signals]);
    const hardSignalsPresent = allSignals.has('S3_credibility_negative') || allSignals.has('S4_mitigation_erosion');

    if (curr.thesis_health === 'Strengthening' && !hardSignalsPresent) {
      return makeVerdict(
        'softening', 3, convictionDelta, gapDelta, thesisScoreDelta, null,
        `For three quarters running, the analyst has tightened conviction or pulled back on fresh-money allocation (soft signals: ${humanizeSignals([...allSignals])}). Normally a streak this long would call for a trim, but the underlying thesis is still rated Strengthening and none of the harder warning signs (credibility break, mitigation track record erosion) have fired. On a Strengthening thesis, a soft-only streak usually reflects the analyst getting more disciplined on a winning name — sizing it more carefully — rather than the thesis itself deteriorating. The trend layer flags this as a watch item but doesn't override the per-call recommendation.`,
      );
    }
    return makeVerdict(
      'deteriorating', 3, convictionDelta, gapDelta, thesisScoreDelta, 'trim_regardless',
      `Three consecutive quarters of soft signals (${humanizeSignals([...allSignals])}). The analyst keeps tightening conviction or revealing mitigation/credibility weakness without ever flagging the thesis as Strengthening again — that's the pattern of a thesis quietly breaking down. The trend layer overrides any Hold to Trim and freezes any Add.`,
    );
  }

  // Rule 3 — two consecutive soft, latest sharp
  if (currCls.sharp && prevCls.soft) {
    return makeVerdict(
      'deteriorating', 2, convictionDelta, gapDelta, thesisScoreDelta, 'trim_regardless',
      `The previous quarter showed soft signals (analyst getting more cautious), and this quarter the picture got worse — two or more concerns fired at once (${humanizeSignals(currCls.signals)}). At least one of those is a hard signal (credibility breaking down or mitigation track record eroding), which means the deterioration isn't just noise. The trend layer overrides to a trim regardless of what the per-call rec says.`,
    );
  }

  // Rule 4 — two consecutive soft, latest mild
  if (currCls.soft && prevCls.soft) {
    if (curr.thesis_health === 'Strengthening') {
      return makeVerdict(
        'softening', 2, convictionDelta, gapDelta, thesisScoreDelta, null,
        `The analyst has shown two quarters of soft signals (${humanizeSignals(currCls.signals)}) — typically this would prompt the trend layer to step the recommendation down one notch. But the underlying thesis is still rated Strengthening, which means the position is fundamentally working. On rising-conviction calls, mild soft signals usually reflect the analyst sizing the position more disciplinedly rather than the thesis breaking. The trend layer flags this as a watch item but keeps the per-call rec in place.`,
      );
    }
    return makeVerdict(
      'softening', 2, convictionDelta, gapDelta, thesisScoreDelta, 'downgrade_one',
      `Two consecutive quarters of soft signals (${humanizeSignals(currCls.signals)}) on a thesis that's no longer rated Strengthening. The analyst keeps becoming more cautious — tightening conviction or pulling back on fresh money — and the underlying thesis hasn't re-strengthened to compensate. The trend layer steps the recommendation down one notch (Add → Hold, or Hold → Trim) to reflect the directional drift.`,
    );
  }

  // Rule 5 — latest soft, priors not
  if (currCls.soft && !prevCls.soft) {
    return makeVerdict(
      'softening', 1, convictionDelta, gapDelta, thesisScoreDelta, null,
      `This quarter showed a single soft signal (${humanizeSignals(currCls.signals)}) but the prior quarter was clean. One isolated quarter of softness isn't enough to act on — could just be the analyst tuning position size on a strong call. The trend layer flags it to monitor; if next quarter also comes in soft, the two-soft rule will kick in and we'll consider stepping the recommendation down.`,
    );
  }

  // Rule 6 — flattening: Strengthening -> Intact with no S1-S4 firing
  const currThesis = curr.thesis_health;
  const prevThesis = prev.thesis_health;
  const prev2Thesis = prev2.thesis_health;
  const recentStrengthening = prevThesis === 'Strengthening' || prev2Thesis === 'Strengthening';
  if (currThesis === 'Intact' && recentStrengthening && !currCls.soft) {
    return makeVerdict(
      'flattening', 0, convictionDelta, gapDelta, thesisScoreDelta, null,
      "The thesis just stepped down from Strengthening to Intact, with none of the soft warning signs firing — typical of a growth name maturing into a steady-state cash generator. It's not deteriorating, but the upside is no longer compounding the way it was. The trend layer doesn't automatically act on this: the right call depends on whether there's a higher-conviction candidate to rotate into, which is a Layer 3 (opportunity scanner) decision we haven't built yet. Until then, treat this as a 'on deck for review' signal.",
    );
  }

  // Rule 7 — improving
  let sizeUp = false;
  const prevSizeForUp = toFloat(prev.recommended_size);
  if (prevSizeForUp) {
    const currSizeForUp = toFloat(curr.recommended_size);
    if (currSizeForUp) {
      sizeUp = (currSizeForUp - prevSizeForUp) >= 3;
    }
  }
  const currGapSingle = toFloat(curr.recommended_size, 0.0) - toFloat(curr.fresh_money_allocation, 0.0);
  const prevGapSingle = toFloat(prev.recommended_size, 0.0) - toFloat(prev.fresh_money_allocation, 0.0);
  const gapNarrowed = currGapSingle <= prevGapSingle;
  const noCredOrMtrDrop = !(currCls.signals.includes('S3_credibility_negative') || currCls.signals.includes('S4_mitigation_erosion'));
  const currImproving = sizeUp && gapNarrowed && noCredOrMtrDrop;

  // Two consecutive improving quarters → upgrade
  let prevSizeUp = false;
  const prev2SizeForUp = toFloat(prev2.recommended_size);
  if (prev2SizeForUp) {
    const prevSizeForUp2 = toFloat(prev.recommended_size);
    if (prevSizeForUp2) {
      prevSizeUp = (prevSizeForUp2 - prev2SizeForUp) >= 3;
    }
  }
  const prevGapNarrowed = (toFloat(prev.recommended_size, 0.0) - toFloat(prev.fresh_money_allocation, 0.0))
    <= (toFloat(prev2.recommended_size, 0.0) - toFloat(prev2.fresh_money_allocation, 0.0));
  const prevImproving = prevSizeUp && prevGapNarrowed;

  if (currImproving && prevImproving) {
    return makeVerdict(
      'improving', 0, convictionDelta, gapDelta, thesisScoreDelta, 'upgrade_one',
      'Two quarters in a row of strengthening conviction — the analyst keeps raising recommended size while keeping the fresh-money gap tight, with no credibility or mitigation concerns appearing. That\'s a clean inflection signal across multiple periods, not a one-off. The trend layer steps the recommendation up one notch (Hold → Add).',
    );
  }
  if (currImproving) {
    // Speculative tier: a single improving quarter is enough for upgrade_one.
    if (tier === 'speculative') {
      return makeVerdict(
        'improving', 0, convictionDelta, gapDelta, thesisScoreDelta, 'upgrade_one',
        'The analyst stepped conviction up this quarter (higher recommended size, fresh-money gap not widening, no credibility or mitigation concerns). On a speculative ticker (small-cap, volatile, or pre-revenue), waiting for a second confirming quarter often means missing the inflection — these names move fast. The trend layer steps the recommendation up one notch now (Hold → Add) rather than waiting.',
      );
    }
    return makeVerdict(
      'improving', 0, convictionDelta, gapDelta, thesisScoreDelta, null,
      'The analyst stepped conviction up this quarter (higher recommended size, fresh-money gap not widening, no credibility or mitigation concerns). On an established ticker we wait for a second confirming quarter before stepping the recommendation up — one strong quarter on a mature name can be noise. Watch this; if next quarter also comes in improving, the trend layer will upgrade.',
    );
  }

  // Rule 8 — stable
  return makeVerdict(
    'stable', 0, convictionDelta, gapDelta, thesisScoreDelta, null,
    'Recent quarters look broadly consistent — conviction holding, no soft signals firing, no improving inflection either. Nothing for the trend layer to act on; the per-call recommendation passes through unchanged.',
  );
}

// ---------------------------------------------------------------------------
// Allocator matrix (TREND_LAYER.md §6)
// ---------------------------------------------------------------------------

/**
 * Apply the §6 matrix, return [finalAction, rationale].
 *
 * Key rule: the matrix acts on verdict.suggested_override, not on
 * verdict.trajectory alone. A trajectory classification without an override
 * is advisory only — the per-call recommendation passes through.
 *
 * `layer3RotationTarget` reserved for future Layer 3 integration — default
 * false means "no rotation target", which leaves flatteners alone.
 */
function applyMatrix(perCallRec, verdict, layer3RotationTarget = false) {
  if (verdict === null || verdict === undefined) {
    return [perCallRec, 'No trend verdict yet — this ticker has fewer than three prior calls in its history, which is the minimum the trend layer needs to evaluate a trajectory. Comes online once a third call lands.'];
  }

  const trajectory = verdict.trajectory;
  const override = verdict.suggested_override;
  const rationale = verdict.rationale || '';

  // Exit and Trim are floors — trend never flips them up.
  if (perCallRec === 'Exit') {
    return ['Exit', `The per-call recommendation is Exit — the trend layer never upgrades a per-call Exit (the analyst's conviction has already capitulated). Trend layer's view of the trajectory: ${rationale}`];
  }
  if (perCallRec === 'Trim') {
    return ['Trim', `The per-call recommendation is Trim — the trend layer never upgrades a per-call Trim (we don't second-guess the analyst's deterioration call upward). Trend layer's view: ${rationale}`];
  }

  // Flattening + Layer 3 rotation is the one trajectory-driven override that
  // stands alone (rotation opportunity cost, not trend deterioration).
  if (trajectory === 'flattening' && layer3RotationTarget) {
    if (perCallRec === 'Hold') {
      return ['Trim', `The thesis is flattening AND Layer 3 surfaced a higher-conviction candidate — rotating from a maturing name to a rising one. ${rationale}`];
    }
    if (perCallRec === 'Add') {
      return ['Hold', `The thesis is flattening AND Layer 3 surfaced a higher-conviction candidate — don't add fresh money to the flattening name; let it ride. ${rationale}`];
    }
  }

  // For Hold and Add, the verbose verdict rationale already explains both the
  // trajectory and whether/why the override fires.
  if (perCallRec === 'Hold' || perCallRec === 'Add') {
    if (override === 'trim_regardless') {
      return [perCallRec === 'Hold' ? 'Trim' : 'Hold', rationale];
    }
    if (override === 'downgrade_one') {
      return [perCallRec === 'Hold' ? 'Trim' : 'Hold', rationale];
    }
    if (override === 'upgrade_one') {
      // On Hold this becomes Add. On Add it's a no-op.
      return ['Add', rationale];
    }
    // No override — pass through.
    return [perCallRec, rationale];
  }

  // Unknown per-call rec — surface what we have plus a note.
  return [perCallRec, `Per-call recommendation '${perCallRec}' wasn't one of the expected values (Add/Hold/Trim/Exit), so the trend layer passes it through unchanged. Trend layer's view: ${rationale}`];
}

// ---------------------------------------------------------------------------
// Three-state confidence flag
// ---------------------------------------------------------------------------

/**
 * Three-state confidence on the final action:
 * - "unknown": insufficient history (no verdict)
 * - "advisory": trend layer saw a non-stable trajectory but did not override
 * - "confident": either an override fired, OR trajectory is stable
 */
function computeFinalConfidence(verdict, perCallRec, finalAction) {
  if (verdict === null || verdict === undefined) return 'unknown';
  const trajectory = verdict.trajectory ?? 'stable';
  const override = verdict.suggested_override;
  if (trajectory === 'stable' || trajectory === 'unknown') return 'confident';
  if (override !== null && override !== undefined && finalAction !== perCallRec) return 'confident';
  return 'advisory';
}

module.exports = {
  encodeThesis,
  encodeMitigation,
  encodeCredibility,
  toFloat,
  detectSoftSignals,
  humanizeSignals,
  classifyQuarter,
  consecutiveSoft,
  computeTrendVerdict,
  applyMatrix,
  computeFinalConfidence,
};

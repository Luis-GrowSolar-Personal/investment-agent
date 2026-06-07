/**
 * moves.js — Recommended Moves engine (Layer 1 allocator output)
 *
 * Produces a per-owner action plan:
 *   - Specific trim/exit amounts per account with tax routing
 *   - Add amounts for under-target portfolio positions
 *   - Watchlist promotion candidates ranked by signal quality
 *   - Capital flow plan: freed capital → destination
 *   - Structural warnings (barbell, position count, 48h, enough number)
 *
 * Analyst/Allocator firewall preserved:
 *   analyst scores only — no transcript text passes through here.
 *
 *   GET  /api/moves              list owners with pending move counts
 *   GET  /api/moves/:owner       full recommended moves for one owner
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_LTCG_RATE   = 0.15;
const DEFAULT_STCG_RATE   = 0.15;
const LTCG_HOLD_DAYS      = 365;
const DEFAULT_CASH_RESERVE = 0.05;   // 5% dry powder floor
const DEFAULT_EST_RATIO   = 0.60;    // 60% established / 40% speculative
const DEFAULT_MAX_POS     = 15;
const DEFAULT_MIN_POS_USD = 1500;

// ─── Tax helpers ──────────────────────────────────────────────────────────────

function daysBetween(a, b) {
  return Math.abs(b - a) / (1000 * 60 * 60 * 24);
}

/**
 * FIFO lot tax computation.
 * Returns { taxCost, ltGain, stGain }.
 * Tax-advantaged accounts always return zeroes.
 */
function computeTrimTax(lots, sharesToSell, currentPrice, ltcgRate, stcgRate, isTaxAdvantaged) {
  if (isTaxAdvantaged) return { taxCost: 0, ltGain: 0, stGain: 0 };

  const now    = new Date();
  const sorted = [...lots]
    .filter(l => !l.closedDate)
    .sort((a, b) => new Date(a.acquiredDate) - new Date(b.acquiredDate));

  let remaining = sharesToSell;
  let ltGain    = 0;
  let stGain    = 0;

  for (const lot of sorted) {
    if (remaining <= 0) break;
    const sell  = Math.min(remaining, lot.shares);
    const gain  = sell * (currentPrice - lot.costBasis);
    const isLT  = daysBetween(new Date(lot.acquiredDate), now) >= LTCG_HOLD_DAYS;
    if (isLT) ltGain += gain; else stGain += gain;
    remaining  -= sell;
  }

  return {
    taxCost: ltGain * ltcgRate + stGain * stcgRate,
    ltGain,
    stGain,
  };
}

// ─── Trim routing ─────────────────────────────────────────────────────────────

/**
 * Given a list of positions across accounts and the number of shares to sell,
 * distribute the sell across accounts — tax-advantaged first — and compute
 * tax per account.
 *
 * Returns an array of per-account routing rows sorted sell-priority first.
 */
function buildTrimRouting(positions, sharesToSell, defaultLtcg, defaultStcg) {
  // Sort: tax-advantaged (IRA/Roth) first
  const sorted = [...positions].sort((a, b) => {
    const ta = t => ['ira', 'roth'].includes(t?.type);
    if (ta(a.account) && !ta(b.account)) return -1;
    if (!ta(a.account) && ta(b.account)) return  1;
    return 0;
  });

  let remaining = sharesToSell;
  const rows    = [];

  for (const pos of sorted) {
    if (remaining <= 0) break;
    const openLots    = (pos.lots || []).filter(l => !l.closedDate);
    const posShares   = openLots.reduce((s, l) => s + l.shares, 0);
    if (posShares <= 0) continue;

    const sell        = Math.min(remaining, posShares);
    const price       = pos.lastPrice ?? 0;
    const isTaxAdv    = ['ira', 'roth'].includes(pos.account?.type);
    const ltcg        = pos.account?.ltcgRate ?? defaultLtcg;
    const stcg        = pos.account?.stcgRate ?? defaultStcg;
    const tax         = computeTrimTax(openLots, sell, price, ltcg, stcg, isTaxAdv);

    rows.push({
      accountId:       pos.accountId,
      accountName:     pos.account?.name   ?? '—',
      accountType:     pos.account?.type   ?? '—',
      isTaxAdvantaged: isTaxAdv,
      sharesToSell:    +sell.toFixed(4),
      dollarAmount:    +(sell * price).toFixed(2),
      taxCost:         +tax.taxCost.toFixed(2),
      ltGain:          +tax.ltGain.toFixed(2),
      stGain:          +tax.stGain.toFixed(2),
    });
    remaining -= sell;
  }

  return rows;
}

// ─── Watchlist candidate scoring ─────────────────────────────────────────────

const TRAJECTORY_SCORE = {
  improving:     5,
  stable:        3,
  flattening:    2,
  softening:     1,
  deteriorating: 0,
  unknown:       0,
};
const HEALTH_SCORE = {
  Strengthening: 4,
  Intact:        3,
  Weakening:     1,
  Broken:        0,
};
const ACTION_SCORE = {
  Add:  3,
  Hold: 1,
  Trim: -2,
  Exit: -5,
};

function scoreCandidate(analysis, tickerType) {
  const traj   = TRAJECTORY_SCORE[analysis?.trajectory]   ?? 0;
  const health = HEALTH_SCORE[analysis?.thesisHealth]      ?? 0;
  const action = ACTION_SCORE[analysis?.finalAction || analysis?.recommendation] ?? 0;
  const type   = tickerType === 'B' ? 2 : 1;
  return traj + health + action + type;
}

// ─── Move generation ──────────────────────────────────────────────────────────

/**
 * Generates a list of moves for a single ticker position, sorted by priority.
 * Returns an array (usually 0 or 1 items, occasionally 2 for compound situations).
 */
function generateTickerMoves(
  ticker, positions, totalPortfolioValue,
  latestAnalysis, profile, ownerTaxRates
) {
  const now           = new Date();
  const specExitSpeed = profile.specExitSpeed ?? 'normal';

  // ── Position metrics ────────────────────────────────────────────────────────
  const openLots    = positions.flatMap(p => (p.lots || []).filter(l => !l.closedDate));
  const totalShares = openLots.reduce((s, l) => s + l.shares,                0);
  const totalCost   = openLots.reduce((s, l) => s + l.shares * l.costBasis,  0);

  // Use lastPrice from any position that has it
  const pricePos    = positions.find(p => p.lastPrice != null);
  const price       = pricePos?.lastPrice ?? (totalShares > 0 ? totalCost / totalShares : 0);
  const mktValue    = totalShares * price;
  const currentPct  = totalPortfolioValue > 0 ? (mktValue / totalPortfolioValue) * 100 : 0;

  // ── Cap enforcement ─────────────────────────────────────────────────────────
  const tickerCap   = ticker.capPercent ?? 100;
  const analystCap  = latestAnalysis?.capPercent ?? tickerCap;
  const hardCapPct  = Math.min(tickerCap, analystCap);

  // ── Analysis fields ─────────────────────────────────────────────────────────
  const thesisHealth    = latestAnalysis?.thesisHealth   ?? '—';
  const recommendation  = latestAnalysis?.recommendation ?? '—';
  const finalAction     = latestAnalysis?.finalAction    ?? recommendation;
  const trajectory      = latestAnalysis?.trajectory     ?? null;
  const ratchetTranche  = latestAnalysis?.ratchetTranche ?? 0;
  const recommendedSize = latestAnalysis?.recommendedSize ?? null;  // % of portfolio
  const tier            = ticker.tierOverride ?? latestAnalysis?.tier ?? null;

  const overCap = currentPct > hardCapPct + 0.5;

  // ── Effective action (specExitSpeed modifier) ───────────────────────────────
  // For speculative tickers, fast exit speed accelerates ratchet.
  let effectiveAction = finalAction;
  if (tier === 'speculative' && specExitSpeed === 'fast') {
    if (ratchetTranche >= 1 || trajectory === 'deteriorating') {
      effectiveAction = 'Exit';
    }
  }
  if (tier === 'speculative' && specExitSpeed === 'patient') {
    // Patient: don't trim on ratchet 1-2 unless over cap
    if (ratchetTranche <= 2 && !overCap && effectiveAction === 'Trim') {
      effectiveAction = 'Hold';
    }
  }

  const moves = [];

  // ── EXIT ───────────────────────────────────────────────────────────────────
  if (effectiveAction === 'Exit' || ratchetTranche >= 3) {
    const routing  = buildTrimRouting(positions, totalShares, ownerTaxRates.ltcg, ownerTaxRates.stcg);
    const taxTotal = routing.reduce((s, r) => s + r.taxCost, 0);

    moves.push({
      moveType:    'EXIT',
      priority:    1,
      symbol:      ticker.symbol,
      shortName:   ticker.shortName ?? ticker.name,
      reason:      ratchetTranche >= 3
        ? `Ratchet tranche ${ratchetTranche} — graduated exit complete`
        : `Thesis ${thesisHealth.toLowerCase()}; exit signal confirmed`,
      thesisHealth,
      finalAction: effectiveAction,
      trajectory,
      tier,
      ratchetTranche,
      currentPct:  +currentPct.toFixed(2),
      hardCapPct:  +hardCapPct.toFixed(1),
      currentMktValue: +mktValue.toFixed(2),
      dollarAmount:    +mktValue.toFixed(2),
      sharesApprox:    +totalShares.toFixed(3),
      taxCost:         +taxTotal.toFixed(2),
      netProceeds:     +(mktValue - taxTotal).toFixed(2),
      accounts:        routing,
    });

    return moves;
  }

  // ── TRIM (over cap) ────────────────────────────────────────────────────────
  if (overCap) {
    const targetValue  = totalPortfolioValue * (hardCapPct / 100);
    const excessValue  = mktValue - targetValue;
    const sharesToSell = price > 0 ? excessValue / price : 0;
    const routing      = buildTrimRouting(positions, sharesToSell, ownerTaxRates.ltcg, ownerTaxRates.stcg);
    const taxTotal     = routing.reduce((s, r) => s + r.taxCost, 0);

    moves.push({
      moveType:    'TRIM_CAP',
      priority:    2,
      symbol:      ticker.symbol,
      shortName:   ticker.shortName ?? ticker.name,
      reason:      `Position at ${currentPct.toFixed(1)}% exceeds ${hardCapPct.toFixed(0)}% cap (Type ${ticker.type})`,
      thesisHealth,
      finalAction: 'Trim',
      trajectory,
      tier,
      ratchetTranche,
      currentPct:  +currentPct.toFixed(2),
      hardCapPct:  +hardCapPct.toFixed(1),
      targetPct:   +hardCapPct.toFixed(1),
      currentMktValue: +mktValue.toFixed(2),
      dollarAmount:    +excessValue.toFixed(2),
      sharesApprox:    +sharesToSell.toFixed(3),
      taxCost:         +taxTotal.toFixed(2),
      netProceeds:     +(excessValue - taxTotal).toFixed(2),
      accounts:        routing,
    });
  }

  // ── TRIM (ratchet) ─────────────────────────────────────────────────────────
  if (ratchetTranche >= 1 && ratchetTranche < 3 && !overCap) {
    // Ratchet 1: trim to cap.  Ratchet 2: trim 40% of remaining position.
    let trimValue;
    if (ratchetTranche === 1) {
      const targetValue = totalPortfolioValue * (hardCapPct / 100);
      trimValue = Math.max(0, mktValue - targetValue);
    } else {
      trimValue = mktValue * 0.40;
    }

    if (trimValue > 100) {  // ignore trivial amounts
      const sharesToSell = price > 0 ? trimValue / price : 0;
      const routing      = buildTrimRouting(positions, sharesToSell, ownerTaxRates.ltcg, ownerTaxRates.stcg);
      const taxTotal     = routing.reduce((s, r) => s + r.taxCost, 0);

      moves.push({
        moveType:    'TRIM_RATCHET',
        priority:    3,
        symbol:      ticker.symbol,
        shortName:   ticker.shortName ?? ticker.name,
        reason:      ratchetTranche === 1
          ? `Thesis weakening — trim to ${hardCapPct.toFixed(0)}% cap`
          : `No improvement after Q2 — trim 40% of position (ratchet ${ratchetTranche})`,
        thesisHealth,
        finalAction: 'Trim',
        trajectory,
        tier,
        ratchetTranche,
        currentPct:  +currentPct.toFixed(2),
        hardCapPct:  +hardCapPct.toFixed(1),
        currentMktValue: +mktValue.toFixed(2),
        dollarAmount:    +trimValue.toFixed(2),
        sharesApprox:    +sharesToSell.toFixed(3),
        taxCost:         +taxTotal.toFixed(2),
        netProceeds:     +(trimValue - taxTotal).toFixed(2),
        accounts:        routing,
      });
    }
  }

  // ── TRIM (analyst signal, no cap violation, no ratchet) ───────────────────
  if (effectiveAction === 'Trim' && !overCap && ratchetTranche === 0) {
    // Trim to recommendedSize, or to 80% of current if no recommendation
    const targetPct   = recommendedSize != null
      ? Math.min(recommendedSize, hardCapPct)
      : currentPct * 0.80;
    const targetValue = totalPortfolioValue * (targetPct / 100);
    const trimValue   = Math.max(0, mktValue - targetValue);

    if (trimValue > 100) {
      const sharesToSell = price > 0 ? trimValue / price : 0;
      const routing      = buildTrimRouting(positions, sharesToSell, ownerTaxRates.ltcg, ownerTaxRates.stcg);
      const taxTotal     = routing.reduce((s, r) => s + r.taxCost, 0);

      moves.push({
        moveType:    'TRIM_SIGNAL',
        priority:    4,
        symbol:      ticker.symbol,
        shortName:   ticker.shortName ?? ticker.name,
        reason:      recommendedSize != null
          ? `Analyst recommends trimming to ${recommendedSize.toFixed(0)}%`
          : 'Trim signal — analyst recommendation',
        thesisHealth,
        finalAction: 'Trim',
        trajectory,
        tier,
        ratchetTranche,
        currentPct:  +currentPct.toFixed(2),
        hardCapPct:  +hardCapPct.toFixed(1),
        targetPct:   +targetPct.toFixed(1),
        currentMktValue: +mktValue.toFixed(2),
        dollarAmount:    +trimValue.toFixed(2),
        sharesApprox:    +sharesToSell.toFixed(3),
        taxCost:         +taxTotal.toFixed(2),
        netProceeds:     +(trimValue - taxTotal).toFixed(2),
        accounts:        routing,
      });
    }
  }

  // ── ADD (existing position, analyst says Add, under target) ───────────────
  if (effectiveAction === 'Add' && currentPct < hardCapPct * 0.90) {
    const targetPct   = recommendedSize != null
      ? Math.min(recommendedSize, hardCapPct)
      : hardCapPct;
    const targetValue = totalPortfolioValue * (targetPct / 100);
    const addValue    = Math.max(0, targetValue - mktValue);

    if (addValue >= 100) {
      const sharesApprox = price > 0 ? addValue / price : 0;
      moves.push({
        moveType:    'ADD',
        priority:    5,
        symbol:      ticker.symbol,
        shortName:   ticker.shortName ?? ticker.name,
        reason:      `Add signal — current ${currentPct.toFixed(1)}% vs target ${targetPct.toFixed(0)}%`,
        thesisHealth,
        finalAction: 'Add',
        trajectory,
        tier,
        ratchetTranche,
        currentPct:  +currentPct.toFixed(2),
        hardCapPct:  +hardCapPct.toFixed(1),
        targetPct:   +targetPct.toFixed(1),
        currentMktValue: +mktValue.toFixed(2),
        dollarAmount:    +addValue.toFixed(2),
        sharesApprox:    +sharesApprox.toFixed(3),
        taxCost:         0,
        netProceeds:     0,
        accounts:        [],
      });
    }
  }

  // If no action move was generated, return a HOLD record
  if (moves.length === 0) {
    moves.push({
      moveType:    'HOLD',
      priority:    99,
      symbol:      ticker.symbol,
      shortName:   ticker.shortName ?? ticker.name,
      reason:      finalAction === 'Hold' ? 'Hold — thesis intact'
        : finalAction === '—'           ? 'No analysis available'
        : `${finalAction} — no immediate action`,
      thesisHealth,
      finalAction:     finalAction,
      trajectory,
      tier,
      ratchetTranche,
      currentPct:  +currentPct.toFixed(2),
      hardCapPct:  +hardCapPct.toFixed(1),
      currentMktValue: +mktValue.toFixed(2),
      dollarAmount:    0,
      sharesApprox:    0,
      taxCost:         0,
      netProceeds:     0,
      accounts:        [],
    });
  }

  // ── 48h flag ───────────────────────────────────────────────────────────────
  if (currentPct > 30) {
    moves.forEach(m => { m.requires48h = true; });
  }

  return moves;
}

// ─── GET /api/moves ───────────────────────────────────────────────────────────

router.get('/', async (req, res) => {
  try {
    const profiles = await prisma.ownerProfile.findMany({ orderBy: { owner: 'asc' } });

    // Quick summary: just owner name and whether they have active positions
    const summaries = profiles.map(p => ({
      owner:       p.owner,
      displayName: p.displayName ?? p.owner,
    }));

    res.json(summaries);
  } catch (err) {
    console.error('GET /moves error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /api/moves/:owner ────────────────────────────────────────────────────

router.get('/:owner', async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);

  try {
    // ── Owner profile ──────────────────────────────────────────────────────
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    const cashReservePct    = profile.cashReservePct    ?? DEFAULT_CASH_RESERVE;
    const estSpecRatio      = profile.estSpecRatio      ?? DEFAULT_EST_RATIO;  // 0-1, established fraction
    const maxPositions      = profile.maxPositions      ?? DEFAULT_MAX_POS;
    const minPositionDollar = profile.minPositionDollar ?? DEFAULT_MIN_POS_USD;

    const ownerTaxRates = { ltcg: DEFAULT_LTCG_RATE, stcg: DEFAULT_STCG_RATE };

    // ── Portfolio accounts + positions ────────────────────────────────────
    const accounts = await prisma.account.findMany({
      where: { owner },
      include: {
        positions: {
          where: { status: 'active' },
          include: {
            lots:   { where: { closedDate: null } },
            ticker: true,
          },
        },
      },
    });

    // ── Portfolio totals ──────────────────────────────────────────────────
    let totalMktValue = 0;
    let totalCash     = 0;
    for (const acct of accounts) {
      totalCash += acct.cashBalance ?? 0;
      for (const pos of acct.positions) {
        const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
        totalMktValue += pos.lastPrice != null
          ? shares * pos.lastPrice
          : pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
      }
    }
    const totalPortfolioValue = totalMktValue + totalCash;
    const cashReserveFloor    = totalPortfolioValue * cashReservePct;
    const freeCash            = Math.max(0, totalCash - cashReserveFloor);

    // ── Group positions by ticker ─────────────────────────────────────────
    const byTicker = new Map();
    for (const acct of accounts) {
      for (const pos of acct.positions) {
        const tid = pos.tickerId;
        if (!byTicker.has(tid)) {
          byTicker.set(tid, { ticker: pos.ticker, positions: [] });
        }
        byTicker.get(tid).positions.push({ ...pos, account: acct });
      }
    }

    // ── Latest analyst score per portfolio ticker ─────────────────────────
    const tickerIds      = [...byTicker.keys()];
    const latestAnalyses = await Promise.all(tickerIds.map(async tickerId => {
      const a = await prisma.analysis.findFirst({
        where:   { transcript: { tickerId } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          id: true,
          thesisHealth:    true,
          recommendation:  true,
          recommendedSize: true,
          capPercent:      true,
          ratchetTranche:  true,
          trajectory:      true,
          finalAction:     true,
          finalConfidence: true,
          tier:            true,
          thesisDelta:     true,
          transcript: { select: { callDate: true } },
        },
      });
      return { tickerId, analysis: a };
    }));

    const analysisMap = new Map(latestAnalyses.map(({ tickerId, analysis }) => [tickerId, analysis]));

    // ── Generate moves ─────────────────────────────────────────────────────
    const allMoves = [];
    let estValue   = 0;
    let specValue  = 0;

    for (const [tickerId, { ticker, positions }] of byTicker.entries()) {
      const latestAnalysis = analysisMap.get(tickerId) ?? null;
      const tickerMoves    = generateTickerMoves(
        ticker, positions, totalPortfolioValue,
        latestAnalysis, profile, ownerTaxRates
      );
      allMoves.push(...tickerMoves);

      // Barbell tracking
      const openLots  = positions.flatMap(p => (p.lots || []).filter(l => !l.closedDate));
      const shares    = openLots.reduce((s, l) => s + l.shares, 0);
      const pricePos  = positions.find(p => p.lastPrice != null);
      const price     = pricePos?.lastPrice ?? 0;
      const mktV      = shares * price;
      const tier      = ticker.tierOverride ?? latestAnalysis?.tier ?? null;
      if (tier === 'established')  estValue  += mktV;
      if (tier === 'speculative')  specValue += mktV;
    }

    // Sort: by priority asc, then by dollar amount desc within same priority
    allMoves.sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority;
      return b.dollarAmount - a.dollarAmount;
    });

    // Split into action moves vs holds
    const actionMoves = allMoves.filter(m => m.moveType !== 'HOLD');
    const holds       = allMoves.filter(m => m.moveType === 'HOLD');

    // ── Watchlist candidates ──────────────────────────────────────────────
    const watchlistTickers = await prisma.ticker.findMany({
      where: { status: 'watchlist' },
    });

    const watchlistCandidates = [];
    for (const wt of watchlistTickers) {
      const a = await prisma.analysis.findFirst({
        where:   { transcript: { tickerId: wt.id } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          thesisHealth:    true,
          recommendation:  true,
          finalAction:     true,
          trajectory:      true,
          recommendedSize: true,
          tier:            true,
          transcript: { select: { callDate: true } },
        },
      });

      if (!a) continue;
      const action = a.finalAction ?? a.recommendation ?? '—';
      if (!['Add', 'Hold'].includes(action)) continue;
      if (['Broken', 'Weakening'].includes(a.thesisHealth) && action !== 'Add') continue;

      const score           = scoreCandidate(a, wt.type);
      const suggestedPct    = a.recommendedSize != null
        ? Math.min(a.recommendedSize, wt.capPercent)
        : Math.min(5, wt.capPercent);
      const suggestedDollar = totalPortfolioValue * (suggestedPct / 100);

      if (suggestedDollar < minPositionDollar) continue;

      watchlistCandidates.push({
        tickerId:         wt.id,
        symbol:           wt.symbol,
        shortName:        wt.shortName ?? wt.name,
        type:             wt.type,
        tier:             wt.tierOverride ?? a.tier ?? null,
        thesisHealth:     a.thesisHealth,
        finalAction:      action,
        trajectory:       a.trajectory ?? null,
        recommendedSize:  a.recommendedSize ?? null,
        suggestedPct:     +suggestedPct.toFixed(1),
        suggestedDollar:  +suggestedDollar.toFixed(0),
        rankScore:        score,
        latestCallDate:   a.transcript?.callDate ?? null,
        hardCapPct:       wt.capPercent,
      });
    }

    // newMoneyBehavior = "highest_conviction": only surface top-2 candidates
    watchlistCandidates.sort((a, b) => b.rankScore - a.rankScore);
    const finalCandidates = (profile.newMoneyBehavior === 'highest_conviction')
      ? watchlistCandidates.slice(0, 2)
      : watchlistCandidates;

    // ── Capital flow plan ─────────────────────────────────────────────────
    const trimSources  = actionMoves
      .filter(m => ['EXIT', 'TRIM_CAP', 'TRIM_RATCHET', 'TRIM_SIGNAL'].includes(m.moveType))
      .map(m => ({
        label:       `${m.moveType === 'EXIT' ? 'Exit' : 'Trim'} ${m.symbol}`,
        dollarFreed: m.dollarAmount,
        taxCost:     m.taxCost,
        netFreed:    m.netProceeds,
        moveType:    m.moveType,
      }));

    const totalNetFreed   = trimSources.reduce((s, r) => s + r.netFreed, 0);
    const totalDeployable = totalNetFreed + freeCash;

    // Uses: first existing ADD moves, then watchlist promotions
    const addUses    = actionMoves
      .filter(m => m.moveType === 'ADD')
      .map(m => ({
        label:       `Add ${m.symbol}`,
        dollarNeeded: m.dollarAmount,
        type:        'add_existing',
      }));
    const promUses   = finalCandidates
      .filter(c => c.finalAction === 'Add')
      .map(c => ({
        label:       `Promote ${c.symbol}`,
        dollarNeeded: c.suggestedDollar,
        type:        'promote',
      }));

    const allUses      = [...addUses, ...promUses];
    const totalNeeded  = allUses.reduce((s, u) => s + u.dollarNeeded, 0);
    const surplus      = totalDeployable - totalNeeded;

    // ── Barbell status ─────────────────────────────────────────────────────
    const classifiedTotal = estValue + specValue;
    const estPct          = classifiedTotal > 0 ? (estValue  / classifiedTotal) * 100 : null;
    const specPct         = classifiedTotal > 0 ? (specValue / classifiedTotal) * 100 : null;
    const specTarget      = (1 - estSpecRatio) * 100;
    const barbellInBalance = specPct == null || Math.abs(specPct - specTarget) <= 7;

    // ── Warnings ───────────────────────────────────────────────────────────
    const warnings = [];

    // 48h wait
    const needs48h = actionMoves.filter(m => m.requires48h);
    for (const m of needs48h) {
      warnings.push({
        type:     '48h_wait',
        symbol:   m.symbol,
        severity: 'yellow',
        message:  `${m.symbol} at ${m.currentPct.toFixed(1)}% — 48-hour review required before confirming hold`,
      });
    }

    // Barbell imbalance
    if (!barbellInBalance && specPct != null) {
      warnings.push({
        type:     'barbell',
        symbol:   null,
        severity: 'amber',
        message:  `Portfolio is ${specPct.toFixed(0)}% speculative vs ${specTarget.toFixed(0)}% target — consider trimming spec positions`,
      });
    }

    // Position count
    const posCount = byTicker.size;
    if (allUses.length > 0 && posCount + allUses.filter(u => u.type === 'promote').length > maxPositions) {
      warnings.push({
        type:     'max_positions',
        symbol:   null,
        severity: 'amber',
        message:  `Adding promotions would exceed max ${maxPositions} positions (currently ${posCount})`,
      });
    }

    // Enough number
    const enoughNumber = profile.enoughNumber ?? null;
    if (enoughNumber && totalPortfolioValue >= enoughNumber) {
      warnings.push({
        type:     'enough_number',
        symbol:   null,
        severity: 'amber',
        message:  `Portfolio ($${Math.round(totalPortfolioValue).toLocaleString()}) has reached the enough number ($${Math.round(enoughNumber).toLocaleString()}) — consider transitioning to passive allocation`,
      });
    }

    // ── Response ───────────────────────────────────────────────────────────
    res.json({
      owner,
      displayName:         profile.displayName ?? owner,
      totalPortfolioValue: +totalPortfolioValue.toFixed(2),
      totalMktValue:       +totalMktValue.toFixed(2),
      totalCash:           +totalCash.toFixed(2),
      cashReserveFloor:    +cashReserveFloor.toFixed(2),
      freeCash:            +freeCash.toFixed(2),
      positionCount:       posCount,
      maxPositions,
      minPositionDollar,

      barbellStatus: {
        estPct:        estPct != null ? +estPct.toFixed(1) : null,
        specPct:       specPct != null ? +specPct.toFixed(1) : null,
        estTarget:     +(estSpecRatio * 100).toFixed(0),
        specTarget:    +specTarget.toFixed(0),
        inBalance:     barbellInBalance,
        classifiedPct: classifiedTotal > 0
          ? +((classifiedTotal / totalMktValue) * 100).toFixed(0)
          : 0,
      },

      moves:               actionMoves,
      holds:               holds.map(h => ({
        symbol:      h.symbol,
        shortName:   h.shortName,
        thesisHealth: h.thesisHealth,
        finalAction: h.finalAction,
        trajectory:  h.trajectory,
        tier:        h.tier,
        currentPct:  h.currentPct,
        currentMktValue: h.currentMktValue,
      })),

      watchlistCandidates: finalCandidates,

      capitalFlow: {
        sources:          trimSources,
        freeCash:         +freeCash.toFixed(2),
        totalNetFreed:    +totalNetFreed.toFixed(2),
        totalDeployable:  +totalDeployable.toFixed(2),
        uses:             allUses,
        totalNeeded:      +totalNeeded.toFixed(2),
        surplus:          +surplus.toFixed(2),
        shortfall:        surplus < 0 ? +(-surplus).toFixed(2) : 0,
      },

      warnings,
    });
  } catch (err) {
    console.error(`GET /moves/${owner} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

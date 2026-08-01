/**
 * moves.js v2 — Recommended Moves engine (Layer 1 allocator output)
 *
 * Model portfolio weight architecture:
 *
 *   1. Classify each position:
 *        ETF              → EST pool (fixed target = capPercent)
 *        Commodity/Crypto → SPEC pool (fixed target = capPercent)
 *        Individual stock → shares remaining pool by type (A/B) multiplier
 *
 *   2. Compute barbell pools:
 *        estPool  = portfolioValue × estRatio  − sum(ETF targets)
 *        specPool = portfolioValue × specRatio − sum(Commodity/Crypto targets)
 *
 *   3. Model weight for individual stocks:
 *        baseWeight  = pool% ÷ targetPositionCount
 *        rawWeight   = baseWeight × typeMultiplier  (B=1.5×, A=1.0×)
 *        normalised  = rawWeight × (pool% / sum(rawWeights)), capped at hardCapPct
 *
 *   4. Move generation (same logic for initial build and ongoing management):
 *        currentPct > modelWeight + tolerance → TRIM
 *        currentPct < modelWeight − tolerance → ADD  (only if thesis ≥ Intact)
 *        Thesis Broken / ratchet ≥ 3           → EXIT regardless
 *        Hard cap violation                     → TRIM_CAP (always)
 *
 *   5. Capital-constrained flow:
 *        Rank uses by priority, greedily allocate (freeCash + trim proceeds)
 *        "Funded now" vs "Queue" split — no more phantom $275K shortfall
 *
 * Analyst/Allocator firewall preserved — no transcript text.
 *
 *   GET  /api/moves              list owners
 *   GET  /api/moves/:owner       full recommended moves for one owner
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { requireAuth } = require('@clerk/express');
const { enforceOwner } = require('../lib/authMiddleware');

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_LTCG_RATE    = 0.15;
const DEFAULT_STCG_RATE    = 0.15;
const LTCG_HOLD_DAYS       = 365;
const DEFAULT_CASH_RESERVE = 0.05;
const DEFAULT_EST_RATIO    = 0.60;
const DEFAULT_MAX_POS      = 15;
const DEFAULT_MIN_POS_USD  = 1500;
const MODEL_WEIGHT_TOL     = 1.0;   // % — ignore drifts smaller than this

// ─── Asset classification ─────────────────────────────────────────────────────

function getBucket(ticker) {
  return ticker.bucketOverride ?? 'equity';
}
function isETF(ticker)             { return getBucket(ticker) === 'etf'; }
function isCommodityOrCrypto(t)    { return ['commodity', 'crypto'].includes(getBucket(t)); }
function isFixedTarget(ticker)     { return isETF(ticker) || isCommodityOrCrypto(ticker); }

/**
 * Returns 'est' | 'spec' | null for a ticker.
 * ETFs  → est.  Commodity/crypto → spec.
 * Individual stocks → tierOverride ?? analyst tier.
 */
function barbellSide(ticker, latestAnalysis) {
  if (isETF(ticker))             return 'est';
  if (isCommodityOrCrypto(ticker)) return 'spec';
  const tier = ticker.tierOverride ?? latestAnalysis?.tier ?? null;
  if (tier === 'established')  return 'est';
  if (tier === 'speculative')  return 'spec';
  return null;
}

// ─── Tax helpers ──────────────────────────────────────────────────────────────

function daysBetween(a, b) {
  return Math.abs(b - a) / (1000 * 60 * 60 * 24);
}

function computeTrimTax(lots, sharesToSell, price, ltcgRate, stcgRate, isTaxAdvantaged) {
  if (isTaxAdvantaged) return { taxCost: 0, ltGain: 0, stGain: 0 };
  const now    = new Date();
  const sorted = [...lots].filter(l => !l.closedDate)
    .sort((a, b) => new Date(a.acquiredDate) - new Date(b.acquiredDate));
  let remaining = sharesToSell, ltGain = 0, stGain = 0;
  for (const lot of sorted) {
    if (remaining <= 0) break;
    const sell = Math.min(remaining, lot.shares);
    const gain = sell * (price - lot.costBasis);
    if (daysBetween(new Date(lot.acquiredDate), now) >= LTCG_HOLD_DAYS) ltGain += gain;
    else stGain += gain;
    remaining -= sell;
  }
  return { taxCost: ltGain * ltcgRate + stGain * stcgRate, ltGain, stGain };
}

function buildTrimRouting(positions, sharesToSell, defaultLtcg, defaultStcg) {
  // Only route through agent-managed accounts. Unmanaged accounts are included
  // in portfolio value totals (for accurate concentration %) but the agent
  // never tells the user to buy/sell from them.
  const managed = positions.filter(p => p.account?.managed);
  const sorted = [...managed].sort((a, b) => {
    const ta = p => ['ira', 'roth'].includes(p?.account?.type);
    return ta(b) - ta(a);
  });
  let remaining = sharesToSell;
  const rows = [];
  for (const pos of sorted) {
    if (remaining <= 0) break;
    const openLots      = (pos.lots || []).filter(l => !l.closedDate);
    const posShares     = openLots.reduce((s, l) => s + l.shares, 0);
    if (posShares <= 0) continue;
    let sell            = Math.min(remaining, posShares);
    const price         = pos.lastPrice ?? 0;
    const isTaxAdv      = ['ira', 'roth'].includes(pos.account?.type);
    const canFractional = pos.account?.allowsFractional ?? false;
    // Enforce whole shares when account doesn't support fractional trading.
    // Floor (conservative) to avoid over-trimming. Skip if nothing left after floor.
    let roundedToWhole = false;
    if (!canFractional && !Number.isInteger(+sell.toFixed(4))) {
      const floored = Math.floor(sell);
      if (floored <= 0) continue; // fractional < 1 share and no fractional allowed — skip
      sell          = floored;
      roundedToWhole = true;
    }
    const tax = computeTrimTax(openLots, sell, price,
      pos.account?.ltcgRate ?? defaultLtcg,
      pos.account?.stcgRate ?? defaultStcg,
      isTaxAdv);
    rows.push({
      accountId:       pos.accountId,
      accountName:     pos.account?.name ?? '—',
      accountType:     pos.account?.type ?? '—',
      isTaxAdvantaged: isTaxAdv,
      roundedToWhole,
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

// ─── Position metrics helper ──────────────────────────────────────────────────

function positionMetrics(positions, totalPortfolioValue) {
  const openLots   = positions.flatMap(p => (p.lots || []).filter(l => !l.closedDate));
  const shares     = openLots.reduce((s, l) => s + l.shares, 0);
  const cost       = openLots.reduce((s, l) => s + l.shares * l.costBasis, 0);
  const pricePos   = positions.find(p => p.lastPrice != null);
  const price      = pricePos?.lastPrice ?? (shares > 0 ? cost / shares : 0);
  const mktValue   = shares * price;
  const currentPct = totalPortfolioValue > 0 ? (mktValue / totalPortfolioValue) * 100 : 0;
  return { shares, cost, price, mktValue, currentPct };
}

// ─── Model weight computation ─────────────────────────────────────────────────

/**
 * Compute model weights (as % of total portfolio) for all individual (non-fixed)
 * positions. Returns Map<tickerId, modelWeightPct>.
 *
 * @param groups       [{ticker, positions, latestAnalysis}] — individual stocks only
 * @param estPoolPct   % of portfolio available for individual EST stocks
 * @param specPoolPct  % of portfolio available for individual SPEC stocks
 * @param targetEst    target # of individual EST positions
 * @param targetSpec   target # of individual SPEC positions
 */
function computeIndividualModelWeights(groups, estPoolPct, specPoolPct, targetEst, targetSpec) {
  const weights = new Map();

  const estGroup  = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'est');
  const specGroup = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'spec');
  const unclassified = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === null);

  function allocate(group, poolPct, targetCount) {
    if (poolPct <= 0 || group.length === 0) {
      group.forEach(g => weights.set(g.ticker.id, 0));
      return;
    }
    // Denominator: whichever is larger — current positions or target count.
    // This ensures current positions don't over-fill the pool when target > current.
    const denom = Math.max(group.length, targetCount);
    const baseWeightPct = poolPct / denom;

    // Raw weights with Type A/B multiplier
    const raws = group.map(g => ({
      id:         g.ticker.id,
      hardCapPct: Math.min(g.ticker.capPercent ?? 100, g.latestAnalysis?.capPercent ?? 100),
      raw:        baseWeightPct * (g.ticker.type === 'B' ? 1.5 : 1.0),
    }));

    // Normalize so sum = poolPct
    const rawSum = raws.reduce((s, r) => s + r.raw, 0);
    const scale  = rawSum > 0 ? poolPct / rawSum : 1;

    raws.forEach(r => {
      weights.set(r.id, +Math.min(r.raw * scale, r.hardCapPct).toFixed(2));
    });
  }

  allocate(estGroup,  estPoolPct,  targetEst);
  allocate(specGroup, specPoolPct, targetSpec);

  // Unclassified: split evenly using whichever pool has room, or assign 0
  unclassified.forEach(g => weights.set(g.ticker.id, 0));

  return weights;
}

// ─── Watchlist candidate scoring ─────────────────────────────────────────────

const TRAJ_SCORE   = { improving: 5, stable: 3, flattening: 2, softening: 1, deteriorating: 0, unknown: 0 };
const HEALTH_SCORE = { Strengthening: 4, Intact: 3, Weakening: 1, Broken: 0 };
const ACTION_SCORE = { Add: 3, Hold: 1, Trim: -2, Exit: -5 };

function scoreCandidate(a, type) {
  return (TRAJ_SCORE[a?.trajectory] ?? 0)
       + (HEALTH_SCORE[a?.thesisHealth] ?? 0)
       + (ACTION_SCORE[a?.finalAction ?? a?.recommendation] ?? 0)
       + (type === 'B' ? 2 : 1);
}

// ─── Move builder helpers ─────────────────────────────────────────────────────

function makeTrimMove(moveType, priority, ticker, positions, currentPct, targetPct,
    mktValue, totalPortfolioValue, latestAnalysis, ownerTaxRates) {
  const price        = positions.find(p => p.lastPrice != null)?.lastPrice ?? 0;
  const trimValue    = Math.max(0, mktValue - totalPortfolioValue * (targetPct / 100));
  const sharesToSell = price > 0 ? trimValue / price : 0;
  const routing      = buildTrimRouting(positions, sharesToSell, ownerTaxRates.ltcg, ownerTaxRates.stcg);
  const taxTotal     = routing.reduce((s, r) => s + r.taxCost, 0);
  const hardCapPct   = Math.min(ticker.capPercent ?? 100, latestAnalysis?.capPercent ?? 100);

  return {
    moveType,
    priority,
    symbol:          ticker.symbol,
    shortName:       ticker.shortName ?? ticker.name,
    bucket:          getBucket(ticker),
    tier:            ticker.tierOverride ?? latestAnalysis?.tier ?? null,
    thesisHealth:    latestAnalysis?.thesisHealth   ?? '—',
    finalAction:     latestAnalysis?.finalAction    ?? latestAnalysis?.recommendation ?? '—',
    trajectory:      latestAnalysis?.trajectory     ?? null,
    ratchetTranche:  latestAnalysis?.ratchetTranche ?? 0,
    currentPct:      +currentPct.toFixed(2),
    targetPct:       +targetPct.toFixed(2),
    hardCapPct:      +hardCapPct.toFixed(1),
    currentMktValue: +mktValue.toFixed(2),
    dollarAmount:    +trimValue.toFixed(2),
    sharesApprox:    +sharesToSell.toFixed(3),
    pricePerShare:   +price.toFixed(4),
    taxCost:         +taxTotal.toFixed(2),
    netProceeds:     +(trimValue - taxTotal).toFixed(2),
    accounts:        routing,
    requires48h:     currentPct > 30,
  };
}

/**
 * Route an ADD move to specific accounts.
 *
 * Priority: Roth → IRA → taxable (best tax shelter for new buys).
 * Within the same account type, prefer the account already holding more
 * shares of this ticker (consolidate rather than fragment).
 * Allocation per account is bounded by that account's cash balance.
 *
 * If no account has cash, still returns one row (the best candidate)
 * flagged with insufficientCash: true so the UI can warn the user.
 */
function buildAddRouting(positions, addValue, price) {
  if (!addValue || addValue <= 0 || price <= 0) return [];

  // Only route through agent-managed accounts (same rule as buildTrimRouting).
  const managedPositions = positions.filter(p => p.account?.managed);

  // Deduplicate by accountId
  const seen    = new Set();
  const deduped = managedPositions.filter(p => {
    if (seen.has(p.accountId)) return false;
    seen.add(p.accountId);
    return true;
  });

  const TYPE_ORDER = { roth: 0, ira: 1, taxable: 2, custodial: 3 };

  const sorted = [...deduped].sort((a, b) => {
    const ta = TYPE_ORDER[a.account?.type] ?? 9;
    const tb = TYPE_ORDER[b.account?.type] ?? 9;
    if (ta !== tb) return ta - tb;
    // Same account type: prefer whichever already holds more shares
    const sharesA = (a.lots ?? []).filter(l => !l.closedDate).reduce((s, l) => s + l.shares, 0);
    const sharesB = (b.lots ?? []).filter(l => !l.closedDate).reduce((s, l) => s + l.shares, 0);
    return sharesB - sharesA;
  });

  let remaining = addValue;
  const rows    = [];

  for (const pos of sorted) {
    if (remaining <= 0) break;
    const cash = pos.account?.cashBalance ?? 0;
    if (cash < 1) continue;
    const canFractional  = pos.account?.allowsFractional ?? false;
    let allocate         = Math.min(remaining, cash);
    let rawShares        = allocate / price;
    let roundedToWhole   = false;
    // Enforce whole shares: floor the share count and recalculate dollar spend.
    // This leaves the residual in `remaining` for the next account.
    if (!canFractional) {
      const wholeShares = Math.floor(rawShares);
      if (wholeShares <= 0) continue; // not enough cash for even 1 share — skip
      allocate       = wholeShares * price;
      rawShares      = wholeShares;
      roundedToWhole = !Number.isInteger(+(addValue / price).toFixed(3)); // flag only if rounding changed result
    }
    rows.push({
      accountId:       pos.accountId,
      accountName:     pos.account?.name ?? '—',
      accountType:     pos.account?.type ?? '—',
      isTaxAdvantaged: ['ira', 'roth'].includes(pos.account?.type),
      roundedToWhole,
      sharesToBuy:     +rawShares.toFixed(3),
      dollarAmount:    +allocate.toFixed(2),
      insufficientCash: false,
    });
    remaining -= allocate;
  }

  // No cash anywhere — still surface the best account so the user knows where to buy
  if (rows.length === 0 && sorted.length > 0) {
    const best          = sorted[0];
    const canFractional = best.account?.allowsFractional ?? false;
    let rawShares       = addValue / price;
    let displayDollar   = addValue;
    let roundedToWhole  = false;
    if (!canFractional) {
      const wholeShares = Math.floor(rawShares);
      rawShares         = wholeShares;
      displayDollar     = wholeShares * price;
      roundedToWhole    = true;
    }
    rows.push({
      accountId:       best.accountId,
      accountName:     best.account?.name ?? '—',
      accountType:     best.account?.type ?? '—',
      isTaxAdvantaged: ['ira', 'roth'].includes(best.account?.type),
      roundedToWhole,
      sharesToBuy:     +rawShares.toFixed(3),
      dollarAmount:    +displayDollar.toFixed(2),
      insufficientCash: true,
    });
  }

  return rows;
}

function makeAddMove(priority, ticker, positions, currentPct, targetPct,
    mktValue, totalPortfolioValue, latestAnalysis) {
  const price        = positions.find(p => p.lastPrice != null)?.lastPrice ?? 0;
  const addValue     = Math.max(0, totalPortfolioValue * (targetPct / 100) - mktValue);
  const sharesApprox = price > 0 ? addValue / price : 0;
  const hardCapPct   = Math.min(ticker.capPercent ?? 100, latestAnalysis?.capPercent ?? 100);
  const accounts     = buildAddRouting(positions, addValue, price);

  return {
    moveType:        'ADD',
    priority,
    symbol:          ticker.symbol,
    shortName:       ticker.shortName ?? ticker.name,
    bucket:          getBucket(ticker),
    tier:            ticker.tierOverride ?? latestAnalysis?.tier ?? null,
    thesisHealth:    latestAnalysis?.thesisHealth   ?? '—',
    finalAction:     latestAnalysis?.finalAction    ?? latestAnalysis?.recommendation ?? '—',
    trajectory:      latestAnalysis?.trajectory     ?? null,
    ratchetTranche:  0,
    currentPct:      +currentPct.toFixed(2),
    targetPct:       +targetPct.toFixed(2),
    hardCapPct:      +hardCapPct.toFixed(1),
    currentMktValue: +mktValue.toFixed(2),
    dollarAmount:    +addValue.toFixed(2),
    sharesApprox:    +sharesApprox.toFixed(3),
    pricePerShare:   +price.toFixed(4),
    taxCost:         0,
    netProceeds:     0,
    accounts,
    requires48h:     false,
  };
}

// ─── Per-ticker move generation ───────────────────────────────────────────────

/**
 * Generate moves for one ticker, given its model weight.
 * Returns an array (usually 0-2 items).
 */
function generateMovesForTicker(
  ticker, positions, totalPortfolioValue,
  latestAnalysis, modelWeightPct,
  profile, ownerTaxRates
) {
  const { mktValue, currentPct } = positionMetrics(positions, totalPortfolioValue);
  const specExitSpeed  = profile.specExitSpeed ?? 'normal';
  const side           = barbellSide(ticker, latestAnalysis);
  const tier           = ticker.tierOverride ?? latestAnalysis?.tier ?? null;
  const hardCapPct     = Math.min(ticker.capPercent ?? 100, latestAnalysis?.capPercent ?? 100);
  const ratchetTranche = latestAnalysis?.ratchetTranche ?? 0;
  const thesisHealth   = latestAnalysis?.thesisHealth ?? '—';

  let finalAction = latestAnalysis?.finalAction ?? latestAnalysis?.recommendation ?? '—';

  // specExitSpeed modifier
  if (tier === 'speculative' && specExitSpeed === 'fast') {
    if (ratchetTranche >= 1 || latestAnalysis?.trajectory === 'deteriorating') finalAction = 'Exit';
  }
  if (tier === 'speculative' && specExitSpeed === 'patient' && ratchetTranche <= 2 && currentPct <= hardCapPct) {
    if (finalAction === 'Trim') finalAction = 'Hold';
  }

  const moves = [];

  // ── 1. EXIT ─────────────────────────────────────────────────────────────────
  if (finalAction === 'Exit' || ratchetTranche >= 3 || thesisHealth === 'Broken') {
    const { shares, price: exitPrice } = positionMetrics(positions, totalPortfolioValue);
    const routing      = buildTrimRouting(positions, shares, ownerTaxRates.ltcg, ownerTaxRates.stcg);
    const taxTotal     = routing.reduce((s, r) => s + r.taxCost, 0);
    moves.push({
      moveType:        'EXIT',
      priority:        1,
      symbol:          ticker.symbol,
      shortName:       ticker.shortName ?? ticker.name,
      bucket:          getBucket(ticker),
      tier,
      thesisHealth,
      finalAction:     'Exit',
      trajectory:      latestAnalysis?.trajectory ?? null,
      ratchetTranche,
      currentPct:      +currentPct.toFixed(2),
      targetPct:       0,
      hardCapPct:      +hardCapPct.toFixed(1),
      currentMktValue: +mktValue.toFixed(2),
      dollarAmount:    +mktValue.toFixed(2),
      sharesApprox:    +shares.toFixed(3),
      pricePerShare:   +exitPrice.toFixed(4),
      taxCost:         +taxTotal.toFixed(2),
      netProceeds:     +(mktValue - taxTotal).toFixed(2),
      accounts:        routing,
      requires48h:     currentPct > 30,
      reason: ratchetTranche >= 3  ? `Ratchet tranche ${ratchetTranche} — graduated exit complete`
            : thesisHealth === 'Broken' ? 'Thesis broken'
            : 'Exit signal',
    });
    return moves;
  }

  // ── 2. TRIM_CAP — hard cap violation (always enforced) ────────────────────
  if (currentPct > hardCapPct + 0.5) {
    moves.push({
      ...makeTrimMove('TRIM_CAP', 2, ticker, positions, currentPct, hardCapPct,
        mktValue, totalPortfolioValue, latestAnalysis, ownerTaxRates),
      reason: `Position at ${currentPct.toFixed(1)}% exceeds Type ${ticker.type} hard cap of ${hardCapPct.toFixed(0)}%`,
    });
  }

  // ── 3. TRIM_RATCHET — graduated exit ratchet ─────────────────────────────
  if (ratchetTranche >= 1 && ratchetTranche < 3 && currentPct <= hardCapPct + 0.5) {
    const ratchetTarget = ratchetTranche === 1
      ? Math.min(modelWeightPct, hardCapPct)
      : currentPct * 0.60; // ratchet 2: trim 40% of position
    const trimValue = Math.max(0, mktValue - totalPortfolioValue * (ratchetTarget / 100));
    if (trimValue > 50) {
      moves.push({
        ...makeTrimMove('TRIM_RATCHET', 3, ticker, positions, currentPct, ratchetTarget,
          mktValue, totalPortfolioValue, latestAnalysis, ownerTaxRates),
        reason: ratchetTranche === 1
          ? `Thesis weakening — trim to model weight (${modelWeightPct.toFixed(1)}%)`
          : `No improvement Q2 — trim 40% of position (ratchet ${ratchetTranche})`,
      });
    }
  }

  // ── 4. TRIM to model weight ────────────────────────────────────────────────
  const overModel  = currentPct > modelWeightPct + MODEL_WEIGHT_TOL;
  const underModel = currentPct < modelWeightPct - MODEL_WEIGHT_TOL;

  if (overModel && moves.length === 0) {
    // Thesis Strengthening above model weight: advisory (let winner run toward hard cap)
    const isWinnerRunning = finalAction === 'Add' && thesisHealth === 'Strengthening'
      && currentPct <= hardCapPct;

    if (isWinnerRunning) {
      moves.push({
        moveType:        'HOLD_ADVISORY',
        priority:        99,
        symbol:          ticker.symbol,
        shortName:       ticker.shortName ?? ticker.name,
        bucket:          getBucket(ticker),
        tier,
        thesisHealth,
        finalAction,
        trajectory:      latestAnalysis?.trajectory ?? null,
        ratchetTranche,
        currentPct:      +currentPct.toFixed(2),
        targetPct:       +modelWeightPct.toFixed(2),
        hardCapPct:      +hardCapPct.toFixed(1),
        currentMktValue: +mktValue.toFixed(2),
        dollarAmount:    0,
        sharesApprox:    0,
        taxCost:         0,
        netProceeds:     0,
        accounts:        [],
        requires48h:     currentPct > 30,
        reason: `Thesis Strengthening — over model weight (${modelWeightPct.toFixed(1)}%) but holding toward ${hardCapPct.toFixed(0)}% cap`,
      });
    } else {
      moves.push({
        ...makeTrimMove('TRIM_MODEL', 4, ticker, positions, currentPct, modelWeightPct,
          mktValue, totalPortfolioValue, latestAnalysis, ownerTaxRates),
        reason: `At ${currentPct.toFixed(1)}% — over model weight of ${modelWeightPct.toFixed(1)}%`,
      });
    }
  }

  // ── 5. ADD to model weight ─────────────────────────────────────────────────
  if (underModel && moves.filter(m => !m.moveType.startsWith('TRIM') && m.moveType !== 'EXIT').length === 0) {
    // Only add if thesis is at least Intact (not Weakening/Broken)
    // Out-of-scope tickers (regression/test data) never generate new buy recommendations
    const canAdd = ticker.inScope !== false
      && (!['Weakening', 'Broken'].includes(thesisHealth) || finalAction === 'Add');
    if (canAdd) {
      moves.push({
        ...makeAddMove(5, ticker, positions, currentPct, modelWeightPct,
          mktValue, totalPortfolioValue, latestAnalysis),
        reason: `At ${currentPct.toFixed(1)}% — below model weight of ${modelWeightPct.toFixed(1)}%`,
      });
    }
  }

  // ── 6. HOLD ───────────────────────────────────────────────────────────────
  if (moves.length === 0) {
    moves.push({
      moveType:        'HOLD',
      priority:        99,
      symbol:          ticker.symbol,
      shortName:       ticker.shortName ?? ticker.name,
      bucket:          getBucket(ticker),
      tier,
      thesisHealth,
      finalAction,
      trajectory:      latestAnalysis?.trajectory ?? null,
      ratchetTranche,
      currentPct:      +currentPct.toFixed(2),
      targetPct:       +modelWeightPct.toFixed(2),
      hardCapPct:      +hardCapPct.toFixed(1),
      currentMktValue: +mktValue.toFixed(2),
      dollarAmount:    0,
      sharesApprox:    0,
      taxCost:         0,
      netProceeds:     0,
      accounts:        [],
      requires48h:     currentPct > 30,
      reason:          `At model weight — no action`,
    });
  }

  return moves;
}

/**
 * Generate moves for a fixed-target asset (ETF, commodity, crypto).
 * These assets count toward their pool but use capPercent as target.
 */
function generateFixedTargetMove(ticker, positions, totalPortfolioValue, latestAnalysis, ownerTaxRates) {
  const { mktValue, currentPct } = positionMetrics(positions, totalPortfolioValue);
  const targetPct  = ticker.capPercent ?? 5;
  const overTarget = currentPct > targetPct + MODEL_WEIGHT_TOL;
  const bucket     = getBucket(ticker);
  const label      = isETF(ticker) ? 'ETF target' : isCommodityOrCrypto(ticker) ? `${bucket} allocation` : 'target';

  if (overTarget) {
    return {
      ...makeTrimMove('TRIM_MODEL', isETF(ticker) ? 4 : 4,
        ticker, positions, currentPct, targetPct,
        mktValue, totalPortfolioValue, latestAnalysis, ownerTaxRates),
      reason: `${ticker.symbol} at ${currentPct.toFixed(1)}% — over ${label} of ${targetPct.toFixed(0)}%`,
    };
  }

  return {
    moveType:        'HOLD',
    priority:        99,
    symbol:          ticker.symbol,
    shortName:       ticker.shortName ?? ticker.name,
    bucket,
    tier:            ticker.tierOverride ?? latestAnalysis?.tier ?? null,
    thesisHealth:    '—',
    finalAction:     '—',
    trajectory:      null,
    ratchetTranche:  0,
    currentPct:      +currentPct.toFixed(2),
    targetPct:       +targetPct.toFixed(1),
    hardCapPct:      +targetPct.toFixed(1),
    currentMktValue: +mktValue.toFixed(2),
    dollarAmount:    0, sharesApprox: 0, taxCost: 0, netProceeds: 0,
    accounts:        [],
    requires48h:     false,
    reason:          `At or below ${label ?? 'target'} — no action`,
  };
}

// ─── Capital flow — funded now vs queue ──────────────────────────────────────

function buildCapitalFlow(trimMoves, addUses, promUses, freeCash) {
  const sources = trimMoves.map(m => ({
    label:       `${m.moveType === 'EXIT' ? 'Exit' : 'Trim'} ${m.symbol}`,
    dollarFreed: m.dollarAmount,
    taxCost:     m.taxCost,
    netFreed:    m.netProceeds,
  }));

  const totalNetFreed  = sources.reduce((s, r) => s + r.netFreed, 0);
  const totalAvailable = totalNetFreed + freeCash;

  // Rank uses: existing ADD moves first (higher priority), then promotions (by score)
  const allUses = [
    ...addUses.map(u => ({ ...u, usePriority: 1 })),
    ...promUses.map(u => ({ ...u, usePriority: 2 })),
  ];

  let remaining = totalAvailable;
  const fundedNow = [];
  const queue     = [];

  for (const use of allUses) {
    if (remaining >= use.dollarNeeded) {
      fundedNow.push({ ...use, status: 'funded', partialAmount: null });
      remaining -= use.dollarNeeded;
    } else if (remaining > 50) {
      fundedNow.push({ ...use, status: 'partial', partialAmount: +remaining.toFixed(2) });
      remaining = 0;
    } else {
      queue.push({ ...use, status: 'queued' });
    }
  }

  return {
    sources,
    freeCash:         +freeCash.toFixed(2),
    totalNetFreed:    +totalNetFreed.toFixed(2),
    totalAvailable:   +totalAvailable.toFixed(2),
    fundedNow,
    queue,
    surplusAfterFunded: +Math.max(0, remaining).toFixed(2),
    queueTotalNeeded:   +queue.reduce((s, u) => s + u.dollarNeeded, 0).toFixed(2),
  };
}

// ─── GET /api/moves ───────────────────────────────────────────────────────────

router.get('/', async (req, res) => {
  try {
    const caller = req.ownerProfile;
    if (!caller) return res.status(401).json({ error: 'No owner profile linked to your account' });
    const isAdmin = caller.role === 'admin';
    const profiles = await prisma.ownerProfile.findMany({
      where: isAdmin ? undefined : { owner: caller.owner },
      orderBy: { owner: 'asc' },
    });
    res.json(profiles.map(p => ({ owner: p.owner, displayName: p.displayName ?? p.owner })));
  } catch (err) {
    console.error('GET /moves error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Core compute function (owner → payload object) ──────────────────────────
// Extracted so it can be called from both the GET route (cache miss)
// and POST /:owner/refresh (force recompute), as well as from schwab.js
// trigger hooks via server/lib/movesCache.js.

async function computeMovesPayload(owner) {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) throw new Error(`Owner "${owner}" not found`);

    const cashReservePct    = profile.cashReservePct    ?? DEFAULT_CASH_RESERVE;
    const estSpecRatio      = profile.estSpecRatio      ?? DEFAULT_EST_RATIO;
    const maxPositions      = profile.maxPositions      ?? DEFAULT_MAX_POS;
    const minPositionDollar = profile.minPositionDollar ?? DEFAULT_MIN_POS_USD;
    const ownerTaxRates     = { ltcg: DEFAULT_LTCG_RATE, stcg: DEFAULT_STCG_RATE };

    // ── Per-owner cap overrides ───────────────────────────────────────────────
    const ownerConfigs = await prisma.ownerTickerConfig.findMany({ where: { owner } });
    const ownerCapMap  = new Map(ownerConfigs.map(c => [c.tickerId, c.capPercent]));

    // Helper: effective cap for a ticker for this owner
    function effectiveCap(ticker) {
      const ownerCap = ownerCapMap.get(ticker.id);
      return ownerCap != null ? ownerCap : (ticker.capPercent ?? 100);
    }

    // ── Accounts + positions ──────────────────────────────────────────────────
    const accounts = await prisma.account.findMany({
      where:   { owner },
      include: {
        positions: {
          where:   { status: 'active' },
          include: { lots: { where: { closedDate: null } }, ticker: true },
        },
      },
    });

    // ── Per-account position config (loaded after accounts so IDs are available) ─
    const acctConfigs  = await prisma.accountPositionConfig.findMany({
      where: { accountId: { in: accounts.map(a => a.id) } },
    });
    const acctConfigMap = new Map(acctConfigs.map(c => [c.accountId, c]));

    // ── Portfolio totals ──────────────────────────────────────────────────────
    let totalMktValue = 0, totalCash = 0;
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

    // ── Group positions by ticker ─────────────────────────────────────────────
    const byTicker = new Map();
    for (const acct of accounts) {
      for (const pos of acct.positions) {
        if (!byTicker.has(pos.tickerId)) {
          byTicker.set(pos.tickerId, { ticker: pos.ticker, positions: [] });
        }
        byTicker.get(pos.tickerId).positions.push({ ...pos, account: acct });
      }
    }

    // ── Latest analyst score per ticker ───────────────────────────────────────
    const analysisMap = new Map();
    for (const tickerId of byTicker.keys()) {
      const a = await prisma.analysis.findFirst({
        where:   { transcript: { tickerId } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          id: true, thesisHealth: true, recommendation: true,
          recommendedSize: true, capPercent: true, ratchetTranche: true,
          trajectory: true, finalAction: true, tier: true,
          transcript: { select: { callDate: true } },
        },
      });
      analysisMap.set(tickerId, a ?? null);
    }

    // ── Classify positions ────────────────────────────────────────────────────
    const fixedGroups      = [];  // ETF / commodity / crypto
    const individualGroups = [];  // equity individual stocks

    for (const [tickerId, { ticker, positions }] of byTicker.entries()) {
      const latestAnalysis = analysisMap.get(tickerId);
      const group = { ticker, positions, latestAnalysis };
      if (isFixedTarget(ticker)) fixedGroups.push(group);
      else individualGroups.push(group);
    }

    // ── Barbell pools ─────────────────────────────────────────────────────────
    const specRatio = 1 - estSpecRatio;

    // Fixed-target contributions to each pool
    let etfTargetPct       = 0;
    let commCryptoTargetPct = 0;
    for (const g of fixedGroups) {
      const tgt = effectiveCap(g.ticker);
      if (isETF(g.ticker))              etfTargetPct        += tgt;
      else if (isCommodityOrCrypto(g.ticker)) commCryptoTargetPct += tgt;
    }

    const estPoolPct  = Math.max(0, estSpecRatio * 100 - etfTargetPct);
    const specPoolPct = Math.max(0, specRatio * 100 - commCryptoTargetPct);

    // Target individual position counts
    const fixedCount      = fixedGroups.length;
    const targetIndividual = Math.max(0, maxPositions - fixedCount);
    const targetEstIndividual  = Math.round(targetIndividual * estSpecRatio);
    const targetSpecIndividual = targetIndividual - targetEstIndividual;

    // ── Model weights ─────────────────────────────────────────────────────────
    const modelWeights = computeIndividualModelWeights(
      individualGroups,
      estPoolPct, specPoolPct,
      targetEstIndividual, targetSpecIndividual
    );

    // ── Generate moves ─────────────────────────────────────────────────────────
    const allMoves = [];

    // Fixed-target assets (inject per-owner cap)
    for (const g of fixedGroups) {
      const tickerWithOwnerCap = { ...g.ticker, capPercent: effectiveCap(g.ticker) };
      const move = generateFixedTargetMove(
        tickerWithOwnerCap, g.positions, totalPortfolioValue, g.latestAnalysis, ownerTaxRates
      );
      allMoves.push(move);
    }

    // Individual stocks
    for (const g of individualGroups) {
      const modelWeightPct = modelWeights.get(g.ticker.id) ?? 0;
      // Inject per-owner cap so generateMovesForTicker uses it for hardCapPct
      const tickerWithOwnerCap = { ...g.ticker, capPercent: effectiveCap(g.ticker) };
      const moves = generateMovesForTicker(
        tickerWithOwnerCap, g.positions, totalPortfolioValue,
        g.latestAnalysis, modelWeightPct, profile, ownerTaxRates
      );
      allMoves.push(...moves);
    }

    // Sort by priority
    allMoves.sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority;
      return b.dollarAmount - a.dollarAmount;
    });

    // ── Derive current/target share counts ──────────────────────────────────
    // All move builders already compute currentMktValue, pricePerShare, and
    // sharesApprox (the size of the delta) — this generically derives the
    // before/after share counts from those instead of duplicating the math
    // per move type. ADD moves toward more shares, everything else (TRIM*,
    // EXIT) moves toward fewer. HOLD_ADVISORY has sharesApprox 0, so target
    // == current, correctly showing no change.
    for (const m of allMoves) {
      const currentShares = m.pricePerShare > 0 ? m.currentMktValue / m.pricePerShare : 0;
      const delta         = m.sharesApprox ?? 0;
      m.currentShares = +currentShares.toFixed(3);
      m.targetShares   = +(m.moveType === 'ADD' ? currentShares + delta : currentShares - delta).toFixed(3);
    }

    // ── Attach prior owner decisions (latest per symbol+moveType, any status) ─
    // Lets the frontend hydrate accept/decline state (and the reason) on load
    // instead of resetting to "undecided" every visit — the move itself still
    // regenerates live from current portfolio state (it's a diff, not a
    // suppressible event), but your last call on it should already be
    // reflected rather than making you re-decide every time you open the tab.
    const priorDecisionRows = await prisma.ownerDecision.findMany({
      where:   { owner },
      include: { ticker: { select: { symbol: true } } },
      orderBy: { decidedAt: 'desc' },
    });
    const priorMap = new Map();
    for (const d of priorDecisionRows) {
      const key = `${d.ticker.symbol}:${d.moveType}`;
      if (!priorMap.has(key)) {
        priorMap.set(key, {
          decision:       d.decision,
          reason:         d.declinedReason ?? null,
          acceptedAmount: d.acceptedAmount ?? null,
          decidedAt:      d.decidedAt,
        });
      }
    }
    for (const m of allMoves) {
      const prior = priorMap.get(`${m.symbol}:${m.moveType}`);
      if (prior) m.priorDecision = prior;
    }

    const actionMoves = allMoves.filter(m => !['HOLD', 'HOLD_ADVISORY'].includes(m.moveType));
    const holdMoves   = allMoves.filter(m =>  ['HOLD', 'HOLD_ADVISORY'].includes(m.moveType));

    // ── Watchlist candidates ──────────────────────────────────────────────────
    // inScope: false excludes regression/test tickers (e.g. evaluator-prompt
    // validation set) that are outside the circle of competence — they should
    // never surface as "Open <symbol>" promotions.
    const watchlistTickers = await prisma.ticker.findMany({
      where: { status: 'watchlist', inScope: { not: false } },
    });

    // Eligibility pass only — sizing happens after, once we know how many
    // candidates are actually competing for each barbell pool (see below).
    const eligible = { est: [], spec: [] };

    for (const wt of watchlistTickers) {
      const a = await prisma.analysis.findFirst({
        where:   { transcript: { tickerId: wt.id } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          thesisHealth: true, recommendation: true, finalAction: true,
          trajectory: true, recommendedSize: true, tier: true,
          transcript: { select: { callDate: true } },
        },
      });
      if (!a) continue;

      const action = a.finalAction ?? a.recommendation ?? '—';
      if (!['Add', 'Hold'].includes(action)) continue;
      if (['Broken', 'Weakening'].includes(a.thesisHealth) && action !== 'Add') continue;

      const score = scoreCandidate(a, wt.type);
      const side  = barbellSide(wt, a);

      eligible[side].push({
        tickerId: wt.id, symbol: wt.symbol, shortName: wt.shortName ?? wt.name,
        type: wt.type, tier: wt.tierOverride ?? a.tier ?? null,
        side, thesisHealth: a.thesisHealth, finalAction: action,
        trajectory: a.trajectory ?? null, recommendedSize: a.recommendedSize ?? null,
        rankScore: score, latestCallDate: a.transcript?.callDate ?? null,
        hardCapPct: wt.capPercent,
      });
    }

    // Dynamic pool division: divide each side's pool by however many
    // candidates are actually eligible (capped at the Admin target count),
    // not always the fixed target count. A candidate that still can't clear
    // minPositionDollar after concentrating the pool is dropped and the pool
    // is re-divided among the survivors — so a thin candidate list doesn't
    // silently orphan capital, it just makes each remaining position bigger.
    // If nothing on a side ever clears the floor, that side's pool share
    // goes unallocated (reported, not hidden) rather than force-filled with
    // weak names or diluted equally.
    function sizeSide(list, poolPct, targetCount) {
      let active = list.slice();
      for (;;) {
        const poolCount  = Math.min(targetCount, active.length);
        if (poolCount === 0) return [];
        const baseWeight = poolPct / poolCount;
        const sized = active.map(c => {
          const rawWeight       = baseWeight * (c.type === 'B' ? 1.5 : 1.0);
          const suggestedPct    = +Math.min(rawWeight, c.hardCapPct ?? 100).toFixed(1);
          const suggestedDollar = +(totalPortfolioValue * (suggestedPct / 100)).toFixed(0);
          return { ...c, suggestedPct, suggestedDollar };
        });
        const survivors = sized.filter(c => c.suggestedDollar >= minPositionDollar);
        if (survivors.length === active.length) return survivors; // converged
        if (survivors.length === 0) return []; // pool too small for this side, period
        active = survivors; // shrink and re-divide the pool among fewer, bigger positions
      }
    }

    const candidates = [
      ...sizeSide(eligible.est,  estPoolPct,  targetEstIndividual),
      ...sizeSide(eligible.spec, specPoolPct, targetSpecIndividual),
    ];

    candidates.sort((a, b) => b.rankScore - a.rankScore);
    // Throttling by conviction rank is no longer applied here — every
    // eligible, model-sized candidate surfaces as a recommended open. The
    // human filters via accept/decline per row, not an algorithmic top-N
    // pre-selection (matches how existing-position ADD/TRIM moves already
    // work — the engine proposes the full model-compliant move, the owner
    // disposes).
    const finalCandidates = candidates;

    // ── Capital flow ──────────────────────────────────────────────────────────
    const trimMoves = actionMoves.filter(m =>
      ['EXIT', 'TRIM_CAP', 'TRIM_RATCHET', 'TRIM_MODEL', 'TRIM_SIGNAL'].includes(m.moveType));
    const addMoves  = actionMoves.filter(m => m.moveType === 'ADD').map(m => ({
      label: `Add ${m.symbol}`, dollarNeeded: m.dollarAmount, type: 'add_existing', symbol: m.symbol,
    }));
    const promUses  = finalCandidates.filter(c => c.finalAction === 'Add').map(c => ({
      label: `Open ${c.symbol}`, dollarNeeded: c.suggestedDollar, type: 'promote', symbol: c.symbol,
    }));

    const capitalFlow = buildCapitalFlow(trimMoves, addMoves, promUses, freeCash);

    // ── Barbell actuals ────────────────────────────────────────────────────────
    let estValue = 0, specValue = 0;
    for (const [tickerId, { ticker, positions }] of byTicker.entries()) {
      const a   = analysisMap.get(tickerId);
      const { mktValue } = positionMetrics(positions, totalPortfolioValue);
      const side = barbellSide(ticker, a);
      if (side === 'est')  estValue  += mktValue;
      if (side === 'spec') specValue += mktValue;
    }
    const classifiedTotal  = estValue + specValue;
    const estPct  = classifiedTotal > 0 ? (estValue  / classifiedTotal) * 100 : null;
    const specPct = classifiedTotal > 0 ? (specValue / classifiedTotal) * 100 : null;
    const specTarget  = (1 - estSpecRatio) * 100;
    const barbellOk   = specPct == null || Math.abs(specPct - specTarget) <= 7;

    // ── Warnings ──────────────────────────────────────────────────────────────
    const warnings = [];
    actionMoves.filter(m => m.requires48h).forEach(m => warnings.push({
      type: '48h_wait', symbol: m.symbol, severity: 'yellow',
      message: `${m.symbol} at ${m.currentPct.toFixed(1)}% — 48-hour review required before confirming hold`,
    }));
    if (!barbellOk && specPct != null) warnings.push({
      type: 'barbell', symbol: null, severity: 'amber',
      message: `Portfolio is ${specPct.toFixed(0)}% speculative vs ${specTarget.toFixed(0)}% target`,
    });
    if (capitalFlow.queue.length > 0 && byTicker.size + capitalFlow.queue.filter(u => u.type === 'promote').length > maxPositions) {
      warnings.push({ type: 'max_positions', symbol: null, severity: 'amber',
        message: `Executing all queued promotions would exceed ${maxPositions}-position limit` });
    }
    if (estPoolPct <= 0) warnings.push({ type: 'pool_exhausted', symbol: null, severity: 'amber',
      message: 'ETF allocations have consumed the full EST pool — trim ETFs to make room for individual names' });
    if (specPoolPct <= 0) warnings.push({ type: 'pool_exhausted', symbol: null, severity: 'amber',
      message: 'Commodity/crypto allocations have consumed the full SPEC pool — trim them to make room for individual names' });

    const enoughNumber = profile.enoughNumber ?? null;
    if (enoughNumber && totalPortfolioValue >= enoughNumber) warnings.push({
      type: 'enough_number', symbol: null, severity: 'amber',
      message: `Portfolio (${money(totalPortfolioValue)}) has reached the enough number (${money(enoughNumber)}) — consider transitioning to passive allocation`,
    });

    // ── Per-account position count warnings ───────────────────────────────────
    // These fire only when no AccountPositionConfig exists for the account
    // (i.e. the user has not yet acknowledged/set a target for it).
    const M_DEFAULT = 10; // default per-account position ceiling

    for (const acct of accounts) {
      if (!acct.managed) continue;
      const acctConfig = acctConfigMap.get(acct.id);
      // Suppress only when user has set a meaningful target (not a null-value placeholder row)
      if (acctConfig?.minPositions != null) continue;

      // Count active positions with open lots in this account
      const currentCount = acct.positions.filter(p =>
        (p.lots || []).reduce((s, l) => s + l.shares, 0) > 0
      ).length;

      // Account value
      const posValue = acct.positions.reduce((sum, pos) => {
        const shares = (pos.lots || []).reduce((s, l) => s + l.shares, 0);
        return sum + shares * (pos.lastPrice ?? 0);
      }, 0);
      const acctValue = posValue + (acct.cashBalance ?? 0);
      const acctPct   = totalPortfolioValue > 0 ? acctValue / totalPortfolioValue : 0;

      const supportedCount = Math.floor(acctValue / minPositionDollar);
      const M = M_DEFAULT;

      // Warning 1: too few positions for account size
      if (supportedCount > 0 && currentCount < supportedCount && currentCount < M) {
        const suggestedTarget = Math.min(supportedCount, M);
        warnings.push({
          type:           'too_few_positions',
          severity:       'amber',
          accountId:      acct.id,
          accountName:    acct.name,
          accountType:    acct.type,
          currentCount,
          supportedCount,
          suggestedTarget,
          message: `${acct.name} has ${currentCount} position${currentCount !== 1 ? 's' : ''} but could support up to ${suggestedTarget} at its current value (${money(acctValue)}). Consider adding ${suggestedTarget - currentCount} more from the conviction list.`,
          actionType:    'update_position_target',
          actionPayload: { owner, accountId: acct.id, suggestedTarget },
        });
      }

      // Warning 2: account over-concentrated in portfolio
      if (acctPct > 0.40 && currentCount < M) {
        const suggestedTarget = Math.min(Math.max(currentCount + 2, supportedCount), M);
        warnings.push({
          type:           'over_concentrated_account',
          severity:       'amber',
          accountId:      acct.id,
          accountName:    acct.name,
          accountType:    acct.type,
          currentCount,
          acctPct:        +(acctPct * 100).toFixed(1),
          suggestedTarget,
          message: `${acct.name} represents ${(acctPct * 100).toFixed(0)}% of your total portfolio with only ${currentCount} position${currentCount !== 1 ? 's' : ''}. Consider raising its position target to reduce concentration risk.`,
          actionType:    'update_position_target',
          actionPayload: { owner, accountId: acct.id, suggestedTarget },
        });
      }
    }

    // ── Account summaries (for bucket UI) ────────────────────────────────────
    const TYPE_ORDER = { roth: 0, ira: 1, taxable: 2, custodial: 3 };
    const accountSummaries = accounts
      .sort((a, b) => (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9))
      .map(acct => {
        const posValue = acct.positions.reduce((sum, pos) => {
          const shares = (pos.lots || []).reduce((s, l) => s + l.shares, 0);
          return sum + shares * (pos.lastPrice ?? 0);
        }, 0);
        return {
          id:          acct.id,
          name:        acct.name,
          type:        acct.type,
          managed:     acct.managed,
          cashBalance: +(acct.cashBalance ?? 0).toFixed(2),
          marketValue: +posValue.toFixed(2),
        };
      });

    return {
      owner, displayName: profile.displayName ?? owner,
      totalPortfolioValue: +totalPortfolioValue.toFixed(2),
      totalMktValue:       +totalMktValue.toFixed(2),
      totalCash:           +totalCash.toFixed(2),
      cashReserveFloor:    +cashReserveFloor.toFixed(2),
      freeCash:            +freeCash.toFixed(2),
      accountSummaries,
      positionCount:       byTicker.size,
      maxPositions,
      barbellStatus: {
        estPct:    estPct  != null ? +estPct.toFixed(1)  : null,
        specPct:   specPct != null ? +specPct.toFixed(1) : null,
        estTarget:  +(estSpecRatio * 100).toFixed(0),
        specTarget: +specTarget.toFixed(0),
        inBalance:  barbellOk,
        estPoolPct:  +estPoolPct.toFixed(1),
        specPoolPct: +specPoolPct.toFixed(1),
      },
      moves:               actionMoves,
      advisories:          holdMoves.filter(m => m.moveType === 'HOLD_ADVISORY'),
      holds:               holdMoves.filter(m => m.moveType === 'HOLD').map(h => ({
        symbol: h.symbol, shortName: h.shortName, bucket: h.bucket,
        thesisHealth: h.thesisHealth, finalAction: h.finalAction,
        trajectory: h.trajectory, tier: h.tier,
        currentPct: h.currentPct, targetPct: h.targetPct, currentMktValue: h.currentMktValue,
      })),
      watchlistCandidates: finalCandidates,
      capitalFlow,
      warnings,
    };
}

// ─── GET /api/moves/:owner ────────────────────────────────────────────────────
// Cache-first: serve from MovesCache if available, compute on first miss.

router.get('/:owner', async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  if (!enforceOwner(req, res, owner)) return;
  try {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    // Check cache
    const cached = await prisma.movesCache.findUnique({ where: { owner } });
    if (cached) {
      return res.json({ ...cached.payload, fromCache: true, computedAt: cached.computedAt });
    }

    // Cache miss — compute, store, return
    const payload    = await computeMovesPayload(owner);
    const computedAt = new Date();
    await prisma.movesCache.upsert({
      where:  { owner },
      update: { payload, computedAt },
      create: { owner, payload, computedAt },
    });
    res.json({ ...payload, fromCache: false, computedAt });
  } catch (err) {
    console.error(`GET /moves/${owner} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// ─── POST /api/moves/:owner/refresh ──────────────────────────────────────────
// Force recompute — called by price refresh, Schwab sync, and manual UI button.

router.post('/:owner/refresh', requireAuth(), async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  if (!enforceOwner(req, res, owner)) return;
  try {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    const payload     = await computeMovesPayload(owner);
    const computedAt  = new Date();
    await prisma.movesCache.upsert({
      where:  { owner },
      update: { payload, computedAt },
      create: { owner, payload, computedAt },
    });
    console.log(`[movesCache] refreshed for ${owner}`);
    res.json({ ...payload, fromCache: false, computedAt });
  } catch (err) {
    console.error(`POST /moves/${owner}/refresh error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /api/moves/:owner/account-configs ────────────────────────────────────
// Returns all accounts for this owner with their AccountPositionConfig (if any).
// Used by the Admin tab per-account config UI.

router.get('/:owner/account-configs', requireAuth(), async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  if (!enforceOwner(req, res, owner)) return;

  try {
    const accounts = await prisma.account.findMany({
      where:   { owner },
      include: { positionConfig: true },
      orderBy: { name: 'asc' },
    });
    res.json(accounts.map(a => ({
      id:          a.id,
      name:        a.name,
      type:        a.type,
      managed:     a.managed,
      cashBalance: a.cashBalance ?? 0,
      config: a.positionConfig ? {
        minPositions: a.positionConfig.minPositions,
        maxPositions: a.positionConfig.maxPositions,
      } : null,
    })));
  } catch (err) {
    console.error(`GET /moves/${owner}/account-configs error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// ─── PATCH /api/moves/:owner/account-config ───────────────────────────────────
// Accept action for position-count warning cards, and Admin tab manual edits.
// Upserts AccountPositionConfig with min/max positions, invalidates moves cache.

router.patch('/:owner/account-config', requireAuth(), async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  if (!enforceOwner(req, res, owner)) return;

  const { accountId, suggestedTarget, maxPositions } = req.body;
  if (!accountId) {
    return res.status(400).json({ error: 'accountId is required' });
  }

  const minPos = suggestedTarget != null ? parseInt(suggestedTarget) : undefined;
  const maxPos = maxPositions    != null ? parseInt(maxPositions)    : undefined;

  // Build update/create data — only set fields that were provided
  const updateData = {};
  if (minPos != null && !isNaN(minPos)) updateData.minPositions = minPos;
  if (maxPos != null && !isNaN(maxPos)) updateData.maxPositions = maxPos;

  // Don't write an empty row — nothing to suppress if no values provided
  if (Object.keys(updateData).length === 0) {
    return res.status(400).json({ error: 'At least one of minPositions or maxPositions is required' });
  }

  try {
    // Verify the account belongs to this owner
    const account = await prisma.account.findFirst({ where: { id: accountId, owner } });
    if (!account) return res.status(404).json({ error: 'Account not found' });

    await prisma.accountPositionConfig.upsert({
      where:  { accountId },
      update: updateData,
      create: { accountId, ...updateData },
    });

    // Re-fetch the config to return current values
    const config = await prisma.accountPositionConfig.findUnique({ where: { accountId } });

    // Invalidate cache so the warning disappears on next load
    await prisma.movesCache.deleteMany({ where: { owner } });

    res.json({ ok: true, accountId, minPositions: config.minPositions, maxPositions: config.maxPositions });
  } catch (err) {
    console.error(`PATCH /moves/${owner}/account-config error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// ─── DELETE /api/moves/:owner/account-config/:accountId ───────────────────────
// Resets per-account position config. Warning will reappear on next load.

router.delete('/:owner/account-config/:accountId', requireAuth(), async (req, res) => {
  const owner     = decodeURIComponent(req.params.owner);
  const accountId = parseInt(req.params.accountId);
  if (!enforceOwner(req, res, owner)) return;

  try {
    const account = await prisma.account.findFirst({ where: { id: accountId, owner } });
    if (!account) return res.status(404).json({ error: 'Account not found' });

    await prisma.accountPositionConfig.deleteMany({ where: { accountId } });
    await prisma.movesCache.deleteMany({ where: { owner } });

    res.json({ ok: true });
  } catch (err) {
    console.error(`DELETE /moves/${owner}/account-config/${accountId} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// Inline money formatter for warning messages
function money(n) {
  if (n == null) return '—';
  return '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

module.exports = router;
module.exports.computeMovesPayload = computeMovesPayload;

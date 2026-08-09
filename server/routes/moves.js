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

// Top-level 4-bucket allocation target (2026-08-08 design) — must sum to 1.0.
// Mirrors client/src/pages/Admin.jsx DEFAULTS. User-owned; independent of
// yearsToGoal/riskTolerance by design (see docs/handoffs or memory for the
// 2026-08-08 design discussion — not tied to time horizon on purpose).
const DEFAULT_EQUITIES_TARGET  = 0.50;
const DEFAULT_ETF_TARGET       = 0.20;
const DEFAULT_CRYPTO_TARGET    = 0.15;
const DEFAULT_COMMODITY_TARGET = 0.15;
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

    // Normalize so the group sums to its FAIR SHARE of the pool
    // (baseWeightPct * group.length), not the full poolPct — rescaling to
    // poolPct unconditionally defeats the whole point of `denom` above: with
    // fewer holdings than targetCount, this group should only claim
    // group.length/denom of the pool, leaving the rest genuinely reserved for
    // new opens. (Caught 2026-08-08 via re-baseline: rescaling to poolPct
    // meant existing holdings alone always consumed the entire established
    // pool, so new opens' allocation — sized separately — was pure double
    // counting on top, not a fair split.) When group.length >= targetCount,
    // denom = group.length, so fairShareSum reduces to exactly poolPct —
    // unchanged from before in that case.
    const fairShareSum = baseWeightPct * group.length;
    const rawSum = raws.reduce((s, r) => s + r.raw, 0);
    const scale  = rawSum > 0 ? fairShareSum / rawSum : 1;

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

/**
 * Routes a brand-new position (no existing Position rows for this ticker,
 * e.g. a watchlist candidate) across the owner's managed accounts by cash
 * availability and account-type priority (Roth -> IRA -> taxable ->
 * custodial) — same priority order as buildAddRouting, but without the
 * "prefers an account that already holds shares" tie-break (nothing holds
 * this ticker yet) and without a share count, since there's no live price
 * for an un-held ticker. Account routing never actually depended on price —
 * only the dollars-to-shares conversion within a row did — so this doesn't
 * need to wait on the live-quote-fetch work to be useful.
 *
 * @param {Array} accounts   raw account rows (same shape used elsewhere in
 *                           computeMovesPayload — .id, .name, .type,
 *                           .managed, .cashBalance)
 * @param {number} dollarAmount
 */
function buildNewPositionRouting(accounts, dollarAmount) {
  if (!dollarAmount || dollarAmount <= 0) return [];

  const TYPE_ORDER = { roth: 0, ira: 1, taxable: 2, custodial: 3 };
  const managed = accounts
    .filter(a => a.managed)
    .sort((a, b) => (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9));

  let remaining = dollarAmount;
  const rows = [];

  for (const acct of managed) {
    if (remaining <= 0) break;
    const cash = acct.cashBalance ?? 0;
    if (cash < 1) continue;
    const allocate = Math.min(remaining, cash);
    rows.push({
      accountId:        acct.id,
      accountName:      acct.name ?? '—',
      accountType:      acct.type ?? '—',
      isTaxAdvantaged:  ['ira', 'roth'].includes(acct.type),
      sharesToBuy:      null, // no live price for a not-yet-held ticker
      dollarAmount:     +allocate.toFixed(2),
      insufficientCash: false,
    });
    remaining -= allocate;
  }

  // No cash anywhere — still surface the best (highest-priority) account so
  // the user knows where this would go once funded, same fallback pattern
  // as buildAddRouting.
  if (rows.length === 0 && managed.length > 0) {
    const best = managed[0];
    rows.push({
      accountId:        best.id,
      accountName:      best.name ?? '—',
      accountType:      best.type ?? '—',
      isTaxAdvantaged:  ['ira', 'roth'].includes(best.type),
      sharesToBuy:      null,
      dollarAmount:     +dollarAmount.toFixed(2),
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
  profile, ownerTaxRates, bypassWinnerProtection = false
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
    // Thesis Strengthening above model weight: advisory (let winner run toward hard
    // cap) — UNLESS this is a re-baseline pass (bypassWinnerProtection), where the
    // user has explicitly asked to reset to target regardless of momentum. See
    // memory/small_account_diversification.md, "re-baseline bypasses the
    // Strengthening exception" (2026-08-08 design decision).
    const isWinnerRunning = !bypassWinnerProtection && finalAction === 'Add' && thesisHealth === 'Strengthening'
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

async function computeMovesPayload(owner, options = {}) {
    // bypassWinnerProtection: true only for an explicit, user-triggered
    // re-baseline pass (see memory/small_account_diversification.md). Every
    // other caller (the everyday GET /api/moves, the cache refresh, schwab
    // sync hooks) leaves this false, preserving the "let a Strengthening
    // thesis run to its hard cap" protection.
    const bypassWinnerProtection = options.bypassWinnerProtection === true;

    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) throw new Error(`Owner "${owner}" not found`);

    const cashReservePct    = profile.cashReservePct    ?? DEFAULT_CASH_RESERVE;
    // Cash is a top-level bucket alongside Equities/ETF/Crypto/Commodities —
    // all five Admin-entered targets are already expressed as a % of TOTAL
    // portfolio value and must sum to 100 (enforced in the Admin UI and the
    // re-baseline modal). No additional scaling is applied here; previously
    // Equities/ETF/Crypto/Commodities were treated as % of *deployable*
    // (post-cash) capital and scaled by (1 - cashReservePct), which made the
    // on-screen bucket inputs sum to 100 while excluding cash — confusing,
    // since cash was still being carved out underneath. Changed 2026-08-09.
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
    // Fired concurrently (Promise.all), not awaited one at a time — this loop
    // is one DB round trip per held ticker, and over a remote Postgres
    // connection (Railway proxy) that adds up fast. Re-baseline exposed this:
    // it recomputes from scratch twice per confirm (no cache to hide behind),
    // so a slow sequential loop here is felt directly as multi-second latency.
    const tickerIds = [...byTicker.keys()];
    const analysisResults = await Promise.all(tickerIds.map(tickerId =>
      prisma.analysis.findFirst({
        where:   { transcript: { tickerId } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          id: true, thesisHealth: true, recommendation: true,
          recommendedSize: true, capPercent: true, ratchetTranche: true,
          trajectory: true, finalAction: true, tier: true,
          transcript: { select: { callDate: true } },
        },
      })
    ));
    const analysisMap = new Map(tickerIds.map((id, i) => [id, analysisResults[i] ?? null]));

    // ── Classify positions ────────────────────────────────────────────────────
    const fixedGroups      = [];  // ETF / commodity / crypto
    const individualGroups = [];  // equity individual stocks

    for (const [tickerId, { ticker, positions }] of byTicker.entries()) {
      const latestAnalysis = analysisMap.get(tickerId);
      const group = { ticker, positions, latestAnalysis };
      if (isFixedTarget(ticker)) fixedGroups.push(group);
      else individualGroups.push(group);
    }

    // ── Top-level allocation targets (2026-08-08 design) ────────────────────────
    // Equities / ETF / Crypto / Commodities are independent top-level targets
    // set directly in Admin (OwnerProfile.equitiesTargetPct etc.) — no longer
    // derived bottom-up from summing whatever per-ticker capPercent happens to
    // be configured on currently-held tickers. estSpecRatio only sub-splits
    // the Equities pool into established vs speculative; it no longer touches
    // ETF/crypto/commodity sizing at all. Per-ticker capPercent is demoted to
    // an in-bucket ceiling (see splitBucketTarget below), not the bucket's
    // source of truth for total size.
    // Raw Admin inputs are already % of TOTAL portfolio value (cash included
    // in the same 100%) — used as-is by every downstream consumer (individual
    // equity weights, fixed-bucket splits, bucket-level ADD moves, and the
    // summary display).
    const equitiesTargetPct  = (profile.equitiesTargetPct    ?? DEFAULT_EQUITIES_TARGET)  * 100;
    const etfTargetPct       = (profile.etfTargetPct         ?? DEFAULT_ETF_TARGET)       * 100;
    const cryptoTargetPct    = (profile.cryptoTargetPct      ?? DEFAULT_CRYPTO_TARGET)    * 100;
    const commodityTargetPct = (profile.commoditiesTargetPct ?? DEFAULT_COMMODITY_TARGET) * 100;

    const estPoolPct  = equitiesTargetPct * estSpecRatio;
    const specPoolPct = equitiesTargetPct * (1 - estSpecRatio);

    // Equity headcount is now fully decoupled from ETF/crypto/commodity
    // holdings — maxPositions governs established+speculative equity count
    // only. (Previously subtracted currently-held fixed-target ticker count
    // from the equity slot budget, which coupled headcount to whatever
    // ETFs/crypto happened to be held — a symptom of the old bottom-up model,
    // not something worth preserving.)
    const targetIndividual = Math.max(0, maxPositions);
    const targetEstIndividual  = Math.round(targetIndividual * estSpecRatio);
    const targetSpecIndividual = targetIndividual - targetEstIndividual;

    // Splits a bucket's top-level target evenly across its currently-held
    // tickers, then applies each ticker's own configured capPercent (if any)
    // strictly as a ceiling — not as the bucket's source of truth. This is an
    // interim simplification for the (uncommon) case of multiple tickers in
    // one ETF/crypto/commodity bucket; which specific ticker to hold, and how
    // to weight several of them, stays outside the agent's scope per the
    // 2026-08-08 design discussion (ticker selection within these buckets is
    // the user's call, not the allocator's).
    function splitBucketTarget(groups, bucketTargetPct) {
      const map = new Map();
      if (groups.length === 0) return map;
      const evenShare = bucketTargetPct / groups.length;
      for (const g of groups) {
        const configuredCap = ownerCapMap.get(g.ticker.id) ?? g.ticker.capPercent ?? null;
        map.set(g.ticker.id, configuredCap != null ? Math.min(evenShare, configuredCap) : evenShare);
      }
      return map;
    }
    const fixedTargetMap = new Map([
      ...splitBucketTarget(fixedGroups.filter(g => isETF(g.ticker)), etfTargetPct),
      ...splitBucketTarget(fixedGroups.filter(g => isCommodityOrCrypto(g.ticker) && getBucket(g.ticker) === 'crypto'), cryptoTargetPct),
      ...splitBucketTarget(fixedGroups.filter(g => isCommodityOrCrypto(g.ticker) && getBucket(g.ticker) === 'commodity'), commodityTargetPct),
    ]);

    // ── Model weights ─────────────────────────────────────────────────────────
    const modelWeights = computeIndividualModelWeights(
      individualGroups,
      estPoolPct, specPoolPct,
      targetEstIndividual, targetSpecIndividual
    );

    // ── Generate moves ─────────────────────────────────────────────────────────
    const allMoves = [];

    // Fixed-target assets (inject top-down bucket target, split across
    // currently-held tickers in that bucket — see splitBucketTarget above)
    for (const g of fixedGroups) {
      const tickerWithOwnerCap = { ...g.ticker, capPercent: fixedTargetMap.get(g.ticker.id) ?? effectiveCap(g.ticker) };
      const move = generateFixedTargetMove(
        tickerWithOwnerCap, g.positions, totalPortfolioValue, g.latestAnalysis, ownerTaxRates
      );
      allMoves.push(move);
    }

    // Bucket-level ADD for an under-target ETF/Crypto/Commodity bucket with no
    // specific ticker to recommend — picking which ETF/crypto/commodity to
    // buy is explicitly outside the agent's scope (2026-08-08 design, see
    // memory/small_account_diversification.md). Only surfaced during a
    // re-baseline pass: the everyday engine doesn't proactively nag about
    // opening a bucket the user hasn't started, only re-baseline's "here's
    // your full target vs. current, both trims and adds" view does.
    if (bypassWinnerProtection) {
      const fixedBuckets = [
        { key: 'etf',       label: 'ETF',          targetPct: etfTargetPct,       groups: fixedGroups.filter(g => isETF(g.ticker)) },
        { key: 'crypto',    label: 'Crypto',       targetPct: cryptoTargetPct,    groups: fixedGroups.filter(g => getBucket(g.ticker) === 'crypto') },
        { key: 'commodity', label: 'Commodities',  targetPct: commodityTargetPct, groups: fixedGroups.filter(g => getBucket(g.ticker) === 'commodity') },
      ];
      for (const b of fixedBuckets) {
        const currentValue = b.groups.reduce((s, g) => s + positionMetrics(g.positions, totalPortfolioValue).mktValue, 0);
        const targetValue  = totalPortfolioValue * (b.targetPct / 100);
        // achievableValue is what the CURRENTLY-HELD tickers can reach at
        // their own per-ticker caps (fixedTargetMap, computed above via
        // splitBucketTarget) — not their raw current mkt value. Comparing
        // against raw currentValue understates the gap whenever held
        // tickers are individually capped below an even split of the
        // bucket target: e.g. two ETFs each capped at 10% can only ever
        // reach 20% combined even if a 25% bucket target is currently
        // "covered" on paper because both are temporarily overweight and
        // about to be trimmed down to their caps. Caught 2026-08-09 via
        // recon into Established/Speculative shortfall — same pattern
        // showed up here for Eduardo's ETF bucket (QQQ+TMFC both capped at
        // 10%, so 20% max achievable vs. a 25% target, with no ADD row to
        // flag the unreachable 5%).
        //
        // But the capped target is only actually reachable when the ticker
        // is OVER its cap — a real TRIM lands it exactly there. When a
        // ticker is UNDER its cap, nothing moves it up:
        // generateFixedTargetMove has no ADD branch (ticker selection for
        // these buckets is outside agent scope — see the reason string
        // below), so an under-cap ticker just HOLDs at its current value.
        // Assuming it contributes its full capped amount overstates
        // achievableValue and understates the "(unallocated)" gap shown to
        // the user. Math.min(currentValue, cappedTarget) picks whichever
        // actually applies: the cap when over (soon-to-be-trimmed there),
        // the current value when under (nothing will move it). Caught
        // 2026-08-09 via server/scripts/verify-allocation-math.sh's first
        // production run — see wrap-ups/fix-fixed-bucket-undercap-achievable-out.md.
        const achievableValue = b.groups.reduce((s, g) => {
          const cappedTarget = (fixedTargetMap.get(g.ticker.id) ?? 0) / 100 * totalPortfolioValue;
          const tickerCurrentValue = positionMetrics(g.positions, totalPortfolioValue).mktValue;
          return s + Math.min(tickerCurrentValue, cappedTarget);
        }, 0);
        const shortfall    = targetValue - achievableValue;
        if (shortfall > minPositionDollar) {
          const currentPct = totalPortfolioValue > 0 ? (currentValue / totalPortfolioValue) * 100 : 0;
          allMoves.push({
            moveType: 'ADD', priority: 5, symbol: null, shortName: `${b.label} (unallocated)`,
            bucket: b.key, tier: null, thesisHealth: '—', finalAction: '—', trajectory: null,
            ratchetTranche: 0, currentPct: +currentPct.toFixed(2), targetPct: +b.targetPct.toFixed(1),
            hardCapPct: +b.targetPct.toFixed(1), currentMktValue: +currentValue.toFixed(2),
            dollarAmount: +shortfall.toFixed(2), sharesApprox: 0, taxCost: 0, netProceeds: 0,
            currentShares: null, targetShares: null, targetValue: +targetValue.toFixed(2),
            accounts: [], requires48h: false, isBucketLevel: true,
            reason: `${b.label} at ${currentPct.toFixed(1)}% — held tickers are capped below the ${b.targetPct.toFixed(1)}% target (per-ticker caps leave ${shortfall > 0 ? 'room' : 'no room'} unclaimed). Pick a specific ${b.label.toLowerCase()} ticker to fund this (outside agent scope).`,
          });
        }
      }
    }

    // Individual stocks
    for (const g of individualGroups) {
      const modelWeightPct = modelWeights.get(g.ticker.id) ?? 0;
      // Inject per-owner cap so generateMovesForTicker uses it for hardCapPct
      const tickerWithOwnerCap = { ...g.ticker, capPercent: effectiveCap(g.ticker) };
      const moves = generateMovesForTicker(
        tickerWithOwnerCap, g.positions, totalPortfolioValue,
        g.latestAnalysis, modelWeightPct, profile, ownerTaxRates, bypassWinnerProtection
      );
      allMoves.push(...moves);
    }

    // Sort by priority
    allMoves.sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority;
      return b.dollarAmount - a.dollarAmount;
    });

    // ── Derive current/target share counts AND dollar values ────────────────
    // All move builders already compute currentMktValue, pricePerShare, and
    // sharesApprox (the size of the delta) — this generically derives both
    // before/after share counts and before/after dollar values from those,
    // instead of duplicating the math per move type. ADD moves toward more
    // shares/value, everything else (TRIM*, EXIT) moves toward fewer/less.
    // HOLD_ADVISORY has sharesApprox 0 and dollarAmount 0, so target ==
    // current either way, correctly showing no change.
    //
    // targetValue (dollars) is the one guaranteed to exist for every row,
    // including brand-new opens with no live price — currentShares/
    // targetShares are null in that case (no price to derive a share count
    // from). The Moves table renders targetValue as the primary column so
    // units stay consistent across every row; share counts are kept in the
    // payload for later use (e.g. once a live quote is fetched at
    // ticket-generation time) but aren't the table's source of truth.
    // isBucketLevel rows (fixed-target "(unallocated)" and scarcity-gap rows)
    // set their own targetValue explicitly, below/above — their dollarAmount
    // isn't "how much more to add to reach currentMktValue + dollarAmount",
    // it's a structural shortfall against the bucket's own target, so the
    // generic current±delta derivation produces a nonsensical number for
    // them (caught 2026-08-09: e.g. ETF unallocated showed $9,420.54 here
    // instead of the real 30% target of $9,436.29).
    for (const m of allMoves) {
      if (m.isBucketLevel) continue;
      const hasPrice       = m.pricePerShare > 0;
      const currentShares  = hasPrice ? m.currentMktValue / m.pricePerShare : 0;
      const delta          = m.sharesApprox ?? 0;
      m.currentShares = hasPrice ? +currentShares.toFixed(3) : null;
      m.targetShares  = hasPrice ? +(m.moveType === 'ADD' ? currentShares + delta : currentShares - delta).toFixed(3) : null;
      m.targetValue   = +(m.moveType === 'ADD' ? m.currentMktValue + m.dollarAmount : m.currentMktValue - m.dollarAmount).toFixed(2);
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

    let actionMoves  = allMoves.filter(m => !['HOLD', 'HOLD_ADVISORY'].includes(m.moveType));
    const holdMoves  = allMoves.filter(m =>  ['HOLD', 'HOLD_ADVISORY'].includes(m.moveType));

    // ── Watchlist candidates ──────────────────────────────────────────────────
    // inScope: false excludes regression/test tickers (e.g. evaluator-prompt
    // validation set) that are outside the circle of competence — they should
    // never surface as "Open <symbol>" promotions.
    //
    // Ticker.status is global (shared across all owners), not owner-specific
    // — a ticker can still say "watchlist" even after THIS owner has a real
    // position in it (e.g. before the next Schwab-sync auto-promotion runs,
    // or if another owner's sync hasn't touched it). Excluding anything
    // already in this owner's byTicker map prevents recommending a "new
    // open" for a ticker already held — which would double-count it and
    // crowd a real candidate out of the sized/ranked slots.
    const watchlistTickers = (await prisma.ticker.findMany({
      where: { status: 'watchlist', inScope: { not: false } },
    })).filter(wt => !byTicker.has(wt.id));

    // Eligibility pass only — sizing happens after, once we know how many
    // candidates are actually competing for each barbell pool (see below).
    // Analysis lookups fire concurrently (Promise.all) rather than one at a
    // time — same reasoning as the held-ticker loop above.
    const eligible = { est: [], spec: [] };

    const watchlistAnalyses = await Promise.all(watchlistTickers.map(wt =>
      prisma.analysis.findFirst({
        where:   { transcript: { tickerId: wt.id } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          thesisHealth: true, recommendation: true, finalAction: true,
          trajectory: true, recommendedSize: true, tier: true,
          transcript: { select: { callDate: true } },
        },
      })
    ));

    for (let i = 0; i < watchlistTickers.length; i++) {
      const wt = watchlistTickers[i];
      const a  = watchlistAnalyses[i];
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

    // Dynamic pool division: cap each side to its best `targetCount`
    // candidates by rank FIRST (targetCount is the real ceiling — derived
    // from the Admin maxPositions setting — on how many new names this side
    // should carry), then shrink from there if any of those can't individually
    // clear minPositionDollar, re-dividing the pool among the survivors so a
    // thin candidate list doesn't silently orphan capital. Capping the count
    // up front (not just using it as a divisor) matters: without it, every
    // eligible watchlist ticker would get sized as if only targetCount
    // existed but still be returned in full — both overshooting the position
    // count and making individual weights no longer sum to the pool.
    function sizeSide(list, poolPct, targetCount) {
      const ranked = [...list].sort((a, b) => b.rankScore - a.rankScore);
      let active = ranked.slice(0, targetCount);
      for (;;) {
        const poolCount  = Math.min(targetCount, active.length);
        if (poolCount === 0) return [];
        const baseWeight = poolPct / poolCount;
        // Raw weights with the Type A/B multiplier, then RESCALED so the
        // group sums back to poolPct before clamping to individual hard
        // caps — mirrors computeIndividualModelWeights.allocate() (used for
        // existing holdings). Without this rescale, Type B's 1.5x inflates
        // the total past the pool whenever any candidate is Type B — e.g.
        // two Type B candidates at baseWeight 15% each become 22.5% each
        // (45% combined) instead of being rescaled down to fit the pool.
        const raws   = active.map(c => ({ c, raw: baseWeight * (c.type === 'B' ? 1.5 : 1.0) }));
        const rawSum = raws.reduce((s, r) => s + r.raw, 0);
        const scale  = rawSum > 0 ? poolPct / rawSum : 1;
        const sized = raws.map(({ c, raw }) => {
          const suggestedPct    = +Math.min(raw * scale, c.hardCapPct ?? 100).toFixed(1);
          const suggestedDollar = +(totalPortfolioValue * (suggestedPct / 100)).toFixed(0);
          return { ...c, suggestedPct, suggestedDollar };
        });
        const survivors = sized.filter(c => c.suggestedDollar >= minPositionDollar);
        if (survivors.length === active.length) return survivors; // converged — everyone clears the floor
        if (survivors.length > 0) { active = survivors; continue; } // some cleared — re-divide among them
        // Nobody cleared the floor at this split — don't give up outright.
        // Two candidates splitting a small pool can both land under the
        // floor individually while either one alone, with the WHOLE pool,
        // would clear it easily (e.g. $1,988 pool / 2 = ~$994 each, both
        // under a $1,500 floor, but $1,988 for just the top-ranked one is
        // comfortably above it). Drop only the single worst-ranked
        // candidate and retry with one fewer, rather than assuming the
        // pool can't support anyone.
        if (active.length === 0) return [];
        active = active.slice(0, -1); // ranked worst-last — drop the tail
      }
    }

    // targetEstIndividual/targetSpecIndividual are TOTAL target slot counts
    // (held + new) per side — not just "how many new ones to recommend".
    // Subtract what's already held on each side before capping candidates,
    // so the engine doesn't recommend more opens than could actually fit
    // under maxPositions even before you decide on any of them. Without
    // this, sizeSide's per-side cap alone can still recommend candidates
    // that push held+new past the position limit — which is what the
    // max_positions warning was catching after the fact.
    let heldEst = 0, heldSpec = 0;
    for (const g of individualGroups) {
      const side = barbellSide(g.ticker, g.latestAnalysis);
      if (side === 'est')  heldEst++;
      if (side === 'spec') heldSpec++;
    }
    const remainingEstSlots  = Math.max(0, targetEstIndividual  - heldEst);
    const remainingSpecSlots = Math.max(0, targetSpecIndividual - heldSpec);

    // Existing holdings (computeIndividualModelWeights, above) already claim
    // heldEst/targetEstIndividual of estPoolPct — computeIndividualModelWeights
    // deliberately divides by targetEstIndividual (not heldEst) specifically so
    // it DOESN'T over-fill the pool when there are fewer holdings than slots,
    // leaving room for new opens. New opens are only entitled to what's left:
    // estPoolPct * (remainingEstSlots / targetEstIndividual) — NOT the full
    // estPoolPct divided by remainingEstSlots, which double-counts against
    // existing holdings' share (caught 2026-08-08 via re-baseline: established
    // bucket target was $7,470 but individual EST rows summed to $15,763 —
    // existing holdings and new opens were each being sized against the full
    // pool independently). Scaling here preserves sizeSide's own "push scarce
    // candidates up proportionally" behavior — it still shrinks poolCount to
    // active.length when supply is short — just within the correctly-sized
    // remaining slice instead of the whole pool.
    const remainingEstPoolPct  = targetEstIndividual  > 0 ? estPoolPct  * (remainingEstSlots  / targetEstIndividual)  : 0;
    const remainingSpecPoolPct = targetSpecIndividual > 0 ? specPoolPct * (remainingSpecSlots / targetSpecIndividual) : 0;

    const estCandidates  = sizeSide(eligible.est,  remainingEstPoolPct,  remainingEstSlots);
    const specCandidates = sizeSide(eligible.spec, remainingSpecPoolPct, remainingSpecSlots);
    const candidates = [...estCandidates, ...specCandidates];
    candidates.sort((a, b) => b.rankScore - a.rankScore);

    // Established/Speculative "(unallocated)" scarcity-gap rows — mirrors the
    // ETF/Crypto/Commodity "(unallocated)" block above, but for a different
    // reason: those buckets are short because ticker selection is outside
    // agent scope (user's call); these are short because no held OR eligible
    // watchlist candidate currently clears the conviction bar to fill the
    // remaining pool — a Radar/sourcing gap, not a user-choice gap (hence the
    // separate `isScarcityGap` flag so the frontend can word it differently).
    // Re-baseline-only (bypassWinnerProtection), same as the fixed-bucket
    // block: this is a full current-vs-target reconciliation concept, not
    // something the everyday Moves tab should proactively nag about.
    if (bypassWinnerProtection) {
      const barbellBuckets = [
        { side: 'established', label: 'Established Equities', poolPct: estPoolPct,  heldGroup: individualGroups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'est'),  sideCandidates: estCandidates },
        { side: 'speculative', label: 'Speculative Equities',  poolPct: specPoolPct, heldGroup: individualGroups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'spec'), sideCandidates: specCandidates },
      ];
      // Per-ticker ACHIEVABLE target — the final resting value each held
      // ticker's own move actually lands on (allMoves[*].targetValue, set
      // by the generic derivation loop above from currentMktValue ±
      // dollarAmount), NOT modelWeights.get()'s raw pre-ratchet weight.
      // These differ whenever a ticker's displayed move takes a different
      // path than a plain TRIM_MODEL-to-model-weight — e.g. TRIM_RATCHET
      // (graduated exit ratchet, currentPct × 0.60 for tranche 2) trims
      // further than the raw model weight would. Summing raw model weights
      // overstated heldTargetSum by exactly the ratchet's extra cut,
      // producing an achievableValue that didn't match "once recommended
      // trims/holds are applied" as promised (caught 2026-08-09 via recon
      // — see wrap-ups/recon-spec-achievable-gap-out.md).
      const targetValueBySymbol = new Map(
        allMoves.filter(m => m.symbol != null).map(m => [m.symbol, m.targetValue])
      );
      for (const b of barbellBuckets) {
        const heldValue = b.heldGroup.reduce((s, g) => s + positionMetrics(g.positions, totalPortfolioValue).mktValue, 0);
        const heldTargetSum = b.heldGroup.reduce((s, g) => {
          const displayed = targetValueBySymbol.get(g.ticker.symbol);
          return s + (displayed != null ? displayed : (modelWeights.get(g.ticker.id) ?? 0) / 100 * totalPortfolioValue);
        }, 0);
        const newOpenSum = b.sideCandidates.reduce((s, c) => s + c.suggestedDollar, 0);
        const achievableValue = heldTargetSum + newOpenSum;
        const bucketTargetValue = totalPortfolioValue * (b.poolPct / 100);
        const shortfall = bucketTargetValue - achievableValue;
        if (shortfall > minPositionDollar && b.sideCandidates.length === 0) {
          // Compare against ACHIEVABLE (what held positions' own model
          // weight + any sized new opens land on, post other recommended
          // trims/holds in this bucket), not raw current $/%. Comparing
          // against raw current value reads backwards whenever the bucket
          // is aggregate overweight from a concentrated holding that's
          // simultaneously being trimmed elsewhere (Andrea's case: SPWR
          // trim pulls the bucket toward achievableValue, not away from
          // it) — "at 29.7%, below target of 18.0%" is self-contradictory
          // when 29.7% actually exceeds 18.0%. achievableValue is always
          // <= bucketTargetValue whenever shortfall > 0, by construction,
          // so this framing can't produce that contradiction. This row is
          // still correct to fire even while the bucket is currently
          // overweight: the reserved new-open slot is empty regardless,
          // and stays empty (or gets MORE exposed) once the overweight
          // holding's trim lands — suppressing it until the trim executes
          // would just delay surfacing a real, standing gap. Caught
          // 2026-08-09 — see wrap-ups/fix-scarcity-row-framing-out.md.
          const achievablePct = totalPortfolioValue > 0 ? (achievableValue / totalPortfolioValue) * 100 : 0;
          actionMoves.push({
            moveType: 'ADD', priority: 5, symbol: null, shortName: `${b.label} (unallocated)`,
            bucket: b.side, tier: b.side, thesisHealth: '—', finalAction: '—', trajectory: null,
            ratchetTranche: 0, currentPct: +achievablePct.toFixed(2), targetPct: +b.poolPct.toFixed(1),
            hardCapPct: +b.poolPct.toFixed(1), currentMktValue: +achievableValue.toFixed(2),
            dollarAmount: +shortfall.toFixed(2), sharesApprox: 0, taxCost: 0, netProceeds: 0,
            currentShares: null, targetShares: null, targetValue: +bucketTargetValue.toFixed(2),
            accounts: [], requires48h: false, isBucketLevel: true, isScarcityGap: true,
            reason: `${b.label}: once recommended trims/holds are applied, held positions plus any new opens account for ${achievablePct.toFixed(1)}% against a ${b.poolPct.toFixed(1)}% target — the remaining ${(b.poolPct - achievablePct).toFixed(1)}% has no watchlist candidate that currently clears the conviction bar. Needs new names sourced (Layer 3 / Opportunity Scanner), not a bigger allocation to what's already held.`,
          });
        }
      }
    }

    // Watchlist candidates are folded directly into actionMoves as real ADD
    // moves — not a separate read-only "suggestions" list. A position moves
    // from watchlist to portfolio as a *result* of accepting a move here
    // (you execute the trade, Schwab sync auto-promotes the ticker once it
    // sees a real position — see schwabSync.js `promotedTickers`), not as a
    // prerequisite for the engine recommending it. currentShares/targetShares
    // are left null (no live quote source for a ticker with no position yet).
    // Account routing itself doesn't need a price though — only the
    // dollars-to-shares conversion does — so buildNewPositionRouting fills
    // in accounts by cash + account-type priority alone.
    const openMoves = candidates.map(c => ({
      moveType:        'ADD',
      priority:        6,
      symbol:          c.symbol,
      shortName:       c.shortName,
      bucket:          null,
      tier:            c.tier,
      thesisHealth:    c.thesisHealth,
      finalAction:     c.finalAction,
      trajectory:      c.trajectory,
      ratchetTranche:  0,
      currentPct:      0,
      targetPct:       c.suggestedPct,
      hardCapPct:      c.hardCapPct,
      currentMktValue: 0,
      dollarAmount:    c.suggestedDollar,
      targetValue:     c.suggestedDollar,
      sharesApprox:    0,
      pricePerShare:   0,
      currentShares:   null,
      targetShares:    null,
      taxCost:         0,
      netProceeds:     0,
      accounts:        buildNewPositionRouting(accounts, c.suggestedDollar),
      requires48h:     false,
      isNewPosition:   true,
      reason: `New position — ${c.side === 'est' ? 'established' : 'speculative'} pool, rank score ${c.rankScore}`,
    }));
    for (const m of openMoves) {
      const prior = priorMap.get(`${m.symbol}:${m.moveType}`);
      if (prior) m.priorDecision = prior;
    }
    actionMoves = [...actionMoves, ...openMoves]
      .sort((a, b) => a.priority !== b.priority ? a.priority - b.priority : b.dollarAmount - a.dollarAmount);

    // ── Capital flow ──────────────────────────────────────────────────────────
    // addMoves now includes both top-ups to existing positions and brand-new
    // opens (openMoves above) uniformly — both just need funding, no reason
    // to treat "promote" as a separate capital-flow category anymore.
    const trimMoves = actionMoves.filter(m =>
      ['EXIT', 'TRIM_CAP', 'TRIM_RATCHET', 'TRIM_MODEL', 'TRIM_SIGNAL'].includes(m.moveType));
    const addMoves  = actionMoves.filter(m => m.moveType === 'ADD').map(m => ({
      label: m.isBucketLevel ? `Fund ${m.shortName}` : `${m.isNewPosition ? 'Open' : 'Add'} ${m.symbol}`,
      dollarNeeded: m.dollarAmount,
      type: m.isBucketLevel ? 'bucket_level' : m.isNewPosition ? 'promote' : 'add_existing',
      symbol: m.symbol,
    }));

    const capitalFlow = buildCapitalFlow(trimMoves, addMoves, [], freeCash);

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

    // ── Allocation summary (six buckets, current vs. target) ──────────────────
    // Same taxonomy the rest of the engine already uses (bucketOverride +
    // tier), just aggregated for the Allocation tab instead of per-ticker
    // moves. estPoolPct/specPoolPct/etfTargetPct/cryptoTargetPct/
    // commodityTargetPct are Admin-entered % of TOTAL portfolio value (see
    // where they're computed, above) — cash is a fifth Admin-entered target,
    // not a derived remainder, and all five are validated to sum to 100 in
    // the UI. bucketEntry below uses these percentages as-is.
    let estEquityValue = 0, specEquityValue = 0, etfValue = 0, cryptoValue = 0, commodityValue = 0;
    const holdings = []; // per-ticker detail for the Allocation tab's bucket drill-down
    for (const [tickerId, { ticker, positions }] of byTicker.entries()) {
      const a = analysisMap.get(tickerId);
      const { shares, mktValue, currentPct } = positionMetrics(positions, totalPortfolioValue);
      const bucket = getBucket(ticker);
      let bucketKey;
      if (bucket === 'etf')            { etfValue       += mktValue; bucketKey = 'etf'; }
      else if (bucket === 'crypto')    { cryptoValue    += mktValue; bucketKey = 'crypto'; }
      else if (bucket === 'commodity') { commodityValue += mktValue; bucketKey = 'commodity'; }
      else {
        const side = barbellSide(ticker, a);
        if (side === 'est')  { estEquityValue  += mktValue; bucketKey = 'established'; }
        if (side === 'spec') { specEquityValue += mktValue; bucketKey = 'speculative'; }
      }
      if (bucketKey) {
        holdings.push({
          bucketKey, symbol: ticker.symbol, shortName: ticker.shortName ?? ticker.name,
          shares: +shares.toFixed(3), mktValue: +mktValue.toFixed(2), currentPct: +currentPct.toFixed(2),
        });
      }
    }
    holdings.sort((a, b) => b.mktValue - a.mktValue);
    // cryptoTargetPct/commodityTargetPct/etfTargetPct are the top-down Admin
    // targets computed earlier — no longer re-derived bottom-up here.

    // targetValue is computed here from full-precision pool percentages
    // (before the display rounding applied to targetPct below) so a
    // consumer summing bucket targetValues gets an exact match to
    // totalPortfolioValue, rather than compounding the 1-decimal display
    // rounding into a visible few-dollar gap (caught 2026-08-08 — the
    // re-baseline confirm screen was re-deriving dollars from the rounded
    // targetPct instead of using this).
    function bucketEntry(key, label, currentValue, scaledPct) {
      return {
        key, label,
        currentValue: +currentValue.toFixed(2),
        targetPct:    +scaledPct.toFixed(1),
        targetValue:  +(totalPortfolioValue * (scaledPct / 100)).toFixed(2),
      };
    }
    const allocation = {
      cashReservePct: +(cashReservePct * 100).toFixed(1),
      holdings,
      buckets: [
        bucketEntry('established', 'Established Equities', estEquityValue,  estPoolPct),
        bucketEntry('speculative', 'Speculative Equities',  specEquityValue, specPoolPct),
        bucketEntry('etf',         'ETF',                   etfValue,        etfTargetPct),
        bucketEntry('crypto',      'Crypto',                cryptoValue,     cryptoTargetPct),
        bucketEntry('commodity',   'Commodities',           commodityValue,  commodityTargetPct),
        { key: 'cash', label: 'Cash', currentValue: +totalCash.toFixed(2),
          targetPct: +(cashReservePct * 100).toFixed(1),
          targetValue: +(totalPortfolioValue * cashReservePct).toFixed(2) },
      ],
    };

    // ── Warnings ──────────────────────────────────────────────────────────────
    const warnings = [];
    actionMoves.filter(m => m.requires48h).forEach(m => warnings.push({
      type: '48h_wait', symbol: m.symbol, severity: 'yellow',
      message: `${m.symbol} at ${m.currentPct.toFixed(1)}% — 48-hour review required before confirming hold`,
    }));
    // Barbell-drift warning removed — the Allocation tab now shows current
    // vs. target per bucket directly and more precisely (it doesn't lump ETF
    // into "established" the way barbellStatus below does), so a duplicate
    // text warning here was redundant and could show conflicting numbers.
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
      allocation,
      moves:               actionMoves,
      advisories:          holdMoves.filter(m => m.moveType === 'HOLD_ADVISORY'),
      holds:               holdMoves.filter(m => m.moveType === 'HOLD').map(h => ({
        symbol: h.symbol, shortName: h.shortName, bucket: h.bucket,
        thesisHealth: h.thesisHealth, finalAction: h.finalAction,
        trajectory: h.trajectory, tier: h.tier,
        currentPct: h.currentPct, targetPct: h.targetPct, currentMktValue: h.currentMktValue,
      })),
      capitalFlow,
      warnings,
      isRebaseline: bypassWinnerProtection,
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

    // Preserve re-baseline mode across a manual refresh — same reasoning as
    // lib/movesCache.js's refreshMovesCache: if the cache currently holds a
    // just-confirmed re-baseline, a plain refresh (e.g. after a price
    // update) shouldn't silently revert it to the everyday winner-protected
    // computation out from under the user.
    const existingCache = await prisma.movesCache.findUnique({ where: { owner } });
    const bypassWinnerProtection = existingCache?.payload?.isRebaseline === true;

    const payload     = await computeMovesPayload(owner, { bypassWinnerProtection });
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

// ─── POST /api/moves/:owner/rebaseline ────────────────────────────────────────
// User-triggered full-precision reset (2026-08-08 design — see
// memory/small_account_diversification.md). Bypasses the "Strengthening →
// don't trim" winner-protection exception for this one computation so every
// overweight holding gets sized exactly to its model weight, regardless of
// thesis momentum. Deliberately NEVER touches MovesCache — this is a preview
// the user reviews and confirms/adjusts before anything is acted on; writing
// it to the everyday cache would make the normal Moves tab show trims on
// healthy winners the next time anyone loads the page, which is not what a
// preview should do.

router.post('/:owner/rebaseline', requireAuth(), async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  if (!enforceOwner(req, res, owner)) return;
  try {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    const payload = await computeMovesPayload(owner, { bypassWinnerProtection: true });
    const computedAt = new Date();

    // persist:true means the user has actually confirmed (not just previewing
    // while adjusting target %) — this becomes THE Recommended Moves list, not
    // a second copy living only in the re-baseline modal. Without this, the
    // confirm screen and the Moves tab would show two different move counts
    // for no reason a user could tell (caught 2026-08-08: 15 vs 9 moves,
    // because the Moves tab was still serving the un-bypassed cache).
    if (req.body?.persist === true) {
      await prisma.movesCache.upsert({
        where:  { owner },
        update: { payload, computedAt },
        create: { owner, payload, computedAt },
      });
      console.log(`[movesCache] re-baselined for ${owner}`);
    }

    res.json({ ...payload, fromCache: false, computedAt });
  } catch (err) {
    console.error(`POST /moves/${owner}/rebaseline error:`, err);
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

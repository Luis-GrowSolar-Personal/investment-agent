/**
 * dashboard.js — Portfolio Analyst / Allocator routes
 *
 * The allocator (Layer 1) receives portfolio state + analyst scores.
 * It NEVER receives raw transcripts (firewall).
 * It produces mechanical recommendations: cap flags, tax-aware trim
 * sequencing, ratchet status, 48-hour hold flags, enough-number check.
 *
 *   GET  /api/dashboard                  list all owners with summary
 *   GET  /api/dashboard/:owner           full allocator output for one owner
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DEFAULT_LTCG_RATE = 0.15;
const DEFAULT_STCG_RATE = 0.15;
const LTCG_HOLD_DAYS    = 365;   // IRS long-term threshold

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Days between two dates */
function daysBetween(a, b) {
  return Math.abs(b - a) / (1000 * 60 * 60 * 24);
}

/**
 * Compute tax cost of trimming `sharesToSell` from a position's lots.
 * Uses FIFO order. Returns { taxCost, ltGain, stGain, isTaxAdvantaged }.
 */
function computeTrimTax(lots, sharesToSell, currentPrice, ltcgRate, stcgRate, isTaxAdvantaged) {
  if (isTaxAdvantaged) {
    return { taxCost: 0, ltGain: 0, stGain: 0, isTaxAdvantaged: true };
  }
  const now = new Date();
  // FIFO: oldest lots first
  const sorted = [...lots]
    .filter(l => !l.closedDate)
    .sort((a, b) => new Date(a.acquiredDate) - new Date(b.acquiredDate));

  let remaining = sharesToSell;
  let ltGain = 0;
  let stGain = 0;

  for (const lot of sorted) {
    if (remaining <= 0) break;
    const sellShares = Math.min(remaining, lot.shares);
    const gain = sellShares * (currentPrice - lot.costBasis);
    const isLT = daysBetween(new Date(lot.acquiredDate), now) >= LTCG_HOLD_DAYS;
    if (isLT) ltGain += gain;
    else       stGain += gain;
    remaining -= sellShares;
  }

  const taxCost = ltGain * ltcgRate + stGain * stcgRate;
  return { taxCost, ltGain, stGain, isTaxAdvantaged: false };
}

/**
 * Given an array of position records (all for the same ticker, across
 * multiple accounts of one owner), compute the consolidated allocator view.
 *
 * Returns an object with all fields needed by the Dashboard.
 */
function buildTickerView(ticker, positions, totalPortfolioValue, ownerTaxRates, ownerCapOverrides) {
  const now = new Date();

  // ── Market value across all positions ──────────────────────────────────
  let totalShares     = 0;
  let totalCost       = 0;
  let totalMktValue   = 0;
  let hasPriceData    = false;

  for (const pos of positions) {
    const openLots = pos.lots.filter(l => !l.closedDate);
    const shares   = openLots.reduce((s, l) => s + l.shares, 0);
    const cost     = openLots.reduce((s, l) => s + l.shares * l.costBasis, 0);
    totalShares += shares;
    totalCost   += cost;
    if (pos.lastPrice != null) {
      totalMktValue += shares * pos.lastPrice;
      hasPriceData = true;
    } else {
      totalMktValue += cost;   // fall back to cost basis
    }
  }

  const currentPct = totalPortfolioValue > 0
    ? totalMktValue / totalPortfolioValue
    : 0;

  // ── Latest analyst score for this ticker ───────────────────────────────
  // Scores come from Analysis → Transcript → Ticker (firewall: no transcript
  // text, only the structured score fields).
  const latestAnalysis = ticker._latestAnalysis;  // pre-joined by caller

  // ── Cap enforcement ────────────────────────────────────────────────────
  // Resulting cap = owner's per-ticker override (OwnerTickerConfig) if set,
  // else the global ticker.capPercent.
  // Hard cap = MIN(resulting cap, analyst recommended cap).
  // Both are stored as 0-100 floats; convert to 0-1 for comparison.
  const ownerCapOverride    = ownerCapOverrides?.get(ticker.id);
  const resultingCapPercent = ownerCapOverride ?? ticker.capPercent ?? 100;
  const tickerCapFraction   = resultingCapPercent / 100;
  const analystCapFraction  = latestAnalysis?.capPercent != null
    ? latestAnalysis.capPercent / 100
    : tickerCapFraction;
  const hardCapFraction = Math.min(tickerCapFraction, analystCapFraction);
  const hardCapPct      = hardCapFraction * 100;

  const overCap      = currentPct > hardCapFraction + 0.005; // 0.5% tolerance
  const approachCap  = !overCap && currentPct > hardCapFraction * 0.85;

  // ── Ratchet status ────────────────────────────────────────────────────
  // ratchetTranche: 0 = none, 1 = trim to cap, 2 = trim 40% more, 3 = exit
  const ratchetTranche = latestAnalysis?.ratchetTranche ?? 0;

  // ── 48-hour flag ──────────────────────────────────────────────────────
  // Any position above 30% of portfolio requires a 48-hour wait.
  const requires48h = currentPct > 0.30;

  // ── Recommendation & health ────────────────────────────────────────────
  const thesisHealth    = latestAnalysis?.thesisHealth   ?? '—';
  const recommendation  = latestAnalysis?.recommendation ?? '—';
  const finalAction     = latestAnalysis?.finalAction    ?? recommendation;
  const trajectory      = latestAnalysis?.trajectory     ?? null;
  const tier            = ticker.tierOverride ?? ticker.tierMechanical ?? null;

  // ── Tax-aware trim routing ─────────────────────────────────────────────
  // For trim/exit recommendations, compute tax cost per account and sort
  // tax-advantaged accounts first (they have 0% tax).
  let trimRouting = null;
  if (['Trim', 'Exit'].includes(finalAction) || overCap || ratchetTranche >= 1) {
    // Determine excess shares to trim (to reach hard cap, or exit all)
    const targetValue   = finalAction === 'Exit' ? 0
      : totalPortfolioValue * hardCapFraction;
    const excessValue   = Math.max(0, totalMktValue - targetValue);
    const samplePrice   = positions.find(p => p.lastPrice != null)?.lastPrice
      ?? (totalShares > 0 ? totalCost / totalShares : 0);
    const sharesToTrim  = samplePrice > 0 ? excessValue / samplePrice : 0;

    // Sort positions: tax-advantaged first (IRA/Roth = $0 tax)
    const sorted = [...positions].sort((a, b) => {
      const taxAdv = t => ['ira', 'roth'].includes(t.account?.type);
      if (taxAdv(a) && !taxAdv(b)) return -1;
      if (!taxAdv(a) && taxAdv(b)) return 1;
      return 0;
    });

    trimRouting = sorted.map(pos => {
      const openLots  = pos.lots.filter(l => !l.closedDate);
      const shares    = openLots.reduce((s, l) => s + l.shares, 0);
      const price     = pos.lastPrice ?? (totalCost / totalShares || 0);
      const isTaxAdv  = ['ira', 'roth'].includes(pos.account?.type);
      const ltcgRate  = pos.account?.ltcgRate ?? ownerTaxRates.ltcg;
      const stcgRate  = pos.account?.stcgRate ?? ownerTaxRates.stcg;
      const tax       = computeTrimTax(openLots, shares, price, ltcgRate, stcgRate, isTaxAdv);

      return {
        accountId:       pos.accountId,
        accountName:     pos.account?.name ?? '—',
        accountType:     pos.account?.type ?? '—',
        isTaxAdvantaged: isTaxAdv,
        shares,
        marketValue:     shares * price,
        taxCost:         tax.taxCost,
        ltGain:          tax.ltGain,
        stGain:          tax.stGain,
      };
    });
  }

  // ── Flags ──────────────────────────────────────────────────────────────
  const flags = [];
  if (overCap)                                   flags.push({ type: 'over_cap',   label: `Over ${hardCapPct.toFixed(0)}% cap`, severity: 'red' });
  if (approachCap)                               flags.push({ type: 'near_cap',   label: `Near ${hardCapPct.toFixed(0)}% cap`, severity: 'amber' });
  if (requires48h)                               flags.push({ type: '48h_wait',   label: '48h hold required',                  severity: 'yellow' });
  if (ratchetTranche >= 1)                       flags.push({ type: 'ratchet',    label: `Ratchet tranche ${ratchetTranche}`,  severity: ratchetTranche >= 3 ? 'red' : 'amber' });
  if (!ticker.inScope)                           flags.push({ type: 'out_scope',  label: 'Out of scope',                       severity: 'slate' });

  return {
    tickerId:      ticker.id,
    symbol:        ticker.symbol,
    name:          ticker.name,
    shortName:     ticker.shortName,
    type:          ticker.type,
    tier,
    inScope:       ticker.inScope,
    hardCapPct,
    currentPct:    +(currentPct * 100).toFixed(2),
    totalShares:   +totalShares.toFixed(4),
    totalMktValue: +totalMktValue.toFixed(2),
    totalCost:     +totalCost.toFixed(2),
    unrealisedGain: +(totalMktValue - totalCost).toFixed(2),
    hasPriceData,
    thesisHealth,
    recommendation,
    finalAction,
    trajectory,
    ratchetTranche,
    overCap,
    approachCap,
    requires48h,
    flags,
    trimRouting,
    latestCallDate: latestAnalysis?._callDate ?? null,
    analysisId:     latestAnalysis?.id ?? null,
  };
}

// ---------------------------------------------------------------------------
// GET /api/dashboard
// Summary list: one row per owner with total portfolio value and flag counts
// ---------------------------------------------------------------------------
router.get('/', async (req, res) => {
  try {
    const profiles = await prisma.ownerProfile.findMany({ orderBy: { owner: 'asc' } });

    const summaries = await Promise.all(profiles.map(async (p) => {
      const accounts = await prisma.account.findMany({
        where: { owner: p.owner },
        include: {
          positions: {
            where: { status: 'active' },
            include: { lots: { where: { closedDate: null } } },
          },
        },
      });

      let totalValue = 0;
      let totalCash  = 0;
      for (const acct of accounts) {
        totalCash += acct.cashBalance ?? 0;
        for (const pos of acct.positions) {
          const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
          totalValue  += pos.lastPrice != null ? shares * pos.lastPrice
            : pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
        }
      }

      return {
        owner:               p.owner,
        displayName:         p.displayName,
        enoughNumber:        p.enoughNumber,
        totalPortfolioValue: totalValue + totalCash,
        accountCount:        accounts.length,
      };
    }));

    res.json(summaries);
  } catch (err) {
    console.error('GET /dashboard error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/dashboard/:owner
// Full allocator output for one owner
// ---------------------------------------------------------------------------
router.get('/:owner', async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);

  try {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    // Pull all accounts + positions + lots for this owner
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

    // ── Total portfolio value ──────────────────────────────────────────
    let totalMktValue = 0;
    let totalCash     = 0;
    for (const acct of accounts) {
      totalCash += acct.cashBalance ?? 0;
      for (const pos of acct.positions) {
        const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
        totalMktValue += pos.lastPrice != null ? shares * pos.lastPrice
          : pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
      }
    }
    const totalPortfolioValue = totalMktValue + totalCash;

    // ── Owner default tax rates ────────────────────────────────────────
    const ownerTaxRates = {
      ltcg: DEFAULT_LTCG_RATE,
      stcg: DEFAULT_STCG_RATE,
    };

    // ── Owner per-ticker cap overrides ─────────────────────────────────
    const ownerConfigs = await prisma.ownerTickerConfig.findMany({ where: { owner } });
    const ownerCapOverrides = new Map(ownerConfigs.map(c => [c.tickerId, c.capPercent]));

    // ── Group positions by ticker ──────────────────────────────────────
    const byTicker = new Map(); // tickerId → { ticker, positions[] }
    for (const acct of accounts) {
      for (const pos of acct.positions) {
        const tid = pos.tickerId;
        if (!byTicker.has(tid)) {
          byTicker.set(tid, { ticker: pos.ticker, positions: [] });
        }
        // Attach account info so trimRouting can read account type
        byTicker.get(tid).positions.push({ ...pos, account: acct });
      }
    }

    // ── Fetch latest Analysis per ticker ──────────────────────────────
    // Query: for each ticker, get the most recent Analysis via its Transcript.
    // This is the analyst score only — no transcript text (firewall preserved).
    const tickerIds = [...byTicker.keys()];
    const latestAnalyses = await Promise.all(tickerIds.map(async (tickerId) => {
      const analysis = await prisma.analysis.findFirst({
        where:   { transcript: { tickerId } },
        orderBy: { transcript: { callDate: 'desc' } },
        select: {
          id: true,
          thesisHealth: true,
          recommendation: true,
          recommendedSize: true,
          capPercent: true,
          ratchetTranche: true,
          trajectory: true,
          finalAction: true,
          finalConfidence: true,
          trendRationale: true,
          thesisDelta: true,
          activeDriverCount: true,
          transcript: { select: { callDate: true } },
        },
      });
      return { tickerId, analysis };
    }));

    // Attach latest analysis to each ticker group
    for (const { tickerId, analysis } of latestAnalyses) {
      const group = byTicker.get(tickerId);
      if (group && analysis) {
        group.ticker._latestAnalysis = {
          ...analysis,
          _callDate: analysis.transcript?.callDate ?? null,
        };
      } else if (group) {
        group.ticker._latestAnalysis = null;
      }
    }

    // ── Build ticker views ─────────────────────────────────────────────
    const tickerViews = [];
    for (const { ticker, positions } of byTicker.values()) {
      // Only score in-scope positions against cap rules
      if (!ticker.inScope) {
        // Still surface them, but skip cap/ratchet logic
        ticker._latestAnalysis = ticker._latestAnalysis ?? null;
      }
      tickerViews.push(
        buildTickerView(ticker, positions, totalPortfolioValue, ownerTaxRates, ownerCapOverrides)
      );
    }

    // Sort: flagged first (over cap → near cap → ratchet), then by weight desc
    tickerViews.sort((a, b) => {
      const severity = v =>
        v.overCap ? 3 : v.ratchetTranche >= 1 ? 2 : v.approachCap ? 1 : 0;
      if (severity(b) !== severity(a)) return severity(b) - severity(a);
      return b.currentPct - a.currentPct;
    });

    // ── Enough Number check ────────────────────────────────────────────
    const enoughNumber  = profile.enoughNumber ?? null;
    const enoughPct     = enoughNumber ? totalPortfolioValue / enoughNumber : null;
    const enoughReached = enoughPct != null && enoughPct >= 1.0;

    // ── Account summary ────────────────────────────────────────────────
    const accountSummary = accounts.map(acct => ({
      id:           acct.id,
      name:         acct.name,
      type:         acct.type,
      managed:      acct.managed,
      cashBalance:  acct.cashBalance,
      marginBalance: acct.marginBalance,
    }));

    res.json({
      owner,
      displayName:         profile.displayName,
      enoughNumber,
      enoughPct:           enoughPct != null ? +enoughPct.toFixed(4) : null,
      enoughReached,
      totalPortfolioValue: +totalPortfolioValue.toFixed(2),
      totalMktValue:       +totalMktValue.toFixed(2),
      totalCash:           +totalCash.toFixed(2),
      accountSummary,
      tickers:             tickerViews,
    });
  } catch (err) {
    console.error(`GET /dashboard/${owner} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

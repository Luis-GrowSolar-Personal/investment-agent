/**
 * ownerTickerConfig.js
 *
 * Per-owner cap % overrides for held positions.
 *
 * GET  /api/owner-ticker-config/:owner
 *   Returns:
 *   - All positions currently held by the owner (any bucket), plus
 *   - ALL tickers with bucketOverride in ('etf','commodity','crypto')
 *     from the Ticker table, even if the owner has no position yet.
 *   This lets admins pre-set caps for fixed-target assets before the
 *   owner opens a position.  Non-held rows are marked isHeld: false.
 *   Equity tickers are only shown if the owner currently holds them.
 *
 * PUT  /api/owner-ticker-config/:owner/:tickerId
 *   Upsert a cap % override for one ticker.
 *   Body: { capPercent: number | null }
 *   Pass null to clear the override (falls back to global Ticker.capPercent).
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { requireAuth } = require('@clerk/express');

// ── GET /api/owner-ticker-config/:owner ──────────────────────────────────────

router.get('/:owner', requireAuth(), async (req, res) => {
  const owner = decodeURIComponent(req.params.owner);
  try {
    // Load all active positions for this owner
    const accounts = await prisma.account.findMany({
      where: { owner },
      include: {
        positions: {
          where: { status: 'active' },
          include: {
            ticker: true,
            lots:   { where: { closedDate: null } },
          },
        },
      },
    });

    // Load all existing overrides for this owner
    const existingConfigs = await prisma.ownerTickerConfig.findMany({
      where: { owner },
    });
    const configMap = new Map(existingConfigs.map(c => [c.tickerId, c]));

    // Deduplicate positions by ticker (a ticker can be in multiple accounts)
    const byTicker = new Map();
    for (const acct of accounts) {
      for (const pos of acct.positions) {
        if (!byTicker.has(pos.tickerId)) {
          byTicker.set(pos.tickerId, {
            ticker:   pos.ticker,
            mktValue: 0,
            shares:   0,
            isHeld:   true,
          });
        }
        const entry = byTicker.get(pos.tickerId);
        const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
        entry.shares   += shares;
        entry.mktValue += pos.lastPrice != null
          ? shares * pos.lastPrice
          : pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
      }
    }

    // Also include ALL ETF / commodity / crypto tickers from the Ticker table,
    // even if this owner has no position in them yet.  Admins can pre-set caps
    // for fixed-target assets before the owner opens a position.
    const fixedTargetTickers = await prisma.ticker.findMany({
      where: { bucketOverride: { in: ['etf', 'commodity', 'crypto'] } },
    });
    for (const ticker of fixedTargetTickers) {
      if (!byTicker.has(ticker.id)) {
        byTicker.set(ticker.id, {
          ticker,
          mktValue: 0,
          shares:   0,
          isHeld:   false,
        });
      }
      // Already-held entries keep isHeld: true from above
    }

    // Total portfolio value (market value + cash)
    const totalCash = accounts.reduce((s, a) => s + (a.cashBalance ?? 0), 0);
    const totalMkt  = [...byTicker.values()].reduce((s, e) => s + e.mktValue, 0);
    const totalPortfolioValue = totalMkt + totalCash;

    // Build response rows
    const rows = [...byTicker.values()].map(({ ticker, mktValue, isHeld }) => {
      const config = configMap.get(ticker.id);
      return {
        tickerId:          ticker.id,
        symbol:            ticker.symbol,
        shortName:         ticker.shortName ?? ticker.name,
        bucket:            ticker.bucketOverride ?? 'equity',
        isHeld,
        globalCapPercent:  ticker.capPercent,          // Ticker-level default
        ownerCapPercent:   config?.capPercent ?? null, // Per-owner override (null = not set)
        effectiveCapPct:   config?.capPercent ?? ticker.capPercent, // What moves engine uses
        currentPct:        totalPortfolioValue > 0
          ? +((mktValue / totalPortfolioValue) * 100).toFixed(2)
          : 0,
        currentMktValue:   +mktValue.toFixed(2),
      };
    });

    // Sort: by bucket then held-before-not-held then symbol
    const BUCKET_ORDER = { etf: 0, commodity: 1, crypto: 2, equity: 3 };
    rows.sort((a, b) => {
      const bo = (BUCKET_ORDER[a.bucket] ?? 9) - (BUCKET_ORDER[b.bucket] ?? 9);
      if (bo !== 0) return bo;
      if (a.isHeld !== b.isHeld) return a.isHeld ? -1 : 1;
      return a.symbol.localeCompare(b.symbol);
    });

    res.json({ owner, totalPortfolioValue: +totalPortfolioValue.toFixed(2), rows });
  } catch (err) {
    console.error(`GET /owner-ticker-config/${owner} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

// ── PUT /api/owner-ticker-config/:owner/:tickerId ─────────────────────────────

router.put('/:owner/:tickerId', requireAuth(), async (req, res) => {
  const owner    = decodeURIComponent(req.params.owner);
  const tickerId = parseInt(req.params.tickerId);
  const { capPercent } = req.body; // number or null

  if (isNaN(tickerId)) return res.status(400).json({ error: 'Invalid tickerId' });

  try {
    if (capPercent === null || capPercent === undefined) {
      // Clear the override
      await prisma.ownerTickerConfig.deleteMany({ where: { owner, tickerId } });
      return res.json({ owner, tickerId, capPercent: null, cleared: true });
    }

    const val = parseFloat(capPercent);
    if (isNaN(val) || val < 0 || val > 100) {
      return res.status(400).json({ error: 'capPercent must be 0–100' });
    }

    const config = await prisma.ownerTickerConfig.upsert({
      where:  { owner_tickerId: { owner, tickerId } },
      create: { owner, tickerId, capPercent: val },
      update: { capPercent: val },
    });

    res.json({ owner, tickerId, capPercent: config.capPercent });
  } catch (err) {
    console.error(`PUT /owner-ticker-config/${owner}/${tickerId} error:`, err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

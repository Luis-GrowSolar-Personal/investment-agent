/**
 * ownerTickerConfig.js
 *
 * Per-owner cap % overrides for held positions.
 *
 * GET  /api/owner-ticker-config/:owner
 *   Returns all positions currently held by the owner,
 *   grouped by asset class, with any existing cap overrides merged in.
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

    // Total portfolio value (market value + cash)
    const totalCash = accounts.reduce((s, a) => s + (a.cashBalance ?? 0), 0);
    const totalMkt  = [...byTicker.values()].reduce((s, e) => s + e.mktValue, 0);
    const totalPortfolioValue = totalMkt + totalCash;

    // Build response rows
    const rows = [...byTicker.values()].map(({ ticker, mktValue }) => {
      const config = configMap.get(ticker.id);
      return {
        tickerId:          ticker.id,
        symbol:            ticker.symbol,
        shortName:         ticker.shortName ?? ticker.name,
        bucket:            ticker.bucketOverride ?? 'equity',
        globalCapPercent:  ticker.capPercent,          // Ticker-level default
        ownerCapPercent:   config?.capPercent ?? null, // Per-owner override (null = not set)
        effectiveCapPct:   config?.capPercent ?? ticker.capPercent, // What moves engine uses
        currentPct:        totalPortfolioValue > 0
          ? +((mktValue / totalPortfolioValue) * 100).toFixed(2)
          : 0,
        currentMktValue:   +mktValue.toFixed(2),
      };
    });

    // Sort: by bucket label then symbol
    const BUCKET_ORDER = { etf: 0, commodity: 1, crypto: 2, equity: 3 };
    rows.sort((a, b) => {
      const bo = (BUCKET_ORDER[a.bucket] ?? 9) - (BUCKET_ORDER[b.bucket] ?? 9);
      return bo !== 0 ? bo : a.symbol.localeCompare(b.symbol);
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

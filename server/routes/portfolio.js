/**
 * portfolio.js — Phase 2 portfolio routes
 *
 * Accounts
 *   GET    /api/portfolio/accounts              list all accounts with position summary
 *   POST   /api/portfolio/accounts              create account
 *   PATCH  /api/portfolio/accounts/:id          update account (cash, margin, settings)
 *   DELETE /api/portfolio/accounts/:id          delete (only if no positions)
 *
 * Positions
 *   GET    /api/portfolio/accounts/:id/positions  list positions with lots for one account
 *   POST   /api/portfolio/positions               create position + initial lots
 *   PATCH  /api/portfolio/positions/:id           update position
 *   DELETE /api/portfolio/positions/:id           soft-delete (status=closed)
 *
 * Lots
 *   POST   /api/portfolio/lots                  add lot to existing position
 *   DELETE /api/portfolio/lots/:id              remove lot
 *
 * Ticker bucket
 *   PATCH  /api/portfolio/tickers/:id/bucket    set bucketOverride
 *
 * Import / prices
 *   POST   /api/portfolio/accounts/:id/import          import CSV + optional JSON
 *   POST   /api/portfolio/accounts/:id/refresh-prices  refresh market prices
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { parsePositionsCSV, parseTransactionsJSON, reconstructLots, smartDefaultBucket } = require('../lib/portfolioImport');
const { refreshAccountPrices } = require('../lib/priceRefresh');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Enrich positions with computed fields: totalShares, avgCostBasis,
 * marketValue, unrealisedGain, and effective bucket.
 */
function enrichPosition(pos) {
  const openLots     = pos.lots.filter(l => !l.closedDate);
  const totalShares  = openLots.reduce((s, l) => s + l.shares, 0);
  const totalCost    = openLots.reduce((s, l) => s + l.shares * l.costBasis, 0);
  const avgCostBasis = totalShares > 0 ? totalCost / totalShares : 0;
  const marketValue  = pos.lastPrice != null ? totalShares * pos.lastPrice : null;
  const unrealisedGain = marketValue != null ? marketValue - totalCost : null;
  const unrealisedGainPct = totalCost > 0 && unrealisedGain != null
    ? unrealisedGain / totalCost
    : null;
  const dayGainDollar = pos.lastPrice != null && pos.dayChangeDollar != null
    ? totalShares * pos.dayChangeDollar
    : null;

  // Effective bucket: override wins, else smart default
  const effectiveBucket = pos.ticker.bucketOverride
    ?? smartDefaultBucket(pos.assetType || '', pos.ticker.symbol);

  return {
    ...pos,
    totalShares,
    avgCostBasis,
    totalCost,
    marketValue,
    unrealisedGain,
    unrealisedGainPct,
    dayGainDollar,
    effectiveBucket,
  };
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

// GET /api/portfolio/accounts
router.get('/accounts', async (req, res) => {
  try {
    const accounts = await prisma.account.findMany({
      include: {
        positions: {
          where: { status: 'active' },
          include: {
            ticker: { select: { id: true, symbol: true, shortName: true, name: true, bucketOverride: true } },
            lots: { where: { closedDate: null } },
          },
        },
      },
      orderBy: { createdAt: 'asc' },
    });

    const enriched = accounts.map(acct => {
      const positions = acct.positions.map(enrichPosition);
      const totalMarketValue = positions.reduce((s, p) => s + (p.marketValue ?? p.totalCost), 0);
      const totalCost        = positions.reduce((s, p) => s + p.totalCost, 0);
      const totalUnrealised  = positions.reduce((s, p) => s + (p.unrealisedGain ?? 0), 0);
      const totalDayGain     = positions.reduce((s, p) => s + (p.dayGainDollar ?? 0), 0);

      // Bucket pills
      const bucketTotals = { equity: 0, etf: 0, crypto: 0, commodity: 0 };
      for (const p of positions) {
        const b = p.effectiveBucket;
        if (b in bucketTotals) bucketTotals[b] += p.marketValue ?? p.totalCost;
      }

      return {
        ...acct,
        positions,
        totalMarketValue,
        totalCost,
        totalUnrealised,
        totalDayGain,
        bucketTotals,
      };
    });

    res.json(enriched);
  } catch (err) {
    console.error('GET /accounts error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/portfolio/accounts
// Body: { name, type, owner, managed?, ltcgRate?, stcgRate?, notes? }
router.post('/accounts', async (req, res) => {
  const { name, type, owner, managed = false, ltcgRate, stcgRate, notes } = req.body;
  if (!name || !type || !owner) {
    return res.status(400).json({ error: 'name, type, and owner are required' });
  }
  const VALID_TYPES = ['taxable', 'ira', 'roth', 'custodial'];
  if (!VALID_TYPES.includes(type)) {
    return res.status(400).json({ error: `type must be one of: ${VALID_TYPES.join(', ')}` });
  }
  try {
    const account = await prisma.account.create({
      data: { name, type, owner, managed, ltcgRate, stcgRate, notes },
    });
    res.status(201).json(account);
  } catch (err) {
    if (err.code === 'P2002') {
      return res.status(409).json({ error: `Account "${name}" already exists for ${owner}` });
    }
    console.error('POST /accounts error:', err);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/portfolio/accounts/:id
// Body: any subset of account fields
router.patch('/accounts/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  const allowed = ['name', 'type', 'owner', 'managed', 'ltcgRate', 'stcgRate',
                   'cashBalance', 'cashAsOfDate', 'marginBalance', 'marginRate',
                   'marginRateAsOf', 'marginAsOfDate', 'notes'];
  const data = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) data[key] = req.body[key];
  }
  // Append to marginRateLog if marginRate is being updated
  if (data.marginRate !== undefined) {
    const existing = await prisma.account.findUnique({ where: { id }, select: { marginRateLog: true } });
    const log = (existing?.marginRateLog || []);
    log.push({ rate: data.marginRate, effectiveDate: new Date().toISOString() });
    data.marginRateLog = log;
  }
  try {
    const account = await prisma.account.update({ where: { id }, data });
    res.json(account);
  } catch (err) {
    console.error('PATCH /accounts/:id error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/portfolio/accounts/:id
router.delete('/accounts/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const count = await prisma.position.count({ where: { accountId: id } });
    if (count > 0) {
      return res.status(409).json({ error: 'Cannot delete account with positions. Remove positions first.' });
    }
    await prisma.account.delete({ where: { id } });
    res.json({ deleted: id });
  } catch (err) {
    console.error('DELETE /accounts/:id error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

// GET /api/portfolio/accounts/:id/positions
router.get('/accounts/:id/positions', async (req, res) => {
  const accountId = parseInt(req.params.id);
  try {
    const positions = await prisma.position.findMany({
      where: { accountId, status: 'active' },
      include: {
        ticker: {
          select: {
            id: true, symbol: true, shortName: true, name: true, type: true,
            inScope: true, status: true, bucketOverride: true,
          },
        },
        lots: { where: { closedDate: null }, orderBy: { acquiredDate: 'asc' } },
      },
      orderBy: { ticker: { symbol: 'asc' } },
    });
    res.json(positions.map(enrichPosition));
  } catch (err) {
    console.error('GET /accounts/:id/positions error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/portfolio/positions
// Body: { tickerId, accountId, lots: [{ shares, costBasis, acquiredDate, notes? }], notes? }
// OR:   { symbol, accountId, lots: [...], notes? }  (symbol resolved to tickerId)
router.post('/positions', async (req, res) => {
  let { tickerId, symbol, accountId, lots = [], notes } = req.body;
  if (!accountId) return res.status(400).json({ error: 'accountId is required' });
  if (!lots.length) return res.status(400).json({ error: 'at least one lot is required' });

  try {
    if (!tickerId && symbol) {
      const ticker = await prisma.ticker.findUnique({ where: { symbol: symbol.toUpperCase() } });
      if (!ticker) return res.status(404).json({ error: `Ticker ${symbol} not found. Add it to RADAR first.` });
      tickerId = ticker.id;
    }
    if (!tickerId) return res.status(400).json({ error: 'tickerId or symbol is required' });

    const position = await prisma.position.upsert({
      where: { tickerId_accountId: { tickerId, accountId } },
      update: { status: 'active', notes: notes ?? undefined },
      create: { tickerId, accountId, notes },
    });

    const createdLots = await Promise.all(
      lots.map(lot => prisma.lot.create({
        data: {
          positionId:   position.id,
          shares:       parseFloat(lot.shares),
          costBasis:    parseFloat(lot.costBasis),
          acquiredDate: new Date(lot.acquiredDate),
          source:       lot.source || 'manual',
          notes:        lot.notes ?? null,
        },
      }))
    );

    res.status(201).json({ position, lots: createdLots });
  } catch (err) {
    console.error('POST /positions error:', err);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/portfolio/positions/:id
router.patch('/positions/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  const allowed = ['status', 'notes', 'closedAt', 'assetType'];
  const data = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) data[key] = req.body[key];
  }
  try {
    const position = await prisma.position.update({ where: { id }, data });
    res.json(position);
  } catch (err) {
    console.error('PATCH /positions/:id error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/portfolio/positions/:id — soft delete
router.delete('/positions/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const position = await prisma.position.update({
      where: { id },
      data: { status: 'closed', closedAt: new Date() },
    });
    res.json(position);
  } catch (err) {
    console.error('DELETE /positions/:id error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Lots
// ---------------------------------------------------------------------------

// POST /api/portfolio/lots
// Body: { positionId, shares, costBasis, acquiredDate, source?, notes? }
router.post('/lots', async (req, res) => {
  const { positionId, shares, costBasis, acquiredDate, source = 'manual', notes } = req.body;
  if (positionId == null || shares == null || costBasis == null || !acquiredDate) {
    return res.status(400).json({ error: 'positionId, shares, costBasis, acquiredDate are required' });
  }
  try {
    const lot = await prisma.lot.create({
      data: {
        positionId: parseInt(positionId),
        shares:     parseFloat(shares),
        costBasis:  parseFloat(costBasis),
        acquiredDate: new Date(acquiredDate),
        source,
        notes: notes ?? null,
      },
    });
    res.status(201).json(lot);
  } catch (err) {
    console.error('POST /lots error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Legacy: keep old path for backwards compat
router.post('/positions/:id/lots', async (req, res) => {
  req.body.positionId = req.params.id;
  return router.handle(
    Object.assign(req, { url: '/lots', method: 'POST' }), res,
    () => res.status(500).json({ error: 'routing error' })
  );
});

// DELETE /api/portfolio/lots/:id
router.delete('/lots/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    await prisma.lot.delete({ where: { id } });
    res.json({ deleted: id });
  } catch (err) {
    console.error('DELETE /lots/:id error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Ticker bucket override
// ---------------------------------------------------------------------------

// PATCH /api/portfolio/tickers/:id/bucket
// Body: { bucket: "equity" | "etf" | "crypto" | "commodity" | null }
router.patch('/tickers/:id/bucket', async (req, res) => {
  const id = parseInt(req.params.id);
  const { bucket } = req.body;
  const VALID = ['equity', 'etf', 'crypto', 'commodity', null];
  if (!VALID.includes(bucket)) {
    return res.status(400).json({ error: 'bucket must be equity, etf, crypto, commodity, or null' });
  }
  try {
    const ticker = await prisma.ticker.update({
      where: { id },
      data: { bucketOverride: bucket },
    });
    res.json(ticker);
  } catch (err) {
    console.error('PATCH /tickers/:id/bucket error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

/**
 * POST /api/portfolio/accounts/:id/import
 * Body: multipart/form-data with:
 *   - positions: CSV text (required)
 *   - transactions: JSON text (optional — for lot reconstruction)
 *
 * The endpoint accepts raw text bodies too (Content-Type: text/plain)
 * for ease of testing. For the UI, the client sends JSON:
 *   { positionsCSV: string, transactionsJSON?: string }
 */
router.post('/accounts/:id/import', async (req, res) => {
  const accountId = parseInt(req.params.id);
  const { positionsCSV, transactionsJSON } = req.body;

  if (!positionsCSV) {
    return res.status(400).json({ error: 'positionsCSV is required' });
  }

  try {
    const account = await prisma.account.findUnique({ where: { id: accountId } });
    if (!account) return res.status(404).json({ error: 'Account not found' });

    // Parse positions CSV
    const { accountMeta, cashBalance, positions: rawPositions } = parsePositionsCSV(positionsCSV);

    // Parse transactions if provided, and reconstruct lots
    let enrichedPositions = rawPositions;
    if (transactionsJSON) {
      const transactions = parseTransactionsJSON(transactionsJSON);
      enrichedPositions = reconstructLots(rawPositions, transactions);
    }

    const results = {
      imported: 0,
      skipped: 0,
      notInRadar: [],
      reconciliationWarnings: [],
    };

    // Update cash balance on account
    if (cashBalance !== null) {
      await prisma.account.update({
        where: { id: accountId },
        data: { cashBalance, cashAsOfDate: new Date() },
      });
    }

    // Upsert each position + lots
    for (const pos of enrichedPositions) {
      // Look up ticker — must exist in RADAR
      const ticker = await prisma.ticker.findUnique({
        where: { symbol: pos.symbol },
      });
      if (!ticker) {
        results.notInRadar.push(pos.symbol);
        results.skipped++;
        continue;
      }

      // Upsert position
      const position = await prisma.position.upsert({
        where: { tickerId_accountId: { tickerId: ticker.id, accountId } },
        update: { status: 'active' },
        create: { tickerId: ticker.id, accountId },
      });

      // Delete old import lots (re-import is a full replace)
      await prisma.lot.deleteMany({
        where: { positionId: position.id, source: 'import' },
      });

      // Create lots
      const lots = pos.lots || [{
        acquiredDate: new Date(),
        shares: pos.qty,
        costBasisPerShare: pos.costBasisPerShare,
        source: 'import',
      }];

      await Promise.all(
        lots.map(lot => prisma.lot.create({
          data: {
            positionId:  position.id,
            shares:      lot.shares,
            costBasis:   lot.costBasisPerShare ?? pos.costBasisPerShare,
            acquiredDate: lot.acquiredDate instanceof Date ? lot.acquiredDate : new Date(lot.acquiredDate),
            source:      'import',
            notes:       lot.notes ?? null,
          },
        }))
      );

      if (pos.reconciled === false) {
        results.reconciliationWarnings.push(pos.symbol);
      }

      results.imported++;
    }

    res.json({
      ...results,
      cashBalance,
      accountMeta,
      message: `Imported ${results.imported} position(s).` +
        (results.notInRadar.length ? ` ${results.notInRadar.length} not in RADAR: ${results.notInRadar.join(', ')}.` : '') +
        (results.reconciliationWarnings.length ? ` Lot reconciliation warnings: ${results.reconciliationWarnings.join(', ')}.` : ''),
    });
  } catch (err) {
    console.error('POST /accounts/:id/import error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Refresh prices
// ---------------------------------------------------------------------------

// POST /api/portfolio/accounts/:id/refresh-prices
router.post('/accounts/:id/refresh-prices', async (req, res) => {
  const accountId = parseInt(req.params.id);
  try {
    const result = await refreshAccountPrices(prisma, accountId);
    res.json(result);
  } catch (err) {
    console.error('POST /accounts/:id/refresh-prices error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Legacy: deprecated Phase 1 cash routes (kept for backwards compat; no-op)
// ---------------------------------------------------------------------------

router.get('/cash', async (req, res) => {
  res.json([]);
});

router.post('/cash', async (req, res) => {
  res.status(410).json({
    error: 'Deprecated. Cash balance is now stored on Account. Use PATCH /api/portfolio/accounts/:id.',
  });
});

module.exports = router;

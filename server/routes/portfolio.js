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
const { parsePositionsCSV, parseTransactionsJSON, reconstructLots, reconstructPositionsFromTransactions, smartDefaultBucket } = require('../lib/portfolioImport');
const { refreshAccountPrices } = require('../lib/priceRefresh');
const { enforceOwner } = require('../lib/authMiddleware');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Ensure an OwnerProfile row exists for the given owner string.
 * No-op if the row already exists. Called any time a new owner value appears.
 */
async function ensureOwnerProfile(owner) {
  await prisma.ownerProfile.upsert({
    where:  { owner },
    update: {},           // nothing to overwrite — user-set fields are preserved
    create: { owner },
  });
}

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
    const caller  = req.ownerProfile;
    const isAdmin = caller?.role === 'admin';
    const accounts = await prisma.account.findMany({
      where: isAdmin ? undefined : { owner: caller?.owner },
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
      const positionsValue   = positions.reduce((s, p) => s + (p.marketValue ?? p.totalCost), 0);
      const cashBalance      = acct.cashBalance ?? 0;
      const marginBalance    = acct.marginBalance ?? 0; // debt — subtract
      // Total account value = positions + cash - margin debt
      const totalMarketValue = positionsValue + cashBalance - marginBalance;
      const totalCost        = positions.reduce((s, p) => s + p.totalCost, 0);
      const totalUnrealised  = positions.reduce((s, p) => s + (p.unrealisedGain ?? 0), 0);
      const totalDayGain     = positions.reduce((s, p) => s + (p.dayGainDollar ?? 0), 0);

      // Compute % of account for each position (denominator = total including cash)
      if (totalMarketValue > 0) {
        for (const pos of positions) {
          pos.pctOfAcct = (pos.marketValue ?? pos.totalCost) / totalMarketValue;
        }
      }

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
  const { name, type, owner, managed = false, ltcgRate, stcgRate, notes, allowsFractional = false } = req.body;
  if (!name || !type || !owner) {
    return res.status(400).json({ error: 'name, type, and owner are required' });
  }
  const VALID_TYPES = ['taxable', 'ira', 'roth', 'custodial'];
  if (!VALID_TYPES.includes(type)) {
    return res.status(400).json({ error: `type must be one of: ${VALID_TYPES.join(', ')}` });
  }
  try {
    const account = await prisma.account.create({
      data: { name, type, owner, managed, ltcgRate, stcgRate, notes, allowsFractional },
    });
    // Auto-create OwnerProfile for new owners (no-op if already exists)
    await ensureOwnerProfile(owner);
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
                   'marginRateAsOf', 'marginAsOfDate', 'notes', 'allowsFractional'];
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
// Cascades: deletes all lots → positions → account
// Requires { confirm: true } in body as an extra safeguard
router.delete('/accounts/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  if (!req.body?.confirm) {
    return res.status(400).json({ error: 'confirm: true required to delete an account' });
  }
  try {
    // Find all position IDs for this account
    const positions = await prisma.position.findMany({
      where: { accountId: id },
      select: { id: true },
    });
    const positionIds = positions.map(p => p.id);

    // Cascade delete lots → positions → account
    if (positionIds.length > 0) {
      await prisma.lot.deleteMany({ where: { positionId: { in: positionIds } } });
      await prisma.position.deleteMany({ where: { accountId: id } });
    }
    await prisma.account.delete({ where: { id } });
    res.json({ deleted: id, positionsRemoved: positionIds.length });
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
      const sym = symbol.toUpperCase();
      let ticker = await prisma.ticker.findUnique({ where: { symbol: sym } });
      if (!ticker) {
        // Auto-create a minimal watchlist entry so Portfolio doesn't require RADAR pre-entry
        const { smartDefaultBucket } = require('../lib/portfolioImport');
        const bucket = smartDefaultBucket('', sym);
        ticker = await prisma.ticker.create({
          data: {
            symbol:        sym,
            name:          sym,
            shortName:     sym,
            type:          'A',
            capPercent:    0,
            status:        'watchlist',
            inScope:       false,
            bucketOverride: bucket !== 'equity' ? bucket : null,
          },
        });
      }
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

// POST /api/portfolio/positions/:id/rename
// Body: { newSymbol: string }
// Reassigns position to a different (or newly created) ticker.
// If the target ticker already has a position in the same account, merges lots into it.
router.post('/positions/:id/rename', async (req, res) => {
  const id = parseInt(req.params.id);
  const { newSymbol } = req.body;
  if (!newSymbol) return res.status(400).json({ error: 'newSymbol is required' });

  const sym = newSymbol.trim().toUpperCase();

  try {
    const position = await prisma.position.findUnique({
      where: { id },
      include: { ticker: true, lots: true },
    });
    if (!position) return res.status(404).json({ error: 'Position not found' });

    // Find or create the target ticker
    let targetTicker = await prisma.ticker.findUnique({ where: { symbol: sym } });
    if (!targetTicker) {
      targetTicker = await prisma.ticker.create({
        data: {
          symbol: sym, name: sym, shortName: sym,
          type: position.ticker.type,
          capPercent: position.ticker.capPercent,
          status: position.ticker.status,
          inScope: position.ticker.inScope,
        },
      });
    }

    // Check if target ticker already has a position in this account
    const existingTarget = await prisma.position.findUnique({
      where: { tickerId_accountId: { tickerId: targetTicker.id, accountId: position.accountId } },
    });

    if (existingTarget) {
      // Merge: move all lots from source position to existing target position
      await prisma.lot.updateMany({
        where: { positionId: id },
        data: { positionId: existingTarget.id },
      });
      // Soft-delete the source position
      await prisma.position.update({
        where: { id },
        data: { status: 'closed', closedAt: new Date() },
      });
      res.json({ merged: true, targetPositionId: existingTarget.id, symbol: sym });
    } else {
      // Simple rename: update tickerId on the position
      const updated = await prisma.position.update({
        where: { id },
        data: { tickerId: targetTicker.id },
      });
      res.json({ merged: false, position: updated, symbol: sym });
    }
  } catch (err) {
    console.error('POST /positions/:id/rename error:', err);
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

  if (!positionsCSV && !transactionsJSON) {
    return res.status(400).json({ error: 'positionsCSV or transactionsJSON is required' });
  }

  try {
    const account = await prisma.account.findUnique({ where: { id: accountId } });
    if (!account) return res.status(404).json({ error: 'Account not found' });

    // Ensure OwnerProfile exists for this account's owner (no-op if already present)
    await ensureOwnerProfile(account.owner);

    let enrichedPositions = [];
    let accountMeta = {};
    let cashBalance = null;

    if (transactionsJSON && !positionsCSV) {
      // JSON-only path: reconstruct positions + lots entirely from transaction history
      const transactions = parseTransactionsJSON(transactionsJSON);
      enrichedPositions = reconstructPositionsFromTransactions(transactions);
      accountMeta = { source: 'transactions JSON' };
    } else {
      // CSV path (with optional JSON for lot dates)
      const parsed = await parsePositionsCSV(positionsCSV);
      accountMeta  = parsed.accountMeta;
      cashBalance  = parsed.cashBalance;
      const rawPositions = parsed.positions;

      if (transactionsJSON) {
        const transactions = parseTransactionsJSON(transactionsJSON);
        enrichedPositions = reconstructLots(rawPositions, transactions);
      } else {
        enrichedPositions = rawPositions;
      }
    }

    const results = {
      imported: 0,
      autoCreated: [],
      reconciliationWarnings: [],
      clearedSchwabPlaceholders: [],
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
      // Look up ticker — auto-create if not in RADAR
      let ticker = await prisma.ticker.findUnique({ where: { symbol: pos.symbol } });
      if (!ticker) {
        const bucket = smartDefaultBucket(pos.assetType, pos.symbol);
        ticker = await prisma.ticker.create({
          data: {
            symbol:        pos.symbol,
            name:          pos.description || pos.symbol,
            shortName:     pos.description ? pos.description.slice(0, 40) : pos.symbol,
            type:          'A',          // default; user can update in RADAR
            capPercent:    0,
            status:        'watchlist',
            inScope:       false,        // not analyst-evaluated
            // Store explicitly — see schwabSync.js for why leaving this null
            // for 'equity' misfiles the position into the ETFs tab at
            // display time (Position has no assetType column, so
            // enrichPosition()'s fallback smartDefaultBucket('', symbol)
            // always returns 'etf').
            bucketOverride: bucket,
          },
        });
        results.autoCreated.push(pos.symbol);
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

      // A CSV import supplies real per-lot cost basis/acquisition dates, so
      // it supersedes any placeholder lot Schwab sync may have created for
      // this position (source: 'schwab' — see schwabSync.js). Clear it here
      // to avoid double-counting shares between the two sources.
      const clearedSchwab = await prisma.lot.deleteMany({
        where: { positionId: position.id, source: 'schwab' },
      });
      if (clearedSchwab.count > 0) {
        results.clearedSchwabPlaceholders.push(pos.symbol);
      }

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
        (results.autoCreated.length ? ` Auto-created ${results.autoCreated.length} new ticker(s): ${results.autoCreated.join(', ')}.` : '') +
        (results.reconciliationWarnings.length ? ` Lot reconciliation warnings: ${results.reconciliationWarnings.join(', ')}.` : '') +
        (results.clearedSchwabPlaceholders.length ? ` Replaced Schwab placeholder lot(s) with imported lot data for: ${results.clearedSchwabPlaceholders.join(', ')}.` : ''),
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

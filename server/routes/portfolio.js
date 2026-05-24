/**
 * portfolio.js — Position, Lot, and CashBalance routes
 *
 * POST   /api/portfolio/positions          create position + initial lots
 * GET    /api/portfolio/positions          list all active positions with lots
 * POST   /api/portfolio/positions/:id/lots add a lot to an existing position
 * DELETE /api/portfolio/lots/:id           remove a lot
 * POST   /api/portfolio/cash              upsert cash balance for an account
 * GET    /api/portfolio/cash              get all cash balances
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

// GET /api/portfolio/positions
// Returns all active positions with their lots and ticker info.
router.get('/positions', async (req, res) => {
  try {
    const positions = await prisma.position.findMany({
      where: { status: 'active' },
      include: {
        ticker: {
          select: {
            symbol: true,
            shortName: true,
            name: true,
            type: true,
            inScope: true,
            status: true,
          },
        },
        lots: {
          where: { closedDate: null },
          orderBy: { acquiredDate: 'asc' },
        },
      },
      orderBy: [
        { ticker: { symbol: 'asc' } },
        { account: 'asc' },
      ],
    });

    // Compute summary fields per position
    const enriched = positions.map(pos => {
      const totalShares = pos.lots.reduce((s, l) => s + l.shares, 0);
      const totalCost   = pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
      const avgCostBasis = totalShares > 0 ? totalCost / totalShares : 0;
      return { ...pos, totalShares, avgCostBasis };
    });

    res.json(enriched);
  } catch (err) {
    console.error('GET /positions error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/portfolio/positions
// Body: { symbol, account, lots: [{ shares, costBasis, acquiredDate, notes? }], notes? }
// Creates the position (or returns existing) and attaches lots.
router.post('/positions', async (req, res) => {
  const { symbol, account, lots = [], notes } = req.body;

  if (!symbol || !account) {
    return res.status(400).json({ error: 'symbol and account are required' });
  }
  if (!['taxable', 'ira', 'roth'].includes(account)) {
    return res.status(400).json({ error: 'account must be taxable, ira, or roth' });
  }
  if (!lots.length) {
    return res.status(400).json({ error: 'at least one lot is required' });
  }

  try {
    // Look up ticker — must already exist in RADAR
    const ticker = await prisma.ticker.findUnique({ where: { symbol: symbol.toUpperCase() } });
    if (!ticker) {
      return res.status(404).json({
        error: `Ticker ${symbol.toUpperCase()} not found. Add it to RADAR first.`,
      });
    }

    // Upsert the position (ticker+account pair)
    const position = await prisma.position.upsert({
      where: { tickerId_account: { tickerId: ticker.id, account } },
      update: { status: 'active', notes: notes ?? undefined },
      create: { tickerId: ticker.id, account, notes },
    });

    // Create all lots
    const createdLots = await Promise.all(
      lots.map(lot =>
        prisma.lot.create({
          data: {
            positionId:  position.id,
            shares:      parseFloat(lot.shares),
            costBasis:   parseFloat(lot.costBasis),
            acquiredDate: new Date(lot.acquiredDate),
            notes:       lot.notes ?? null,
          },
        })
      )
    );

    res.status(201).json({ position, lots: createdLots });
  } catch (err) {
    console.error('POST /positions error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/portfolio/positions/:id/lots
// Add a new lot to an existing position.
// Body: { shares, costBasis, acquiredDate, notes? }
router.post('/positions/:id/lots', async (req, res) => {
  const positionId = parseInt(req.params.id);
  const { shares, costBasis, acquiredDate, notes } = req.body;

  if (!shares || !costBasis || !acquiredDate) {
    return res.status(400).json({ error: 'shares, costBasis, and acquiredDate are required' });
  }

  try {
    const position = await prisma.position.findUnique({ where: { id: positionId } });
    if (!position) return res.status(404).json({ error: 'Position not found' });

    const lot = await prisma.lot.create({
      data: {
        positionId,
        shares:      parseFloat(shares),
        costBasis:   parseFloat(costBasis),
        acquiredDate: new Date(acquiredDate),
        notes:       notes ?? null,
      },
    });
    res.status(201).json(lot);
  } catch (err) {
    console.error('POST /positions/:id/lots error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/portfolio/lots/:id
// Remove a specific lot. Hard delete — use only before any live trading history
// exists. Post-launch this should soft-delete via closedDate.
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
// Cash balances
// ---------------------------------------------------------------------------

// GET /api/portfolio/cash
router.get('/cash', async (req, res) => {
  try {
    const balances = await prisma.cashBalance.findMany();
    res.json(balances);
  } catch (err) {
    console.error('GET /cash error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/portfolio/cash
// Body: { account, balance, asOfDate }
// Upserts cash balance for the given account.
router.post('/cash', async (req, res) => {
  const { account, balance, asOfDate } = req.body;

  if (!account || balance === undefined || !asOfDate) {
    return res.status(400).json({ error: 'account, balance, and asOfDate are required' });
  }
  if (!['taxable', 'ira', 'roth'].includes(account)) {
    return res.status(400).json({ error: 'account must be taxable, ira, or roth' });
  }

  try {
    const row = await prisma.cashBalance.upsert({
      where:  { account },
      update: { balance: parseFloat(balance), asOfDate: new Date(asOfDate) },
      create: { account, balance: parseFloat(balance), asOfDate: new Date(asOfDate) },
    });
    res.json(row);
  } catch (err) {
    console.error('POST /cash error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

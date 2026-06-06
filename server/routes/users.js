/**
 * users.js — OwnerProfile (Users tab) routes
 *
 *   GET    /api/users                  list all owner profiles
 *   POST   /api/users                  create a new owner profile manually
 *   PATCH  /api/users/:owner           update displayName, enoughNumber
 *   DELETE /api/users/:owner           delete (only if no accounts reference this owner)
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');

// GET /api/users
// Returns all OwnerProfile rows, each enriched with account count and
// total portfolio value (sum of position market values across all accounts).
router.get('/', async (req, res) => {
  try {
    const profiles = await prisma.ownerProfile.findMany({
      orderBy: { owner: 'asc' },
    });

    // Enrich each profile with account count and aggregate portfolio value
    const enriched = await Promise.all(profiles.map(async (p) => {
      const accounts = await prisma.account.findMany({
        where: { owner: p.owner },
        include: {
          positions: {
            where: { status: 'active' },
            include: { lots: { where: { closedDate: null } } },
          },
        },
      });

      const accountCount = accounts.length;

      // Sum market value across all positions (use lastPrice × shares if available)
      let totalMarketValue = 0;
      let totalCash = 0;
      for (const acct of accounts) {
        totalCash += acct.cashBalance ?? 0;
        for (const pos of acct.positions) {
          const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
          if (pos.lastPrice != null) {
            totalMarketValue += shares * pos.lastPrice;
          } else {
            // Fall back to cost basis if no price available
            const cost = pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
            totalMarketValue += cost;
          }
        }
      }

      return {
        ...p,
        accountCount,
        totalPortfolioValue: totalMarketValue + totalCash,
      };
    }));

    res.json(enriched);
  } catch (err) {
    console.error('GET /users error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/users
// Body: { owner, displayName?, enoughNumber? }
// Creates a new OwnerProfile manually (without needing an account first).
router.post('/', async (req, res) => {
  const { owner, displayName, enoughNumber } = req.body;
  if (!owner || !owner.trim()) {
    return res.status(400).json({ error: 'owner is required' });
  }
  try {
    const profile = await prisma.ownerProfile.create({
      data: { owner: owner.trim(), displayName, enoughNumber },
    });
    res.status(201).json(profile);
  } catch (err) {
    if (err.code === 'P2002') {
      return res.status(409).json({ error: `Owner "${owner}" already exists` });
    }
    console.error('POST /users error:', err);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/users/:owner
// Accepts any subset of OwnerProfile fields.
// Numeric fields: enoughNumber, minPositionDollar, cashReservePct, yearsToGoal, estSpecRatio
// String fields:  displayName, riskTolerance, taxSensitivity, accountPurpose,
//                 benchmarkBaseline, specExitSpeed, newMoneyBehavior
// Int fields:     maxPositions
// JSON fields:    domainsOfInterest (string[])
router.patch('/:owner', async (req, res) => {
  const { owner } = req.params;
  const body = req.body;
  const data = {};

  // String fields — empty string → null
  const strFields = ['displayName', 'riskTolerance', 'taxSensitivity', 'accountPurpose',
                     'benchmarkBaseline', 'specExitSpeed', 'newMoneyBehavior'];
  for (const f of strFields) {
    if (body[f] !== undefined) data[f] = body[f] === '' ? null : body[f];
  }

  // Float fields — empty string → null
  const floatFields = ['enoughNumber', 'minPositionDollar', 'cashReservePct', 'estSpecRatio'];
  for (const f of floatFields) {
    if (body[f] !== undefined) data[f] = body[f] === '' || body[f] === null ? null : Number(body[f]);
  }

  // Int fields
  if (body.maxPositions !== undefined) {
    data.maxPositions = body.maxPositions === '' || body.maxPositions === null ? null : parseInt(body.maxPositions);
  }
  if (body.yearsToGoal !== undefined) {
    data.yearsToGoal = body.yearsToGoal === '' || body.yearsToGoal === null ? null : parseInt(body.yearsToGoal);
  }

  // JSON fields
  if (body.domainsOfInterest !== undefined) {
    data.domainsOfInterest = body.domainsOfInterest ?? null;
  }

  try {
    const profile = await prisma.ownerProfile.update({
      where: { owner },
      data,
    });
    res.json(profile);
  } catch (err) {
    if (err.code === 'P2025') {
      return res.status(404).json({ error: `Owner "${owner}" not found` });
    }
    console.error('PATCH /users/:owner error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/users/:owner
// Blocked if any Account rows reference this owner.
router.delete('/:owner', async (req, res) => {
  const { owner } = req.params;
  try {
    const accountCount = await prisma.account.count({ where: { owner } });
    if (accountCount > 0) {
      return res.status(409).json({
        error: `Cannot delete owner "${owner}" — ${accountCount} account(s) still reference them. Delete or reassign accounts first.`,
      });
    }
    await prisma.ownerProfile.delete({ where: { owner } });
    res.json({ deleted: owner });
  } catch (err) {
    if (err.code === 'P2025') {
      return res.status(404).json({ error: `Owner "${owner}" not found` });
    }
    console.error('DELETE /users/:owner error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

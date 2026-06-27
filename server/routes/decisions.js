/**
 * decisions.js — Owner decision log for move-card recommendations
 *
 * POST /api/decisions  — record an accept or decline for one move card
 * GET  /api/decisions  — retrieve decisions for the calling owner (optional: ?since=ISO)
 */

const express      = require('express');
const router       = express.Router();
const prisma       = require('../lib/prisma');
const { requireAuth } = require('@clerk/express');

// ─── POST /api/decisions ──────────────────────────────────────────────────────
// Body: { symbol, moveType, decision, acceptedAmount?, declinedReason?, systemSnapshot }
// Owner is derived from the authenticated session — never from the body.

router.post('/', requireAuth(), async (req, res) => {
  const caller = req.ownerProfile;
  if (!caller) return res.status(401).json({ error: 'No owner profile linked to your account' });

  const { symbol, moveType, decision, acceptedAmount, declinedReason, systemSnapshot } = req.body;

  if (!symbol || !moveType || !decision) {
    return res.status(400).json({ error: 'symbol, moveType, and decision are required' });
  }
  if (!['accepted', 'declined', 'deferred'].includes(decision)) {
    return res.status(400).json({ error: 'decision must be accepted | declined | deferred' });
  }

  try {
    // Resolve tickerId from symbol — only portfolio + watchlist tickers expected here.
    const ticker = await prisma.ticker.findUnique({ where: { symbol: symbol.toUpperCase() } });
    if (!ticker) return res.status(404).json({ error: `Ticker "${symbol}" not found` });

    const record = await prisma.ownerDecision.create({
      data: {
        owner:          caller.owner,
        tickerId:       ticker.id,
        moveType,
        decision,
        acceptedAmount: acceptedAmount ?? null,
        declinedReason: declinedReason ?? null,
        systemSnapshot: systemSnapshot ?? {},
      },
    });

    res.json({ id: record.id, decidedAt: record.decidedAt });
  } catch (err) {
    console.error('POST /decisions error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /api/decisions ───────────────────────────────────────────────────────
// Returns all decisions for the calling owner, newest first.
// Optional query: ?since=2026-06-01T00:00:00Z

router.get('/', requireAuth(), async (req, res) => {
  const caller = req.ownerProfile;
  if (!caller) return res.status(401).json({ error: 'No owner profile linked to your account' });

  try {
    const since = req.query.since ? new Date(req.query.since) : undefined;
    const rows  = await prisma.ownerDecision.findMany({
      where: {
        owner:     caller.owner,
        ...(since ? { decidedAt: { gte: since } } : {}),
      },
      orderBy: { decidedAt: 'desc' },
      include: { ticker: { select: { symbol: true, name: true } } },
    });
    res.json(rows);
  } catch (err) {
    console.error('GET /decisions error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

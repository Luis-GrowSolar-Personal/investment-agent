const express = require('express');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');

const router = express.Router();

// GET /api/radar/tickers — all tickers with latest analysis + transcript count
router.get('/tickers', requireAuth(), async (req, res) => {
  try {
    const tickers = await prisma.ticker.findMany({
      include: {
        transcripts: {
          include: {
            analyses: { orderBy: { createdAt: 'desc' } },
          },
          orderBy: { callDate: 'desc' },
        },
      },
      orderBy: { symbol: 'asc' },
    });

    const result = tickers.map(ticker => {
      // Find the most recent analysis across all transcripts
      let latestAnalysis = null;
      for (const t of ticker.transcripts) {
        for (const a of t.analyses) {
          if (!latestAnalysis || a.createdAt > latestAnalysis.createdAt) {
            latestAnalysis = a;
          }
        }
      }

      return {
        id: ticker.id,
        symbol: ticker.symbol,
        name: ticker.name,
        status: ticker.status,
        capPercent: ticker.capPercent,
        type: ticker.type,
        transcriptCount: ticker.transcripts.length,
        latestAnalysis: latestAnalysis
          ? {
              thesisHealth: latestAnalysis.thesisHealth,
              recommendation: latestAnalysis.recommendation,
              recommendedSize: latestAnalysis.recommendedSize,
              createdAt: latestAnalysis.createdAt,
            }
          : null,
      };
    });

    res.json(result);
  } catch (err) {
    console.error('Error in GET /api/radar/tickers:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radar/tickers/:id/history — full thesis trajectory for one ticker
router.get('/tickers/:id/history', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const transcripts = await prisma.transcript.findMany({
      where: { tickerId: id },
      include: {
        analyses: { orderBy: { createdAt: 'asc' } },
      },
      orderBy: { callDate: 'asc' },
    });

    const history = transcripts.flatMap(t =>
      t.analyses.map(a => ({
        transcriptId: t.id,
        callDate: t.callDate,
        thesisHealth: a.thesisHealth,
        recommendation: a.recommendation,
        recommendedSize: a.recommendedSize,
        createdAt: a.createdAt,
      }))
    );

    res.json(history);
  } catch (err) {
    console.error('Error in GET /api/radar/tickers/:id/history:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/radar/tickers/:id — update name, type, capPercent, status
router.patch('/tickers/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  const { name, type, capPercent, status } = req.body;

  try {
    const updated = await prisma.ticker.update({
      where: { id },
      data: {
        ...(name      !== undefined && { name }),
        ...(type      !== undefined && { type }),
        ...(capPercent !== undefined && { capPercent }),
        ...(status    !== undefined && { status }),
      },
    });
    res.json(updated);
  } catch (err) {
    console.error('Error in PATCH /api/radar/tickers/:id:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/radar/tickers/:id — delete ticker and all associated data
router.delete('/tickers/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    // Must delete in FK dependency order: analyses → transcripts → ticker
    await prisma.analysis.deleteMany({
      where: { transcript: { tickerId: id } },
    });
    await prisma.transcript.deleteMany({ where: { tickerId: id } });
    await prisma.ticker.delete({ where: { id } });
    res.json({ deleted: true });
  } catch (err) {
    console.error('Error in DELETE /api/radar/tickers/:id:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

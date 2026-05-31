const express = require('express');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');

const router = express.Router();

// ── Shared re-scoring helpers ─────────────────────────────────────────────────

function extractSection(text, name) {
  const regex = new RegExp(`##\\s+${name}[\\s\\S]*?(?=\\n##|$)`, 'i');
  const m = text.match(regex);
  return m ? m[0] : '';
}

function firstLineParse(section, candidates) {
  const firstLine = section.split('\n').find(l => l.trim() && !l.startsWith('#')) ?? '';
  // Anchor to the start of the line — the prompt always puts the verdict first
  // ("Hold - ...", "Add to 15%", "Score: Weakening"). This prevents false matches
  // from body text like "will add a line" or "previously intact".
  for (const val of candidates) {
    if (new RegExp(`^\\s*(score:\\s*)?${val}\\b`, 'i').test(firstLine)) return val;
  }
  // Fallback: whole-word match anywhere in the full section
  for (const val of candidates) {
    if (new RegExp(`\\b${val}\\b`, 'i').test(section)) return val;
  }
  return null;
}

function rescoreRaw(rawOutput) {
  const thesisHealth   = firstLineParse(extractSection(rawOutput, 'THESIS HEALTH'),  ['Strengthening', 'Intact', 'Weakening', 'Broken']);
  const recommendation = firstLineParse(extractSection(rawOutput, 'RECOMMENDATION'), ['Exit', 'Trim', 'Add', 'Hold']);
  return { thesisHealth, recommendation };
}

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
      // Find the analysis from the most recent transcript by callDate.
      // Transcripts are already ordered callDate desc, so take the first one with an analysis.
      // Do NOT use analysis.createdAt — a re-evaluated old call would have a fresh timestamp
      // and would incorrectly outrank a more recent earnings call.
      let latestAnalysis = null;
      for (const t of ticker.transcripts) {
        if (t.analyses.length > 0) {
          latestAnalysis = t.analyses[0]; // analyses ordered createdAt desc; [0] is most recent
          break;
        }
      }

      // Days since the latest transcript's call date — drives the
      // "expected new transcript" badge in the UI. We use the latest
      // transcript by callDate (whether it has an analysis or not), since
      // staleness is a property of the call itself.
      // null when no transcripts exist yet (no badge to show).
      const latestTranscript = ticker.transcripts[0]; // ordered callDate desc
      const lastCallDate = latestTranscript ? latestTranscript.callDate : null;
      const daysSinceLastCall = lastCallDate
        ? Math.floor((Date.now() - new Date(lastCallDate).getTime()) / (1000 * 60 * 60 * 24))
        : null;

      return {
        id: ticker.id,
        symbol: ticker.symbol,
        name: ticker.name,
        shortName: ticker.shortName,
        status: ticker.status,
        capPercent: ticker.capPercent,
        type: ticker.type,
        inScope: ticker.inScope,
        tierOverride: ticker.tierOverride,
        tierMechanical: ticker.tierMechanical,
        transcriptCount: ticker.transcripts.length,
        lastCallDate,
        daysSinceLastCall,
        latestAnalysis: latestAnalysis
          ? {
              id: latestAnalysis.id,
              thesisHealth: latestAnalysis.thesisHealth,
              recommendation: latestAnalysis.recommendation,
              recommendedSize: latestAnalysis.recommendedSize,
              createdAt: latestAnalysis.createdAt,
              // Trend-layer fields (populated by sync_trend_to_db.py).
              // null when no verdict yet (insufficient history or pre-Stage-1 row).
              tier: latestAnalysis.tier,
              trajectory: latestAnalysis.trajectory,
              suggestedOverride: latestAnalysis.suggestedOverride,
              finalAction: latestAnalysis.finalAction,
              finalConfidence: latestAnalysis.finalConfidence,
              trendRationale: latestAnalysis.trendRationale,
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

// GET /api/radar/tickers/by-symbol/:symbol — lightweight lookup for Evaluator counter
router.get('/tickers/by-symbol/:symbol', requireAuth(), async (req, res) => {
  const symbol = req.params.symbol.toUpperCase();
  try {
    const ticker = await prisma.ticker.findUnique({
      where: { symbol },
      include: { _count: { select: { transcripts: true } } },
    });
    if (!ticker) return res.json(null);
    res.json({ id: ticker.id, symbol: ticker.symbol, shortName: ticker.shortName, transcriptCount: ticker._count.transcripts, status: ticker.status });
  } catch (err) {
    console.error('Error in GET /api/radar/tickers/by-symbol/:symbol:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radar/transcripts/:id — fetch transcript + most recent analysis
router.get('/transcripts/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const transcript = await prisma.transcript.findUnique({
      where: { id },
      select: {
        id: true,
        title: true,
        callDate: true,
        rawText: true,
        analyses: {
          orderBy: { createdAt: 'desc' },
          take: 1,
          select: { rawOutput: true, thesisHealth: true, recommendation: true, recommendedSize: true },
        },
      },
    });
    if (!transcript) return res.status(404).json({ error: 'Not found' });
    const { analyses, ...rest } = transcript;
    res.json({ ...rest, analysis: analyses[0] ?? null });
  } catch (err) {
    console.error('Error in GET /api/radar/transcripts/:id:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radar/tickers/:id/history — full thesis trajectory for one ticker.
// Returns the LATEST analysis per transcript (mirrors the radar list and the
// sync_trend_to_db.py latest-per-transcript filter). The rebackfill flow
// deliberately preserves older prompt-version analyses in the DB as an audit
// trail, but the history view shows only the active (latest createdAt)
// analysis per call to keep the trajectory readable.
router.get('/tickers/:id/history', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const transcripts = await prisma.transcript.findMany({
      where: { tickerId: id },
      include: {
        // orderBy createdAt desc + take 1 → the latest analysis per transcript
        analyses: { orderBy: { createdAt: 'desc' }, take: 1 },
      },
      orderBy: { callDate: 'asc' },
    });

    const history = transcripts.flatMap(t =>
      t.analyses.map(a => ({
        transcriptId: t.id,
        callDate: t.callDate,
        title: t.title,
        thesisHealth: a.thesisHealth,
        recommendation: a.recommendation,
        recommendedSize: a.recommendedSize,
        createdAt: a.createdAt,
        // Trend-layer fields
        tier: a.tier,
        trajectory: a.trajectory,
        suggestedOverride: a.suggestedOverride,
        finalAction: a.finalAction,
        finalConfidence: a.finalConfidence,
        trendRationale: a.trendRationale,
      }))
    );

    res.json(history);
  } catch (err) {
    console.error('Error in GET /api/radar/tickers/:id/history:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radar/advisories — every Analysis where the trend layer noticed
// a non-stable trajectory but didn't override the per-call recommendation.
// These are the "noticed something, didn't act" cases worth periodic review
// for emerging heuristics. Newest first.
router.get('/advisories', requireAuth(), async (req, res) => {
  try {
    const advisories = await prisma.analysis.findMany({
      where: { finalConfidence: 'advisory' },
      include: {
        transcript: {
          select: {
            id: true,
            callDate: true,
            title: true,
            ticker: { select: { id: true, symbol: true, shortName: true, status: true } },
          },
        },
      },
      orderBy: [
        { transcript: { callDate: 'desc' } },
      ],
    });

    const result = advisories.map(a => ({
      analysisId: a.id,
      transcriptId: a.transcript.id,
      callDate: a.transcript.callDate,
      title: a.transcript.title,
      tickerId: a.transcript.ticker.id,
      symbol: a.transcript.ticker.symbol,
      shortName: a.transcript.ticker.shortName,
      tickerStatus: a.transcript.ticker.status,
      perCallRec: a.recommendation,
      thesisHealth: a.thesisHealth,
      recommendedSize: a.recommendedSize,
      tier: a.tier,
      trajectory: a.trajectory,
      finalAction: a.finalAction,
      trendRationale: a.trendRationale,
    }));

    res.json(result);
  } catch (err) {
    console.error('Error in GET /api/radar/advisories:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/radar/tickers — create a ticker without a transcript (ETFs, commodities, crypto)
// Body: { symbol, name, shortName?, bucket?, notes? }
router.post('/tickers', requireAuth(), async (req, res) => {
  const { symbol, name, shortName, bucket, notes } = req.body;
  if (!symbol || !name) {
    return res.status(400).json({ error: 'symbol and name are required' });
  }
  const VALID_BUCKETS = ['equity', 'etf', 'crypto', 'commodity', null, undefined];
  if (!VALID_BUCKETS.includes(bucket)) {
    return res.status(400).json({ error: 'bucket must be equity, etf, crypto, commodity, or omitted' });
  }
  try {
    const existing = await prisma.ticker.findUnique({ where: { symbol: symbol.trim().toUpperCase() } });
    if (existing) {
      return res.status(409).json({ error: `Ticker ${symbol.toUpperCase()} already exists` });
    }
    const ticker = await prisma.ticker.create({
      data: {
        symbol:        symbol.trim().toUpperCase(),
        name:          name.trim(),
        shortName:     shortName?.trim() || name.trim().slice(0, 40),
        type:          'A',
        capPercent:    0,
        status:        'watchlist',
        inScope:       false,
        bucketOverride: bucket || null,
        notes:         notes || null,
      },
    });
    res.status(201).json(ticker);
  } catch (err) {
    console.error('POST /radar/tickers error:', err);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/radar/tickers/:id — update name, type, capPercent, status, inScope, tierOverride
router.patch('/tickers/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  const { symbol, name, type, capPercent, status, inScope, tierOverride } = req.body;

  try {
    const newSymbol = symbol?.trim().toUpperCase();

    // If renaming the symbol, check for an existing ticker with that symbol
    if (newSymbol) {
      const conflict = await prisma.ticker.findUnique({ where: { symbol: newSymbol } });
      if (conflict && conflict.id !== id) {
        // Merge: move all transcripts from current ticker to the existing one, then delete current
        await prisma.transcript.updateMany({
          where: { tickerId: id },
          data: { tickerId: conflict.id },
        });
        await prisma.ticker.delete({ where: { id } });
        // Update the surviving ticker with any additional fields provided
        const updated = await prisma.ticker.update({
          where: { id: conflict.id },
          data: {
            ...(name        !== undefined && { name }),
            ...(type        !== undefined && { type }),
            ...(capPercent  !== undefined && { capPercent }),
            ...(status      !== undefined && { status }),
            ...(inScope     !== undefined && { inScope }),
            ...(tierOverride !== undefined && { tierOverride: tierOverride || null }),
          },
        });
        return res.json({ ...updated, merged: true });
      }
    }

    const updated = await prisma.ticker.update({
      where: { id },
      data: {
        ...(newSymbol    !== undefined && { symbol: newSymbol }),
        ...(name         !== undefined && { name }),
        ...(type         !== undefined && { type }),
        ...(capPercent   !== undefined && { capPercent }),
        ...(status       !== undefined && { status }),
        ...(inScope      !== undefined && { inScope }),
        ...(tierOverride !== undefined && { tierOverride: tierOverride || null }),
      },
    });
    res.json(updated);
  } catch (err) {
    console.error('Error in PATCH /api/radar/tickers/:id:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/radar/transcripts/:id/rescore — re-score one transcript's analysis
router.post('/transcripts/:id/rescore', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const transcript = await prisma.transcript.findUnique({
      where: { id },
      include: { analyses: { orderBy: { createdAt: 'desc' }, take: 1 } },
    });
    if (!transcript) return res.status(404).json({ error: 'Not found' });
    const analysis = transcript.analyses[0];
    if (!analysis) return res.status(404).json({ error: 'No analysis to re-score' });

    const scores = rescoreRaw(analysis.rawOutput);
    const thesisHealth   = scores.thesisHealth   ?? analysis.thesisHealth;
    const recommendation = scores.recommendation ?? analysis.recommendation;

    await prisma.analysis.update({ where: { id: analysis.id }, data: { thesisHealth, recommendation } });
    res.json({ analysisId: analysis.id, thesisHealth, recommendation });
  } catch (err) {
    console.error('Error in POST /api/radar/transcripts/:id/rescore:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/radar/tickers/:id/rescore — re-score all analyses for one ticker
router.post('/tickers/:id/rescore', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const transcripts = await prisma.transcript.findMany({
      where: { tickerId: id },
      include: { analyses: { orderBy: { createdAt: 'desc' }, take: 1 } },
    });

    let updated = 0;
    for (const t of transcripts) {
      const analysis = t.analyses[0];
      if (!analysis) continue;
      const scores = rescoreRaw(analysis.rawOutput);
      const thesisHealth   = scores.thesisHealth   ?? analysis.thesisHealth;
      const recommendation = scores.recommendation ?? analysis.recommendation;
      if (thesisHealth !== analysis.thesisHealth || recommendation !== analysis.recommendation) {
        await prisma.analysis.update({ where: { id: analysis.id }, data: { thesisHealth, recommendation } });
        updated++;
      }
    }
    res.json({ updated });
  } catch (err) {
    console.error('Error in POST /api/radar/tickers/:id/rescore:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/radar/rescore-all — re-score every analysis in the database
router.post('/rescore-all', requireAuth(), async (req, res) => {
  try {
    const analyses = await prisma.analysis.findMany({ select: { id: true, rawOutput: true, thesisHealth: true, recommendation: true } });

    let updated = 0;
    for (const analysis of analyses) {
      const scores = rescoreRaw(analysis.rawOutput);
      const thesisHealth   = scores.thesisHealth   ?? analysis.thesisHealth;
      const recommendation = scores.recommendation ?? analysis.recommendation;
      if (thesisHealth !== analysis.thesisHealth || recommendation !== analysis.recommendation) {
        await prisma.analysis.update({ where: { id: analysis.id }, data: { thesisHealth, recommendation } });
        updated++;
      }
    }
    res.json({ total: analyses.length, updated });
  } catch (err) {
    console.error('Error in POST /api/radar/rescore-all:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/radar/transcripts/:id — update transcript title
router.patch('/transcripts/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  const { title } = req.body;
  try {
    const updated = await prisma.transcript.update({
      where: { id },
      data: { title: title?.trim() || null },
    });
    res.json({ id: updated.id, title: updated.title });
  } catch (err) {
    console.error('Error in PATCH /api/radar/transcripts/:id:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/radar/transcripts/:id — delete one transcript and its analyses
router.delete('/transcripts/:id', requireAuth(), async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    await prisma.analysis.deleteMany({ where: { transcriptId: id } });
    await prisma.transcript.delete({ where: { id } });
    res.json({ deleted: true });
  } catch (err) {
    console.error('Error in DELETE /api/radar/transcripts/:id:', err.message);
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

const express = require('express');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');

const router = express.Router();

// ── Analysis parsers ──────────────────────────────────────────────────────────

function extractSection(text, sectionName) {
  const regex = new RegExp(`##\\s+${sectionName}[\\s\\S]*?(?=\\n##|$)`, 'i');
  const match = text.match(regex);
  return match ? match[0] : '';
}

function parseThesisHealth(text) {
  const section = extractSection(text, 'THESIS HEALTH');
  for (const val of ['Strengthening', 'Intact', 'Weakening', 'Broken']) {
    if (section.toLowerCase().includes(val.toLowerCase())) return val;
  }
  return 'Unknown';
}

function parseRecommendation(text) {
  const section = extractSection(text, 'RECOMMENDATION');
  for (const val of ['Exit', 'Trim', 'Add', 'Hold']) {
    if (section.toLowerCase().includes(val.toLowerCase())) return val;
  }
  return 'Unknown';
}

function parseRecommendedSize(text) {
  const section = extractSection(text, 'RECOMMENDATION');
  const match = section.match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? parseFloat(match[1]) : null;
}

// ── Title generation ──────────────────────────────────────────────────────────

function generateTitle(shortName, symbol, callDate) {
  const date = callDate ? new Date(callDate) : new Date();
  const quarter = Math.floor(date.getMonth() / 3) + 1;
  const year = date.getFullYear();
  return `${shortName} (${symbol}) Q${quarter} ${year} Earnings Call Transcript`;
}

// ── Route ─────────────────────────────────────────────────────────────────────

router.post('/', requireAuth(), async (req, res) => {
  const { transcript, tickerSymbol, tickerName, shortName, callDate, title, analysis, structuredScore } = req.body;

  if (!tickerSymbol || typeof tickerSymbol !== 'string' || tickerSymbol.trim().length === 0) {
    return res.status(400).json({ error: 'tickerSymbol is required' });
  }
  if (!analysis || typeof analysis !== 'string' || analysis.trim().length === 0) {
    return res.status(400).json({ error: 'analysis is required' });
  }
  if (!transcript || typeof transcript !== 'string' || transcript.trim().length === 0) {
    return res.status(400).json({ error: 'transcript is required' });
  }

  const symbol = tickerSymbol.trim().toUpperCase();

  // shortName fallback: provided → first word of tickerName → symbol
  const effectiveShortName =
    shortName?.trim() ||
    (tickerName?.trim() ? tickerName.trim().split(/\s+/)[0] : symbol);

  const thesisHealth    = parseThesisHealth(analysis);
  const recommendation  = parseRecommendation(analysis);
  const recommendedSize = parseRecommendedSize(analysis);

  try {
    const ticker = await prisma.ticker.upsert({
      where: { symbol },
      // Update shortName if provided — it may have been corrected by the user
      update: {
        ...(shortName?.trim() && { shortName: shortName.trim() }),
      },
      create: {
        symbol,
        name: tickerName?.trim() || symbol,
        shortName: effectiveShortName,
        type: 'A',
        capPercent: 35,
      },
    });

    // Enforce 6-transcript limit for watchlist tickers (Design Principle #3)
    if (ticker.status === 'watchlist') {
      const existing = await prisma.transcript.findMany({
        where: { tickerId: ticker.id },
        orderBy: { callDate: 'asc' },
        select: { id: true },
      });
      if (existing.length >= 6) {
        const oldest = existing[0];
        await prisma.analysis.deleteMany({ where: { transcriptId: oldest.id } });
        await prisma.transcript.delete({ where: { id: oldest.id } });
      }
    }

    // Use saved shortName (may have just been updated) for the title
    const displayShortName = ticker.shortName || effectiveShortName;
    const standardTitle = title?.trim() || generateTitle(displayShortName, symbol, callDate);

    const transcriptRecord = await prisma.transcript.create({
      data: {
        tickerId: ticker.id,
        rawText:  transcript,
        callDate: callDate ? new Date(callDate) : new Date(),
        title:    standardTitle,
      },
    });

    const s = structuredScore || {};
    const analysisRecord = await prisma.analysis.create({
      data: {
        transcriptId:    transcriptRecord.id,
        rawOutput:       analysis,
        thesisHealth,
        recommendation,
        recommendedSize,
        // Structured score fields (all optional)
        thesisDelta:                     s.thesisDelta                     ?? null,
        freshMoneyAllocation:            s.freshMoneyAllocation            ?? null,
        stumbleType:                     s.stumbleType                     ?? null,
        threatMechanismImpaired:         s.threatMechanismImpaired         ?? null,
        credibilityDelta:                s.credibilityDelta                ?? null,
        activeDriverCount:               s.activeDriverCount               ?? null,
        ratchetTranche:                  s.ratchetTranche                  ?? null,
        blindSpotsTriggered:             s.blindSpotsTriggered             ?? null,
        capPercent:                      s.capPercent                      ?? null,
        mitigationArgumentPresent:       s.mitigationArgumentPresent       ?? null,
        mitigationCapabilityTrackRecord: s.mitigationCapabilityTrackRecord ?? null,
      },
    });

    res.json({
      tickerId:     ticker.id,
      transcriptId: transcriptRecord.id,
      analysisId:   analysisRecord.id,
      title:        standardTitle,
    });
  } catch (err) {
    console.error('Error in /api/save:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

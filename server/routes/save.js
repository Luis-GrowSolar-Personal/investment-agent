const express = require('express');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');

const router = express.Router();

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

router.post('/', requireAuth(), async (req, res) => {
  const { transcript, tickerSymbol, tickerName, callDate, analysis } = req.body;

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

  const thesisHealth = parseThesisHealth(analysis);
  const recommendation = parseRecommendation(analysis);
  const recommendedSize = parseRecommendedSize(analysis);

  try {
    const ticker = await prisma.ticker.upsert({
      where: { symbol },
      update: {},
      create: {
        symbol,
        name: tickerName?.trim() || symbol,
        type: 'A',
        capPercent: 35,
      },
    });

    const transcriptRecord = await prisma.transcript.create({
      data: {
        tickerId: ticker.id,
        rawText: transcript,
        callDate: callDate ? new Date(callDate) : new Date(),
      },
    });

    const analysisRecord = await prisma.analysis.create({
      data: {
        transcriptId: transcriptRecord.id,
        rawOutput: analysis,
        thesisHealth,
        recommendation,
        recommendedSize,
      },
    });

    res.json({
      tickerId: ticker.id,
      transcriptId: transcriptRecord.id,
      analysisId: analysisRecord.id,
    });
  } catch (err) {
    console.error('Error in /api/save:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

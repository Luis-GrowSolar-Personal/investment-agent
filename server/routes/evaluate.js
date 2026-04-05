const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');
const { requireAuth } = require('@clerk/express');
const prisma = require('../lib/prisma');

const router = express.Router();
const client = new Anthropic();

// Read prompt at startup, relative to repo root
const PROMPT_PATH = path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md');
const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8');

// --- Parsing helpers ---

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
  // Check Exit before Trim/Add/Hold to avoid partial matches
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

// --- Route ---

router.post('/', requireAuth(), async (req, res) => {
  const { transcript, tickerSymbol, tickerName, callDate } = req.body;

  if (!transcript || typeof transcript !== 'string' || transcript.trim().length === 0) {
    return res.status(400).json({ error: 'transcript is required' });
  }
  if (!tickerSymbol || typeof tickerSymbol !== 'string' || tickerSymbol.trim().length === 0) {
    return res.status(400).json({ error: 'tickerSymbol is required' });
  }

  const symbol = tickerSymbol.trim().toUpperCase();

  try {
    // 1. Call Claude
    const message = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content: `Please evaluate the following earnings call transcript:\n\n${transcript}`,
        },
      ],
    });

    const analysis = message.content[0].text;

    // 2. Parse structured fields from response
    const thesisHealth = parseThesisHealth(analysis);
    const recommendation = parseRecommendation(analysis);
    const recommendedSize = parseRecommendedSize(analysis);

    // 3. Upsert Ticker — never overwrite name/type if it already exists
    const ticker = await prisma.ticker.upsert({
      where: { symbol },
      update: {},
      create: {
        symbol,
        name: tickerName?.trim() || symbol,
        type: 'A',       // default; user can update via dashboard later
        capPercent: 35,  // default
      },
    });

    // 4. Create Transcript
    const transcript_record = await prisma.transcript.create({
      data: {
        tickerId: ticker.id,
        rawText: transcript,
        callDate: callDate ? new Date(callDate) : new Date(),
      },
    });

    // 5. Create Analysis
    const analysisRecord = await prisma.analysis.create({
      data: {
        transcriptId: transcript_record.id,
        rawOutput: analysis,
        thesisHealth,
        recommendation,
        recommendedSize,
      },
    });

    res.json({
      analysis,
      tickerId: ticker.id,
      transcriptId: transcript_record.id,
      analysisId: analysisRecord.id,
    });
  } catch (err) {
    console.error('Error in /api/evaluate:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

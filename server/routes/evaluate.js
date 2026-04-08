const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');
const { requireAuth } = require('@clerk/express');

const router = express.Router();
const client = new Anthropic();

const PROMPT_PATH = path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md');
const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8');

function parseMetadata(raw) {
  const match = raw.match(/---METADATA---\s*(\{[\s\S]*?\})\s*---END METADATA---/);
  if (!match) return { tickerSymbol: null, companyName: null, callDate: null, shortName: null };
  try {
    return JSON.parse(match[1]);
  } catch {
    return { tickerSymbol: null, companyName: null, callDate: null, shortName: null };
  }
}

function stripMetadata(raw) {
  return raw.replace(/\n*---METADATA---[\s\S]*?---END METADATA---\s*$/, '').trim();
}

function parseStructured(raw) {
  const match = raw.match(/---STRUCTURED---\s*(\{[\s\S]*?\})\s*---END STRUCTURED---/);
  if (!match) return null;
  try {
    return JSON.parse(match[1]);
  } catch {
    return null;
  }
}

function stripStructured(raw) {
  return raw.replace(/\n*---STRUCTURED---[\s\S]*?---END STRUCTURED---\s*/g, '').trim();
}

router.post('/', requireAuth(), async (req, res) => {
  const { transcript } = req.body;

  if (!transcript || typeof transcript !== 'string' || transcript.trim().length === 0) {
    return res.status(400).json({ error: 'transcript is required' });
  }

  try {
    const message = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content:
            `Please evaluate the following earnings call transcript:\n\n${transcript}\n\n` +
            `After your evaluation, extract the following from the transcript and append it exactly in this format:\n` +
            `---METADATA---\n` +
            `{"tickerSymbol":"...","companyName":"...","callDate":"YYYY-MM-DD","shortName":"..."}\n` +
            `---END METADATA---\n` +
            `shortName is the short commonly-used name for the company (e.g. "Amprius" not "Amprius Technologies Inc."). ` +
            `Use null for any field you cannot find.`,
        },
      ],
    });

    const raw = message.content[0].text;
    const metadata = parseMetadata(raw);
    const structuredScore = parseStructured(raw);
    // Strip both blocks before returning the narrative
    const analysis = stripStructured(stripMetadata(raw));

    res.json({
      analysis,
      structuredScore,
      tickerSymbol: metadata.tickerSymbol,
      companyName: metadata.companyName,
      callDate: metadata.callDate,
      shortName: metadata.shortName,
    });
  } catch (err) {
    console.error('Error in /api/evaluate:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

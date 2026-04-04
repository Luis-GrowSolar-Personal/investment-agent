const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');

const router = express.Router();
const client = new Anthropic();

// Read prompt at startup, relative to repo root
const PROMPT_PATH = path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md');
const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8');

router.post('/', async (req, res) => {
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
          content: `Please evaluate the following earnings call transcript:\n\n${transcript}`,
        },
      ],
    });

    const analysis = message.content[0].text;
    res.json({ analysis });
  } catch (err) {
    console.error('Anthropic API error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

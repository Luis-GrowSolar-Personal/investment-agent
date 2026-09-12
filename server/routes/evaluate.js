const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');
const { requireAuth } = require('@clerk/express');

const { PROMPT_VERSION, MODEL_VERSION } = require('../lib/versions');
const { checkPromptHash } = require('../lib/versionGuard');

const router = express.Router();
const client = new Anthropic();

const PROMPT_PATH = path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md');
const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8');

// Checked once at startup so a mismatch is visible in the logs immediately,
// not just the first time someone calls /api/evaluate. Deliberate deviation
// from 2026-09-03-prompt-version-drift.md §7 / 2026-09-05 §8, which proposed
// refusing to BOOT on mismatch: Luis tests against the deployed Railway app,
// and taking the whole app down over a prompt hash is a worse failure than a
// disabled scoring route. So: log loudly, and evaluate.js's own request
// handler below is what actually refuses to score. See wrap-up for this run.
// Wrapped in try/catch (2026-09-12 follow-up, prompts/drift-guards-followup.md):
// checkPromptHash() reads VERSION_REGISTRY.json, and an unreadable/malformed
// registry would otherwise throw here, at require() time -- the same
// boot-refusal landmine Step 1 of that follow-up defused in versions.js,
// found also present here while doing that fix. Same fix, same reasoning:
// the scoring route below (POST /) is the enforcement point; a registry
// read failure at import must not take the whole server down.
let startupCheck;
try {
  startupCheck = checkPromptHash('evaluation_prompt', systemPrompt);
} catch (err) {
  console.error(
    `[versionGuard] STARTUP: could not check evaluation_prompt against the registry: ${err.message}\n` +
    `  Scoring will be REFUSED (fail-closed) until the registry is readable again.`
  );
  startupCheck = { ok: false, promotedHash: 'UNREADABLE', actualHash: 'UNREADABLE', candidateUsed: null };
}
if (!startupCheck.ok) {
  console.error(
    `[versionGuard] STARTUP MISMATCH on evaluation_prompt: ${startupCheck.reason || '(registry unreadable)'}\n` +
    `  promoted=${startupCheck.promotedHash}\n  actual=${startupCheck.actualHash}\n` +
    `  Scoring will be REFUSED until PROMPT_CANDIDATE names a registered candidate, or the file is restored.`
  );
} else if (startupCheck.candidateUsed) {
  console.warn(
    `[versionGuard] evaluation_prompt running as PROMPT_CANDIDATE="${startupCheck.candidateUsed}" ` +
    `(not the promoted version). Every row written this session will be stamped with the candidate version.`
  );
}

function parseMetadata(raw) {
  const match = raw.match(/---METADATA---\s*(\{[\s\S]*?\})\s*---END METADATA---/);
  if (!match) return { tickerSymbol: null, companyName: null, callDate: null, shortName: null, fiscalQuarter: null, fiscalYear: null };
  try {
    return JSON.parse(match[1]);
  } catch {
    return { tickerSymbol: null, companyName: null, callDate: null, shortName: null, fiscalQuarter: null, fiscalYear: null };
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

  let promptCheck;
  try {
    promptCheck = checkPromptHash('evaluation_prompt', systemPrompt);
  } catch (err) {
    // Registry unreadable -- refuse the request cleanly rather than letting
    // an uncaught throw crash this async handler. Same fail-closed outcome
    // as a hash mismatch, just a different cause.
    console.error(`[versionGuard] request-time check failed: ${err.message}`);
    return res.status(503).json({
      error: 'Scoring refused: VERSION_REGISTRY.json could not be read',
      detail: err.message,
    });
  }
  if (!promptCheck.ok) {
    return res.status(409).json({
      error: 'Scoring refused: docs/EVALUATION_PROMPT.md does not match the promoted artifact in VERSION_REGISTRY.json',
      promotedHash: promptCheck.promotedHash,
      actualHash: promptCheck.actualHash,
      hint: 'Restore the promoted content, or set PROMPT_CANDIDATE=<registered candidate version> to score deliberately against a candidate.',
    });
  }
  // A candidate override stamps the candidate's version, not the promoted
  // one -- the whole point of the escape hatch is that this row is
  // auditable as candidate output, never mistaken for a promoted-prompt row.
  const effectivePromptVersion = promptCheck.candidateUsed || PROMPT_VERSION;

  try {
    const message = await client.messages.create({
      model: MODEL_VERSION,
      max_tokens: 4096,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content:
            `Please evaluate the following earnings call transcript:\n\n${transcript}\n\n` +
            `After your evaluation, extract the following from the transcript and append it exactly in this format:\n` +
            `---METADATA---\n` +
            `{"tickerSymbol":"...","companyName":"...","callDate":"YYYY-MM-DD","shortName":"...","fiscalQuarter":null,"fiscalYear":null}\n` +
            `---END METADATA---\n` +
            `shortName is the short commonly-used name for the company (e.g. "Amprius" not "Amprius Technologies Inc."). ` +
            `fiscalQuarter is the integer quarter number stated in the call title (e.g. 4 for "Q4 2025 Earnings Call") — do NOT derive it from the call date. ` +
            `fiscalYear is the fiscal year stated in the call title (e.g. 2025 for "Q4 2025 Earnings Call"). ` +
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
      promptVersion: effectivePromptVersion,
      modelVersion:  MODEL_VERSION,
      tickerSymbol: metadata.tickerSymbol,
      companyName: metadata.companyName,
      callDate: metadata.callDate,
      shortName: metadata.shortName,
      fiscalQuarter: metadata.fiscalQuarter ?? null,
      fiscalYear: metadata.fiscalYear ?? null,
    });
  } catch (err) {
    console.error('Error in /api/evaluate:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

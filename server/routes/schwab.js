/**
 * schwab.js
 *
 * Schwab Trader API — OAuth scaffolding (Phase 1).
 *
 * GET /api/schwab/connect
 *   Auth required. Redirects the browser to Schwab's authorization page.
 *
 * GET /api/schwab/callback
 *   Schwab redirects here with ?code=... after the user authorizes.
 *   Exchanges the code for tokens and persists them (SchwabToken, singleton
 *   row). Not behind requireAuth() — see note below.
 *
 * GET /api/schwab/status
 *   Auth required. Connection status only — never returns token values.
 *
 * GET /api/schwab/accounts
 *   Auth required. Phase 2 step 1 — READ-ONLY preview of Schwab-linked
 *   accounts + positions (masked account numbers), alongside existing
 *   local Account rows for comparison. No DB writes.
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { requireAuth } = require('@clerk/express');
const schwabAuth = require('../lib/schwabAuth');
const { previewAccounts } = require('../lib/schwabAccounts');

// ── GET /api/schwab/connect ───────────────────────────────────────────────

router.get('/connect', requireAuth(), (req, res) => {
  try {
    const url = schwabAuth.getAuthUrl();
    res.redirect(url);
  } catch (err) {
    console.error('GET /schwab/connect error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/schwab/callback ──────────────────────────────────────────────
//
// Not behind requireAuth(): this is a server-to-browser redirect from
// Schwab's own domain, and the only effect is writing to the singleton
// SchwabToken row (no user-scoped data, no portfolio data). The /connect
// step above is already gated on a logged-in session.

router.get('/callback', async (req, res) => {
  const { code, error } = req.query;

  if (error) {
    return res.status(400).send(`Schwab authorization error: ${error}`);
  }
  if (!code) {
    return res.status(400).send('Missing "code" parameter from Schwab callback');
  }

  try {
    await schwabAuth.exchangeCodeForTokens(prisma, code);
    // Phase 2 will redirect to the Portfolio page with a success banner.
    res.redirect('/?schwab=connected');
  } catch (err) {
    console.error('GET /schwab/callback error:', err);
    res.status(500).send(`Schwab token exchange failed: ${err.message}`);
  }
});

// ── GET /api/schwab/status ────────────────────────────────────────────────

router.get('/status', requireAuth(), async (req, res) => {
  try {
    const status = await schwabAuth.getStatus(prisma);
    res.json(status);
  } catch (err) {
    console.error('GET /schwab/status error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/schwab/accounts ──────────────────────────────────────────────

router.get('/accounts', requireAuth(), async (req, res) => {
  try {
    const result = await previewAccounts(prisma);
    res.json(result);
  } catch (err) {
    console.error('GET /schwab/accounts error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

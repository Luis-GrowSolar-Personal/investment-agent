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
 *
 * GET /api/schwab/reconcile
 *   Auth required. Phase 2 step 2 — matches Schwab accounts to local
 *   Account rows by schwabAccountHash, returns matched/unmatched accounts
 *   plus position-level share-count diffs for matched accounts. No DB writes.
 *
 * POST /api/schwab/match
 *   Auth required. Body: { accountId, schwabAccountHash }. Links an existing
 *   local Account to a Schwab account hash.
 *
 * POST /api/schwab/accounts/create
 *   Auth required. Body: { schwabAccountHash, name, type, owner, managed? }.
 *   Creates a new local Account for an unmatched Schwab account — name/type/
 *   owner are user-confirmed, never guessed (tax + allocator implications).
 *
 * POST /api/schwab/sync/:accountId
 *   Auth required. Syncs cash balance + new positions for a matched account.
 *   Never overwrites manual/import lots — see schwabSync.js for details.
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { requireAuth } = require('@clerk/express');
const schwabAuth = require('../lib/schwabAuth');
const { previewAccounts } = require('../lib/schwabAccounts');
const schwabSync = require('../lib/schwabSync');

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

// ── GET /api/schwab/reconcile ─────────────────────────────────────────────

router.get('/reconcile', requireAuth(), async (req, res) => {
  try {
    const result = await schwabSync.getReconciliation(prisma);
    res.json(result);
  } catch (err) {
    console.error('GET /schwab/reconcile error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/schwab/match ────────────────────────────────────────────────

router.post('/match', requireAuth(), async (req, res) => {
  const { accountId, schwabAccountHash } = req.body;
  if (!accountId || !schwabAccountHash) {
    return res.status(400).json({ error: 'accountId and schwabAccountHash are required' });
  }
  try {
    const account = await schwabSync.matchAccount(prisma, parseInt(accountId), schwabAccountHash);
    res.json(account);
  } catch (err) {
    if (err.code === 'P2002') {
      return res.status(409).json({ error: 'That Schwab account is already linked to a different local account' });
    }
    console.error('POST /schwab/match error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/schwab/accounts/create ─────────────────────────────────────

router.post('/accounts/create', requireAuth(), async (req, res) => {
  const { schwabAccountHash, name, type, owner, managed } = req.body;
  try {
    const account = await schwabSync.createAccountFromSchwab(prisma, {
      schwabAccountHash, name, type, owner, managed,
    });
    res.status(201).json(account);
  } catch (err) {
    if (err.code === 'P2002') {
      return res.status(409).json({ error: `Account "${name}" already exists for ${owner}, or that Schwab account is already linked` });
    }
    console.error('POST /schwab/accounts/create error:', err);
    res.status(400).json({ error: err.message });
  }
});

// ── POST /api/schwab/sync/:accountId ──────────────────────────────────────

router.post('/sync/:accountId', requireAuth(), async (req, res) => {
  const accountId = parseInt(req.params.accountId);
  try {
    const result = await schwabSync.syncAccount(prisma, accountId);
    res.json(result);
  } catch (err) {
    console.error('POST /schwab/sync/:accountId error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

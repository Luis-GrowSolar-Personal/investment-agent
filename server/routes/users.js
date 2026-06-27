/**
 * users.js — OwnerProfile (Users tab) routes
 *
 *   GET    /api/users                  list all owner profiles
 *   POST   /api/users                  create a new owner profile manually
 *   PATCH  /api/users/:owner           update displayName, enoughNumber
 *   DELETE /api/users/:owner           delete (only if no accounts reference this owner)
 */

const express = require('express');
const router  = express.Router();
const prisma  = require('../lib/prisma');
const { requireAdmin } = require('../lib/authMiddleware');
const { clerkClient }  = require('@clerk/express');

// All /api/users routes are admin-only.
// Bootstrap bypass: if no admin with a Clerk ID exists yet, allow through
// so the first admin can self-configure (see authMiddleware.js).
router.use(requireAdmin);

// GET /api/users/clerk-users
// Lists all Clerk users so the Admin UI can link logins to OwnerProfiles.
// Must be defined before /:owner routes to avoid being swallowed by the param.
// Returns: [{ id, email, firstName, lastName, lastActiveAt }]
router.get('/clerk-users', async (req, res) => {
  try {
    const response = await clerkClient.users.getUserList({ limit: 200 });
    const users = (response.data ?? []).map(u => ({
      id:           u.id,
      email:        u.emailAddresses?.[0]?.emailAddress ?? '',
      firstName:    u.firstName ?? '',
      lastName:     u.lastName  ?? '',
      lastActiveAt: u.lastActiveAt ?? null,
    }));
    res.json(users);
  } catch (err) {
    console.error('GET /users/clerk-users error:', err);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/users
// Returns all OwnerProfile rows, each enriched with account count and
// total portfolio value (sum of position market values across all accounts).
router.get('/', async (req, res) => {
  try {
    const profiles = await prisma.ownerProfile.findMany({
      orderBy: { owner: 'asc' },
    });

    // Enrich each profile with account count and aggregate portfolio value
    const enriched = await Promise.all(profiles.map(async (p) => {
      const accounts = await prisma.account.findMany({
        where: { owner: p.owner },
        include: {
          positions: {
            where: { status: 'active' },
            include: { lots: { where: { closedDate: null } } },
          },
        },
      });

      const accountCount = accounts.length;

      // Sum market value across all positions (use lastPrice × shares if available)
      let totalMarketValue = 0;
      let totalCash = 0;
      for (const acct of accounts) {
        totalCash += acct.cashBalance ?? 0;
        for (const pos of acct.positions) {
          const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
          if (pos.lastPrice != null) {
            totalMarketValue += shares * pos.lastPrice;
          } else {
            // Fall back to cost basis if no price available
            const cost = pos.lots.reduce((s, l) => s + l.shares * l.costBasis, 0);
            totalMarketValue += cost;
          }
        }
      }

      return {
        ...p,
        accountCount,
        totalPortfolioValue: totalMarketValue + totalCash,
      };
    }));

    res.json(enriched);
  } catch (err) {
    console.error('GET /users error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/users
// Body: { owner, displayName?, enoughNumber? }
// Creates a new OwnerProfile manually (without needing an account first).
router.post('/', async (req, res) => {
  const { owner, displayName, enoughNumber } = req.body;
  if (!owner || !owner.trim()) {
    return res.status(400).json({ error: 'owner is required' });
  }
  try {
    const profile = await prisma.ownerProfile.create({
      data: { owner: owner.trim(), displayName, enoughNumber },
    });
    res.status(201).json(profile);
  } catch (err) {
    if (err.code === 'P2002') {
      return res.status(409).json({ error: `Owner "${owner}" already exists` });
    }
    console.error('POST /users error:', err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/users/:owner/invite
// Body: { email }
// Two-path logic:
//   1. Email already has a Clerk account → link clerkUserId directly (no invite email needed).
//   2. Email is new to Clerk → create an invitation, save inviteEmail on the profile.
//      autoLinkMiddleware will complete the link when the user accepts and first logs in.
router.post('/:owner/invite', async (req, res) => {
  const { owner } = req.params;
  const email = req.body.email?.trim().toLowerCase();
  if (!email) return res.status(400).json({ error: 'email is required' });

  try {
    const profile = await prisma.ownerProfile.findUnique({ where: { owner } });
    if (!profile) return res.status(404).json({ error: `Owner "${owner}" not found` });

    // Check whether this email already has a Clerk account
    const existing = await clerkClient.users.getUserList({ emailAddress: [email] });
    const clerkUser = existing.data?.[0];

    if (clerkUser) {
      // Already a Clerk user — link directly, no invite needed
      const updated = await prisma.ownerProfile.update({
        where: { owner },
        data: { clerkUserId: clerkUser.id, inviteEmail: null },
      });
      return res.json({ ...updated, message: 'User already exists — linked directly.' });
    }

    // New user — send a Clerk invitation
    await clerkClient.invitations.createInvitation({ emailAddress: email });

    const updated = await prisma.ownerProfile.update({
      where: { owner },
      data: { inviteEmail: email },
    });
    res.json({ ...updated, message: `Invite sent to ${email}.` });
  } catch (err) {
    // Clerk throws on duplicate active invitations — surface a readable message
    const clerkMsg = err.errors?.[0]?.longMessage ?? err.errors?.[0]?.message;
    if (clerkMsg) return res.status(409).json({ error: clerkMsg });
    console.error('POST /users/:owner/invite error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/users/:owner/invite
// Cancels a pending invite by clearing inviteEmail.
// The Clerk invitation itself is left to expire (7-day TTL) — no Clerk API call needed.
router.delete('/:owner/invite', async (req, res) => {
  const { owner } = req.params;
  try {
    const updated = await prisma.ownerProfile.update({
      where: { owner },
      data: { inviteEmail: null },
    });
    res.json(updated);
  } catch (err) {
    if (err.code === 'P2025') {
      return res.status(404).json({ error: `Owner "${owner}" not found` });
    }
    console.error('DELETE /users/:owner/invite error:', err);
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/users/:owner
// Accepts any subset of OwnerProfile fields.
// Numeric fields: enoughNumber, minPositionDollar, cashReservePct, yearsToGoal, estSpecRatio
// String fields:  displayName, riskTolerance, taxSensitivity, accountPurpose,
//                 benchmarkBaseline, specExitSpeed, newMoneyBehavior
// Int fields:     maxPositions
// JSON fields:    domainsOfInterest (string[])
router.patch('/:owner', async (req, res) => {
  const { owner } = req.params;
  const body = req.body;
  const data = {};

  // String fields — empty string → null
  const strFields = ['displayName', 'clerkUserId', 'riskTolerance', 'taxSensitivity',
                     'accountPurpose', 'benchmarkBaseline', 'specExitSpeed', 'newMoneyBehavior'];
  for (const f of strFields) {
    if (body[f] !== undefined) data[f] = body[f] === '' ? null : body[f];
  }

  // Role field — never null; default to 'user'
  if (body.role !== undefined) {
    data.role = ['admin', 'user'].includes(body.role) ? body.role : 'user';
  }

  // Float fields — empty string → null
  const floatFields = ['enoughNumber', 'minPositionDollar', 'cashReservePct', 'estSpecRatio'];
  for (const f of floatFields) {
    if (body[f] !== undefined) data[f] = body[f] === '' || body[f] === null ? null : Number(body[f]);
  }

  // Int fields
  if (body.maxPositions !== undefined) {
    data.maxPositions = body.maxPositions === '' || body.maxPositions === null ? null : parseInt(body.maxPositions);
  }
  if (body.yearsToGoal !== undefined) {
    data.yearsToGoal = body.yearsToGoal === '' || body.yearsToGoal === null ? null : parseInt(body.yearsToGoal);
  }

  // JSON fields
  if (body.domainsOfInterest !== undefined) {
    data.domainsOfInterest = body.domainsOfInterest ?? null;
  }

  try {
    const profile = await prisma.ownerProfile.update({
      where: { owner },
      data,
    });
    res.json(profile);
  } catch (err) {
    if (err.code === 'P2025') {
      return res.status(404).json({ error: `Owner "${owner}" not found` });
    }
    console.error('PATCH /users/:owner error:', err);
    res.status(500).json({ error: err.message });
  }
});

// DELETE /api/users/:owner
// Blocked if any Account rows reference this owner.
router.delete('/:owner', async (req, res) => {
  const { owner } = req.params;
  try {
    const accountCount = await prisma.account.count({ where: { owner } });
    if (accountCount > 0) {
      return res.status(409).json({
        error: `Cannot delete owner "${owner}" — ${accountCount} account(s) still reference them. Delete or reassign accounts first.`,
      });
    }
    await prisma.ownerProfile.delete({ where: { owner } });
    res.json({ deleted: owner });
  } catch (err) {
    if (err.code === 'P2025') {
      return res.status(404).json({ error: `Owner "${owner}" not found` });
    }
    console.error('DELETE /users/:owner error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

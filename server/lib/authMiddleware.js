/**
 * authMiddleware.js — Role-based access control for Express routes.
 *
 * requireAdmin
 * ────────────
 * Allows only Clerk-authenticated users whose OwnerProfile.clerkUserId
 * matches their Clerk ID AND whose role is 'admin'.
 *
 * Bootstrap bypass: if no OwnerProfile has both role='admin' and a
 * non-null clerkUserId yet, all authenticated requests are allowed
 * through. This lets the first admin link their Clerk account via the
 * Admin page without getting locked out. Once any admin is configured,
 * the gate is active for all subsequent requests.
 *
 * Depends on clerkMiddleware() having already run (populates req.auth).
 */

const prisma = require('./prisma');

/**
 * requireAdmin
 * Uses req.ownerProfile set by autoLinkMiddleware — no extra DB query in the
 * common case. Falls back to a DB check only when the profile is null (i.e.
 * the Clerk user isn't linked yet) to support the bootstrap scenario where
 * the first admin needs to self-configure.
 */
async function requireAdmin(req, res, next) {
  if (!req.auth?.userId) {
    return res.status(401).json({ error: 'Unauthenticated' });
  }

  const profile = req.ownerProfile; // set by autoLinkMiddleware

  if (!profile) {
    // Unlinked user — check bootstrap mode (no admin configured at all)
    try {
      const adminExists = await prisma.ownerProfile.findFirst({
        where: { role: 'admin', clerkUserId: { not: null } },
        select: { owner: true },
      });
      if (!adminExists) return next(); // cold-start bypass
    } catch (err) {
      console.error('[requireAdmin] bootstrap check error:', err.message);
    }
    return res.status(403).json({ error: 'Admin access required' });
  }

  if (profile.role !== 'admin') {
    return res.status(403).json({ error: 'Admin access required' });
  }

  next();
}

/**
 * enforceOwner
 * Call inside a route handler to verify the caller may access `targetOwner`.
 * Admins pass always. Non-admins pass only if their owner matches.
 * Returns true if access is granted, false if a 403 was already sent.
 *
 * Usage:
 *   if (!enforceOwner(req, res, owner)) return;
 */
function enforceOwner(req, res, targetOwner) {
  const profile = req.ownerProfile;
  if (!profile) {
    res.status(401).json({ error: 'Unauthenticated' });
    return false;
  }
  if (profile.role === 'admin') return true;
  if (profile.owner === targetOwner) return true;
  res.status(403).json({ error: 'Access denied' });
  return false;
}

module.exports = { requireAdmin, enforceOwner };

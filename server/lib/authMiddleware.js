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

async function requireAdmin(req, res, next) {
  const userId = req.auth?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'Unauthenticated' });
  }

  try {
    // Bootstrap mode: allow through if no admin is configured yet.
    const adminExists = await prisma.ownerProfile.findFirst({
      where: { role: 'admin', clerkUserId: { not: null } },
      select: { owner: true },
    });
    if (!adminExists) {
      return next(); // cold-start — first admin can self-configure
    }

    // Normal mode: caller must be an admin.
    const profile = await prisma.ownerProfile.findFirst({
      where: { clerkUserId: userId },
    });
    if (!profile || profile.role !== 'admin') {
      return res.status(403).json({ error: 'Admin access required' });
    }

    req.ownerProfile = profile; // available to route handlers if needed
    next();
  } catch (err) {
    console.error('[requireAdmin] error:', err.message);
    res.status(500).json({ error: 'Auth check failed' });
  }
}

module.exports = { requireAdmin };

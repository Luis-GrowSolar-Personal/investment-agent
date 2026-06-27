/**
 * autoLink.js — Auto-link middleware
 *
 * Runs on every authenticated API request. Checks whether the Clerk user
 * is already linked to an OwnerProfile. If not, fetches their email from
 * Clerk and looks for a matching `inviteEmail` on any OwnerProfile. If
 * found, sets clerkUserId and clears inviteEmail automatically — so the
 * first request after accepting an invite just works, no admin action needed.
 *
 * Performance:
 *  - Fast path: one indexed DB query (clerkUserId lookup). Returns immediately
 *    if already linked (~all requests after the first login).
 *  - Slow path: one DB query + one Clerk API call, fires at most once per user
 *    (the first time they hit the API after accepting an invite).
 *
 * Errors in this middleware never block the request — they are logged and
 * execution continues. A failed auto-link can be resolved manually in Admin.
 */

const prisma = require('./prisma');
const { clerkClient } = require('@clerk/express');

async function autoLinkMiddleware(req, res, next) {
  const userId = req.auth?.userId;
  if (!userId) return next(); // unauthenticated — nothing to do

  try {
    // Fast path: already linked — fetch full profile and attach to request
    let profile = await prisma.ownerProfile.findFirst({
      where: { clerkUserId: userId },
    });

    if (!profile) {
      // Slow path: check for pending invite match
      const clerkUser = await clerkClient.users.getUser(userId);
      const email = clerkUser.emailAddresses?.[0]?.emailAddress;
      if (email) {
        const pending = await prisma.ownerProfile.findFirst({
          where: { inviteEmail: email.toLowerCase() },
        });
        if (pending) {
          // Auto-link and clear the invite
          profile = await prisma.ownerProfile.update({
            where: { owner: pending.owner },
            data: { clerkUserId: userId, inviteEmail: null },
          });
          console.log(`[autoLink] Linked Clerk user ${userId} (${email}) → owner "${profile.owner}"`);
        }
      }
    }

    // Attach the caller's OwnerProfile to the request for downstream use.
    // Routes and middleware can read req.ownerProfile without an extra DB query.
    req.ownerProfile = profile ?? null;
  } catch (err) {
    // Never block the request — log and continue
    console.error('[autoLink] error:', err.message);
    req.ownerProfile = null;
  }

  next();
}

module.exports = { autoLinkMiddleware };

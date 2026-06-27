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
    // Fast path: already linked to a profile → skip
    const linked = await prisma.ownerProfile.findFirst({
      where: { clerkUserId: userId },
      select: { owner: true },
    });
    if (linked) return next();

    // Slow path: fetch email from Clerk and check for a pending invite
    const clerkUser = await clerkClient.users.getUser(userId);
    const email = clerkUser.emailAddresses?.[0]?.emailAddress;
    if (!email) return next();

    const profile = await prisma.ownerProfile.findFirst({
      where: { inviteEmail: email.toLowerCase() },
      select: { owner: true },
    });
    if (!profile) return next();

    // Match found — link and clear the pending invite
    await prisma.ownerProfile.update({
      where: { owner: profile.owner },
      data: { clerkUserId: userId, inviteEmail: null },
    });
    console.log(`[autoLink] Linked Clerk user ${userId} (${email}) → owner "${profile.owner}"`);
  } catch (err) {
    // Never block the request — log and continue
    console.error('[autoLink] error:', err.message);
  }

  next();
}

module.exports = { autoLinkMiddleware };

/**
 * movesCache.js
 *
 * Thin helpers for refreshing the MovesCache table from outside the moves
 * router (e.g. after a Schwab sync or price refresh).
 *
 * Uses a lazy require of ../routes/moves to avoid circular-dependency
 * issues at module load time — by the time these functions are called,
 * all modules are fully initialised.
 */

const prisma = require('./prisma');

/**
 * Recompute moves for one owner and upsert into MovesCache.
 * Fire-and-forget safe: always returns a resolved promise (errors are logged).
 */
async function refreshMovesCache(owner) {
  try {
    const { computeMovesPayload } = require('../routes/moves');
    const payload    = await computeMovesPayload(owner);
    const computedAt = new Date();
    await prisma.movesCache.upsert({
      where:  { owner },
      update: { payload, computedAt },
      create: { owner, payload, computedAt },
    });
    console.log(`[movesCache] refreshed for ${owner}`);
  } catch (err) {
    console.error(`[movesCache] refresh failed for ${owner}:`, err.message);
  }
}

/**
 * Recompute moves for ALL owners in OwnerProfile.
 * Used after price refreshes that affect every portfolio.
 */
async function refreshAllMovesCache() {
  try {
    const owners = await prisma.ownerProfile.findMany({ select: { owner: true } });
    await Promise.all(owners.map(p => refreshMovesCache(p.owner)));
  } catch (err) {
    console.error('[movesCache] refreshAllMovesCache error:', err.message);
  }
}

module.exports = { refreshMovesCache, refreshAllMovesCache };

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
 *
 * Preserves re-baseline mode: this is called from fire-and-forget background
 * triggers (Schwab sync, price refresh on every page load via NavBar's
 * auto-sync effect) that have no idea whether the cache they're about to
 * overwrite is a normal computation or a just-confirmed re-baseline. Without
 * checking, a background price refresh landing seconds after a re-baseline
 * confirm would silently revert every winner-protected trim and drop the
 * ETF/Crypto/Commodity "unallocated" bucket adds — defeating the entire
 * point of re-baseline, invisibly, before the user even looks at the Moves
 * tab. (Caught 2026-08-08: confirmed 55/25/10/10, but the Moves tab showed
 * AMD/NVDA back under "Let Run" and no ETF/Crypto/Commodity adds at all —
 * traced to NavBar's on-load refresh-prices call racing the confirm.)
 * Fix: read whether the CURRENT cache entry was itself a re-baseline
 * (payload.isRebaseline) and, if so, recompute in that same mode instead of
 * silently resetting to the everyday winner-protected mode.
 *
 * 2026-08-23: the same treatment extended to payload.isFreshStart ("Full
 * reset" mode), which was added after the 2026-08-08 fix above and never
 * wired in here — so any profile PATCH or Schwab sync silently dropped an
 * owner out of Full reset back into plain re-baseline. GET /:owner in
 * routes/moves.js already preserved both; this brings the two paths in line.
 */
async function refreshMovesCache(owner) {
  try {
    const { computeMovesPayload } = require('../routes/moves');
    const existing = await prisma.movesCache.findUnique({ where: { owner } });
    const bypassWinnerProtection = existing?.payload?.isRebaseline === true;
    const freshStart             = existing?.payload?.isFreshStart === true;
    const payload    = await computeMovesPayload(owner, { bypassWinnerProtection, freshStart });
    const computedAt = new Date();
    await prisma.movesCache.upsert({
      where:  { owner },
      update: { payload, computedAt },
      create: { owner, payload, computedAt },
    });
    const preserved = freshStart ? ' (preserved full-reset mode)'
      : bypassWinnerProtection ? ' (preserved re-baseline mode)'
      : '';
    console.log(`[movesCache] refreshed for ${owner}${preserved}`);
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

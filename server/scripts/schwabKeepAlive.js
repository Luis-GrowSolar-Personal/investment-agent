/**
 * schwabKeepAlive.js
 *
 * One-shot script: refreshes the Schwab OAuth token, then exits. Intended to
 * be run as a Railway Cron Job service (not the main web service) on a
 * schedule of every 12 hours (cron expression given in setup docs, not
 * repeated here to avoid an unescaped comment terminator).
 *
 * This is a belt-and-suspenders duplicate of schwabAuth.startTokenKeepAlive(),
 * which already does the same 24h-interval refresh from inside the always-on
 * web process. The two overlap deliberately:
 *
 *   - startTokenKeepAlive() covers the common case (web service running).
 *   - This cron job covers the case where the web service was ever asleep,
 *     redeployed and slow to boot, or the in-process timer died silently —
 *     Railway Cron Jobs run as their own isolated service/container on their
 *     own schedule, independent of the web service's uptime.
 *
 * Either one alone is enough to keep the refresh_token (~7 day lifetime)
 * from expiring. Together, one has to fail for multiple days in a row before
 * the token actually lapses.
 *
 * Usage (Railway Cron Job service, same repo/env as the main service):
 *   Start command: node server/scripts/schwabKeepAlive.js
 *   Schedule: every 12 hours — see docs/handoffs setup notes for the exact
 *   cron expression (omitted here to avoid an unescaped comment terminator).
 *
 * Requires the same env vars as the main service: DATABASE_URL,
 * SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET. (SCHWAB_REDIRECT_URI is not needed
 * here — that's only used for the initial /connect + /callback handshake.)
 */

const prisma = require('../lib/prisma');
const schwabAuth = require('../lib/schwabAuth');

async function main() {
  const row = await prisma.schwabToken.findUnique({ where: { id: 1 } });
  if (!row) {
    console.log('[schwabKeepAlive] Schwab not connected yet — nothing to do.');
    return;
  }

  try {
    await schwabAuth.refreshAccessToken(prisma);
    console.log('[schwabKeepAlive] refresh succeeded at', new Date().toISOString());
  } catch (err) {
    console.error('[schwabKeepAlive] refresh failed:', err.message);
    process.exitCode = 1;
  }
}

main()
  .catch(err => {
    console.error('[schwabKeepAlive] unexpected error:', err);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());

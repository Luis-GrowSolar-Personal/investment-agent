// Usage: node reconcile-all-live.js
// Whole-portfolio reconciliation against LIVE Schwab data (no CSV needed) —
// calls the same schwabSync.getReconciliation() the app's own reconcile
// view uses, for every matched account, read-only (no writes).
const { PrismaClient } = require('@prisma/client');
const schwabSync = require('../lib/schwabSync');

(async () => {
  const prisma = new PrismaClient();
  const { matched, unmatchedSchwab, unmatchedLocal, ignoredSchwab } = await schwabSync.getReconciliation(prisma);

  for (const { schwab, local, positionDiffs, localOnly } of matched) {
    console.log(`\n=== ${local.name} (id ${local.id}) vs live Schwab ===`);
    if (positionDiffs.length === 0 && localOnly.length === 0) {
      console.log('All positions match. Account is clean.');
      continue;
    }
    for (const d of positionDiffs) {
      console.log(`${d.status.toUpperCase().padEnd(12)} ${d.symbol}: schwab ${d.schwabShares} vs local ${d.localShares}`);
    }
    for (const l of localOnly) {
      console.log(`LOCAL-ONLY   ${l.symbol}: local ${l.localShares} shares, not in Schwab (no open lots to flag)`);
    }
  }

  if (unmatchedSchwab.length) {
    console.log(`\nSchwab accounts with no local match: ${unmatchedSchwab.map(a => a.hashValue).join(', ')}`);
  }
  if (unmatchedLocal.length) {
    console.log(`Local accounts with no Schwab hash linked: ${unmatchedLocal.map(a => a.name).join(', ')}`);
  }
  if (ignoredSchwab.length) {
    console.log(`Ignored Schwab accounts (not checked): ${ignoredSchwab.length}`);
  }

  await prisma.$disconnect();
})();

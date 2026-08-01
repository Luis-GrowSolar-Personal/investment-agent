/**
 * diagnose_diversification.js
 *
 * Read-only diagnostic: why does the moves engine recommend fewer new
 * positions than the target slot count would allow for a given owner?
 * Prints, in order:
 *   1. Every watchlist ticker + its latest analysis + eligibility verdict
 *      (same filter computeMovesPayload uses) — shows exactly how many
 *      candidates actually exist to recommend, and why any were excluded.
 *   2. The owner's profile settings that drive target slot counts.
 *   3. The owner's live computeMovesPayload() output — allocation buckets,
 *      currently-held tickers, and every recommended move (flagging which
 *      are new-position opens vs. trims/adds on existing holdings).
 *
 * Nothing here mutates data — read-only queries plus the same
 * computeMovesPayload() function the live app uses, so the numbers match
 * exactly what the Portfolio Manager page shows.
 *
 * Usage:
 *   node server/scripts/diagnose_diversification.js "<owner key>"
 *   node server/scripts/diagnose_diversification.js         (lists owner keys)
 */

const prisma = require('../lib/prisma');
const { computeMovesPayload } = require('../routes/moves');

function isETF(ticker)          { return (ticker.bucketOverride ?? 'equity') === 'etf'; }
function isCommodityOrCrypto(t) { return ['commodity', 'crypto'].includes(t.bucketOverride ?? 'equity'); }
function barbellSide(ticker, analysis) {
  if (isETF(ticker)) return 'est';
  if (isCommodityOrCrypto(ticker)) return 'spec';
  const tier = ticker.tierOverride ?? analysis?.tier ?? null;
  if (tier === 'established') return 'est';
  if (tier === 'speculative') return 'spec';
  return null;
}

async function main() {
  const ownerArg = process.argv[2];
  const owners = await prisma.ownerProfile.findMany({ select: { owner: true, displayName: true } });

  if (!ownerArg) {
    console.log('Usage: node diagnose_diversification.js "<owner key>"\n\nAvailable owners:');
    owners.forEach(o => console.log(`  ${o.owner}  (${o.displayName ?? o.owner})`));
    return;
  }

  console.log('=== 1. Watchlist ticker eligibility ===\n');
  const watchlistTickers = await prisma.ticker.findMany({
    where: { status: 'watchlist', inScope: { not: false } },
  });

  let eligibleEst = 0, eligibleSpec = 0;
  for (const wt of watchlistTickers) {
    const a = await prisma.analysis.findFirst({
      where:   { transcript: { tickerId: wt.id } },
      orderBy: { transcript: { callDate: 'desc' } },
      select:  { thesisHealth: true, recommendation: true, finalAction: true, tier: true },
    });
    if (!a) {
      console.log(`  ${wt.symbol.padEnd(8)} NO ANALYSIS — never evaluated, excluded`);
      continue;
    }
    const action = a.finalAction ?? a.recommendation ?? '—';
    const side   = barbellSide(wt, a);
    let verdict  = 'eligible';
    if (!['Add', 'Hold'].includes(action)) {
      verdict = `excluded (action=${action})`;
    } else if (['Broken', 'Weakening'].includes(a.thesisHealth) && action !== 'Add') {
      verdict = `excluded (health=${a.thesisHealth}, action=${action})`;
    } else {
      if (side === 'est')  eligibleEst++;
      if (side === 'spec') eligibleSpec++;
    }
    console.log(`  ${wt.symbol.padEnd(8)} side=${(side ?? '?').padEnd(4)} action=${action.padEnd(6)} health=${(a.thesisHealth ?? '—').padEnd(13)} -> ${verdict}`);
  }
  console.log(`\n  Total watchlist tickers: ${watchlistTickers.length}`);
  console.log(`  Eligible established:    ${eligibleEst}`);
  console.log(`  Eligible speculative:    ${eligibleSpec}`);

  console.log(`\n=== 2. "${ownerArg}" — profile settings ===\n`);
  const profile = await prisma.ownerProfile.findUnique({ where: { owner: ownerArg } });
  if (!profile) {
    console.log(`No owner found for "${ownerArg}". Available: ${owners.map(o => o.owner).join(', ')}`);
    return;
  }
  console.log(`  minPositionDollar: ${profile.minPositionDollar}`);
  console.log(`  maxPositions:      ${profile.maxPositions}`);
  console.log(`  estSpecRatio:      ${profile.estSpecRatio}`);
  console.log(`  cashReservePct:    ${profile.cashReservePct}`);

  console.log(`\n=== 3. "${ownerArg}" — live computeMovesPayload() output ===\n`);
  const payload = await computeMovesPayload(ownerArg);
  console.log(`  Total portfolio value: $${payload.totalPortfolioValue}`);

  console.log(`\n  Allocation buckets:`);
  payload.allocation.buckets.forEach(b => {
    console.log(`    ${b.label.padEnd(22)} current $${String(b.currentValue).padEnd(10)} target ${b.targetPct}%`);
  });

  console.log(`\n  Currently held tickers (${payload.allocation.holdings.length}):`);
  payload.allocation.holdings.forEach(h => {
    console.log(`    ${h.symbol.padEnd(8)} ${h.bucketKey.padEnd(12)} $${h.mktValue}  (${h.currentPct}%)`);
  });

  console.log(`\n  Recommended moves (${payload.moves.length} total):`);
  payload.moves.forEach(m => {
    const tag = m.isNewPosition ? '[NEW OPEN]' : '[EXISTING]';
    console.log(`    ${tag} ${m.moveType.padEnd(14)} ${m.symbol.padEnd(8)} $${m.dollarAmount}  — ${m.reason}`);
  });
}

main()
  .catch(e => console.error('ERROR:', e))
  .finally(() => prisma.$disconnect());

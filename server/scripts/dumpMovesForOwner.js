/**
 * dumpMovesForOwner.js — calls computeMovesPayload directly (live, read-only,
 * no writes) and prints every move/hold with the fields needed to check
 * bucket-sizing math by hand: symbol, moveType, currentPct, targetPct,
 * dollarAmount, plus the total portfolio value used as the denominator.
 *
 * Read-only: computeMovesPayload does not write to the DB.
 *
 * Usage:
 *   node server/scripts/dumpMovesForOwner.js "Andrea Morales"
 *   node server/scripts/dumpMovesForOwner.js "Andrea Morales" --freshStart
 *   node server/scripts/dumpMovesForOwner.js "Andrea Morales" --symbols=QQQ,TMFC,QGRW,SOLZ,BTC
 */

const { computeMovesPayload } = require('../routes/moves');

async function main() {
  const owner = process.argv[2];
  const flags = process.argv.slice(3);
  const freshStart = flags.includes('--freshStart');
  const symbolsFlag = flags.find(f => f.startsWith('--symbols='));
  const onlySymbols = symbolsFlag ? new Set(symbolsFlag.split('=')[1].split(',')) : null;

  if (!owner) {
    console.error('Usage: node dumpMovesForOwner.js "<owner>" [--freshStart] [--symbols=A,B,C]');
    process.exit(1);
  }

  const payload = await computeMovesPayload(owner, {
    freshStart,
    bypassWinnerProtection: freshStart,
  });

  console.log(
    `\n=== ${owner} === totalPortfolioValue=$${Number(payload.totalPortfolioValue ?? 0).toFixed(2)} ` +
    `isFreshStart=${payload.isFreshStart} isRebaseline=${payload.isRebaseline}`
  );

  const rows = [...(payload.moves || []), ...(payload.holds || [])];
  rows.sort((a, b) => (a.symbol || '[bucket]').localeCompare(b.symbol || '[bucket]'));

  for (const m of rows) {
    const sym = m.symbol || '[bucket]';
    if (onlySymbols && !onlySymbols.has(sym)) continue;
    const cur = typeof m.currentPct === 'number' ? m.currentPct.toFixed(2) + '%' : '?';
    const tgt = typeof m.targetPct === 'number' ? m.targetPct.toFixed(2) + '%' : '?';
    const amt = typeof m.dollarAmount === 'number' ? '$' + m.dollarAmount.toFixed(0) : '?';
    console.log(
      `  ${(m.moveType || 'HOLD').padEnd(12)} ${sym.padEnd(8)} cur=${cur.padEnd(8)} tgt=${tgt.padEnd(8)} amt=${amt.padEnd(9)} reason=${m.reason || ''}`
    );
  }

  process.exit(0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});

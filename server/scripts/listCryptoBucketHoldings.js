/**
 * listCryptoBucketHoldings.js — for each named owner, lists every currently
 * held ticker whose effective bucket (per moves.js's getBucket()) is
 * 'crypto', to explain the crypto-bucket group count used as the divisor
 * in splitBucketTarget() (server/routes/moves.js ~line 1224-1237).
 *
 * getBucket() is: ticker.bucketOverride ?? 'equity' — it does NOT fall back
 * to smartDefaultBucket(). So a ticker only counts as crypto here if its
 * Ticker.bucketOverride column is explicitly 'crypto' in the DB right now.
 *
 * Usage:
 *   node server/scripts/listCryptoBucketHoldings.js "Andrea Morales" "Eduardo Morales"
 */

const prisma = require('../lib/prisma');

function getBucket(ticker) {
  return ticker.bucketOverride ?? 'equity';
}

async function heldTickersFor(owner) {
  const accounts = await prisma.account.findMany({
    where: { owner },
    include: {
      positions: {
        where: { status: 'active' },
        include: { ticker: true, lots: { where: { closedDate: null } } },
      },
    },
  });

  const byTicker = new Map();
  for (const acct of accounts) {
    for (const pos of acct.positions) {
      const shares = pos.lots.reduce((s, l) => s + l.shares, 0);
      if (shares <= 0) continue; // skip zero-share/closed-out positions
      if (!byTicker.has(pos.tickerId)) {
        byTicker.set(pos.tickerId, { ticker: pos.ticker, accounts: [] });
      }
      byTicker.get(pos.tickerId).accounts.push(acct.name);
    }
  }

  // Per-owner cap override layer (OwnerTickerConfig), same source moves.js
  // reads via ownerCapMap: effective cap = owner override ?? global ticker cap.
  const overrides = await prisma.ownerTickerConfig.findMany({ where: { owner } });
  const ownerCapMap = new Map(overrides.map(o => [o.tickerId, o.capPercent]));
  for (const entry of byTicker.values()) {
    const override = ownerCapMap.get(entry.ticker.id);
    entry.effectiveCapPercent = override ?? entry.ticker.capPercent ?? null;
    entry.capSource = override != null ? 'owner-override' : (entry.ticker.capPercent != null ? 'global-default' : 'none');
  }

  return [...byTicker.values()];
}

async function main() {
  const owners = process.argv.slice(2);
  if (owners.length === 0) {
    console.error('Usage: node listCryptoBucketHoldings.js "<owner A>" ["<owner B>" ...]');
    process.exit(1);
  }

  for (const owner of owners) {
    const held = await heldTickersFor(owner);
    console.log(`\n=== ${owner} ===`);
    console.log('All held tickers (symbol : bucketOverride -> effective bucket : inScope : capPercent[global->effective, source] : accounts)');
    for (const { ticker, accounts, effectiveCapPercent, capSource } of held) {
      console.log(
        `  ${ticker.symbol.padEnd(8)} : ${String(ticker.bucketOverride).padEnd(8)} -> ${getBucket(ticker).padEnd(9)} : inScope=${ticker.inScope} : capPercent=${ticker.capPercent}->${effectiveCapPercent} (${capSource}) : [${accounts.join(', ')}]`
      );
    }
    const cryptoGroups = held.filter(h => getBucket(h.ticker) === 'crypto');
    console.log(`  --> crypto-bucket group count (splitBucketTarget divisor) = ${cryptoGroups.length}`);
    console.log(`      crypto tickers: ${cryptoGroups.map(h => h.ticker.symbol).join(', ') || '(none)'}`);
  }

  await prisma.$disconnect();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});

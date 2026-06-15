/**
 * debug_transactions.js
 *
 * Prints raw Schwab transaction data for one account so we can verify
 * field names before the auto-resolve logic depends on them.
 *
 * Usage (from project root):
 *   node server/scripts/debug_transactions.js [accountId] [days]
 *
 * Defaults: first matched account, last 60 days.
 *
 * Examples:
 *   node server/scripts/debug_transactions.js
 *   node server/scripts/debug_transactions.js 3
 *   node server/scripts/debug_transactions.js 3 30
 */

require('dotenv').config();
const { PrismaClient } = require('@prisma/client');
const { getTransactions } = require('../lib/schwabAuth');

const prisma = new PrismaClient();

async function main() {
  const accountId = parseInt(process.argv[2]) || null;
  const days      = parseInt(process.argv[3]) || 60;

  // Find account
  const account = accountId
    ? await prisma.account.findUnique({ where: { id: accountId } })
    : await prisma.account.findFirst({ where: { schwabAccountHash: { not: null } } });

  if (!account) {
    console.error('No Schwab-linked account found. Pass an accountId as the first argument.');
    process.exit(1);
  }

  console.log(`\nAccount: ${account.name} (id=${account.id}, hash=${account.schwabAccountHash})`);
  console.log(`Fetching last ${days} days of TRADE transactions...\n`);

  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  const txns = await getTransactions(prisma, account.schwabAccountHash, startDate);

  if (!Array.isArray(txns) || txns.length === 0) {
    console.log('No transactions returned.');
    return;
  }

  console.log(`Total transactions: ${txns.length}\n`);

  // Print each transaction with the fields we care about
  for (const txn of txns) {
    console.log('─'.repeat(60));
    console.log(`type:           ${txn.type}`);
    console.log(`tradeDate:      ${txn.tradeDate}`);
    console.log(`settlementDate: ${txn.settlementDate}`);
    console.log(`netAmount:      ${txn.netAmount}`);
    console.log(`description:    ${txn.description ?? '—'}`);

    const items = txn.transferItems ?? [];
    if (items.length === 0) {
      console.log('transferItems:  (none)');
    } else {
      console.log(`transferItems:  (${items.length})`);
      for (const item of items) {
        console.log('  ├─ instrument:     ', JSON.stringify(item.instrument ?? {}));
        console.log('  ├─ amount:         ', item.amount);
        console.log('  ├─ price:          ', item.price);
        console.log('  ├─ cost:           ', item.cost);
        console.log('  ├─ positionEffect: ', item.positionEffect);
        console.log('  └─ feeType:        ', item.feeType);
      }
    }
    console.log();
  }

  // Summary: just the equity OPENING legs (what auto-resolve will use)
  console.log('═'.repeat(60));
  console.log('OPENING legs (buys) — what auto-resolve matches against:\n');
  let foundAny = false;
  for (const txn of txns) {
    for (const item of (txn.transferItems ?? [])) {
      if (item.positionEffect !== 'OPENING') continue;
      const sym = item.instrument?.symbol ?? '?';
      console.log(`  ${sym.padEnd(8)} ${String(Math.abs(item.amount ?? 0)).padEnd(12)} shares @ $${item.price ?? '?'}  (${txn.tradeDate})`);
      foundAny = true;
    }
  }
  if (!foundAny) console.log('  (none found — check positionEffect field name above)');
  console.log();
}

main()
  .catch(err => { console.error(err); process.exit(1); })
  .finally(() => prisma.$disconnect());

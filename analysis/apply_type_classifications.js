#!/usr/bin/env node
// Applies type_classifications.json → Ticker.type + Ticker.capPercent in the DB.
// Type A → 35%, Type B → 50%. ETFs (not in JSON) are untouched.
// Run from repo root: node analysis/apply_type_classifications.js [--dry-run]

const { PrismaClient } = require('../server/node_modules/@prisma/client');
const path = require('path');
const fs = require('fs');

const DRY_RUN = process.argv.includes('--dry-run');
const CAP = { A: 35, B: 50 };

async function main() {
  const json = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'data/type_classifications.json'), 'utf8')
  );
  const classifications = json.classifications;

  const prisma = new PrismaClient();
  const tickers = await prisma.ticker.findMany({
    select: { id: true, symbol: true, type: true, capPercent: true, status: true },
  });

  const changes = [];
  const skipped = [];

  for (const ticker of tickers) {
    const cls = classifications[ticker.symbol];
    if (!cls) {
      skipped.push(ticker.symbol);
      continue;
    }
    const newCap = CAP[cls.type];
    if (ticker.type === cls.type && ticker.capPercent === newCap) continue;

    changes.push({
      id: ticker.id,
      symbol: ticker.symbol,
      status: ticker.status,
      oldType: ticker.type,
      newType: cls.type,
      oldCap: ticker.capPercent,
      newCap,
    });
  }

  if (changes.length === 0) {
    console.log('No changes needed — DB already matches classifications.');
    await prisma.$disconnect();
    return;
  }

  console.log(`\n${DRY_RUN ? '[DRY RUN] ' : ''}${changes.length} ticker(s) to update:\n`);
  console.log('  Symbol   Status      Old       New');
  console.log('  ──────   ──────────  ────────  ────────');
  for (const c of changes) {
    const old = `${c.oldType}/${c.oldCap}%`;
    const neu = `${c.newType}/${c.newCap}%`;
    console.log(`  ${c.symbol.padEnd(8)} ${c.status.padEnd(10)}  ${old.padEnd(8)}  ${neu}`);
  }

  if (skipped.length) {
    console.log(`\n  Skipped (no entry in JSON — ETFs or unlisted): ${skipped.join(', ')}`);
  }

  if (DRY_RUN) {
    console.log('\nDry run complete. Re-run without --dry-run to apply.');
    await prisma.$disconnect();
    return;
  }

  for (const c of changes) {
    await prisma.ticker.update({
      where: { id: c.id },
      data: { type: c.newType, capPercent: c.newCap },
    });
  }

  console.log('\nDone. All changes applied.');
  await prisma.$disconnect();
}

main().catch(e => { console.error(e); process.exit(1); });

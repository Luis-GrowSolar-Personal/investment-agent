// Usage: node reconcile-from-csv.js <path-to-schwab-csv> <account-name-substring>
const fs = require('fs');
const { PrismaClient } = require('@prisma/client');

const [,, csvPath, accountNameSubstr] = process.argv;
if (!csvPath || !accountNameSubstr) {
  console.error('Usage: node reconcile-from-csv.js <csv-path> <account-name-substring>');
  process.exit(1);
}

function parseCsv(text) {
  const lines = text.split('\n').filter(l => l.trim().length > 0);
  // Line 0: title, line 1: header (quoted fields)
  const rows = lines.slice(1).map(line => {
    const fields = [];
    const re = /"([^"]*)"/g;
    let m;
    while ((m = re.exec(line)) !== null) fields.push(m[1]);
    return fields;
  });
  const header = rows[0];
  const symbolIdx = header.indexOf('Symbol');
  const qtyIdx = header.findIndex(h => h.startsWith('Qty'));
  const assetTypeIdx = header.indexOf('Asset Type');
  const positions = [];
  for (const row of rows.slice(1)) {
    const symbol = row[symbolIdx];
    if (!symbol || symbol === 'Cash & Cash Investments' || symbol === 'Positions Total') continue;
    const qty = parseFloat((row[qtyIdx] || '').replace(/,/g, ''));
    if (!isFinite(qty)) continue;
    positions.push({ symbol, qty, assetType: row[assetTypeIdx] });
  }
  return positions;
}

(async () => {
  const prisma = new PrismaClient();
  const csvPositions = parseCsv(fs.readFileSync(csvPath, 'utf8'));

  const account = await prisma.account.findFirst({
    where: { name: { contains: accountNameSubstr, mode: 'insensitive' } },
  });
  if (!account) {
    console.error(`No account found matching "${accountNameSubstr}"`);
    process.exit(1);
  }

  const localPositions = await prisma.position.findMany({
    where: { accountId: account.id, status: 'active' },
    include: { ticker: { select: { symbol: true } }, lots: { where: { closedDate: null } } },
  });
  const localBySymbol = new Map(localPositions.map(p => [
    p.ticker.symbol,
    { totalShares: p.lots.reduce((s, l) => s + l.shares, 0), lotCount: p.lots.length },
  ]));
  const csvBySymbol = new Map(csvPositions.map(p => [p.symbol, p.qty]));

  console.log(`\n=== Reconciling "${account.name}" (id ${account.id}) against ${csvPath} ===\n`);

  let mismatches = 0;
  for (const [symbol, csvQty] of csvBySymbol) {
    const local = localBySymbol.get(symbol);
    if (!local) {
      console.log(`SCHWAB-ONLY  ${symbol}: Schwab ${csvQty}, not tracked locally at all`);
      mismatches++;
    } else if (Math.abs(local.totalShares - csvQty) > 0.0005) {
      console.log(`MISMATCH     ${symbol}: Schwab ${csvQty} vs local ${local.totalShares} (diff ${(csvQty - local.totalShares).toFixed(4)})`);
      mismatches++;
    }
  }
  for (const [symbol, local] of localBySymbol) {
    if (!csvBySymbol.has(symbol)) {
      console.log(`LOCAL-ONLY   ${symbol}: local ${local.totalShares} shares (${local.lotCount} lot(s)), not in Schwab export`);
      mismatches++;
    }
  }
  console.log(mismatches === 0 ? '\nAll positions match. Account is clean.\n' : `\n${mismatches} discrepanc${mismatches === 1 ? 'y' : 'ies'} found — see above.\n`);

  await prisma.$disconnect();
})();

/**
 * compareOwnerProfiles.js — side-by-side diff of two OwnerProfile rows,
 * plus their per-ticker cap overrides (OwnerTickerConfig), read directly
 * from Postgres via Prisma — no HTTP/Clerk auth needed.
 *
 * Usage:
 *   node server/scripts/compareOwnerProfiles.js "Andrea Morales" "Eduardo Morales"
 */

const prisma = require('../lib/prisma');

const PROFILE_FIELDS = [
  'minPositionDollar', 'maxPositions', 'cashReservePct',
  'yearsToGoal', 'estSpecRatio', 'riskTolerance',
  'equitiesTargetPct', 'etfTargetPct', 'cryptoTargetPct', 'commoditiesTargetPct',
  'taxSensitivity', 'accountPurpose',
  'domainsOfInterest', 'benchmarkBaseline',
  'specExitSpeed', 'newMoneyBehavior',
];

function fmt(v) {
  if (v === null || v === undefined) return '(null)';
  if (Array.isArray(v)) return JSON.stringify([...v].sort());
  return String(v);
}

function sameValue(a, b) {
  // Arrays (e.g. domainsOfInterest) should compare as sets, not by stored
  // order — sort before stringifying so a re-save that reorders the same
  // elements doesn't falsely show as a diff.
  const norm = (v) => (Array.isArray(v) ? JSON.stringify([...v].sort()) : JSON.stringify(v));
  return norm(a) === norm(b);
}

async function main() {
  const [ownerA, ownerB] = process.argv.slice(2);
  if (!ownerA || !ownerB) {
    console.error('Usage: node compareOwnerProfiles.js "<owner A>" "<owner B>"');
    process.exit(1);
  }

  const [profileA, profileB] = await Promise.all([
    prisma.ownerProfile.findUnique({ where: { owner: ownerA } }),
    prisma.ownerProfile.findUnique({ where: { owner: ownerB } }),
  ]);

  if (!profileA) { console.error(`Owner not found: "${ownerA}"`); process.exit(1); }
  if (!profileB) { console.error(`Owner not found: "${ownerB}"`); process.exit(1); }

  console.log(`\n===== OwnerProfile fields: ${ownerA}  vs  ${ownerB} =====\n`);
  let anyDiff = false;
  for (const f of PROFILE_FIELDS) {
    const va = profileA[f];
    const vb = profileB[f];
    const diff = !sameValue(va, vb);
    if (diff) anyDiff = true;
    console.log(
      `${diff ? '[DIFF]' : '[SAME]'} ${f.padEnd(22)} ${fmt(va).padEnd(30)} ${fmt(vb)}`
    );
  }
  if (!anyDiff) console.log('\nNo differences in any top-level OwnerProfile field.');

  // Per-ticker cap overrides — union of every ticker either owner holds or
  // has an explicit override for, falling back to Ticker.capPercent when no
  // OwnerTickerConfig row exists (mirrors the app's own fallback logic).
  const [configsA, configsB, accountsA, accountsB] = await Promise.all([
    prisma.ownerTickerConfig.findMany({ where: { owner: ownerA }, include: { ticker: true } }),
    prisma.ownerTickerConfig.findMany({ where: { owner: ownerB }, include: { ticker: true } }),
    prisma.account.findMany({
      where: { owner: ownerA },
      include: { positions: { where: { status: 'active' }, include: { ticker: true } } },
    }),
    prisma.account.findMany({
      where: { owner: ownerB },
      include: { positions: { where: { status: 'active' }, include: { ticker: true } } },
    }),
  ]);

  const tickerMap = new Map(); // tickerId -> ticker row
  const capA = new Map();      // tickerId -> effective cap for owner A
  const capB = new Map();

  for (const c of configsA) { tickerMap.set(c.tickerId, c.ticker); capA.set(c.tickerId, c.capPercent ?? c.ticker.capPercent); }
  for (const c of configsB) { tickerMap.set(c.tickerId, c.ticker); capB.set(c.tickerId, c.capPercent ?? c.ticker.capPercent); }
  for (const acct of accountsA) for (const p of acct.positions) {
    tickerMap.set(p.ticker.id, p.ticker);
    if (!capA.has(p.ticker.id)) capA.set(p.ticker.id, p.ticker.capPercent);
  }
  for (const acct of accountsB) for (const p of acct.positions) {
    tickerMap.set(p.ticker.id, p.ticker);
    if (!capB.has(p.ticker.id)) capB.set(p.ticker.id, p.ticker.capPercent);
  }

  console.log(`\n===== Per-ticker cap %: ${ownerA}  vs  ${ownerB} =====\n`);
  const symbols = [...tickerMap.values()].sort((x, y) => x.symbol.localeCompare(y.symbol));
  for (const t of symbols) {
    const va = capA.has(t.id) ? capA.get(t.id) : '(no cap set, not held)';
    const vb = capB.has(t.id) ? capB.get(t.id) : '(no cap set, not held)';
    const diff = !sameValue(va, vb);
    console.log(`${diff ? '[DIFF]' : '[SAME]'} ${t.symbol.padEnd(10)} ${fmt(va).padEnd(30)} ${fmt(vb)}`);
  }

  await prisma.$disconnect();
}

main().catch(async (err) => {
  console.error(err);
  await prisma.$disconnect();
  process.exit(1);
});

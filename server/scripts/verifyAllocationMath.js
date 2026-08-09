/**
 * verifyAllocationMath.js
 *
 * Automated replacement for the manual "screenshot Admin + Allocation tab +
 * Recommended Moves, add up numbers by hand" verification that found four
 * real bugs in one session (see wrap-ups/*.md: stale cache, the cash
 * off-the-top scaling flaw, the contradictory scarcity-row framing, and the
 * ratchet-vs-model-weight mismatch). For every owner, for every one of the
 * six allocation buckets, reconstructs "what the bucket target should equal
 * given the individual moves/holds the engine actually generated" and
 * compares it against payload.allocation.buckets' own targetValue.
 *
 * Reconciliation rule per bucket type (learned the hard way this session):
 *
 *   Established / Speculative (barbell equity buckets):
 *     sum, across every row with bucket ∈ {'equity', null} and
 *     tier === <side>, that row's RESOLVED target — row.targetValue if it
 *     has one (a real move), else row.currentMktValue (a HOLD/advisory,
 *     which by construction leaves the position unchanged). Add the
 *     matching "<label> (unallocated)" scarcity-gap row's dollarAmount, if
 *     one exists for that side. Must equal the bucket's targetValue.
 *
 *     Using the raw model weight instead of the resolved target here is
 *     exactly the bug this script is designed to catch — see
 *     wrap-ups/recon-spec-achievable-gap-out.md. A ticker on TRIM_RATCHET/
 *     TRIM_CAP can have a resolved target hundreds of dollars away from its
 *     model weight.
 *
 *   ETF / Crypto / Commodities (fixed-target buckets):
 *     same idea, but rows are matched by bucket === <key> instead of tier.
 *     SIVR/BTC-style tickers (bucket: 'commodity'/'crypto' but tagged with
 *     an equity-style tier for display) are correctly excluded from the
 *     barbell buckets by the bucket !== 'equity' check above, and correctly
 *     INCLUDED here by the bucket === <key> check — this was a real mistake
 *     an earlier recon pass in this session made by hand
 *     (wrap-ups/recon-established-spec-shortfall-out.md).
 *
 *   Cash:
 *     no individual-move reconciliation — just re-derive
 *     cashReservePct/100 * totalPortfolioValue independently and confirm it
 *     matches the bucket's targetValue.
 *
 * Usage:
 *   DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-) \
 *     node server/scripts/verifyAllocationMath.js
 *   (or just run server/scripts/verify-allocation-math.sh, which does the
 *   above for you)
 *
 * Exit code 0 if every bucket for every owner reconciles within the $2
 * rounding tolerance; exit code 1 if anything fails — safe to wire into a
 * pre-deploy check or CI later, not just a manual tool.
 */

const { PrismaClient } = require('../node_modules/@prisma/client');
const { computeMovesPayload } = require('../routes/moves');

const TOLERANCE = 2; // dollars — allows for .toFixed(2) rounding noise across many summed figures

const BUCKET_DEFS = [
  { key: 'established', label: 'Established Equities', mode: 'barbell', side: 'established' },
  { key: 'speculative', label: 'Speculative Equities',  mode: 'barbell', side: 'speculative' },
  { key: 'etf',         label: 'ETF',                   mode: 'fixed' },
  { key: 'crypto',      label: 'Crypto',                mode: 'fixed' },
  { key: 'commodity',   label: 'Commodities',           mode: 'fixed' },
  { key: 'cash',        label: 'Cash',                  mode: 'cash' },
];

function resolvedTarget(row) {
  // A real move (TRIM*/ADD/EXIT) always has targetValue set by
  // computeMovesPayload's generic derivation loop. A HOLD/advisory row
  // (including out-of-scope tickers denied an ADD) never gets one — its
  // resolved target is just its unchanged current value.
  return row.targetValue != null ? row.targetValue : row.currentMktValue;
}

function reconstructBucket(def, allRows) {
  let sum = 0;
  for (const row of allRows) {
    if (row.isBucketLevel) continue;
    const matches = def.mode === 'barbell'
      ? row.tier === def.side && (row.bucket === 'equity' || row.bucket == null)
      : row.bucket === def.key;
    if (matches) sum += resolvedTarget(row);
  }
  // Add the bucket-level "(unallocated)" row's shortfall, if the engine
  // generated one for this bucket (only surfaces during a re-baseline pass,
  // i.e. bypassWinnerProtection: true).
  const unallocatedKey = def.mode === 'barbell' ? def.side : def.key;
  for (const row of allRows) {
    if (row.isBucketLevel && row.bucket === unallocatedKey) sum += row.dollarAmount;
  }
  return sum;
}

async function verifyOwner(prisma, owner) {
  const payload = await computeMovesPayload(owner, { bypassWinnerProtection: true });
  const allRows = [...payload.moves, ...payload.holds, ...payload.advisories];

  const results = [];
  for (const def of BUCKET_DEFS) {
    const bucket = payload.allocation.buckets.find(b => b.key === def.key);
    if (!bucket) {
      results.push({ owner, label: def.label, target: null, reconstructed: null, diff: null, pass: false, note: 'bucket missing from payload.allocation.buckets' });
      continue;
    }
    const target = bucket.targetValue;
    let reconstructed;
    if (def.mode === 'cash') {
      reconstructed = (payload.allocation.cashReservePct / 100) * payload.totalPortfolioValue;
    } else {
      reconstructed = reconstructBucket(def, allRows);
    }
    const diff = reconstructed - target;
    results.push({
      owner, label: def.label,
      target: +target.toFixed(2), reconstructed: +reconstructed.toFixed(2),
      diff: +diff.toFixed(2), pass: Math.abs(diff) <= TOLERANCE,
    });
  }
  return results;
}

async function main() {
  const prisma = new PrismaClient();
  let allPass = true;
  try {
    const owners = await prisma.ownerProfile.findMany();
    if (owners.length === 0) {
      console.log('No OwnerProfile rows found — nothing to verify.');
      process.exit(0);
    }

    for (const o of owners) {
      console.log(`\n===== ${o.owner} =====`);
      let results;
      try {
        results = await verifyOwner(prisma, o.owner);
      } catch (e) {
        console.log(`  ERROR computing payload: ${e.message}`);
        allPass = false;
        continue;
      }
      for (const r of results) {
        const status = r.pass ? 'PASS' : 'FAIL';
        if (!r.pass) allPass = false;
        const line = `  [${status}] ${r.label.padEnd(22)} target=$${r.target ?? 'n/a'}  reconstructed=$${r.reconstructed ?? 'n/a'}  diff=$${r.diff ?? 'n/a'}`;
        console.log(r.note ? `${line}  (${r.note})` : line);
      }
    }
  } finally {
    await prisma.$disconnect();
  }

  console.log(`\n${allPass ? 'ALL BUCKETS RECONCILE' : 'RECONCILIATION FAILURES FOUND'} — exit code ${allPass ? 0 : 1}`);
  process.exit(allPass ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
